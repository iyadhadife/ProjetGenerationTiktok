import pygame
import math
center = (150, 150)

class Ball:
    def __init__(self, x_pos, y_pos, radius, color, mass, retention, y_speed, x_speed, id):
        self.x_pos = x_pos
        self.y_pos = y_pos
        self.radius = radius
        self.color = color
        self.mass = mass
        self.retention = retention
        self.y_speed = y_speed
        self.x_speed = x_speed
        self.id = id
        self.circle = ''

    def move(self, dx, dy):
        self.x += dx
        self.y += dy

    def draw(self, surface):
        self.circle = pygame.draw.circle(surface, self.color, (self.x_pos, self.y_pos), self.radius)
    
    def check_gravity(self,dist_center_floor):
        dx = self.x_pos - center[0]
        dy = self.y_pos - center[1]
        dist = math.sqrt(dx*dx + dy*dy)
        if abs(self.y_pos - dist_center_floor) <= self.radius:
            self.x_speed+=-1*self.x_speed*self.retention
            self.y_speed+=-1*self.y_speed*self.retention
        else:
            self.y_speed+=9.81*self.mass
