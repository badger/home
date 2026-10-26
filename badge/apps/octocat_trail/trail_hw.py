"""Guarded hardware adapters for The Octocat Trail.

Every sensor, light and IR call is wrapped so the app degrades instead of
crashing in the Badge Simulator, which has no IR, a static IMU and a
constant light sensor. Nothing here touches the display.
"""

import trail_logic as tl

LIGHT_ADC_PIN = 43
IR_TX_PIN = 16
# (pio, state machine) pairs to try for the sender. PIO0 SM0 is left free
# for the badge's IR receiver.
SENDER_SLOTS = ((0, 1), (1, 0), (1, 1))
FRAME_MS = 77
MUTE_MS = 250
MAX_PENDING = 96


class Sensors:
    """IMU and ambient light, with fallbacks for missing hardware."""

    def __init__(self, device):
        self.device = device
        self.imu_ok = True
        self.light_source = None
        self.adc = None
        self.light_failed = False

    def imu(self):
        """(ax, ay, az) or None when there is no IMU."""
        if not self.imu_ok:
            return None
        try:
            values = self.device.imu()
            return (float(values[0]), float(values[1]), float(values[2]))
        except Exception:
            self.imu_ok = False
            return None

    def light(self):
        """Raw 16-bit ambient light from GPIO43/ADC3, or None."""
        if self.light_failed:
            return None
        if self.light_source != "adc":
            try:
                value = int(self.device.light_level())
                self.light_source = "badge"
                return value
            except Exception:
                if self.light_source == "badge":
                    return None
        try:
            if self.adc is None:
                import machine
                self.adc = machine.ADC(LIGHT_ADC_PIN)
            value = int(self.adc.read_u16())
            self.light_source = "adc"
            return value
        except Exception:
            self.light_failed = True
            return None


class CaseLights:
    """Sets the four case lights only when the values change."""

    def __init__(self, device):
        self.device = device
        self.last = None
        self.ok = True

    def set(self, a, b=None, c=None, d=None):
        if b is None:
            b = c = d = a
        values = (quantize(a), quantize(b), quantize(c), quantize(d))
        if values == self.last or not self.ok:
            return
        self.last = values
        try:
            self.device.caselights(values[0], values[1], values[2], values[3])
        except Exception:
            self.ok = False

    def off(self):
        self.last = None
        try:
            self.device.caselights(0)
        except Exception:
            pass


def quantize(value):
    value = tl.clamp(float(value), 0.0, 1.0)
    return int(value * 20 + 0.5) / 20.0


try:
    from aye_arr.nec.remotes.descriptor import RemoteDescriptor as _Descriptor
except Exception:
    _Descriptor = object


class TrailBeam(_Descriptor):
    """Our NEC address for the badge's shared IR receiver."""
    NAME = "OctocatTrail"
    ADDRESS = tl.IR_ADDRESS
    BUTTON_CODES = {}

    def __init__(self):
        if _Descriptor is not object:
            _Descriptor.__init__(self)
        self.on_known = None
        self.on_any = None


def make_descriptor():
    return TrailBeam()


def open_sender():
    try:
        from aye_arr.nec import NECSender
    except Exception:
        return None
    for pio, sm in SENDER_SLOTS:
        try:
            sender = NECSender(IR_TX_PIN, pio, sm)
            sender.start()
            return sender
        except Exception:
            pass
    return None


class IrLink:
    """Beams packets on NEC address 0x54 and collects packets from other
    badges running The Octocat Trail. Inbound bytes arrive through on_any,
    which only queues them; process() decodes them in the frame loop."""

    def __init__(self, nonce):
        self.inbox = tl.IrInbox(nonce)
        self.nonce = nonce & 0x7F
        self.pending = []
        self.queue = []
        self.total = 0
        self.tx = None
        self.binding = None
        self.listening = False
        self.mute_until = 0
        self.next_at = 0
        self.frames_sent = 0

    def open(self):
        self.listening = self._listen()
        self.tx = open_sender()
        return self

    def _listen(self):
        try:
            from badgeware.ir import ir
        except Exception:
            return False
        try:
            descriptor = make_descriptor()
            binding = ir.bind(descriptor)
            if binding is None:
                binding = descriptor
            binding.on_any = self.on_byte
            binding.on_known = self.on_known
            self.binding = binding
            return True
        except Exception:
            return False

    def on_byte(self, command):
        if len(self.pending) < MAX_PENDING:
            self.pending.append(int(command) & 0xFF)

    def on_known(self, _key):
        pass

    def can_send(self):
        return self.tx is not None

    def status(self):
        if self.tx is not None:
            return "IR ready" if self.listening else "IR send only"
        if self.listening:
            return "IR listening"
        return "IR off"

    def sending(self):
        return len(self.queue) > 0

    def progress(self):
        if not self.total:
            return 1.0
        return 1.0 - len(self.queue) / float(self.total)

    def beam(self, packet, repeats=tl.BEAM_REPEATS):
        frames = []
        for _ in range(repeats):
            for byte in packet:
                frames.append(byte)
        if not self.queue:
            self.total = 0
        self.queue.extend(frames)
        self.total += len(frames)
        return True

    def update(self, now):
        """Send at most one frame per call; each real frame blocks ~77 ms.
        Without a transmitter, frames are paced at that rate so a simulated
        beam lasts as long as a real one."""
        if not self.queue:
            return
        if self.tx is None and now < self.next_at:
            return
        byte = self.queue.pop(0)
        if self.tx is not None:
            try:
                self.tx.send_addr_cmd(tl.IR_ADDRESS, byte)
                self.frames_sent += 1
            except Exception:
                self.tx = None
        self.next_at = now + FRAME_MS
        self.mute_until = now + FRAME_MS + MUTE_MS

    def process(self, now):
        """Return new packets from other badges, ignoring our own echoes."""
        if not self.pending:
            return []
        incoming = self.pending
        self.pending = []
        if self.queue or now < self.mute_until:
            return []
        packets = []
        for byte in incoming:
            packet = self.inbox.feed(byte, now)
            if packet is not None:
                packets.append(packet)
        return packets

    def close(self):
        self.queue = []
        if self.tx is not None:
            try:
                self.tx.stop()
            except Exception:
                pass
            self.tx = None
        if self.listening:
            try:
                from badgeware.ir import ir
                ir.close()
            except Exception:
                pass
            self.listening = False
        self.binding = None
