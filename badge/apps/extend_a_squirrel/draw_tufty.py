import math
import sys
import os

sys.path.insert(0, "/system/apps/extend_a_squirrel")
os.chdir("/system/apps/extend_a_squirrel")

small_font = font.nope
very_small_font = font.sins

screen.antialias = image.X2

sqirl = image.load("assets/sqirl.png").spritesheet(20, 1)
acorn10 = image.load("assets/acorn10.png")
acorn15 = image.load("assets/acorn15.png")
acorn_multi = image.load("assets/acorn_multi.png")
background = image.load("assets/bg.png")


def center_text(text, y):
    w, _ = screen.measure_text(text)
    screen.text(text, (screen.width // 2) - (w / 2), y)


class Renderer:
    def __init__(self):
        # Setting the basics of the grid.
        self.HEIGHT = 108
        self.WIDTH = 160

        # Dictionary to translate grid level to grid dimensions.
        self.grids = {
            1: 7,
            2: 10,
            3: 14,
            4: 19,
            5: 24
        }

        # Initialising how many cells and where to put them on screen.
        # This gets overwritten for actual gameplay by values passed in from the game settings.
        self.GRIDLEVEL = 1
        self.Y_CELLS = self.grids[self.GRIDLEVEL]
        self.CELL_SIZE = math.floor(self.HEIGHT / self.Y_CELLS)
        self.X_CELLS = math.floor(self.WIDTH / self.CELL_SIZE)
        self.X_OFFSET = math.floor((self.WIDTH - (self.X_CELLS * self.CELL_SIZE)) / 2)
        self.Y_OFFSET = math.floor((self.HEIGHT - (self.Y_CELLS * self.CELL_SIZE)) / 2)

    # These two methods simply translate grid square coordinates to pixel coordinates on the screen.
    def grid_to_screen_x(self, pos):
        return (pos * self.CELL_SIZE) + self.X_OFFSET

    def grid_to_screen_y(self, pos):
        return (pos * self.CELL_SIZE) + self.Y_OFFSET

    # Given a queried cell and its neighbour, returns an int representing where the neighbour is in relation.
    # 0 = N, 1 = E, 2 = S, 3 = W
    def get_neighbour(self, current_cell_x, current_cell_y, neighbour_cell_x, neighbour_cell_y):
        if neighbour_cell_x == current_cell_x - 1:
            return 3
        if neighbour_cell_x == current_cell_x + 1:
            return 1
        if neighbour_cell_x == 0 and current_cell_x == self.X_CELLS - 1:  # Edge cases - literally. This and the next case deal with when you cross the edges of the playfield.
            return 1
        if neighbour_cell_x == self.X_CELLS - 1 and current_cell_x == 0:
            return 3
        if neighbour_cell_y == current_cell_y - 1:
            return 0
        if neighbour_cell_y == current_cell_y + 1:
            return 2
        if neighbour_cell_y == 0 and current_cell_y == self.Y_CELLS - 1:  # See previous edge case.
            return 2
        if neighbour_cell_y == self.Y_CELLS - 1 and current_cell_y == 0:
            return 0

        return 0  # you shouldn't be able to get here, if both the x and y are the same as yours then it's your square

    # Returns the index of the correct sprite for a tail segment.
    def get_orientation(self, snake, index):

        this_segment = snake.body[index]
        this_x = this_segment[0]
        this_y = this_segment[1]

        # If it's the first tail segment, the previous position is the position of the head.
        # Otherwise, it's the previous tail segment in the list.
        if index == 0:
            prev_segment = snake.lastpos
        else:
            prev_segment = snake.body[index - 1]

        prev_x = prev_segment[0]
        prev_y = prev_segment[1]

        # Use get_neighbour to figure out where the previous segment is...
        prev_coord = self.get_neighbour(this_x, this_y, prev_x, prev_y)

        # ... and use that value to look up the right sprite.
        # If it's the last segment that's easy:
        if index == len(snake.body) - 1:
            if prev_coord == 0:
                return 16
            if prev_coord == 1:
                return 17
            if prev_coord == 2:
                return 18
            if prev_coord == 3:
                return 19

        # Otherwise we have to do the same for the next tail segment:
        else:
            next_segment = snake.body[index + 1]

            next_x = next_segment[0]
            next_y = next_segment[1]

            next_coord = self.get_neighbour(this_x, this_y, next_x, next_y)

            # And then pick from the 12 different combinations of the tail entering and exiting the cell.
            # 4 different entry points, 3 different exit points (as it's game over if you enter and exit the same side).
            if prev_coord == 0:
                if next_coord == 2:
                    return 4
                if next_coord == 1:
                    return 8
                if next_coord == 3:
                    return 15
            elif prev_coord == 1:
                if next_coord == 3:
                    return 5
                if next_coord == 2:
                    return 9
                if next_coord == 0:
                    return 12
            elif prev_coord == 2:
                if next_coord == 0:
                    return 6
                if next_coord == 3:
                    return 10
                if next_coord == 1:
                    return 13
            else:
                if next_coord == 1:
                    return 7
                if next_coord == 0:
                    return 11
                if next_coord == 2:
                    return 14

        return 0

    # Drawing the intro is easy, we're just placing text and images.
    def draw_intro(self, game_speed, gridsize):
        bg = image.load("assets/title.png")
        screen.blit(bg, vec2(0, 0))

        self.GRIDLEVEL = gridsize
        self.Y_CELLS = self.grids[self.GRIDLEVEL]
        self.CELL_SIZE = math.floor(self.HEIGHT / self.Y_CELLS)
        self.X_CELLS = math.floor(self.WIDTH / self.CELL_SIZE)
        self.X_OFFSET = math.floor((self.WIDTH - (self.X_CELLS * self.CELL_SIZE)) / 2)
        self.Y_OFFSET = math.floor((self.HEIGHT - (self.Y_CELLS * self.CELL_SIZE)) / 2)

        screen.pen = color.white

        if int(badge.ticks / 500) % 2:
            screen.font = small_font
            center_text("Press SELECT to start", 10)

        screen.font = very_small_font
        center_text(f"A/C to change speed ({game_speed})", 25)
        center_text(f"U/D to change grid size ({gridsize})", 35)

    # Drawing the playfield isn't much harder.
    def draw_play(self, snake, apple, score):
        # Setting the screen to black, then making a rectangle for the actual playfield.
        screen.pen = color.rgb(0, 0, 0)
        screen.clear()
        screen.blit(background, vec2(0, 0))
        screen.pen = color.rgb(0, 0, 0, 128)
        screen.shape(shape.rectangle(self.X_OFFSET, self.Y_OFFSET, self.X_CELLS * self.CELL_SIZE, self.Y_CELLS * self.CELL_SIZE))

        # First draw the snake's head, the direction also picks the sprite index
        head_dir = 0
        if snake.direction == 0:
            head_dir = 0
        if snake.direction == 1:
            head_dir = 1
        if snake.direction == 2:
            head_dir = 2
        if snake.direction == 3:
            head_dir = 3
        snake_head = sqirl.sprite(head_dir, 0)
        screen.blit(snake_head, rect(self.grid_to_screen_x(snake.x), self.grid_to_screen_y(snake.y), self.CELL_SIZE, self.CELL_SIZE))

        # Then we loop through the body, using get_orientation to pick a sprite and then draw it
        for i in range(len(snake.body)):
            segment = snake.body[i]
            sprite_index = self.get_orientation(snake, i)
            snake_body = sqirl.sprite(sprite_index, 0)
            screen.blit(snake_body, rect(self.grid_to_screen_x(segment[0]), self.grid_to_screen_y(segment[1]), self.CELL_SIZE, self.CELL_SIZE))

        # Draw the apple.
        screen.blit(acorn15, rect(self.grid_to_screen_x(apple.x), self.grid_to_screen_y(apple.y), self.CELL_SIZE, self.CELL_SIZE))

        # Draw the score. This involves two loops,
        # since every ten points we want to smoosh them into a "tens" icon.
        # scoreX is the pixel coordinate to draw the icon, it gets incremented with each icon we draw
        # whether that's a ten or a one icon.
        scoreX = 0
        score_tens = math.floor(score / 10)
        score_units = score % 10

        if score_tens > 0:
            for _ in range(score_tens):
                screen.blit(acorn_multi, vec2(scoreX, 109))
                scoreX += 11

        if score_units > 0:
            for _ in range(score_units):
                screen.blit(acorn10, vec2(scoreX, 109))
                scoreX += 11

    # Drawing the game over screen is again just images and text like the intro screen.
    def draw_gameover(self):

        bg = image.load("assets/gameover.png")
        screen.blit(bg, vec2(0, 0))

        screen.pen = color.white

        if int(badge.ticks / 500) % 2:
            screen.font = small_font
            center_text("Press SELECT to play again", screen.height - 20)
