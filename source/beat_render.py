"""
Rendu d'une vidéo TikTok où chaque rebond tombe exactement sur un temps fort de la musique.

1. librosa détecte les temps forts (onsets) du morceau.
2. Les temps sont répartis entre les balles. Entre deux temps, la trajectoire de la balle est calculée
   (parabole sous gravité) pour qu'elle touche l'arc le plus proche du centre pile au temps suivant.
3. En moyenne un temps sur N (tirage aléatoire), la balle vise l'ouverture de l'arc : elle le traverse, le détruit et marque un point.
4. Les images sont envoyées à ffmpeg, et la musique + un son de rebond à chaque impact forment la bande-son.

Utilisé par l'API web (web/backend) et en ligne de commande :
    python beat_render.py ma_musique.mp3 --output ../VideoResult/tiktok.mp4
"""
import argparse
import math
import os
import random
import subprocess
import tempfile
from dataclasses import dataclass, field, asdict

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import imageio_ffmpeg
import numpy as np
import pygame
from pydub import AudioSegment

from audio_image_scripts.color import generate_rgb_gradient

HERE = os.path.dirname(os.path.abspath(__file__))
BOUNCE_SOUND = os.path.join(os.path.dirname(HERE), "bin", "bouncing_sound", "bouncing_ball_v1.mp3")
W, H = 1080, 1920


@dataclass
class Config:
    # Vidéo
    fps: int = 60
    max_duration: float = 60.0          # secondes ; la vidéo dure au plus la musique
    title: str = ""
    background: str = "#0f0f14"
    # Arcs
    arc_count: int = 20
    arc_spacing: int = 25
    inner_radius: int = 200
    gap_degrees: float = 54.0           # taille de l'ouverture de chaque arc
    rotation_speed: float = 1.2         # degrés par image
    arc_color_start: str = "#ff0000"
    arc_color_end: str = "#280000"
    arc_thickness: int = 7
    # Balles
    ball_names: list = field(default_factory=lambda: ["USA", "China"])
    ball_colors: list = field(default_factory=lambda: ["#ffffff", "#ffffff"])
    ball_radius: int = 20
    gravity: float = 0.6                # pixels / image²
    # Synchronisation musicale
    beats_per_break: int = 4            # en moyenne un arc détruit tous les N rebonds
    min_beat_interval: float = 0.25     # secondes entre deux rebonds d'une même balle
    sensitivity: float = 0.07           # seuil de détection (plus bas = plus de temps détectés)
    bounce_sound: bool = True
    bounce_volume: float = -6.0         # dB
    seed: int | None = None


def hex_to_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def detect_beats(music_path, sensitivity, min_interval):
    """Temps forts du morceau (en secondes), espacés d'au moins min_interval."""
    import librosa
    y, sr = librosa.load(music_path, sr=22050, mono=True)
    onsets = librosa.onset.onset_detect(y=y, sr=sr, units="time", delta=sensitivity, backtrack=False)
    beats, last = [], -math.inf
    for t in onsets:
        if t - last >= min_interval:
            beats.append(float(t))
            last = t
    return beats, len(y) / sr


class Arc:
    def __init__(self, radius, start, color):
        self.radius = float(radius)
        self.target_radius = float(radius)
        self.start = start            # angle (radians, sens pygame : anti-horaire, y vers le haut)
        self.color = color


class Ball:
    def __init__(self, name, color, x, y):
        self.name, self.color = name, color
        self.x, self.y = x, y
        self.score = 0
        self.plan = None              # (frame de départ, x0, y0, vx, vy, gravité, frame d'arrivée)

    def position_at(self, frame):
        f0, x0, y0, vx, vy, g, _ = self.plan
        t = frame - f0
        return x0 + vx * t, y0 + vy * t + 0.5 * g * t * t


