from micropython import const
import badger2040
from badger2040 import UPDATE_NORMAL, UPDATE_MEDIUM, UPDATE_FAST, UPDATE_TURBO, BUTTON_A, BUTTON_B, BUTTON_C, BUTTON_DOWN, BUTTON_UP, WIDTH, HEIGHT
from time import sleep
import random
import gc

# **SCREEN IS USED IN PORTRAIT**

C = const

HALF_W = C(int(WIDTH/2))
HALF_H = C(int(HEIGHT/2))

CELL_SIDE = C(23)    # Num of px tall and wide
CELL_SPACING = C(3)  # Vert. and horiz. spacing between cell borders in the grid
# Top left of the grid
GRID_ORIGIN_X = C(int(HALF_W - (CELL_SIDE*3 + CELL_SPACING*2.5)))
GRID_ORIGIN_Y = C(int(HALF_H - (CELL_SIDE*2.5 + CELL_SPACING*2)))

CELL_FONT = C("serif")
CELL_FONT_SCALE = C(0.8)
HEADER_FONT = C("sans")

LETTERS = C("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

# Grid data
grid = [[""]*5] * 6

display = badger2040.Badger2040()

### Functions ###

def select_word():
    # There are 2,309 winner words
    idx = random.randint(0, 2309)
    f = open("/examples/winners.txt", "r")
    f.seek(idx * 5)
    winner_word = f.read(5)
    f.close()
    gc.collect()
    return winner_word.upper()

all_words = open("/examples/all_words.txt", "r")

def valid_word(word):
    word = word.lower()
    all_words.seek(0)
    # Binary search through file
    lo = 0
    hi = 12972 # 12,972 words in the file
    while lo < hi:
        mid = (lo + hi) // 2
        all_words.seek(mid * 5)
        if all_words.read(5) < word: # 5 letter words
            lo = mid + 1
        else:
            hi = mid
    
    # lo is the index of the closest match
    all_words.seek(lo * 5)
    return all_words.read(5) == word

def conv_grid_coords(x, y):
    """Converts portrait grid coords into landscape grid coords"""

    return 5-y, x


def draw_cell(x, y, outline, fill, text, char):
    x, y = conv_grid_coords(x, y)
    # Top left of this cell
    org_x = GRID_ORIGIN_X + CELL_SIDE*x + CELL_SPACING*x
    org_y = GRID_ORIGIN_Y + CELL_SIDE*y + CELL_SPACING*y
    # Fill block
    display.set_pen(fill)
    display.rectangle(org_x, org_y, CELL_SIDE+1, CELL_SIDE+1) # +1 because rectangle width/height isn't inclusive
    # Draw outline if needed
    if outline != fill:
        display.set_pen(outline)
        side = CELL_SIDE + 1 # Used a lot below, since line() doesn't go to the final point
        display.line(org_x, org_y, org_x+side, org_y) # Top
        display.line(org_x, org_y+side-1, org_x+side, org_y+side-1) # Bottom
        display.line(org_x, org_y, org_x, org_y+side) # Left
        display.line(org_x+side-1, org_y, org_x+side-1, org_y+side) # Right
    # Draw letter if needed
    if char:
        display.set_font(CELL_FONT)
        display.set_pen(text)
        display.text(
            char,
            org_x+int(CELL_SIDE/2)-1,
            org_y+int((CELL_SIDE-display.measure_text(char, CELL_FONT_SCALE))/2),
            scale=CELL_FONT_SCALE,
            angle=90
        )

# Cell Style:
#     Empty cell: black outline, white fill
#     Correct cell: black outline, white fill, black letter
#     Yellow cell: black outline (?), grey fill, white letter
#     Wrong cell: black outline, black fill, white letter
#     Unsubmitted cell: black outline, white fill, black letter

def draw_grid():
    for y in range(6):
        for x in range(5):
            char = grid[y][x]
            if char == "":
                # Empty
                draw_cell(x, y, 0, 15, 0, char)
            elif char == WORD[x]:
                # Correct
                draw_cell(x, y, 0, 15, 0, char)
            elif char in WORD:
                # In word but wrong place
                draw_cell(x, y, 0, 9, 0, char)
            elif char not in WORD:
                draw_cell(x, y, 0, 0, 15, char)


### Main code ###

WORD = select_word()
print(WORD)

#if not DEBUG:
    # Start-up screen
    #display.set_update_speed(UPDATE_NORMAL)
    #display.set_pen(0)
    #display.set_font(HEADER_FONT)
    #display.text("Wordle", HALF_W+20, HALF_H-51, angle=90)
    #display.text("by makeworld", HALF_W-20, HALF_H-29, scale=0.5, angle=90)
    #display.update()
    #sleep(3)

# Initial screen
display.set_update_speed(UPDATE_NORMAL)
display.set_pen(15)
display.clear()
display.set_pen(0)
display.set_font(HEADER_FONT)
display.text("Wordle", WIDTH-35, HALF_H-51, scale=1, angle=90)
draw_grid()
display.update()

### Letter selection ###

# Position on grid
pos_x = 0
pos_y = 0

# Letters to be submitted
# Ex: ["C", "R", "A", "", ""]
row = [""] * 5
row_char_idx = [-1] * 5 # Index in LETTERS

display.set_update_speed(UPDATE_TURBO)

while True:
    if display.pressed(BUTTON_B):
        # Next letter
        row_char_idx[pos_x] = (row_char_idx[pos_x]+1) % 26
        row[pos_x] = LETTERS[row_char_idx[pos_x]]
    elif display.pressed(BUTTON_C):
        # Prev letter
        if row_char_idx[pos_x] == -1:
            # First time in the cell, set to Z
            # Otherwise (-1-1)%26 will set it to Y
            row_char_idx[pos_x] = 25
        else:
            row_char_idx[pos_x] = (row_char_idx[pos_x]-1) % 26
        row[pos_x] = LETTERS[row_char_idx[pos_x]]
    elif display.pressed(BUTTON_A):
        # Submit row
        
        if row[pos_x] == "":
            # Row isn't finished
            sleep(0.2) # Debounce
            continue
        
        if not valid_word("".join(row)):
            sleep(0.2) # Debounce
            continue
        
        # Submit to grid
        grid[pos_y] = row
        # Move to new row
        pos_y += 1
        pos_x = 0
        # Reset data for row
        row = [""] * 5
        row_char_idx = [-1] * 5
        # Draw grid
        display.set_update_speed(UPDATE_FAST)
        draw_grid()
        
        # Is the game over?
        if pos_y == 6 or "".join(grid[pos_y-1]) == WORD:
            pos_y -= 1 # Allow usage of pos_y in end game code
            break    
    elif display.pressed(BUTTON_UP):
        # Delete letter
        # Erase current letter
        draw_cell(pos_x, pos_y, 0, 15, 0, "")
        # Reset data for current letter
        row[pos_x] = ""
        row_char_idx[pos_x] = -1
        # Update position
        pos_x = max(0, pos_x-1)
        display.set_update_speed(UPDATE_FAST) # Better update
    elif display.pressed(BUTTON_DOWN) and row[pos_x] != "":
        # Next letter
        pos_x = min(pos_x+1, 4)
        display.set_update_speed(UPDATE_FAST) # Better update
    else:
        # No button pressed, so check buttons again without updating screen
        continue
    
    # A button was pressed, so draw
    draw_cell(pos_x, pos_y, 0, 15, 0, row[pos_x])
    display.update()
    display.set_update_speed(UPDATE_TURBO) # Reset update speed in case it was changed


# End game screen

display.set_pen(0)
display.set_font(HEADER_FONT)

if "".join(grid[pos_y]) == WORD:
    # Won
    display.text("You won!", 30, HALF_H-55, angle=90, scale=0.8)
else:
    # Lost
    display.text(WORD, 30, int(HALF_H-display.measure_text(WORD)/2), angle=90)

display.update()


