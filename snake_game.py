import pygame
import sys
import random

# Initialize Pygame
pygame.init()

# Constants
WINDOW_WIDTH = 600
WINDOW_HEIGHT = 600
GRID_SIZE = 20  # Size of each grid square
GRID_WIDTH = WINDOW_WIDTH // GRID_SIZE
GRID_HEIGHT = WINDOW_HEIGHT // GRID_SIZE

# Colors (R, G, B)
WHITE = (255, 255, 255)
GRAY = (100, 100, 100)
BLACK = (0, 0, 0)
RED = (220, 20, 60)
GREEN = (0, 255, 0)

# Directions
UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)

# Set up display
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption('Snake Game')
clock = pygame.time.Clock()
font = pygame.font.SysFont('Arial', 25)

def draw_grid():
    """Draws grid lines on the screen."""
    for x in range(0, WINDOW_WIDTH, GRID_SIZE):
        pygame.draw.line(screen, GRAY, (x, 0), (x, WINDOW_HEIGHT))
    for y in range(0, WINDOW_HEIGHT, GRID_SIZE):
        pygame.draw.line(screen, GRAY, (0, y), (WINDOW_WIDTH, y))

def draw_snake(snake_positions):
    """Draws the snake on the screen."""
    for pos in snake_positions:
        rect = pygame.Rect(pos[0], pos[1], GRID_SIZE, GRID_SIZE)
        pygame.draw.rect(screen, GREEN, rect)

def draw_food(position):
    """Draws the food on the screen."""
    rect = pygame.Rect(position[0], position[1], GRID_SIZE, GRID_SIZE)
    pygame.draw.rect(screen, RED, rect)

def generate_food(snake_positions):
    """Generates a new food position not occupied by the snake."""
    while True:
        x = random.randrange(0, GRID_WIDTH) * GRID_SIZE
        y = random.randrange(0, GRID_HEIGHT) * GRID_SIZE
        food_position = (x, y)
        if food_position not in snake_positions:
            return food_position

def show_score(score):
    """Displays the current score on the screen."""
    score_surf = font.render(f"Score: {score}", True, BLACK)
    screen.blit(score_surf, (10, 10))

def game_over_screen(final_score):
    """Displays the game over screen with the final score."""
    game_over_font = pygame.font.SysFont('Arial', 50)
    game_over_surf = game_over_font.render("GAME OVER", True, RED)
    final_score_surf = font.render(f"Final Score: {final_score}", True, BLACK)
    screen.blit(game_over_surf, (WINDOW_WIDTH // 2 - game_over_surf.get_width() // 2,
                                 WINDOW_HEIGHT // 2 - game_over_surf.get_height()))
    screen.blit(final_score_surf, (WINDOW_WIDTH // 2 - final_score_surf.get_width() // 2,
                                   WINDOW_HEIGHT // 2 + final_score_surf.get_height()))
    pygame.display.flip()
    pygame.time.wait(3000)

def main():
    # Initial snake settings
    snake_positions = [(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2)]
    direction = random.choice([UP, DOWN, LEFT, RIGHT])
    score = 0

    # Generate initial food position
    food_position = generate_food(snake_positions)

    # Game loop
    while True:
        # Event handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            # Controls
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP and direction != DOWN:
                    direction = UP
                elif event.key == pygame.K_DOWN and direction != UP:
                    direction = DOWN
                elif event.key == pygame.K_LEFT and direction != RIGHT:
                    direction = LEFT
                elif event.key == pygame.K_RIGHT and direction != LEFT:
                    direction = RIGHT

        # Move snake
        x, y = snake_positions[0]
        dx, dy = direction
        new_head = ((x + dx * GRID_SIZE) % WINDOW_WIDTH, (y + dy * GRID_SIZE) % WINDOW_HEIGHT)

        # Check collisions
        if new_head in snake_positions:
            game_over_screen(score)
            main()  # Restart the game
            return

        snake_positions = [new_head] + snake_positions[:-1]

        # Check if snake ate the food
        if new_head == food_position:
            snake_positions.append(snake_positions[-1])
            score += 1
            food_position = generate_food(snake_positions)

        # Drawing
        screen.fill(WHITE)
        draw_grid()
        draw_snake(snake_positions)
        draw_food(food_position)
        show_score(score)
        pygame.display.flip()
        clock.tick(10)  # Control the game speed

if __name__ == "__main__":
    main()