import pygame
import math
from Ball import Ball
class Wall:
    def __init__(self, x, y, radius):
        self.x = x
        self.y = y
        self.radius = radius

    def draw(self, surface):
        pygame.draw.circle(surface, (0, 100, 255), (self.x, self.y), self.radius, 1)
