import pygame, sys, math
from pygame.locals import *
import random 
from collections import deque

class Ball:
    def __init__(self, x_pos, y_pos, radius, color, mass=1, restitution=0.5, x_speed=0, y_speed=0, gravity=0.81, trail_length=20, bool_trail=False):
        self.x = float(x_pos)
        self.y = float(y_pos)
        self.r = radius
        self.color = color
        self.mass = mass
        self.rest = restitution
        self.vx = x_speed
        self.vy = y_speed
        self.g = gravity
        self.trail_pts = deque(maxlen=trail_length)  # longueur de la traînée
        self.bool_trail = bool_trail

    def apply_gravity(self):
        self.vy += self.g * self.mass # accélère la vitesse verticale

    def move(self,max_speed=20):
        self.x += min(self.vx, max_speed)  # Limite la vitesse horizontale
        self.y += min(self.vy, max_speed)  # Limite la vitesse verticale

    def check_collision_and_gravity_on_circles(self, wall):
        BOUNCESTOP = 0.01
        if wall.in_the_wall(self):
            self.apply_gravity()
        else:
            if wall.point_in_arc(self)==False:
                self.apply_gravity()
                return True
            else:
                wall.Correct_ball_position(self)
                if math.fabs(self.vy)+math.fabs(self.vx) > BOUNCESTOP:
                    self.vx = self.vx*-1*self.rest
                    self.vy = self.vy*-1*self.rest
                    self.rest = math.fabs(random.normalvariate(1.0,0.2))
                else:
                    self.vy = 0
                    self.vx = 0
        
    def draw(self, screen):
        if self.bool_trail:
            # stocker la position
            self.trail_pts.appendleft((int(self.x), int(self.y)))

            # dessiner la traînée directement SUR screen (ou sur trail si tu veux)
            for i, (px, py) in enumerate(self.trail_pts):
                alpha = int(255 * (1 - i / len(self.trail_pts)))  # décroissant
                surf = pygame.Surface((2*self.r, 2*self.r), pygame.SRCALPHA)
                surf.fill((0,0,0,0))
                surf_circle_color = (*self.color[:3], alpha)
                pygame.draw.circle(surf, surf_circle_color, (self.r, self.r), self.r)
                screen.blit(surf, (px - self.r, py - self.r))

            # balle nette par-dessus
            pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.r)
            pygame.draw.circle(screen, (255,255,255), (int(self.x), int(self.y)), self.r, 2)
        else:
            pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.r)
            pygame.draw.circle(screen, (255,255,255), (int(self.x), int(self.y)), self.r, 2)