class Scene:
    def __init__(self, cfg: Config, beats):
        self.cfg = cfg
        self.rng = random.Random(cfg.seed)
        self.center = (W / 2, H / 2)
        self.gap = math.radians(cfg.gap_degrees)
        self.rot = math.radians(cfg.rotation_speed)
        colors = generate_rgb_gradient(hex_to_rgb(cfg.arc_color_start), hex_to_rgb(cfg.arc_color_end), max(cfg.arc_count, 2))
        offset = self.rng.uniform(0, 2 * math.pi)
        self.arcs = [Arc(cfg.inner_radius + (i + 1) * cfg.arc_spacing, offset + 0.1 * (i + 1), colors[i])
                     for i in range(cfg.arc_count)]

        n = max(1, len(cfg.ball_names))
        self.balls = []
        for i in range(n):
            angle = 2 * math.pi * i / n
            self.balls.append(Ball(cfg.ball_names[i], hex_to_rgb(cfg.ball_colors[i % len(cfg.ball_colors)]),
                                   self.center[0] + 30 * math.cos(angle), self.center[1] + 30 * math.sin(angle)))

        # Les temps forts sont distribués à tour de rôle entre les balles
        # (on ignore les temps des 0,3 premières secondes : la balle n'aurait pas le temps d'y aller)
        frames = [round(t * cfg.fps) for t in beats if t >= 0.3]
        self.schedule = [frames[i::n] for i in range(n)]
        self.bounce_frames = []
        for ball, sched in zip(self.balls, self.schedule):
            self._plan(ball, 0, sched)

    # --- planification -----------------------------------------------------------------
    def _arc_start_at(self, arc, frame, now):
        return arc.start + self.rot * (frame - now)

    def _plan(self, ball, now, sched):
        """Calcule la trajectoire qui amène la balle sur l'arc intérieur au prochain temps fort."""
        future = [f for f in sched if f > now]
        if not future or not self.arcs:
            ball.plan = (now, ball.x, ball.y, 0.0, 0.0, 0.0, math.inf)
            ball.breaking = False
            return
        arrival = future[0]
        T = arrival - now
        arc = self.arcs[0]
        reach = arc.target_radius - self.cfg.ball_radius - self.cfg.arc_thickness / 2
        start = self._arc_start_at(arc, arrival, now)
        # En moyenne un rebond sur N traverse l'ouverture : tirage aléatoire pour que le vainqueur reste incertain
        breaking = self.rng.random() < 1 / max(1, self.cfg.beats_per_break)
        if breaking:
            angle = start - self.gap / 2                       # milieu de l'ouverture
        else:
            margin = min(0.25, (2 * math.pi - self.gap) / 4)
            angle = start + self.rng.uniform(margin, 2 * math.pi - self.gap - margin)
        tx = self.center[0] + reach * math.cos(angle)
        ty = self.center[1] - reach * math.sin(angle)

        # Parabole x(t)=x0+vx t, y(t)=y0+vy t+g t²/2 qui passe par la cible à t=T.
        # On réduit la gravité si la courbe sortait du cercle (à g=0 c'est une corde : toujours à l'intérieur).
        g = self.cfg.gravity
        for _ in range(8):
            vx = (tx - ball.x) / T
            vy = (ty - ball.y) / T - 0.5 * g * T
            ts = np.linspace(0, T, 24)
            xs = ball.x + vx * ts - self.center[0]
            ys = ball.y + vy * ts + 0.5 * g * ts * ts - self.center[1]
            if np.all(np.hypot(xs, ys) <= reach + 1):
                break
            g *= 0.5
        else:
            g, vx, vy = 0.0, (tx - ball.x) / T, (ty - ball.y) / T
        ball.plan = (now, ball.x, ball.y, vx, vy, g, arrival)
        ball.breaking = breaking

    # --- simulation image par image ------------------------------------------------------
    def step(self, frame):
        for arc in self.arcs:
            arc.start += self.rot
            if arc.radius > arc.target_radius:              # resserrement animé après une destruction
                arc.radius = max(arc.target_radius, arc.radius - 5)

        for ball, sched in zip(self.balls, self.schedule):
            ball.x, ball.y = ball.position_at(frame)
            if frame == ball.plan[6]:
                self.bounce_frames.append(frame)
                if ball.breaking and self.arcs:
                    self.arcs.pop(0)
                    ball.score += 1
                    for arc in self.arcs:
                        arc.target_radius -= self.cfg.arc_spacing
                self._plan(ball, frame, sched)

    def draw(self, screen, fonts):
        screen.fill(hex_to_rgb(self.cfg.background))
        cx, cy = self.center
        for arc in self.arcs:
            r = arc.radius
            rect = pygame.Rect(cx - r, cy - r, 2 * r, 2 * r)
            pygame.draw.arc(screen, arc.color, rect, arc.start, arc.start + 2 * math.pi - self.gap, self.cfg.arc_thickness)
        for ball in self.balls:
            pygame.draw.circle(screen, ball.color, (int(ball.x), int(ball.y)), self.cfg.ball_radius)
            pygame.draw.circle(screen, (255, 255, 255), (int(ball.x), int(ball.y)), self.cfg.ball_radius, 2)

        if self.cfg.title:
            text = fonts["title"].render(self.cfg.title, True, (255, 255, 255))
            screen.blit(text, text.get_rect(center=(W / 2, 330)))
        n = len(self.balls)
        for i, ball in enumerate(self.balls):
            text = fonts["score"].render(f"{ball.name} {ball.score}", True, ball.color)
            screen.blit(text, text.get_rect(center=(W * (i + 1) / (n + 1), 520)))


