import pygame
import math
from Ball import Ball
class Wall:
    def __init__(self, x, y, rayon):
        self.x = x
        self.y = y
        self.rayon = rayon

    def draw(self, surface):
        pygame.draw.circle(surface, (0, 100, 255), (self.x, self.y), self.rayon, 1)

    def ball_collision(self, ball):
        if isinstance(ball, Ball):
            # Check for collision with the ball
            dx = ball.x - self.x
            dy = ball.y - self.y
            distance = math.hypot(dx, dy)
            if distance <= ball.r + self.rayon:
                # Collision detected, resolve it
                overlap = ball.r + self.rayon - distance
                # Move the ball out of the wall
                ball.x += dx / distance * overlap
                ball.y += dy / distance * overlap
                # Reflect the ball's velocity
                ball.vx = -ball.vx * ball.rest
                ball.vy = -ball.vy * ball.rest
