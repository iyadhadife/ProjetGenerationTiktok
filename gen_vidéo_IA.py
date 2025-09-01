import pygame, sys, math
from pygame.locals import *
from Ball import Ball

pygame.init()
screen = pygame.display.set_mode((300, 300))
clock = pygame.time.Clock()

nb_cercles = 1
rayon_step = 150
center = (150, 150)

ball = Ball(150, 150, radius=5, color=(255, 0, 0), restitution=0.9, x_speed=1, y_speed=1, gravity=0.5)

while True:
    for e in pygame.event.get():
        if e.type == QUIT:
            pygame.quit()
            sys.exit()

    screen.fill((0, 0, 0))

    # Appliquer gravité et mouvement
    ball.apply_gravity()
    ball.move()

    # Collision avec chaque cercle
    for i in range(nb_cercles):
        rayon = (i + 1) * rayon_step
        ball.check_collision_circle(center, rayon)
        pygame.draw.circle(screen, (0, 100, 255), center, rayon, 1)

    ball.draw(screen)

    pygame.display.flip()
    clock.tick(60)
