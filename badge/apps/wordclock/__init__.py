import sys
import os
import time
import ntptime
import network

from badgeware import screen, PixelFont, shapes, brushes, run

# Word Clock v1.0.0
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Jeffrey Luszcz
# https://github.com/jeff-luszcz/wordclock-badge2025

# Note: this app requires WiFi and internet access to sync time via NTP
# Note: adjust UTC_OFFSET below to your local timezone
# The app will attempt to connect to WiFi and sync time on first run
# The app will PAUSE updating the display for 10 seconds until time is synced, Don't Panic!

# enter your offset from UTC here (E.G. BOSTON IS UTC-5)
UTC_OFFSET = -5

# DO NOT EDIT THESE VALUES HERE, EDIT IN SECRETS.PY IN THE ROOT DIRECTORY
# OF THE BADGE WHEN MOUNTED IN USB MODE!
# Default to None in case secrets cannot be imported
WIFI_SSID = None
WIFI_PASSWORD = None

# Attempt to import from secrets.py (should be in root)
try:
    sys.path.insert(0, "/")
    from secrets import WIFI_SSID, WIFI_PASSWORD
    sys.path.pop(0)
except ImportError:
    WIFI_SSID = None
    WIFI_PASSWORD = None


# Global WiFi connection object
wlan_global = None
wifi_initialized = False
ntp_synced = False

def init_wifi():
    if not WIFI_SSID or not WIFI_PASSWORD:
        screen.brush = brushes.color(0, 0, 0)
        screen.draw(shapes.rectangle(0, 0, 160, 120))
        font = PixelFont.load("/system/assets/fonts/awesome.ppf")
        screen.font = font
        screen.brush = brushes.color(255, 255, 255)
        screen.text("WiFi credentials", 0, 0)
        screen.text("not found", 0, 15)
        screen.text("SSID: {}".format("None" if not WIFI_SSID else "OK"), 0, 30)
        time.sleep(3)
        return None

    screen.brush = brushes.color(0, 0, 0)
    screen.draw(shapes.rectangle(0, 0, 160, 120))
    font = PixelFont.load("/system/assets/fonts/awesome.ppf")
    screen.font = font
    screen.brush = brushes.color(255, 255, 255)
    screen.text("Connecting to", 0, 0)
    screen.text(WIFI_SSID[:20], 0, 15)  # Truncate if too long
    
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if not wlan.isconnected():
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        for i in range(20):
            screen.text("Attempt {}".format(i+1), 0, 30)
            if wlan.isconnected():
                break
            time.sleep(0.5)

    screen.brush = brushes.color(0, 0, 0)
    screen.draw(shapes.rectangle(0, 0, 160, 120))
    screen.brush = brushes.color(255, 255, 255)
    
    if wlan.isconnected():
        screen.text("Connected!", 0, 0)
        ip_info = wlan.ifconfig()
        screen.text(ip_info[0], 0, 15)
        screen.text("Syncing time...", 0, 30)
        time.sleep(2)
        return wlan
    else:
        screen.text("Failed to", 0, 0)
        screen.text("connect to", 0, 15)
        screen.text(WIFI_SSID[:20], 0, 30)
        time.sleep(3)
        return None


# the Github Universe 2025 badge is 39 characters wide
# or 20 characters with a single space between each character and no space on the end
# thre screen is 160 pixels wide and 120 pixels tall

# Variables for each spaced string (variable name = string with spaces removed)
M = "M G K "
IT = "I T "
P = "P "
R = "R "
IS = "I S "
TEN_1 = "T E N "
A_1 = "A "
HALF = "H A L F "
P_4 = "P "
YUJ = "Y U J "
QUARTER = "Q U A R T E R "
N = "N "
TWENTY = "T W E N T Y "
X = "X "
W = "W B Y C "
FIVE = "F I V E "
A = "A "
MINUTES = "M I N U T E S "
V_3 = "V L"
PAST = "P A S T "
P_4 = "P "
TO = "T O "
ONE = "O N E "
R_4 = "R "
TWO = "T W O "
Y = "Y P R J "
THREE = "T H R E E "
V_5="V T O "
FOUR = "F O U R "
A_5 = "A Y "
FIVE_5 = "F I V E"
FG = "F G W "
SIX = "S I X "
L_6 = "L P U B "
O_6 = "O "
SEVEN = "S E V E N "
EIGHT = "E I G H T "
NINE = "N I N E "
V_7= "V T M O "
TEN = "T E N "
H_7= "H "
ELEVEN = "E L E V E N "
FG = "F G "
TWELVE = "T W E L V E "
OCLOCK = "O C L O C K "
U_8 = "U R G R "
U_4 = "U "

