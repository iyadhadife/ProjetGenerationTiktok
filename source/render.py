"""
Rendu "headless" de la simulation : aucune fenêtre, aucun enregistrement d'écran ni de carte son.

Chaque image est calculée puis envoyée directement à ffmpeg, et la bande-son est reconstruite
à partir de la musique et du son de rebond placé au moment exact de chaque collision.
C'est ce mode qui tourne dans le conteneur Docker.

Usage : python render.py [--duration 30] [--output ../VideoResult/tiktok.mp4] [--seed 42]
"""
import argparse
import math
import os
import random
import subprocess
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import imageio_ffmpeg
import pygame
from pydub import AudioSegment

from audio_image_scripts.color import generate_rgb_gradient
from bouncing1v1.Ball import Ball
from bouncing1v1.Wall import ArcWall

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MUSIC = os.path.join(ROOT, "bin", "MusiqueChill1", "Free.mp3")
BOUNCE = os.path.join(ROOT, "bin", "bouncing_sound", "bouncing_ball_v1.mp3")

FPS = 60
W, H = 1080, 1920


class BounceLog:
    """Remplace pygame.mixer.Sound : au lieu de jouer le son, on note l'image où il doit être joué."""

    def __init__(self):
        self.frame = 0
        self.frames = []

    def play(self):
        self.frames.append(self.frame)


def simulate(duration, seed):
    """Génère les images de la simulation (même scène que gen_vidéo_IA.py) et la liste des rebonds."""
    random.seed(seed)
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    font = pygame.font.SysFont("Arial", 50)

    nb_cercles, radius_step, starting_radius = 20, 25, 200
    center = (540, 960)
    end_angle = math.pi * 1.7
    max_speed = 15

    colors = generate_rgb_gradient((255, 0, 0), (40, 0, 0), nb_cercles)
    ball = Ball(center[0] - radius_step / 2, center[1] - radius_step / 2, radius=20, color=(255, 255, 255),
                restitution=1, x_speed=1, y_speed=1, mass=1, name='USA')
    ball2 = Ball(center[0] + radius_step / 2, center[1] + radius_step / 2, radius=20, color=(255, 255, 255),
                 restitution=1, x_speed=1, y_speed=1, mass=1, name='China')

    start_point = random.uniform(math.pi, math.pi * 2)
    walls = [ArcWall(center[0], center[1], radius=starting_radius + (i + 1) * radius_step, id=i,
                     start_angle=start_point + 0.1 * (i + 1), end_angle=end_angle + start_point + 0.1 * (i + 1),
                     color=colors[i])
             for i in range(nb_cercles)]
    walls.sort(key=lambda w: w.area_of_wall())
    rotation = 0.02

    bounces = BounceLog()
    end_frame = int(duration * FPS)
    frame = 0
    while frame < end_frame:
        bounces.frame = frame
        screen.fill((15, 15, 20))

        # Chaque balle rebondit sur l'arc le plus proche du centre ; le traverser le détruit
        for current, other in ((ball, ball2), (ball2, ball)):
            if walls and current.check_collision_and_gravity_on_circles(walls[0], other, ball_bouncing_sound=bounces):
                walls.pop(0)
                for wall in walls:
                    wall.radius -= radius_step
            current.move(max_speed=max_speed)

        # Les arcs tournent, et se resserrent tant que le premier n'est pas revenu au rayon de départ
        shrinking = bool(walls) and walls[0].radius > starting_radius
        for wall in walls:
            wall.start_angle += 2 * rotation
            wall.end_angle += 2 * rotation
            if shrinking:
                wall.radius -= 10
            wall.draw(screen)

        ball.draw(screen)
        ball2.draw(screen)
        for b, x in ((ball, 800), (ball2, 300)):
            text = font.render(f"{b.name} {b.wall_broken}", True, (255, 255, 255))
            screen.blit(text, text.get_rect(center=(x, 600)))

        yield pygame.image.tostring(screen, "RGB")

        # Une fois le dernier arc détruit, on garde encore une seconde puis on s'arrête
        if not walls:
            end_frame = min(end_frame, frame + FPS)
        frame += 1

    pygame.quit()
    simulate.bounce_frames = bounces.frames
    simulate.duration = frame / FPS


def build_soundtrack(duration, bounce_frames, path):
    """Musique + un son de rebond à chaque collision (au plus un toutes les 3 images pour éviter la saturation)."""
    track = AudioSegment.from_file(MUSIC)[:int(duration * 1000)]
    track = track + AudioSegment.silent(duration=max(0, int(duration * 1000) - len(track)))
    bounce = AudioSegment.from_file(BOUNCE) - 6
    last = -10
    for frame in bounce_frames:
        if frame - last >= 3:
            track = track.overlay(bounce, position=int(frame * 1000 / FPS))
            last = frame
    track.export(path, format="wav")


def main():
    parser = argparse.ArgumentParser(description="Génère une vidéo TikTok verticale (1080x1920) de la simulation.")
    parser.add_argument("--duration", type=float, default=30,
                        help="durée maximale en secondes ; la vidéo s'arrête 1 s après le dernier arc (défaut : 30)")
    parser.add_argument("--output", default=os.path.join(ROOT, "VideoResult", "tiktok.mp4"))
    parser.add_argument("--seed", type=int, default=None, help="graine aléatoire pour reproduire une vidéo")
    args = parser.parse_args()
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        silent_video = os.path.join(tmp, "video.mp4")
        audio = os.path.join(tmp, "audio.wav")

        print(f"🎥 Rendu (au plus {args.duration:g} s) à {FPS} ips...")
        writer = imageio_ffmpeg.write_frames(silent_video, (W, H), fps=FPS, codec="libx264",
                                             pix_fmt_out="yuv420p", quality=7, macro_block_size=1)
        writer.send(None)
        for frame in simulate(args.duration, args.seed):
            writer.send(frame)
        writer.close()

        print(f"🔊 Bande-son : musique + {len(simulate.bounce_frames)} rebonds...")
        build_soundtrack(simulate.duration, simulate.bounce_frames, audio)

        print("🎬 Fusion audio + vidéo...")
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", silent_video, "-i", audio,
                        "-c:v", "copy", "-c:a", "aac", "-shortest", args.output], check=True)
    print(f"✅ Vidéo prête : {args.output}")


if __name__ == "__main__":
    main()
