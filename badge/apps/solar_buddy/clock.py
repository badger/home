"""Wrap-safe badge timing, with a CPython implementation for the preview."""

import time


def ticks_ms():
    if hasattr(time, "ticks_ms"):
        return time.ticks_ms()
    return int(time.monotonic() * 1000)


def elapsed(now, then):
    if hasattr(time, "ticks_diff"):
        return time.ticks_diff(now, then)
    return now - then
