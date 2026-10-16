import math
from badgeware import brushes, shapes, io, Matrix, screen

# bright icon colours
bold = [
    brushes.color(211, 250, 55),
    brushes.color(48, 148, 255),
    brushes.color(95, 237, 131),
    brushes.color(225, 46, 251),
    brushes.color(216, 189, 14),
    brushes.color(255, 128, 210),
]

# create faded out variants for inactive icons
fade = 1.8
faded = [
    brushes.color(211 / fade, 250 / fade, 55 / fade),
    brushes.color(48 / fade, 148 / fade, 255 / fade),
    brushes.color(95 / fade, 237 / fade, 131 / fade),
    brushes.color(225 / fade, 46 / fade, 251 / fade),
    brushes.color(216 / fade, 189 / fade, 14 / fade),
    brushes.color(255 / fade, 128 / fade, 210 / fade),
]

# icon shape
squircle = shapes.squircle(0, 0, 20, 4)
shade_brush = brushes.color(0, 0, 0, 30)


class Icon:
    active_icon = None

    def __init__(self, pos, name, index, icon):
        self.active = False
        self.pos = pos
        self.icon = icon
        self.name = name
        self.index = index
        self.spin = False

    def activate(self, active):
        # if this icon wasn't already activated then flag it for the spin animation
        if not self.active and active:
            self.spin = True
            self.spin_start = io.ticks
        self.active = active
        if active:
            Icon.active_icon = self

    def draw(self):
        width = 1
        sprite_width = self.icon.width
        sprite_offset = sprite_width / 2

        if self.spin:
            # create a spin animation that runs over 100ms
            speed = 100
            frame = io.ticks - self.spin_start

            # calculate the width of the tile during this part of the animation
            width = round(math.cos(frame / speed) * 3) / 3

            # ensure the width never reduces to zero or the icon disappears
            width = max(0.1, width) if width > 0 else min(-0.1, width)

            # determine how to offset and scale the sprite to match the tile width
            sprite_width = width * self.icon.width
            sprite_offset = abs(sprite_width) / 2

            # once the animation has completed unset the spin flag
            if frame > (speed * 6):
                self.spin = False

        # transform to the icon position
        squircle.transform = Matrix().translate(*self.pos).scale(width, 1)

        # draw the icon shading
        screen.brush = shade_brush
        squircle.transform = squircle.transform.scale(1.1, 1.1)
        screen.draw(squircle)

        # draw the icon body
        squircle.transform = squircle.transform.scale(1 / 1.1, 1 / 1.1)
        if self.active:
            screen.brush = bold[self.index]
        else:
            screen.brush = faded[self.index]
        squircle.transform = squircle.transform.translate(-1, -1)
        screen.draw(squircle)
        squircle.transform = squircle.transform.translate(2, 2)
        screen.brush = shade_brush
        screen.draw(squircle)

        # draw the icon sprite
        if sprite_width > 0:
            self.icon.alpha = 255 if self.active else 100
            screen.scale_blit(
                self.icon,
                self.pos[0] - sprite_offset - 1,
                self.pos[1] - 13,
                sprite_width,
                24,
            )
