import librosa
import time
import math 
import bouncing1v1.Ball as Ball
import bouncing1v1.Wall as Wall
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

# Paramètres de la balle
ball_radius = 20
ball_pos = [100, 600 - ball_radius]
floor = 800

# Fréquence de mise à jour
clock = pygame.time.Clock()
# Fonction pour dessiner la balle

def draw_ball(screen, color, ball_pos=ball_pos, ball_radius=ball_radius):
    pygame.draw.circle(screen, color, ball_pos, ball_radius)

# Fonction pour faire rebondir la balle
def bounce_ball():
    global ball_pos, ball_velocity
    ball_velocity = -15  # Vitesse initiale vers le haut

def polynomial(t : float, r1 : float, r2 : float, height=100, floor=floor):
    mid = (r1 + r2) / 2
    return floor + (height * (1 - ((t - mid) / ((r2 - r1) / 2))**2))


