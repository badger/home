from scroll_list import ScrollList


class TextFileViewer(ScrollList):
    def __init__(self, file_path, on_close=lambda: None):
        super().__init__("", file_path)
        self.content_items = self.load_file(file_path)
        self.on_close = on_close
        self.wrap_around = False

        self.pan_idx = 0

    def on_button_back(self):
        self.pan_idx = max(0, self.pan_idx - 1)

    def on_button_forward(self):
        self.pan_idx = self.pan_idx + 1

    def on_button_select(self):
        self.on_close()

    def render_item(self, item, index):
        return super().render_item(item[self.pan_idx:], index)

    def load_file(self, file_path=None):
        try:
            with open(file_path, "r") as f:
                return f.readlines()
        except Exception as e:
            return [f"Error loading file: {e}"]
