"""Mona's personal Universe agenda."""

import os
import sys
import time

APP_DIR = "/system/apps/universe_agenda"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)
sys.path.insert(0, "/system")

import utc_clock
import universe_agenda as reminders

agenda = reminders.service if reminders.installed else reminders.Agenda()
tab = 0
selected = 0
setting = 0
message = ""
sync_step = 0
screen.fill_rule = image.EVEN_ODD


def line(value, x, y, width=None):
    screen.text(reminders.fit(screen, value, width or screen.width - x - 5), x, y)


def sync_clock():
    global sync_step, message
    try:
        if sync_step == 1:
            import wifi
            message = "Connecting to WiFi..."
            if wifi.connect():
                sync_step = 2
                message = "Syncing UTC clock..."
            else:
                message = "WiFi failed; check Settings"
                sync_step = 0
        elif sync_step == 2:
            utc_clock.sync()
            agenda.clock_ready = True
            agenda.last_check = None
            sync_step = 0
            message = "Clock synced (Pacific display)"
    except (OSError, ValueError) as error:
        message = "Sync failed: " + str(error)
        print("Universe clock: " + str(error))
        sync_step = 0


def update():
    global tab, selected, setting, message, sync_step
    if badge.pressed(BUTTON_LEFT) or badge.pressed(BUTTON_RIGHT):
        tab = 1 - tab
    direction = int(badge.pressed(BUTTON_DOWN)) - int(badge.pressed(BUTTON_UP))
    if tab == 0:
        selected = max(0, min(len(agenda.events) - 1, selected + direction))
    else:
        setting = (setting + direction) % 3

    if badge.pressed(BUTTON_SELECT) and not sync_step:
        try:
            if tab == 0:
                agenda.import_agenda()
                selected = 0
                message = "Imported %d sessions" % len(agenda.events)
            elif setting == 0:
                index = reminders.LEADS.index(agenda.state["lead_minutes"])
                agenda.save({"lead_minutes": reminders.LEADS[(index + 1) % len(reminders.LEADS)]})
                message = "Reminder lead saved"
            elif setting == 1:
                agenda.save({"enabled": not agenda.state["enabled"]})
                message = "Reminders " + ("on" if agenda.state["enabled"] else "off")
            else:
                sync_step = 1
                message = "Connecting to WiFi..."
        except (OSError, ValueError) as error:
            message = str(error)
            print("Universe agenda: " + message)

    # Let the status render before the network operation on the next frame.
    elif sync_step:
        sync_clock()

    screen.pen = color.rgb(13, 17, 23)
    screen.rectangle(screen.clip)
    screen.font = font.ark
    reminders.draw_mona(screen, screen.width - 18, 18)
    screen.pen = color.rgb(211, 250, 55)
    line("Mona's Universe", 6, 4, screen.width - 40)
    screen.pen = color.rgb(190, 133, 255)
    if agenda.clock_ready:
        now = utc_clock.pacific_time()
        line("%02d:%02d:%02d Pacific" % (now[3], now[4], now[5]), 6, 17, screen.width - 35)
    else:
        line("Clock not synced", 6, 17, screen.width - 35)

    screen.pen = color.rgb(255, 255, 255)
    if tab:
        options = (
            "Remind: %d min before" % agenda.state["lead_minutes"],
            "Reminders: " + ("ON" if agenda.state["enabled"] else "OFF"),
            "Sync clock via WiFi",
        )
        for index, option in enumerate(options):
            line(("> " if index == setting else "  ") + option, 6, 38 + 14 * index)
    elif agenda.events:
        event = agenda.events[selected]
        start = utc_clock.pacific_time(utc_clock.parse_utc(event["start"]))
        line("%d/%d  %02d/%02d %02d:%02d PT" %
             (selected + 1, len(agenda.events), start[1], start[2], start[3], start[4]), 6, 35)
        line(event["title"], 6, 50)
        line(event["location"], 6, 64)
        line("Source: " + agenda.state["source"], 6, 78)
    else:
        line("Account not connected", 6, 37)
        line("No sessions loaded", 6, 51)
        line("Sign in to Universe", 6, 65)
        line("Then transfer agenda", 6, 79)

    screen.pen = color.rgb(190, 133, 255)
    status = agenda.error or message
    if not reminders.installed:
        status = "Global alerts OFF: install main"
    line(status, 6, screen.height - 27)
    screen.pen = color.rgb(180, 190, 200)
    line("L/R: tabs  UP/DN: choose", 6, screen.height - 17)
    line("SEL: " + ("change/sync" if tab else "reload") + "  HOME: exit", 6, screen.height - 8)
    if not reminders.installed:
        agenda.tick(badge.ticks_delta)


run(update)
