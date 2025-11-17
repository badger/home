# 2048

The classic 2048 sliding tile puzzle game for the GitHub Universe 2025 Badge.

## Controls

- **A** - Move tiles left
- **C** - Move tiles right
- **UP** - Move tiles up
- **DOWN** - Move tiles down
- **B** - Start new game (when game over)
- **HOME** - Return to menu

## How to Play

The goal is to slide numbered tiles on a 4×4 grid to combine them and create a tile with the number 2048.

1. Use the directional controls to slide all tiles in that direction
2. When two tiles with the same number touch, they merge into one tile with their sum
3. After each move, a new tile (2 or 4) appears in a random empty spot
4. The game is won when a tile with 2048 is created
5. The game is lost when no more moves are possible

## Features

- **GitHub-themed colors** - Beautiful gradient from GitHub's design system
- **Score tracking** - Keep track of your current score
- **Best score persistence** - Your high score is saved between games
- **Win detection** - Celebrate when you reach 2048!
- **Continue playing** - Keep going after 2048 to reach higher tiles

## Scoring

Each time two tiles merge, you earn points equal to the value of the new tile. For example:
- Merging two 2s = 4 points
- Merging two 4s = 8 points
- Merging two 64s = 128 points
- And so on...

## Strategy Tips

- Keep your highest tile in a corner
- Build tiles in a consistent direction
- Don't just randomly swipe - plan ahead!
- Always maintain a path to merge tiles

Good luck reaching 2048!