# Booleans controlling brightness for each piece (True = bright white, False = very dim gray)
M_ON = False
IT_ON = True
P_ON = False
IS_ON = True
R_ON = False
TEN_1_ON = False
A_1_ON = False
HALF_ON = False
# New booleans for the second line pieces
YUJ_ON = False
QUARTER_ON = False
N_ON = False
TWENTY_ON = False
X_ON = False
# Booleans for the third line pieces
FIVE_ON = False
W_ON = False
A_ON = False
MINUTES_ON = False
V_3_ON = False
# Booleans for the fourth line (time) pieces
PAST_ON = False
P_4_ON = False
TO_ON = False
ONE_ON = False
R_4_ON = False
TWO_ON = False
Y_ON = False
# Booleans for the new fifth line pieces
THREE_ON = False
V_3b_ON = False  # if you want separate control for the V_3 instance on this line
FOUR_ON = False
A_5_ON = False
FIVE_5_ON = False
SIX_ON = False
L_6_ON = False
O_6_ON = False
NINE_ON = False
V_7_ON = False
TEN_ON = False
H_7_ON = False
ELEVEN_ON = False
SEVEN_ON = False
EIGHT_ON = False
TWELVE_ON = False
FG_ON = False
U_8_ON = False
OCLOCK_ON = False

