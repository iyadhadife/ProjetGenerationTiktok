import pygame, sys, math
from pygame.locals import *
import random 

center = (150, 150)

class Ball:
    def __init__(self, x_pos, y_pos, radius, color, mass=1, restitution=0.9, x_speed=0, y_speed=0, gravity=0.5):
        self.x = float(x_pos)
        self.y = float(y_pos)
        self.r = radius
        self.color = color
        self.mass = mass
        self.rest = restitution
        self.vx = x_speed
        self.vy = y_speed
        self.g = gravity

    def apply_gravity(self):
        self.vy += self.g * self.mass # accélère la vitesse verticale

    def move(self):
        self.x += self.vx
        self.y += self.vy

    def check_collision_circle(self, center, radius):
        BOUNCESTOP = 0.1
        dx = self.x - center[0]
        dy = self.y - center[1]
        dist = math.hypot(dx, dy)
        if dist + self.r > radius:
            # vecteur normal
            nx, ny = dx / dist, dy / dist
            dot = self.vx * nx + self.vy * ny
            # réflexion amortie
            self.vx -= 2 * dot * nx * self.rest
            self.vy -= 2 * dot * ny * self.rest
        else:
            if self.vy > BOUNCESTOP:
                self.vy = self.vy*-1*self.rest
            else:
                self.vy = 0
        
    def draw(self, surface):
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.r)