def render(music_path, output, cfg: Config, progress=lambda done, total: None, log=print):
    log("🎵 Détection des temps forts...")
    beats, music_duration = detect_beats(music_path, cfg.sensitivity, cfg.min_beat_interval)
    if not beats:
        raise ValueError("Aucun temps fort détecté : baisse la sensibilité ou choisis un autre morceau.")
    duration = min(music_duration, cfg.max_duration)
    beats = [t for t in beats if t < duration]
    log(f"   {len(beats)} temps forts sur {duration:.1f} s")

    pygame.init()
    screen = pygame.display.set_mode((W, H))
    fonts = {"score": pygame.font.SysFont("Arial", 56, bold=True), "title": pygame.font.SysFont("Arial", 72, bold=True)}
    scene = Scene(cfg, beats)
    total = int(duration * cfg.fps)
    end = total

    with tempfile.TemporaryDirectory() as tmp:
        silent = os.path.join(tmp, "video.mp4")
        audio = os.path.join(tmp, "audio.wav")
        writer = imageio_ffmpeg.write_frames(silent, (W, H), fps=cfg.fps, codec="libx264",
                                             pix_fmt_out="yuv420p", quality=7, macro_block_size=1)
        writer.send(None)
        frame = 0
        while frame < end:
            scene.step(frame)
            scene.draw(screen, fonts)
            writer.send(pygame.image.tostring(screen, "RGB"))
            if not scene.arcs:                                 # dernier arc détruit : fin une seconde après
                end = min(end, frame + cfg.fps)
            frame += 1
            if frame % cfg.fps == 0:
                progress(frame, end)
        writer.close()
        pygame.quit()

        log("🔊 Bande-son...")
        length_ms = int(frame * 1000 / cfg.fps)
        track = AudioSegment.from_file(music_path)[:length_ms]
        if cfg.bounce_sound:
            bounce = AudioSegment.from_file(BOUNCE_SOUND) + cfg.bounce_volume
            for f in scene.bounce_frames:
                track = track.overlay(bounce, position=int(f * 1000 / cfg.fps))
        track.export(audio, format="wav")

        log("🎬 Fusion audio + vidéo...")
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", silent, "-i", audio,
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", output], check=True)
    progress(end, end)
    return {"beats": len(beats), "bounces": len(scene.bounce_frames), "duration": frame / cfg.fps,
            "scores": {b.name: b.score for b in scene.balls}}


def main():
    parser = argparse.ArgumentParser(description="Vidéo TikTok dont les rebonds suivent la musique.")
    parser.add_argument("music")
    parser.add_argument("--output", default=os.path.join(os.path.dirname(HERE), "VideoResult", "tiktok.mp4"))
    for name, value in asdict(Config()).items():
        if isinstance(value, (int, float, str)) and not isinstance(value, bool):
            parser.add_argument("--" + name.replace("_", "-"), type=type(value), default=value)
    parser.add_argument("--seed", type=int, default=None)
    args = vars(parser.parse_args())
    music, output = args.pop("music"), args.pop("output")
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    cfg = Config(**args)
    print(render(music, output, cfg, progress=lambda d, t: print(f"   {d}/{t} images", end="\r")))


if __name__ == "__main__":
    main()
