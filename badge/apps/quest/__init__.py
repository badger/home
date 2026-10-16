import os
import sys

APP_DIRS = ("/remote/apps/quest", "/system/apps/quest", "/apps/quest", "/quest")
APP_DIR = next(path for path in APP_DIRS if is_dir(path))
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

from aye_arr.nec import NECReceiver
from badgeware import State
from beacon import GithubUniverseBeacon
import ui

screen.antialias = image.X2

small_font = font.ark
large_font = font.absolute
splash = image.load("assets/splash.png")


class Quest:
    def __init__(self, quest_id, code, name):
        self.id = quest_id
        self.name = name
        self.code = code


quests = (
    Quest(1, 0x11, "Hack Your Badge"),
    Quest(2, 0x22, "Whats up Docs"),
    Quest(3, 0x33, "Stars Lounge"),
    Quest(4, 0x44, "GitHub Next"),
    Quest(5, 0x55, "Open Source Zone"),
    Quest(6, 0x66, "Demos & Donuts"),
    Quest(7, 0x77, "GitHub Learn"),
    Quest(8, 0x88, "Octocat Generator"),
    Quest(9, 0x99, "Makerspace"),
)

for quest in quests:
    GithubUniverseBeacon.BUTTON_CODES[quest.id] = quest.code

state = {"completed": []}
State.load("quest", state)

last_task_completed = None
last_task_completed_at = None


def complete_quest(quest_id):
    global last_task_completed, last_task_completed_at

    if 1 <= quest_id <= len(quests) and quest_id not in state["completed"]:
        last_task_completed = quests[quest_id - 1]
        last_task_completed_at = badge.ticks
        state["completed"].append(quest_id)
        State.save("quest", state)


ir = GithubUniverseBeacon()
ir.on_known = complete_quest

# The Universe 2026 schematic routes the VSOP38338 IR receiver to GPIO17.
receiver = NECReceiver(17, 0, 0)
receiver.bind(ir)
receiver.start()


def draw_completion():
    elapsed = badge.ticks - last_task_completed_at
    zoom_duration = 250

    if elapsed < zoom_duration:
        progress = elapsed / zoom_duration
        width = screen.width * progress
        height = screen.height * progress
        splash.alpha = int(progress * 255)
        screen.blit(
            splash,
            rect(
                (screen.width - width) / 2,
                (screen.height - height) / 2,
                width,
                height,
            ),
        )
        return

    splash.alpha = 255
    screen.blit(splash, vec2(0, 0))

    label = last_task_completed.name
    message = (
        "Side Quest Complete!"
        if len(state["completed"]) == len(quests)
        else "Location Unlocked!"
    )

    screen.font = large_font
    label_width, _ = screen.measure_text(label)
    screen.font = small_font
    message_width, _ = screen.measure_text(message)

    screen.pen = color.rgb(46, 160, 67, 220)
    label_corners = (4, 4, 0, 0) if label_width < message_width else (4, 4, 4, 4)
    message_corners = (4, 4, 4, 4) if label_width < message_width else (0, 0, 4, 4)
    screen.shape(
        shape.rounded_rectangle(
            (screen.width - label_width) / 2 - 4,
            2,
            label_width + 8,
            18,
            *label_corners,
        )
    )
    screen.shape(
        shape.rounded_rectangle(
            (screen.width - message_width) / 2 - 4,
            20,
            message_width + 8,
            12,
            *message_corners,
        )
    )

    screen.pen = color.white
    screen.font = large_font
    screen.text(label, (screen.width - label_width) / 2, 2)
    screen.font = small_font
    screen.text(message, (screen.width - message_width) / 2, 19)


def update():
    global last_task_completed_at

    receiver.decode()

    screen.pen = color.rgb(35, 41, 37)
    screen.clear()
    ui.draw_status(state["completed"])
    ui.draw_tiles(state["completed"])

    if last_task_completed_at is not None and badge.pressed():
        last_task_completed_at = None

    if last_task_completed_at is not None:
        draw_completion()


def on_exit():
    receiver.stop()


run(update)
