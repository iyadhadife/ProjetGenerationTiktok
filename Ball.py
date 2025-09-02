import pygame, sys, math
from pygame.locals import *
import random 

center = (300, 300)

class Ball:
    def __init__(self, x_pos, y_pos, radius, color, mass=1, restitution=0.5, x_speed=0, y_speed=0, gravity=0.81):
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

    def check_collision_and_gravity_on_circles(self, center, radius):
        BOUNCESTOP = 0.001
        dx = self.x - center[0]
        dy = self.y - center[1]
        dist = math.hypot(dx, dy)
        if dist + self.r < radius:
            self.apply_gravity()
        else:
            if math.fabs(self.vy) > BOUNCESTOP:
                self.vx = self.vx*-1*self.rest
                self.vy = self.vy*-1*self.rest
            else:
                self.vy = 0
                self.vx = 0
        
    def draw(self, surface):
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.r)
