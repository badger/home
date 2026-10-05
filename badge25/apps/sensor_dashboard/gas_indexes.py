class GasIndexes:
    def __init__(self, native, ticks_diff):
        self.native = native
        self.diff = ticks_diff
        self.reset()

    def reset(self):
        self.native.reset()
        self.voc = None
        self.nox = None
        self.samples = 0
        self.last_sample = None

    def process(self, voc_raw, nox_raw, now):
        if self.last_sample is not None:
            interval = self.diff(now, self.last_sample)
            if interval < 750:
                return
            if interval > 1500:
                print("Sensor dashboard: gas indexes reset after sampling gap")
                self.reset()
        voc, nox = self.native.process(voc_raw, nox_raw)
        self.samples += 1
        self.last_sample = now
        self.voc = voc if voc > 0 else None
        self.nox = nox if nox > 0 else None


def index_caption(value, baseline):
    if value is None:
        return "Warming up"
    if value < baseline:
        return "Below usual"
    if value == baseline:
        return "Background" if baseline == 1 else "Usual"
    return "Above usual"
