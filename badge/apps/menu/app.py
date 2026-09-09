import os
import math

import ui

DEFAULT_ICON = image.load("default_icon.png")

# bright icon colours
COLORS = [color.orange, color.blue, color.red, color.green, color.yellow, color.grape]
HIGHLIGHT = ((0.0, color.rgb(255, 255, 255, 64)), (1.0, color.rgb(255, 255, 255, 0)))

# icon shape
squircle = shape.squircle(0, 0, 20, 4)
shade_brush = color.rgb(0, 0, 0, 50)
# Built once: the geometry is fixed and each icon's position comes from the
# shape's transform, which the brush folds in at render time. Constructing it per
# icon per frame rebuilt an identical 256-entry lookup table six times a frame,
# about 2.6ms.
highlight_brush = brush.gradient(brush.RADIAL, -20, -20, 0, 30, HIGHLIGHT)


class App:
    def __init__(self, collection, name, path):
        self.active = False
        self.index = len(collection)
        self.pos = vec2((self.index % 3) * 48 + 32, (math.floor((self.index % 6) / 3)) * 48 + 42)
        self.icon = image.load(f"{path}/icon.png") if file_exists(f"{path}/icon.png") else DEFAULT_ICON
        self.name = name
        self.path = path
        self.spin = False
        collection.append(self)

    def activate(self, active):
        # if this icon wasn't already activated then flag it for the spin animation
        if not self.active and active:
            self.spin = True
            self.spin_start = badge.ticks
        self.active = active

    def draw(self):
        width = 1
        sprite_width = self.icon.width
        sprite_offset = sprite_width / 2

        if self.spin:
            # create a spin animation that runs over 100ms
            speed = 100
            frame = badge.ticks - self.spin_start

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

        # transform to the icon position (TODO: Fix need to fudge position by .5 pixels for smoother squircle)
        squircle.transform = mat3().translate(self.pos.x + 0.5, self.pos.y + 0.5).scale(width, 1)

        # draw the icon shading
        screen.pen = shade_brush
        screen.shape(squircle)

        # draw the icon body
        screen.pen = COLORS[self.index % 6]
        screen.alpha = 255 if self.active else 128

        squircle.transform = squircle.transform.translate(-1, -1)
        screen.shape(squircle)
        squircle.transform = squircle.transform.translate(2, 2)
        screen.pen = shade_brush
        screen.shape(squircle)
        squircle.transform = squircle.transform.translate(-1, -1)
        screen.pen = highlight_brush
        screen.shape(squircle)

        screen.alpha = 255

        # draw the icon sprite
        if sprite_width > 0:
            self.icon.alpha = 255 if self.active else 100
            screen.blit(
                self.icon,
                rect(
                    self.pos.x - sprite_offset - 1,
                    self.pos.y - 13,
                    sprite_width,
                    24
                )
            )


class Apps:
    def __init__(self, root):
        self.apps = []
        self.active_index = 0

        def capitalize(word):
            if len(word) <= 1:
                return word
            return word[0].upper() + word[1:]

        for path in sorted(os.listdir(root)):
            name = " ".join([capitalize(word) for word in path.split("_")])

            if is_dir(f"{root}/{path}"):
                if path not in ("menu", "startup") and (file_exists(f"{root}/{path}/__init__.py") or file_exists(f"{root}/{path}/__init__.mpy")):
                    App(self.apps, name, f"{root}/{path}")

    @property
    def active(self):
        return self.apps[self.active_index]

    def activate(self, index):
        self.active_index = index
        for app in self.apps:
            app.activate(app.index == index)

    def draw_icons(self):
        offset = (self.active_index // 6) * 6
        for app in self.apps[offset:offset + 6]:
            app.draw()

    def draw_label(self):
        label = self.active.name
        w, _ = screen.measure_text(label)
        screen.pen = ui.phosphor
        screen.shape(shape.rounded_rectangle(80 - (w / 2) - 4, 100, w + 8, 15, 4))
        screen.pen = color.rgb(20, 40, 60)
        screen.text(label, 80 - (w / 2), 101)

    def draw_pagination(self, x=150, y=65):
        pages = math.ceil(len(self.apps) / 6)
        selected_page = self.active_index // 6
        y -= (pages * 7) / 2

        for page in range(pages):
            offset = page * 6
            pips = len(self.apps[offset:offset + 6])
            for pip in range(pips):
                if self.active_index - (page * 6) == pip:
                    screen.pen = color.rgb(255, 255, 255, 200)
                else:
                    screen.pen = color.rgb(255, 255, 255, 100) if page == selected_page else color.rgb(255, 255, 255, 50)
                screen.put(x + (pip % 3) * 2, y + (page * 7) + (pip // 3) * 2)

    def __len__(self):
        return len(self.apps)

    def __getitem__(self, i):
        return self.apps[i]
