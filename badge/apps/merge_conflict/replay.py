import binascii
import json
import machine
import os
import random
import struct
import sys
from micropython import const

MAGIC = b"BWRP"
VERSION = 1
STATE_DIR = "/state"
REPLAY_DIR = STATE_DIR + "/replays"
PARTIAL = ".part"
KEPT = ".bwr"
KEEP = 3
MIN_STALE_BYTES = 16 * 1024
MAX_BYTES = 320 * 1024
RESERVE_BYTES = 160 * 1024
BUFFER_BYTES = 48 * 1024
IDLE_FLUSH_BYTES = 8 * 1024
FORCE_FLUSH_BYTES = 32 * 1024

HAS_MASKS = const(1)
HAS_IMU = const(2)
HAS_STATUS = const(4)
HAS_JOURNAL = const(8)

LINK_EVENTS = (1, 7)
FIRST_HANDLE = 9

FLAG_UPSIDE_DOWN = const(1)
FLAG_ROTATED = const(2)

TAG_NONE = const(0)
TAG_TRUE = const(1)
TAG_FALSE = const(2)
TAG_INT = const(3)
TAG_FLOAT = const(4)
TAG_STR = const(5)
TAG_BYTES = const(6)
TAG_LIST = const(7)
TAG_OTHER = const(8)

MASK_COUNT = const(12)
IMU_FORMAT = "<6h"
IMU_BYTES = const(12)
JOURNAL_LIMIT = const(255)

COPY_FORMATS = {}


def actions():
    return (BUTTON_LEFT, BUTTON_RIGHT, BUTTON_SELECT, BUTTON_UP,
            BUTTON_DOWN, BUTTON_HOME, BUTTON_BACK, BUTTON_MENU)


def controls():
    return (badge.pad, badge.buttons, badge.all)


def status_flags():
    return (FLAG_UPSIDE_DOWN if badge.upside_down() else 0) | (FLAG_ROTATED if badge.rotate_180() else 0)


class Writer:
    def __init__(self, size):
        self.buffer = bytearray(size)
        self.view = memoryview(self.buffer)
        self.position = 0

    def byte(self, value):
        self.buffer[self.position] = value
        self.position += 1

    def varint(self, value):
        buffer = self.buffer
        position = self.position
        while value >= 0x80:
            buffer[position] = (value & 0x7F) | 0x80
            position += 1
            value >>= 7
        buffer[position] = value
        self.position = position + 1

    def raw(self, data):
        length = len(data)
        if not length:
            return
        if self.position + length > len(self.buffer):
            raise IndexError
        layout = COPY_FORMATS.get(length)
        if layout is None:
            layout = COPY_FORMATS[length] = "%ds" % length
        struct.pack_into(layout, self.buffer, self.position, data)
        self.position += length

    def encode(self, value):
        self.position = self.encode_at(value, self.position)

    def encode_at(self, value, position):
        buffer = self.buffer
        kind = type(value)
        if kind is int:
            zigzag = value << 1 if value >= 0 else ((-value) << 1) - 1
            buffer[position] = TAG_INT
            position += 1
            while zigzag >= 0x80:
                buffer[position] = (zigzag & 0x7F) | 0x80
                position += 1
                zigzag >>= 7
            buffer[position] = zigzag
            return position + 1
        if kind is bytes or kind is bytearray or kind is memoryview:
            length = len(value)
            if length >= 0x80:
                buffer[position] = TAG_BYTES
                self.position = position + 1
                self.varint(length)
                self.raw(value)
                return self.position
            buffer[position] = TAG_BYTES
            buffer[position + 1] = length
            self.position = position + 2
            self.raw(value)
            return self.position
        if kind is list or kind is tuple:
            length = len(value)
            buffer[position] = TAG_LIST
            self.position = position + 1
            self.varint(length)
            position = self.position
            for item in value:
                position = self.encode_at(item, position)
            return position
        if value is None:
            buffer[position] = TAG_NONE
            return position + 1
        if value is True:
            buffer[position] = TAG_TRUE
            return position + 1
        if value is False:
            buffer[position] = TAG_FALSE
            return position + 1
        if kind is float:
            buffer[position] = TAG_FLOAT
            struct.pack_into("<f", buffer, position + 1, value)
            return position + 5
        data = value.encode() if kind is str else str(value).encode()
        buffer[position] = TAG_STR if kind is str else TAG_OTHER
        self.position = position + 1
        self.varint(len(data))
        self.raw(data)
        return self.position


