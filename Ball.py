import pygame, sys, math
from pygame.locals import *
import random 
from collections import deque

class Ball:
    def __init__(self, x_pos, y_pos, radius, color, mass=1, restitution=0.5, x_speed=0, y_speed=0, gravity=0.81, trail_length=20, bool_trail=False, name =''):
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
        self.wall_broken = 0
        self.name = name

    def ball_collision(self, ball2):
        dx = ball2.x - self.x
        dy = ball2.y - self.y
        distance = math.hypot(dx, dy)

        if distance < self.r + ball2.r:
            # 1. Calcul du chevauchement
            overlap = (self.r + ball2.r) - distance

            # 2. Normalisation du vecteur de séparation
            if distance != 0:
                nx = dx / distance
                ny = dy / distance
            else:
                # Cas où les centres sont exactement superposés
                nx, ny = 1, 0  

            # 3. Décaler les balles de moitié de l'overlap chacune
            self.x -= nx * (overlap / 2)
            self.y -= ny * (overlap / 2)
            ball2.x += nx * (overlap / 2)
            ball2.y += ny * (overlap / 2)

            # 4. Inverser les vitesses (simple, mais pas réaliste)
            self.vx *= -1
            self.vy *= -1
            ball2.vx *= -1
            ball2.vy *= -1

    def apply_gravity(self):
        self.vy += self.g * self.mass # accélère la vitesse verticale

    def move(self,max_speed=20):
        self.x += min(self.vx, max_speed)  # Limite la vitesse horizontale
        self.y += min(self.vy, max_speed)  # Limite la vitesse verticale

    def check_collision_and_gravity_on_circles(self, wall, ball2, ball_bouncing_sound : pygame.mixer.Sound = None):
        BOUNCESTOP = 0.01
        if wall.in_the_wall(self):
            self.apply_gravity()
            self.ball_collision(ball2)
        else:
            if wall.point_in_arc(self)==False:
                self.apply_gravity()
                self.wall_broken += 1
                return True
            else:
                if ball_bouncing_sound != None:
                    ball_bouncing_sound.play()
                wall.Correct_ball_position(self)
                if math.fabs(self.vy)+math.fabs(self.vx) > BOUNCESTOP:
                    self.vx = self.vx*-1*self.rest
                    self.vy = self.vy*-1*self.rest
                    # self.rest = math.fabs(random.normalvariate(1.0,0.2))
                    self.rest=1
                else:
                    self.vy = 0
                    self.vx = 0
        
    def draw(self, screen):
        font = pygame.font.SysFont("Arial", 11)
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
            text = font.render(self.name, True, (int(self.x), int(self.y)))
            text_rect = text.get_rect(center=(int(self.x), int(self.y)))
            screen.blit(text, text_rect)
        else:
            pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.r)
            pygame.draw.circle(screen, (255,255,255), (int(self.x), int(self.y)), self.r, 2)
            text = font.render(self.name, True, (0,0,0))
            text_rect = text.get_rect(center=(int(self.x), int(self.y)))
            screen.blit(text, text_rect)
