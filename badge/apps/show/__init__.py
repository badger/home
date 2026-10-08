import sparkle

if not sparkle.request_local_show():
    raise RuntimeError("Sparkle show is unavailable")

run(lambda: None)
