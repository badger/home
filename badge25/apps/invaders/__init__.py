import sys
import os
import random

sys.path.insert(0, "/system/apps/invaders")
os.chdir("/system/apps/invaders")

from badgeware import screen, PixelFont, io, brushes, shapes, run

large_font = PixelFont.load("/system/assets/fonts/ziplock.ppf")
small_font = PixelFont.load("/system/assets/fonts/nope.ppf")


class GameState:
    INTRO = 1
    PLAYING = 2
    GAME_OVER = 3


class Player:
    def __init__(self):
        self.x = 70
        self.y = 105
        self.width = 12
        self.height = 8
        self.speed = 2
        self.shoot_cooldown = 0
        
    def move_left(self):
        self.x = max(5, self.x - self.speed)
    
    def move_right(self):
        self.x = min(screen.width - self.width - 5, self.x + self.speed)
    
    def can_shoot(self):
        return self.shoot_cooldown <= 0
    
    def shoot(self):
        if self.can_shoot():
            bullets.append(Bullet(self.x + self.width // 2, self.y - 2, -3))
            self.shoot_cooldown = 15
    
    def update(self):
        if self.shoot_cooldown > 0:
            self.shoot_cooldown -= 1
    
    def draw(self):
        # Draw player ship (simple triangle/spaceship)
        screen.brush = brushes.color(100, 255, 100)
        # Body
        screen.draw(shapes.rectangle(self.x + 3, self.y + 2, 6, 6))
        # Cockpit
        screen.brush = brushes.color(150, 255, 150)
        screen.draw(shapes.rectangle(self.x + 4, self.y + 3, 4, 3))
        # Wings
        screen.brush = brushes.color(80, 200, 80)
        screen.draw(shapes.rectangle(self.x, self.y + 5, 3, 3))
        screen.draw(shapes.rectangle(self.x + 9, self.y + 5, 3, 3))


class Alien:
    def __init__(self, x, y, alien_type=0):
        self.x = x
        self.y = y
        self.width = 10
        self.height = 8
        self.alive = True
        self.alien_type = alien_type
        
    def draw(self):
        if not self.alive:
            return
        
        # Animate aliens (2 frames)
        anim_frame = (io.ticks // 500) % 2
        
        # Different colors for different alien types
        if self.alien_type == 0:
            color = (255, 50, 50)  # Red
        elif self.alien_type == 1:
            color = (255, 150, 50)  # Orange
        else:
            color = (255, 255, 50)  # Yellow
            
        screen.brush = brushes.color(*color)
        
        # Body
        screen.draw(shapes.rectangle(self.x + 1, self.y + 2, 8, 4))
        # Eyes (animated)
        screen.brush = brushes.color(255, 255, 255)
        if anim_frame == 0:
            screen.draw(shapes.rectangle(self.x + 2, self.y + 3, 2, 2))
            screen.draw(shapes.rectangle(self.x + 6, self.y + 3, 2, 2))
        else:
            screen.draw(shapes.rectangle(self.x + 2, self.y + 4, 2, 1))
            screen.draw(shapes.rectangle(self.x + 6, self.y + 4, 2, 1))
        
        # Antennae
        screen.brush = brushes.color(*color)
        screen.draw(shapes.rectangle(self.x + 1, self.y, 2, 2))
        screen.draw(shapes.rectangle(self.x + 7, self.y, 2, 2))
    
    def bounds(self):
        return (self.x, self.y, self.width, self.height)


class Bullet:
    def __init__(self, x, y, dy):
        self.x = x
        self.y = y
        self.dy = dy  # negative for player bullets, positive for alien bullets
        self.active = True
        
    def update(self):
        self.y += self.dy
        if self.y < 0 or self.y > screen.height:
            self.active = False
    
    def draw(self):
        if self.active:
            if self.dy < 0:  # Player bullet
                screen.brush = brushes.color(150, 255, 255)
            else:  # Alien bullet
                screen.brush = brushes.color(255, 100, 100)
            screen.draw(shapes.rectangle(self.x, self.y, 2, 4))
    
    def bounds(self):
        return (self.x, self.y, 2, 4)


class Shield:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.width = 16
        self.height = 10
        # Create a 2D grid of blocks (1 = intact, 0 = destroyed)
        # Shield shape (classic space invaders shield)
        pattern = [
            [1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1],
            [1, 0, 0, 0, 1],
        ]
        self.blocks = pattern
        self.block_width = self.width // 5
        self.block_height = self.height // 4
    
    def draw(self):
        screen.brush = brushes.color(50, 200, 50)
        for row in range(len(self.blocks)):
            for col in range(len(self.blocks[row])):
                if self.blocks[row][col] == 1:
                    bx = self.x + col * self.block_width
                    by = self.y + row * self.block_height
                    screen.draw(shapes.rectangle(bx, by, self.block_width, self.block_height))
    
    def hit(self, bullet_bounds):
        """Check if bullet hits shield and damage it"""
        bx, by, bw, bh = bullet_bounds
        
        for row in range(len(self.blocks)):
            for col in range(len(self.blocks[row])):
                if self.blocks[row][col] == 1:
                    block_x = self.x + col * self.block_width
                    block_y = self.y + row * self.block_height
                    
                    if check_collision(bullet_bounds, 
                                     (block_x, block_y, self.block_width, self.block_height)):
                        self.blocks[row][col] = 0
                        return True
        return False


# Game variables
state = GameState.INTRO
player = None
aliens = []
bullets = []
shields = []
score = 0
wave = 1
alien_move_direction = 1
alien_move_timer = 0
alien_move_speed = 30
alien_shoot_timer = 0


def init_game():
    global player, aliens, bullets, shields, score, wave, alien_move_direction, alien_move_speed
    player = Player()
    aliens = []
    bullets = []
    shields = []
    score = 0
    wave = 1
    alien_move_direction = 1
    alien_move_speed = 30
    spawn_aliens()
    spawn_shields()


def spawn_aliens():
    global aliens
    aliens = []
    
    # Create rows of aliens
    for row in range(4):
        for col in range(8):
            alien_type = min(row, 2)  # 0, 1, or 2
            x = 15 + col * 16
            y = 15 + row * 12
            aliens.append(Alien(x, y, alien_type))


def spawn_shields():
    global shields
    shields = []
    
    # Create 4 shields
    shield_y = 88
    spacing = 37
    for i in range(4):
        x = 12 + i * spacing
        shields.append(Shield(x, shield_y))


def update():
    draw_background()
    
    if state == GameState.INTRO:
        intro()
    elif state == GameState.PLAYING:
        play()
    elif state == GameState.GAME_OVER:
        game_over()


def intro():
    global state
    
    # Draw title
    screen.font = large_font
    center_text("INVADERS", 30)
    
    # Draw some example aliens
    example_alien = Alien(50, 50, 0)
    example_alien.draw()
    example_alien2 = Alien(70, 50, 1)
    example_alien2.draw()
    example_alien3 = Alien(90, 50, 2)
    example_alien3.draw()
    
    # Blink button message
    if int(io.ticks / 500) % 2:
        screen.font = small_font
        center_text("Press B to start", 80)
        center_text("A/C to move", 92)
        center_text("B to shoot", 100)
    
    if io.BUTTON_B in io.pressed:
        state = GameState.PLAYING
        init_game()


def play():
    global state, score, wave, alien_move_direction, alien_move_timer, alien_move_speed, alien_shoot_timer
    
    # Handle player input
    if io.BUTTON_A in io.held or io.BUTTON_UP in io.held:
        player.move_left()
    if io.BUTTON_C in io.held or io.BUTTON_DOWN in io.held:
        player.move_right()
    if io.BUTTON_B in io.pressed:
        player.shoot()
    
    player.update()
    
    # Update bullets
    for bullet in bullets[:]:
        bullet.update()
        if not bullet.active:
            bullets.remove(bullet)
    
    # Move aliens
    alien_move_timer += 1
    if alien_move_timer >= alien_move_speed:
        alien_move_timer = 0
        move_aliens()
    
    # Alien shooting
    alien_shoot_timer += 1
    if alien_shoot_timer >= 60:
        alien_shoot_timer = 0
        alien_shoot()
    
    # Check bullet-shield collisions
    for bullet in bullets[:]:
        if bullet.active:
            for shield in shields:
                if shield.hit(bullet.bounds()):
                    bullet.active = False
                    if bullet in bullets:
                        bullets.remove(bullet)
                    break
    
    # Check bullet-alien collisions
    for bullet in bullets[:]:
        if bullet.dy < 0:  # Player bullet
            for alien in aliens:
                if alien.alive and check_collision(bullet.bounds(), alien.bounds()):
                    alien.alive = False
                    bullet.active = False
                    score += (3 - alien.alien_type) * 10
                    if bullet in bullets:
                        bullets.remove(bullet)
                    break
    
    # Check bullet-player collisions
    for bullet in bullets[:]:
        if bullet.dy > 0:  # Alien bullet
            if check_collision(bullet.bounds(), (player.x, player.y, player.width, player.height)):
                state = GameState.GAME_OVER
    
    # Check if aliens reached player
    for alien in aliens:
        if alien.alive and alien.y + alien.height >= player.y:
            state = GameState.GAME_OVER
    
    # Check if all aliens defeated
    if all(not alien.alive for alien in aliens):
        wave += 1
        alien_move_speed = max(10, alien_move_speed - 3)
        spawn_aliens()
    
    # Draw everything
    for bullet in bullets:
        bullet.draw()
    
    for alien in aliens:
        alien.draw()
    
    for shield in shields:
        shield.draw()
    
    player.draw()
    
    # Draw score
    screen.font = small_font
    shadow_text(f"Score: {score}", 3, 2)
    shadow_text(f"Wave: {wave}", screen.width - 50, 2)


def move_aliens():
    global alien_move_direction
    
    # Check if any alien hit the edge
    hit_edge = False
    for alien in aliens:
        if alien.alive:
            if (alien.x <= 5 and alien_move_direction < 0) or \
               (alien.x + alien.width >= screen.width - 5 and alien_move_direction > 0):
                hit_edge = True
                break
    
    if hit_edge:
        # Move down and reverse direction
        alien_move_direction *= -1
        for alien in aliens:
            if alien.alive:
                alien.y += 4
    else:
        # Move horizontally
        for alien in aliens:
            if alien.alive:
                alien.x += alien_move_direction * 2


def alien_shoot():
    # Find bottom-most alien in a random column
    alive_aliens = [a for a in aliens if a.alive]
    if alive_aliens:
        shooter = random.choice(alive_aliens)
        bullets.append(Bullet(shooter.x + shooter.width // 2, shooter.y + shooter.height, 2))


def check_collision(bounds1, bounds2):
    x1, y1, w1, h1 = bounds1
    x2, y2, w2, h2 = bounds2
    
    return not (x1 + w1 < x2 or x2 + w2 < x1 or y1 + h1 < y2 or y2 + h2 < y1)


def game_over():
    global state
    
    # Game over caption
    screen.font = large_font
    center_text("GAME OVER!", 30)
    
    # Player's final score
    screen.font = small_font
    center_text(f"Final score: {score}", 50)
    center_text(f"Waves: {wave}", 60)
    
    # Flash button message
    if int(io.ticks / 500) % 2:
        screen.brush = brushes.color(255, 255, 255)
        center_text("Press B to restart", 80)
    
    if io.BUTTON_B in io.pressed:
        state = GameState.INTRO


def draw_background():
    # Space background
    screen.brush = brushes.color(10, 10, 30)
    screen.clear()
    
    # Draw stars
    random.seed(12345)  # Fixed seed for consistent star positions
    for _ in range(30):
        x = random.randint(0, screen.width)
        y = random.randint(0, screen.height)
        brightness = random.randint(100, 255)
        screen.brush = brushes.color(brightness, brightness, brightness)
        screen.draw(shapes.rectangle(x, y, 1, 1))


def shadow_text(text, x, y):
    screen.brush = brushes.color(20, 20, 40, 200)
    screen.text(text, x + 1, y + 1)
    screen.brush = brushes.color(255, 255, 255)
    screen.text(text, x, y)


def center_text(text, y):
    w, _ = screen.measure_text(text)
    shadow_text(text, 80 - (w / 2), y)


if __name__ == "__main__":
    run(update)


