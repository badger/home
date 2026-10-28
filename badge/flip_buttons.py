SWAP = {
    BUTTON_UP: BUTTON_DOWN,
    BUTTON_DOWN: BUTTON_UP,
    BUTTON_LEFT: BUTTON_RIGHT,
    BUTTON_RIGHT: BUTTON_LEFT,
}
EVENTS = ("held", "pressed", "released", "changed")

installed = False


def flipped():
    return bool(badge.rotate_180())


class Buttons:
    def __init__(self, source):
        self._source = source

    def __getattr__(self, name):
        return getattr(self._source, name)


def physical(source, name):
    original = getattr(source, name)

    def event(button=None):
        if not flipped():
            return original(button) if button is not None else original()
        if button is None:
            return {SWAP.get(action, action) for action in original()}
        return original(SWAP.get(button, button))

    return event


def combined(name, buttons, pad):
    original = getattr(badge, name)
    pad_event = getattr(pad, name)

    def event(button=None):
        if not flipped():
            return original(button) if button is not None else original()
        if button is None:
            actions = {action for action in original() if action not in SWAP}
            actions.update(action for action in pad_event() if action in SWAP)
            actions.update(action for action in buttons(name)() if action in SWAP)
            return actions
        if button in SWAP:
            return bool(pad_event(button) or buttons(name)(button))
        return original(button)

    return event


def direction_for(held, physical_held, original):
    def direction():
        if not flipped() or not any(physical_held(action) for action in SWAP):
            return original()
        return vec2(
            int(held(BUTTON_RIGHT)) - int(held(BUTTON_LEFT)),
            int(held(BUTTON_DOWN)) - int(held(BUTTON_UP)),
        )

    return direction


def install():
    global installed
    if installed:
        return
    source = badge.buttons
    pad = badge.pad
    names = [name for name in EVENTS if all(hasattr(group, name) for group in (badge, source, pad))]
    wrapped = Buttons(source)
    for name in names:
        setattr(wrapped, name, physical(source, name))

    def buttons(name):
        return getattr(wrapped, name)

    events = {name: combined(name, buttons, pad) for name in names}
    direction = direction_for(events["held"], source.held, badge.direction)

    for name in names:
        events[name]()
        events[name](BUTTON_UP)
        getattr(wrapped, name)()
    direction()

    for name, event in events.items():
        setattr(badge, name, event)
    badge.direction = direction
    badge.buttons = wrapped
    installed = True