def set_time_words(hour, minute):
    """Set word booleans based on current hour and minute"""
    global IT_ON, IS_ON, HALF_ON, QUARTER_ON, TWENTY_ON, FIVE_ON, TEN_1_ON, A_1_ON, M_ON
    global MINUTES_ON, PAST_ON, P_4_ON, TO_ON, ONE_ON, TWO_ON, THREE_ON, FOUR_ON, X_ON, W_ON, Y_ON
    global FIVE_5_ON, SIX_ON, SEVEN_ON, EIGHT_ON, NINE_ON, TEN_ON
    global ELEVEN_ON, TWELVE_ON, OCLOCK_ON, A_ON, U_4_ON, FG_ON, YUJ_ON
    
    # Reset all time booleans
    M_ON = False
    HALF_ON = False
    YUJ_ON = False
    QUARTER_ON = False
    TWENTY_ON = False
    X_ON = False
    W_ON = False
    FIVE_ON = False
    TEN_1_ON = False
    A_1_ON = False
    MINUTES_ON = False
    PAST_ON = False
    P_4_ON = False
    TO_ON = False
    U_4_ON = False
    ONE_ON = False
    TWO_ON = False
    Y_ON = False
    THREE_ON = False
    FOUR_ON = False
    FIVE_5_ON = False
    SIX_ON = False
    SEVEN_ON = False
    EIGHT_ON = False
    NINE_ON = False
    TEN_ON = False
    ELEVEN_ON = False
    TWELVE_ON = False
    FG_ON = False
    OCLOCK_ON = False
    A_ON = False
    
    # IT and IS always on
    IT_ON = True
    IS_ON = True
    YUJ_ON = False
    
    # Normalize hour to 12-hour format
    display_hour = hour % 12
    if display_hour == 0:
        display_hour = 12
    
    # Helper to turn on hour word
    def set_hour(h):
        global ONE_ON, TWO_ON, THREE_ON, FOUR_ON, FIVE_5_ON, SIX_ON
        global SEVEN_ON, EIGHT_ON, NINE_ON, TEN_ON, ELEVEN_ON, TWELVE_ON
        if h == 1: ONE_ON = True
        elif h == 2: TWO_ON = True
        elif h == 3: THREE_ON = True
        elif h == 4: FOUR_ON = True
        elif h == 5: FIVE_5_ON = True
        elif h == 6: SIX_ON = True
        elif h == 7: SEVEN_ON = True
        elif h == 8: EIGHT_ON = True
        elif h == 9: NINE_ON = True
        elif h == 10: TEN_ON = True
        elif h == 11: ELEVEN_ON = True
        elif h == 12: TWELVE_ON = True

    # Exact hour (0 minutes)
    # 0-4 minutes: just show the hour (no "o'clock")
    if 0 <= minute <= 4:
        set_hour(display_hour)
        OCLOCK_ON = True
    # 5-9 minutes past the hour
    elif 5 <= minute <= 9:
        FIVE_ON = True
        PAST_ON = True
        set_hour(display_hour)
    # 10-14 minutes: ten minutes past the hour
    elif 10 <= minute <= 14:
        TEN_1_ON = True
        MINUTES_ON = True
        PAST_ON = True
        set_hour(display_hour)
    # 15-19 minutes: quarter past the hour
    elif 15 <= minute <= 19:
        A_1_ON = True
        QUARTER_ON = True
        PAST_ON = True
        set_hour(display_hour)
    # 20-24 minutes: twenty past the hour
    elif 20 <= minute <= 24:
        TWENTY_ON = True
        PAST_ON = True
        set_hour(display_hour)
    # 25-29 minutes: twenty five past the hour
    elif 25 <= minute <= 29:
        TWENTY_ON = True
        FIVE_ON = True
        PAST_ON = True
        set_hour(display_hour)
    # 30-34 minutes: half past the hour
    elif 30 <= minute <= 34:
        HALF_ON = True
        PAST_ON = True
        set_hour(display_hour)
    # 35-39 minutes: twenty five to next hour
    elif 35 <= minute <= 39:
        TWENTY_ON = True
        FIVE_ON = True
        TO_ON = True
        next_hour = display_hour + 1
        if next_hour > 12:
            next_hour = 1
        set_hour(next_hour)
    # 40-44 minutes: twenty to next hour
    elif 40 <= minute <= 44:
        TWENTY_ON = True
        TO_ON = True
        next_hour = display_hour + 1
        if next_hour > 12:
            next_hour = 1
        set_hour(next_hour)
    # 45-49 minutes: quarter to next hour
    elif 45 <= minute <= 49:
        A_1_ON = True
        QUARTER_ON = True
        TO_ON = True
        next_hour = display_hour + 1
        if next_hour > 12:
            next_hour = 1
        set_hour(next_hour)
    # 50-54 minutes: ten to next hour
    elif 50 <= minute <= 54:
        TEN_1_ON = True
        TO_ON = True
        next_hour = display_hour + 1
        if next_hour > 12:
            next_hour = 1
        set_hour(next_hour)
    # 55-59 minutes: five to next hour
    elif 55 <= minute <= 59:
        FIVE_ON = True
        TO_ON = True
        next_hour = display_hour + 1
        if next_hour > 12:
            next_hour = 1
        set_hour(next_hour)
     # Add more time ranges as needed...

