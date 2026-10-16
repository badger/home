from badgeware import PixelFont, screen, brushes, shapes, io

small_font = PixelFont.load("/system/assets/fonts/ark.ppf")
small_char_width = 7
large_font = PixelFont.load("/system/assets/fonts/absolute.ppf")

SCREEN_WIDTH = 160
SCREEN_HEIGHT = 120

CHAR_COUNT_WIDTH = SCREEN_WIDTH // small_char_width

ROW_HEIGHT = 10

HOLD_DELAY = 10
DEBOUNCE_MS = 150  # Debounce delay in milliseconds


class ScrollList:
    def __init__(self, title="", subtitle="", contents=None):
        self.index = None
        self.title_text = title
        self.subtitle_text = subtitle
        self.content_items = contents or []

        self.padding = 5
        self.wrap_around = True

        self._held_cache = {}
        self._debounce_cache = {}
        self._current_render_y = 0

    def update(self):
        self._current_render_y = 0
        self.handle_io()
        self.render()

    def handle_io(self):
        self.connect_input(io.BUTTON_UP, self.on_button_up)
        self.connect_input(io.BUTTON_DOWN, self.on_button_down)
        self.connect_input(io.BUTTON_A, self.on_button_back)
        self.connect_input(io.BUTTON_C, self.on_button_forward)

        if io.BUTTON_B in io.pressed:
             self.on_button_select()

    def connect_input(self, button, action):
        # Check if enough time has passed since last action for this button
        now = io.ticks
        last_action_time = self._debounce_cache.get(button, 0)
        
        if button in io.pressed:
            # Only trigger if debounce period has elapsed
            if now - last_action_time >= DEBOUNCE_MS:
                action()
                self._debounce_cache[button] = now
        elif button in io.held:
            # For held buttons, use the existing hold delay mechanism
            if self._held_cache.get(button, 0) + 1 >= HOLD_DELAY:
                # Check debounce for held actions too
                if now - last_action_time >= DEBOUNCE_MS:
                    action()
                    self._debounce_cache[button] = now
            else:
                self._held_cache[button] = self._held_cache.get(button, 0) + 1
        else:
            self._held_cache[button] = 0

    def on_button_up(self):
        if self.index is None:
            self.index = len(self.content_items) - 1
        else:
            if self.wrap_around:
                self.index = (self.index - 1) % len(self.content_items)
            else:
                self.index = max(0, self.index - 1)

    def on_button_down(self):
        if self.index == None:
            self.index = 0
        else:
            if self.wrap_around:
                self.index = (self.index + 1) % len(self.content_items)
            else:
                self.index = min(len(self.content_items) - 1, self.index + 1)

    def on_button_back(self):
        pass

    def on_button_select(self):
        pass

    def on_button_forward(self):
        pass

    def render(self):
        self.render_background()
        self.render_title()
        self.render_subtitle()
        self.render_contents()

    def render_background(self):
        screen.brush = brushes.color(0, 0, 0)
        screen.draw(shapes.rectangle(0, 0, 160, 120))

    def render_title(self):
        if self.title_text:
            screen.brush = brushes.color(0, 255, 0)
            screen.font = large_font
            screen.text(self.title_text, self.padding, self._current_render_y)
            self._current_render_y += 20

    def render_subtitle(self):
        if self.subtitle_text:
            screen.brush = brushes.color(100, 100, 100)
            screen.font = small_font
            screen.text(
                self.subtitle_text[-CHAR_COUNT_WIDTH:],
                self.padding,
                self._current_render_y,
            )
            self._current_render_y += 10

    def render_contents(self):
        vspace = SCREEN_HEIGHT - self._current_render_y
        row_count = vspace // ROW_HEIGHT

        start_row = max(0, (self.index or 0) - (row_count // 2))
        end_row = start_row + row_count

        items_to_render = self.content_items[start_row:end_row]

        for i, item in enumerate(items_to_render):
            self.render_item(item, i + start_row)

    def render_item(self, item, index, brush=brushes.color(255, 255, 255)):
        is_selected = index == self.index

        if is_selected:
            screen.brush = brushes.color(0, 50, 0)
            screen.draw(shapes.rectangle(0, self._current_render_y, SCREEN_WIDTH, 12))

        screen.font = small_font
        screen.brush = brush
        screen.text(item, self.padding, self._current_render_y)
        self._current_render_y += 10
