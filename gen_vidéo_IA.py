import pygame, sys, math
from pygame.locals import *
from Ball import Ball
# Initialiser Pygame
pygame.init()
screen = pygame.display.set_mode((800, 800))
clock = pygame.time.Clock()

# Lecture audio
audio_path = r"C:\Users\ihadi\Downloads\pirate-tavern-full-version-167990.mp3"
pygame.mixer.music.load(audio_path)
pygame.mixer.music.play()

# Paramètres cercles
nb_cercles = 200
rayon_step = 5
center = (400, 400)

# Balle
ball = Ball(0, 0, 5, (255, 0, 0), 1, 0.9, 1, 0.5, 1)

while True:
    screen.fill((0, 0, 0))

    # Dessiner les cercles concentriques
    for i in range(nb_cercles):
        rayon = (i+1) * rayon_step
        pygame.draw.circle(screen, (0, 100, 255), center, rayon, 1)

    # Vérifier collision avec les parois
    for i in range(nb_cercles):
        rayon = (i+1) * rayon_step
        if ball.check_gravity(rayon):
            ball.move(ball.x_speed, ball.y_speed)
            break

    # Dessiner la balle
    ball.draw(screen)

    # Gestion événements
    for ev in pygame.event.get():
        if ev.type == QUIT:
            pygame.quit()
            sys.exit()

    pygame.display.flip()
    clock.tick(60)
