import pygame, sys, math
from pygame.locals import *

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
ball = {"x": 400, "y": 200, "vx": 3, "vy": 2, "r": 8}

while True:
    screen.fill((0, 0, 0))

    # Dessiner les cercles concentriques
    for i in range(nb_cercles):
        rayon = (i+1) * rayon_step
        pygame.draw.circle(screen, (0, 100, 255), center, rayon, 1)

    # Déplacer la balle
    ball["x"] += ball["vx"]
    ball["y"] += ball["vy"]

    # Calcul de la distance du centre
    dx = ball["x"] - center[0]
    dy = ball["y"] - center[1]
    dist = math.sqrt(dx*dx + dy*dy)

    # Vérifier collision avec les parois
    for i in range(nb_cercles):
        rayon = (i+1) * rayon_step
        if abs(dist - rayon) <= ball["r"]:  # collision détectée
            # Vecteur normal (centre → balle)
            nx, ny = dx/dist, dy/dist
            # Projection de la vitesse sur la normale
            dot = ball["vx"]*nx + ball["vy"]*ny
            # Réflexion
            ball["vx"] -= 2*dot*nx
            ball["vy"] -= 2*dot*ny
            break

    # Dessiner la balle
    pygame.draw.circle(screen, (255, 0, 0), (int(ball["x"]), int(ball["y"])), ball["r"])

    # Gestion événements
    for ev in pygame.event.get():
        if ev.type == QUIT:
            pygame.quit()
            sys.exit()

    pygame.display.flip()
    clock.tick(60)
