import librosa
import time
import math 
import bouncing1v1.Ball as Ball
import bouncing1v1.Wall as Wall
import numpy as np
import pygame
import musicbouncing.music_highlight as mh

ips = 60
W,H = 1080, 1920

highlights = mh.onsets_frames()
# Initialiser Pygame
pygame.init()

# Paramètres de la fenêtre
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption('Balle Rebonds')

# Audio
audio_path = r"C:\Users\ihadi\Downloads\pirate-tavern-full-version-167990.mp3"
pygame.mixer.music.load(audio_path)
pygame.mixer.music.play()
# Couleurs
black = (15, 15, 20)
white = (255, 255, 255)

# Paramètres de la balle
ball_radius = 20
ball_pos = [100, 600 - ball_radius]
ball_velocity = 0
floor = 800

# Fréquence de mise à jour
clock = pygame.time.Clock()
# Boucle principale
running = True
onset_index = 0
start_time = time.time()

while running:
    screen.fill(black)
    mh.draw_ball(screen=screen, color=white, ball_pos=ball_pos, ball_radius=ball_radius)

    # Vérifier les événements
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    if onset_index < len(highlights):
        t = time.time() - start_time
        # If we're still inside the interval
        if onset_index > 0 and t < highlights[onset_index]:
            r1 = highlights[onset_index - 1]
            r2 = highlights[onset_index]
            ball_pos[0] = t * 60 # move across screen
            ball_pos[1] = mh.polynomial(t, r1, r2, height=50)  # bounce arc
        elif t >= highlights[onset_index]:
            onset_index += 1

    ball_pos[0] -= 20/ips
    pygame.display.flip()
    clock.tick(ips)

pygame.quit()
