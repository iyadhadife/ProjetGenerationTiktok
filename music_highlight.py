import librosa
import time
import math 
import Ball as Ball
import Wall as Wall
import numpy as np
import pygame

def onsets_frames(audio_path = r"C:\Users\ihadi\Downloads\pirate-tavern-full-version-167990.mp3"):
    # Charger le fichier audio
    y, sr = librosa.load(audio_path)

    # Détecter les onsets
    highlights = librosa.onset.onset_detect(y=y, sr=sr)

    # Convertir les indices de trames en temps (secondes)
    highlights = librosa.frames_to_time(highlights, sr=sr)
    return highlights

# highlights = onsets_frames()
# print(highlights)

def velocity_ball(highlight: np.ndarray, now: float, ball: Ball, wall: Wall, ips: int = 60):
    # Temps restant avant le prochain "highlight"
    est = highlight[0] - now
    if est >0:
        nb_ips = est * ips  # nombre d'images

        # Calcul de la distance (radiale) restante jusqu'au mur
        dist, dx, dy = wall.distance_to_middle(ball)
        dist = wall.radius - dist - ball.r

        vx, vy = ball.vx, ball.vy
        dist_v = math.hypot(vx, vy)
        if vy < 0 or vx < 0:
            # Inverser la direction de la balle
            dist_v = dist_v + wall.radius

        if dist_v == 0 or nb_ips <= 0 or dist <= 0:
            # Aucun mouvement ou cas invalides : on évite la division par zéro ou logique absurde
            highlight = highlight[1:]
            return highlight

        dist_v_needed = dist / nb_ips  # norme de vitesse cible

        scale = dist_v_needed / dist_v
        ball.vx *= scale
        ball.vy *= scale

        # Supprime le premier "moment important"
    highlight = np.delete(highlight, 0)
    return highlight

ips = 60
W,H = 1080, 1920

highlights = onsets_frames()
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

# Fonction pour dessiner la balle
def draw_ball():
    pygame.draw.circle(screen, white, ball_pos, ball_radius)

# Fonction pour faire rebondir la balle
def bounce_ball():
    global ball_pos, ball_velocity
    ball_velocity = -15  # Vitesse initiale vers le haut

# Boucle principale
running = True
onset_index = 0
start_time = time.time()

def polynomial(t : float, r1 : float, r2 : float, height=100, floor=floor):
    mid = (r1 + r2) / 2
    return floor + (height * (1 - ((t - mid) / ((r2 - r1) / 2))**2))


while running:
    screen.fill(black)
    draw_ball()

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
            ball_pos[1] = polynomial(t, r1, r2, height=50)  # bounce arc
        elif t >= highlights[onset_index]:
            onset_index += 1

    ball_pos[0] -= 20/ips
    pygame.display.flip()
    clock.tick(ips)

pygame.quit()
