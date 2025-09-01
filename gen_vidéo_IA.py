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

nb_cercles = 2
rayon_step = 150
center = (300, 300)

ball = Ball(300, 300, radius=5, color=(255, 0, 0), restitution=0.95, x_speed=1, y_speed=1, gravity=0.5)
walls = [Wall(300, 300, radius=150)]
while True:
    for e in pygame.event.get():
        if e.type == QUIT:
            pygame.quit()
            sys.exit()

    screen.fill((0, 0, 0))

    ball.apply_gravity()
    ball.move()

    # Collision avec chaque cercle
    for i in range(nb_cercles):
        rayon = (i + 1) * rayon_step
        ball.check_collision_circle(center, rayon)
        pygame.draw.circle(screen, (0, 100, 255), center, rayon, 1)

    ball.draw(screen)

    pygame.display.flip()
    clock.tick(300)