def get_varint(data, index):
    value = 0
    shift = 0
    while True:
        byte = data[index]
        index += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, index
        shift += 7


def decode(data, index):
    tag = data[index]
    index += 1
    if tag == TAG_NONE:
        return None, index
    if tag == TAG_TRUE:
        return True, index
    if tag == TAG_FALSE:
        return False, index
    if tag == TAG_INT:
        zigzag, index = get_varint(data, index)
        return (zigzag >> 1) if not zigzag & 1 else -((zigzag + 1) >> 1), index
    if tag == TAG_FLOAT:
        return struct.unpack_from("<f", data, index)[0], index + 4
    length, index = get_varint(data, index)
    if tag == TAG_LIST:
        items = []
        for _ in range(length):
            item, index = decode(data, index)
            items.append(item)
        return items, index
    chunk = bytes(data[index:index + length])
    index += length
    if tag == TAG_BYTES:
        return chunk, index
    if tag == TAG_STR:
        return chunk.decode(), index
    return sys.modules["bluetooth"].UUID(chunk.decode()), index


def read_file(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None


def ensure_dir(path):
    try:
        os.stat(path)
    except OSError:
        os.mkdir(path)


def free_bytes(path):
    stats = os.statvfs(path)
    return stats[0] * stats[3]


def next_path(app):
    ensure_dir(STATE_DIR)
    ensure_dir(REPLAY_DIR)
    prefix = app + "-"
    numbers = []
    for name in os.listdir(REPLAY_DIR):
        if not name.startswith(prefix):
            continue
        stem = name[:-len(PARTIAL)] if name.endswith(PARTIAL) else name[:-len(KEPT)] if name.endswith(KEPT) else None
        if stem is None or not stem[len(prefix):].isdigit():
            continue
        if name.endswith(PARTIAL):
            if os.stat(REPLAY_DIR + "/" + name)[6] < MIN_STALE_BYTES:
                os.remove(REPLAY_DIR + "/" + name)
                continue
            os.rename(REPLAY_DIR + "/" + name, REPLAY_DIR + "/" + stem + KEPT)
        numbers.append(int(stem[len(prefix):]))
    numbers.sort()
    newest = numbers[-1] if numbers else 0
    while numbers and (len(numbers) >= KEEP or free_bytes(STATE_DIR) < MAX_BYTES + RESERVE_BYTES):
        os.remove("%s/%s%04d%s" % (REPLAY_DIR, prefix, numbers.pop(0), KEPT))
    if free_bytes(STATE_DIR) < MAX_BYTES + RESERVE_BYTES:
        raise OSError("no space")
    return "%s/%s%04d" % (REPLAY_DIR, prefix, newest + 1)


def random_seed():
    urandom = getattr(os, "urandom", None)
    if urandom is not None:
        return struct.unpack("<I", urandom(4))[0]
    return random.getrandbits(32)


class Off:
    path = None

    def journal(self, kind, value):
        return value

    def keep(self):
        pass

    def idle(self):
        pass

    def close(self):
        pass


class Recorder:
    def __init__(self, app, files):
        self.bits = {action: 1 << bit for bit, action in enumerate(actions())}
        self.sources = controls()
        self.seed = random_seed()
        random.seed(self.seed)
        self.stem = next_path(app)
        self.path = self.stem + PARTIAL
        self.kept = False
        header = {
            "app": app,
            "version": VERSION,
            "seed": self.seed,
            "id": binascii.hexlify(machine.unique_id()).decode(),
            "ticks": badge.ticks,
            "flags": status_flags(),
            "files": {},
        }
        for path in files:
            data = read_file(path)
            if data is not None:
                header["files"][path] = binascii.hexlify(data).decode()
        encoded = json.dumps(header).encode()

        self.writer = Writer(BUFFER_BYTES)
        self.writer.raw(MAGIC)
        self.writer.raw(struct.pack("<HI", VERSION, len(encoded)))
        with open(self.path, "wb") as f:
            f.write(self.writer.view[:self.writer.position])
            f.write(encoded)
        self.written = self.writer.position + len(encoded)
        self.writer.position = 0

        self.masks = bytearray(MASK_COUNT)
        self.last_masks = bytearray(MASK_COUNT)
        self.imu = bytearray(IMU_BYTES)
        self.last_imu = bytearray(IMU_BYTES)
        self.last_status = header["flags"] << 8
        self.last_ticks = header["ticks"]
        self.kinds = {}
        self.frame_start = 0
        self.contents_at = -1
        self.journal_at = -1
        self.frame_open = False
        self.flush_requested = False
        self.recording = True
        self.real_poll = badge.poll
        badge.poll = self.poll

    def poll(self):
        self.frame_open = False
        writer = self.writer
        if self.recording and (writer.position >= FORCE_FLUSH_BYTES or (self.flush_requested and writer.position >= IDLE_FLUSH_BYTES)):
            self.flush()
        self.flush_requested = False
        self.real_poll()
        if not self.recording:
            return

        masks = self.masks
        bits = self.bits
        index = 0
        for source in self.sources:
            for group in (source._held, source._pressed, source._released, source._changed):
                mask = 0
                for action in group:
                    mask |= bits.get(action, 0)
                masks[index] = mask
                index += 1
        try:
            struct.pack_into(IMU_FORMAT, self.imu, 0, *badge._imu_readings)
        except (TypeError, ValueError, OverflowError):
            pass
        status = (badge._imu_events & 0xFF) | (status_flags() << 8)

        contents = 0
        if masks != self.last_masks:
            contents |= HAS_MASKS
        if self.imu != self.last_imu:
            contents |= HAS_IMU
        if status != self.last_status:
            contents |= HAS_STATUS

        ticks = badge.ticks
        self.frame_start = writer.position
        writer.varint(max(0, ticks - self.last_ticks))
        self.contents_at = writer.position
        writer.byte(contents)
        if contents & HAS_MASKS:
            writer.raw(masks)
        if contents & HAS_IMU:
            writer.raw(self.imu)
        if contents & HAS_STATUS:
            writer.byte(status & 0xFF)
            writer.byte(status >> 8)

        self.masks, self.last_masks = self.last_masks, masks
        self.imu, self.last_imu = self.last_imu, self.imu
        self.last_status = status
        self.last_ticks = ticks
        self.journal_at = -1
        self.frame_open = True

    def kind_bytes(self, kind):
        data = self.kinds.get(kind)
        if data is None:
            data = self.kinds[kind] = kind.encode()
        return data

    def journal(self, kind, value):
        if not (self.recording and self.frame_open):
            return value
        writer = self.writer
        buffer = writer.buffer
        try:
            if self.journal_at < 0:
                buffer[self.contents_at] |= HAS_JOURNAL
                self.journal_at = writer.position
                writer.byte(0)
            if buffer[self.journal_at] >= JOURNAL_LIMIT:
                raise ValueError
            data = self.kind_bytes(kind)
            writer.byte(TAG_STR)
            writer.varint(len(data))
            writer.raw(data)
            writer.encode(value)
            buffer[self.journal_at] += 1
        except (IndexError, ValueError):
            writer.position = self.frame_start
            self.frame_open = False
            self.flush()
            self.recording = False
        return value

    def idle(self):
        self.flush_requested = True

    def flush(self):
        writer = self.writer
        if not writer.position or not self.recording:
            writer.position = 0
            return
        try:
            with open(self.path, "ab") as f:
                f.write(writer.view[:writer.position])
        except OSError:
            self.recording = False
        self.written += writer.position
        writer.position = 0
        if self.written >= MAX_BYTES:
            self.recording = False

    def keep(self):
        if self.kept:
            return
        try:
            os.rename(self.path, self.stem + KEPT)
        except OSError:
            return
        self.path = self.stem + KEPT
        self.kept = True

    def close(self):
        self.frame_open = False
        self.flush()
        self.recording = False
        badge.poll = self.real_poll
        if not self.kept:
            try:
                os.remove(self.path)
            except OSError:
                pass


class FakeUUID:
    def __init__(self, value):
        text = str(value)
        if text.startswith("UUID("):
            text = text[5:-1].strip("'\"")
        self.value = text.lower()

    def __eq__(self, other):
        return isinstance(other, FakeUUID) and other.value == self.value

    def __hash__(self):
        return hash(self.value)

    def __str__(self):
        return "UUID('%s')" % self.value


class FakeBLE:
    def gatts_register_services(self, services):
        handles = []
        next_handle = FIRST_HANDLE
        for _uuid, characteristics in services:
            handles.append(tuple(range(next_handle, next_handle + len(characteristics))))
            next_handle += len(characteristics)
        return tuple(handles)

    def gatts_read(self, handle):
        return b""

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class FakeBluetooth:
    UUID = FakeUUID

    def BLE(self):
        return FakeBLE()


class Player:
    def __init__(self, path):
        self.table = actions()
        with open(path, "rb") as f:
            self.data = f.read()
        if self.data[:4] != MAGIC:
            raise ValueError("not a replay")
        _version, length = struct.unpack_from("<HI", self.data, 4)
        start = len(MAGIC) + 6
        self.header = json.loads(self.data[start:start + length])
        self.index = start + length
        self.frame_number = 0
        self.ticks = self.header["ticks"]
        self.last_ticks = self.ticks
        self.masks = bytes(MASK_COUNT)
        self.queue = []
        try:
            import js
            self.mark = js.replay_mark
        except (ImportError, AttributeError):
            self.mark = None

        sys.modules["bluetooth"] = FakeBluetooth()
        unique_id = binascii.unhexlify(self.header["id"])
        machine.unique_id = lambda: unique_id
        for file_path, content in self.header["files"].items():
            ensure_dir(file_path.rsplit("/", 1)[0])
            with open(file_path, "wb") as f:
                f.write(binascii.unhexlify(content))
        random.seed(self.header["seed"])

        player = self
        badge_class = type(badge)
        badge_class.ticks = property(lambda _badge: player.ticks)
        badge_class.ticks_delta = property(lambda _badge: player.ticks - player.last_ticks)
        badge._imu = self
        badge._imu_readings = (0, 0, 0, 0, 0, 0)
        badge._imu_events = 0
        self.apply_flags(self.header["flags"])
        badge.poll = self.poll

    def apply_flags(self, flags):
        badge._upside_down = bool(flags & FLAG_UPSIDE_DOWN)
        badge.rotate_180(bool(flags & FLAG_ROTATED))

    def poll(self):
        try:
            self.read_frame()
        except IndexError:
            raise SystemExit
        for number, source in enumerate(controls()):
            groups = [tuple(action for bit, action in enumerate(self.table) if mask & (1 << bit))
                      for mask in self.masks[number * 4:number * 4 + 4]]
            source.set_state(*groups)
        self.frame_number += 1

    def read_frame(self):
        data = self.data
        if self.index >= len(data):
            raise IndexError
        delta, index = get_varint(data, self.index)
        contents = data[index]
        index += 1
        if contents & HAS_MASKS:
            self.masks = data[index:index + MASK_COUNT]
            index += MASK_COUNT
        if contents & HAS_IMU:
            badge._imu_readings = struct.unpack_from(IMU_FORMAT, data, index)
            index += IMU_BYTES
        if contents & HAS_STATUS:
            badge._imu_events = data[index]
            self.apply_flags(data[index + 1])
            index += 2
        queue = []
        if contents & HAS_JOURNAL:
            count = data[index]
            index += 1
            for _ in range(count):
                kind, index = decode(data, index)
                value, index = decode(data, index)
                queue.append((kind, value))
        self.index = index
        self.queue = queue
        self.last_ticks = self.ticks
        self.ticks += delta

    def journal(self, kind, value):
        for position, (logged_kind, logged_value) in enumerate(self.queue):
            if logged_kind == kind:
                self.queue.pop(position)
                if kind == "ble" and self.mark is not None:
                    for event in logged_value:
                        if event[0] in LINK_EVENTS:
                            self.mark(self.ticks)
                return logged_value
        return value

    def keep(self):
        pass

    def idle(self):
        pass

    def close(self):
        pass


def start(app, files=(), enabled=True):
    try:
        source = REPLAY_FILE
    except NameError:
        source = None
    if source:
        return Player(source)
    if not enabled:
        return Off()
    try:
        return Recorder(app, files)
    except OSError:
        return Off()
