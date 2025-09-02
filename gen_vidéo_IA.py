import pygame, sys, math
from pygame.locals import *
from Ball import Ball
from Wall import Wall

# Initialiser Pygame
pygame.init()
screen = pygame.display.set_mode((600, 600))
clock = pygame.time.Clock()

# Lecture audio
audio_path = r"C:\Users\ihadi\Downloads\pirate-tavern-full-version-167990.mp3"
pygame.mixer.music.load(audio_path)
pygame.mixer.music.play()

nb_cercles = 1
rayon_step = 150
center = (300, 300)

ball = Ball(center[0], center[1], radius=5, color=(255, 0, 0), restitution=0.9, x_speed=3, y_speed=2, mass=2)
walls = [Wall(center[0], center[1], radius=(i + 1) * rayon_step) for i in range(nb_cercles)]

while True:
    for e in pygame.event.get():
        if e.type == QUIT:
            pygame.quit()
            sys.exit()

    screen.fill((0, 0, 0))

    ball.move()

    # Collision avec chaque cercle
    for wall in walls:
        ball.check_collision_and_gravity_on_circles(center, wall.radius)
        wall.draw(screen)

    ball.draw(screen)

    pygame.display.flip()
    clock.tick(5)