def update():
    # global hourTest, minuteTest
    global wlan_global, wifi_initialized, ntp_synced
    
    # Initialize WiFi on first call
    if not wifi_initialized:
        wifi_initialized = True
        wlan_global = init_wifi()
    
    # Clear the screen with black background
    screen.brush = brushes.color(0, 0, 0)
    screen.draw(shapes.rectangle(0, 0, 160, 120))
    
    # Load font first
    font = PixelFont.load("/system/assets/fonts/awesome.ppf")
    screen.font = font
    
    # Only check WiFi status if NTP hasn't synced yet
    if not ntp_synced:
        # Check if wlan_global exists
        if not wlan_global:
            screen.brush = brushes.color(255, 0, 0)
            screen.text("WiFi not init", 0, 0)
            screen.text("Check secrets.py", 0, 15)
            return None
        
        # Check WiFi connectivity
        if not wlan_global.isconnected():
            screen.brush = brushes.color(255, 0, 0)
            screen.text("No WiFi", 0, 0)
            screen.text("Connection", 0, 15)
            # Try to reconnect
            if WIFI_SSID and WIFI_PASSWORD:
                screen.text("Reconnecting...", 0, 30)
                wlan_global.connect(WIFI_SSID, WIFI_PASSWORD)
            return None
        
        # WiFi is connected - try NTP sync once
        try:
            screen.brush = brushes.color(255, 255, 0)
            screen.text("WiFi Connected!", 0, 0)
            screen.text("Syncing time...", 0, 15)
            ntptime.settime()
            ntp_synced = True
            screen.text("Time synced!", 0, 30)
            time.sleep(2)
        except Exception as e:
            screen.brush = brushes.color(255, 255, 0)
            screen.text("WiFi Connected!", 0, 0)
            screen.text("NTP sync failed:", 0, 15)
            screen.text(str(e)[:20], 0, 30)
            time.sleep(2)
            return None
    
    # Clear and show clock (only reached if ntp_synced is True)
    screen.brush = brushes.color(0, 0, 0)
    screen.draw(shapes.rectangle(0, 0, 160, 120))
    screen.font = font
    
    now = time.localtime()
    set_time_words(now[3]+UTC_OFFSET, now[4])

    # Load a cool font
    font = PixelFont.load("/system/assets/fonts/awesome.ppf")
    
    # Set up very dim gray text by default (will override per-segment)
    screen.brush = brushes.color(64, 64, 64)
    screen.font = font
    
    # Build segments for the first line (text, boolean_flag)
    segments = [
        (M, M_ON),
        (IT, IT_ON),
        (P, P_ON),
        (IS, IS_ON),
        (R, R_ON),
        (TEN_1, TEN_1_ON),
        (A_1, A_1_ON),
        (HALF, HALF_ON),
        (P_4, P_4_ON),
    ]

    # Build segments for the second line (text, boolean_flag)
    segments2 = [
        (YUJ, YUJ_ON),
        (QUARTER, QUARTER_ON),
        (N, N_ON),
        (TWENTY, TWENTY_ON),
        (X, X_ON),
    ]

    # Build segments for the third line (text, boolean_flag)
    segments3 = [
        (W, W_ON),
        (FIVE, FIVE_ON),
        (A, A_ON),
        (MINUTES, MINUTES_ON),
        (V_3, V_3_ON),
    ]

    # Build segments for the fourth line (text, boolean_flag)
    segments4 = [
        (PAST, PAST_ON),
        (TO, TO_ON),
        (P_4, P_4_ON),
        (ONE, ONE_ON),
        (R_4, R_4_ON),
        (TWO, TWO_ON),
        (Y, Y_ON),
    ]

    # Build segments for the fifth/new line (text, boolean_flag)
    segments5 = [
        (THREE, THREE_ON),
        (V_5, V_3b_ON),
        (FOUR, FOUR_ON),
        (A_5, A_5_ON),
        (FIVE_5, FIVE_5_ON),
    ]

    # Build segments for the sixth line: SIX, L_6, SEVEN, O_6, EIGHT
    segments6 = [
        (SIX, SIX_ON),
        (L_6, L_6_ON),
        (SEVEN, SEVEN_ON),
        (O_6, O_6_ON),
        (EIGHT, EIGHT_ON),
    ]

    # Build segments for the seventh line: NINE, V_7, TEN, H_7, ELEVEN
    segments7 = [
        (NINE, NINE_ON),
        (V_7, V_7_ON),
        (TEN, TEN_ON),
        (H_7, H_7_ON),
        (ELEVEN, ELEVEN_ON),
    ]
    # Build segments for the eighth line: TWELVE, U_8, OCLOCK
    segments8 = [
        (FG, FG_ON),
        (TWELVE, TWELVE_ON),
        (U_8, U_8_ON),
        (OCLOCK, OCLOCK_ON),
    ]
    # Compose full strings and per-character flags for lines (trim trailing spaces)
    line0 = "".join(s[0].rstrip() for s in segments)
    flags0 = []
    for text, flag in segments:
        t = text.rstrip()
        flags0.extend([flag] * len(t))    


    line1 = "".join(s[0].rstrip() for s in segments2)
    flags1 = []
    for text, flag in segments2:
        t = text.rstrip()
        flags1.extend([flag] * len(t))

    line2 = "".join(s[0].rstrip() for s in segments3)
    flags2 = []
    for text, flag in segments3:
        t = text.rstrip()
        flags2.extend([flag] * len(t))

    line3 = "".join(s[0].rstrip() for s in segments4)
    flags3 = []
    for text, flag in segments4:
        t = text.rstrip()
        flags3.extend([flag] * len(t))

    line4 = "".join(s[0].rstrip() for s in segments5)
    flags4 = []
    for text, flag in segments5:
        t = text.rstrip()
        flags4.extend([flag] * len(t))

    # Compose sixth line (line5)
    line5 = "".join(s[0].rstrip() for s in segments6)
    flags5 = []
    for text, flag in segments6:
        t = text.rstrip()
        flags5.extend([flag] * len(t))

    # Compose seventh line (line6)
    line6 = "".join(s[0].rstrip() for s in segments7)
    flags6 = []
    for text, flag in segments7:
        t = text.rstrip()
        flags6.extend([flag] * len(t))

    # Compose eighth line (line7)
    line7 = "".join(s[0].rstrip() for s in segments8)
    flags7 = []
    for text, flag in segments8:
        t = text.rstrip()
        flags7.extend([flag] * len(t))

    # Composed lines list (including the new eighth line)
    composed_lines = [line0, line1, line2, line3, line4, line5, line6, line7]
    composed_flags = [flags0, flags1, flags2, flags3, flags4, flags5, flags6, flags7]
 
    # Compute per-line heights for composed lines
    composed_heights = [screen.measure_text(l)[1] for l in composed_lines]
 
    # Prepare segments lists for drawing (will draw each segment and track x position)
    all_segments = [segments, segments2, segments3, segments4, segments5, segments6, segments7, segments8]

    # Column-aligned drawing: build char matrix, compute per-column widths, then draw per-character
    line_spacing = 0
    start_y = 0
    bright_brush = brushes.color(255, 255, 255)        


    dim_brush = brushes.color(64, 64, 64)

    # Build character matrix (preserve segment spacing)
    char_matrix = []
    max_line_len = 0
    for line_segs in all_segments:
        chars = ""
        flags = []
        for text, flag in line_segs:
            chars += text
            flags.extend([flag] * len(text))
        char_matrix.append((chars, flags))
        if len(chars) > max_line_len:
            max_line_len = len(chars)

    # Compute max width per column (use space for missing chars)
    col_widths = [0] * max_line_len
    for col in range(max_line_len):
        max_w = 0
        for chars, _ in char_matrix:
            ch = chars[col] if col < len(chars) else " "
            w, _ = screen.measure_text(ch)
            if w > max_w:
                max_w = w
        col_widths[col] = max_w

    # Compute cumulative x for each column
    col_x = [0] * max_line_len
    x_acc = 0
    for col, w in enumerate(col_widths):
        col_x[col] = x_acc
        x_acc += w

    # Draw each line's characters at column x positions (center each glyph in its column)
    y = start_y
    for line_idx, (chars, flags) in enumerate(char_matrix):
        for col in range(len(chars)):
            ch = chars[col]
            if ch == " ":
                continue
            char_w, _ = screen.measure_text(ch)
            offset = int((col_widths[col] - char_w) / 2)
            draw_x = col_x[col] + offset
            screen.brush = bright_brush if flags[col] else dim_brush
            screen.text(ch, draw_x, y)
        h = composed_heights[line_idx] if line_idx < len(composed_heights) else screen.measure_text("A")[1]
        y += h + line_spacing

    return None









    # Get current time and set word booleans (commented out for testing)
    # now = time.localtime()
    # set_time_words(now[3], now[4])
    #print(hourTest , minuteTest)
    #set_time_words(hourTest, minuteTest)
    #minuteTest +=1
    #if (minuteTest >= 60):
    #    minuteTest = 0
    #    hourTest +=1
    #    if (hourTest >12):
    #        hourTest =1 
    #time.sleep(.5)
    

    # Load a cool font
    # font = PixelFont.load("/system/assets/fonts/awesome.ppf")
    
    # Set up very dim gray text by default (will override per-segment)
    # screen.brush = brushes.color(64, 64, 64)
    # screen.font = font
    
    # Build segments for the first line (text, boolean_flag)

