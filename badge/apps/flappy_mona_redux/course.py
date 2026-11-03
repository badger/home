import random

from fish import HEIGHT as FISH_HEIGHT
from fish import WIDTH as FISH_WIDTH
from fish import Fish
from obstacle import GAP, TILE, Obstacle
from tower import LAYOUTS, WALL, Tower
from world import SPEED
from world import WIDTH as SCREEN_WIDTH

FIRST_SPAWN = 0.5  # seconds until the first wall
SPAWN_EVERY = 1.5  # seconds between walls
FIRST_FISH = 3  # the third plain wall carries the first fish
FISH_EVERY = (4, 7)  # then one fish every 4 to 7 plain walls
FISH_MARGIN = 14  # keeps fish off the spikes
FISH_SPACING = 3  # a wall fish never comes sooner than this many walls after a tower's fish
TOWER_ORDER = ("roof", "steps", "hill", "steps")  # the roof opens the game, then the order repeats
TOWER_EVERY = (3, 5)  # plain walls between towers (never fewer than 3, or two towers would overlap)
TOWER_CLEARANCE = 150  # clear space before and after a tower
TOWER_LEAD = (TOWER_CLEARANCE + TILE) / SPEED - SPAWN_EVERY  # extra wait so the last wall clears a tower


class Course:
    def __init__(self):
        self.obstacles = []
        self.fish = []
        self.tower = None
        self.holding = False  # plain walls wait while a tower crosses the screen
        self.spawn_in = FIRST_SPAWN
        self.fish_in = FIRST_FISH
        self.walls_to_tower = 0  # plain walls left before the next tower, which opens the game
        self.towers = 0

    def spawn(self):
        if self.walls_to_tower <= 0:
            self.spawn_tower()
        else:
            self.spawn_wall()

    def spawn_tower(self):
        self.tower = Tower(LAYOUTS[TOWER_ORDER[self.towers % len(TOWER_ORDER)]])
        self.towers += 1
        self.holding = True
        self.walls_to_tower = random.randint(TOWER_EVERY[0], TOWER_EVERY[1])
        fish = self.tower.make_fish()
        if fish:
            self.fish.extend(fish)
            self.fish_in = max(self.fish_in, FISH_SPACING)

    def spawn_wall(self):
        obstacle = Obstacle()
        self.obstacles.append(obstacle)

        self.walls_to_tower -= 1
        if self.walls_to_tower <= 0:
            self.spawn_in += TOWER_LEAD

        self.fish_in -= 1
        if self.fish_in <= 0:
            self.fish_in = random.randint(FISH_EVERY[0], FISH_EVERY[1])
            low = obstacle.gap_y + FISH_MARGIN
            high = obstacle.gap_y + GAP - FISH_HEIGHT - FISH_MARGIN
            self.fish.append(Fish(obstacle.x + (TILE - FISH_WIDTH) / 2, random.randint(low, high)))

    def update(self, dt):
        if self.holding and self.tower.right_end() <= SCREEN_WIDTH - TOWER_CLEARANCE:
            self.holding = False
            self.spawn_in = 0.0
        if not self.holding:
            self.spawn_in -= dt
            if self.spawn_in <= 0:
                self.spawn_in += SPAWN_EVERY
                self.spawn()

        if self.tower is not None:
            self.tower.update(dt)
            if self.tower.right_end() <= 0:
                self.tower = None
        for obstacle in self.obstacles:
            obstacle.update(dt)
        for fish in self.fish:
            fish.update(dt)

        self.obstacles = [o for o in self.obstacles if o.x > -TILE]
        self.fish = [f for f in self.fish if f.x > -FISH_WIDTH]

    def hits(self, box, hazard):
        """What Mona ran into, if anything: WALL, SPIKE or ROLLER."""
        for obstacle in self.obstacles:
            if obstacle.hits(box):
                return WALL
        if self.tower is not None:
            return self.tower.hits(box, hazard)
        return None

    def take_fish(self, box):
        for fish in self.fish:
            if fish.touches(box):
                self.fish.remove(fish)
                return fish
        return None

    def count_passed(self, x):
        count = 0
        for obstacle in self.obstacles:
            if not obstacle.passed and obstacle.x < x:
                obstacle.passed = True
                count += 1
        tower = self.tower
        if tower is not None and not tower.passed and tower.right_end() < x:
            tower.passed = True
            count += 1
        return count

    def draw(self, cam=0):
        if self.tower is not None:
            self.tower.draw(cam)
        for obstacle in self.obstacles:
            obstacle.draw(cam)
        for fish in self.fish:
            fish.draw(cam)
