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
    gravity: float = 0.6                # pixels / image² (à 60 ips ; ajustée automatiquement à 30 ips)
    # Synchronisation musicale
    beats_per_break: int = 4            # en moyenne un arc détruit tous les N rebonds
    min_beat_interval: float = 0.35     # secondes minimum entre deux rebonds (seul le temps le plus fort est gardé)
    selectivity: float = 0.4            # part des temps forts les plus faibles ignorés (0 = tous, 0.9 = les 10 % les plus forts)
    sensitivity: float = 0.07           # seuil de détection (plus bas = plus de temps détectés)
    bounce_sound: bool = True
    bounce_volume: float = -6.0         # dB
    piano: str = "off"                  # "off", "mix" ou "solo" : chaque rebond joue la note de la musique
    piano_volume: float = -4.0
    seed: int | None = None


def hex_to_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def detect_beats(music_path, sensitivity, min_interval, selectivity=0.0):
    """Meilleurs temps forts du morceau (en secondes).

    Sur une musique rapide, rebondir sur chaque temps donnerait des trajets minuscules. On mesure donc
    la force de chaque temps, on écarte les plus faibles (selectivity), puis on garde en priorité les plus
    forts : un temps est ignoré s'il tombe à moins de min_interval d'un temps plus fort déjà retenu.
    """
    import librosa
    y, sr = librosa.load(music_path, sr=22050, mono=True)
    duration = len(y) / sr
    envelope = librosa.onset.onset_strength(y=y, sr=sr)
    frames = librosa.onset.onset_detect(onset_envelope=envelope, sr=sr, delta=sensitivity, backtrack=False)
    if len(frames) == 0:
        return [], duration
    times = librosa.frames_to_time(frames, sr=sr)
    strengths = envelope[frames]
    threshold = np.quantile(strengths, min(max(selectivity, 0.0), 0.95))
    candidates = sorted(((s, float(t)) for s, t in zip(strengths, times) if s >= threshold), reverse=True)
    kept = []
    for _, t in candidates:
        if all(abs(t - k) >= min_interval for k in kept):
            kept.append(t)
    return sorted(kept), duration


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
        self.free = False             # vol libre (plus de temps fort à viser) : simple physique
        self.vx = self.vy = 0.0
        self.breaking = False

    def position_at(self, frame):
        f0, x0, y0, vx, vy, g, _ = self.plan
        t = frame - f0
        return x0 + vx * t, y0 + vy * t + 0.5 * g * t * t

    def velocity_at(self, frame):
        f0, _, _, vx, vy, g, _ = self.plan
        return vx, vy + g * (frame - f0)


class Scene:
    def __init__(self, cfg: Config, beats):
        self.cfg = cfg
        self.rng = random.Random(cfg.seed)
        self.center = (W / 2, H / 2)
        self.gap = math.radians(cfg.gap_degrees)
        self.rot = math.radians(cfg.rotation_speed)
        self.g = cfg.gravity * (60 / cfg.fps) ** 2   # même chute à l'écran quel que soit le nombre d'ips
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

        # Gravité adaptée au tempo : un vol sous gravité g dans un cercle de rayon R dure au plus ~2·√(4R/g).
        # On choisit g pour que la plupart des intervalles entre deux rebonds d'une balle soient de vrais
        # vols paraboliques (le réglage de l'utilisateur reste un maximum).
        gaps = [b - a for sched in self.schedule for a, b in zip(sched, sched[1:])]
        if gaps:
            typical = float(np.percentile(gaps, 90))
            self.g = min(self.g, 8 * self._reach(cfg.inner_radius + cfg.arc_spacing) / typical ** 2)
        for ball, sched in zip(self.balls, self.schedule):
            self._plan(ball, 0, sched, (0.0, 0.0))

    # --- planification -----------------------------------------------------------------
    def _arc_start_at(self, arc, frame, now):
        return arc.start + self.rot * (frame - now)

    def _reach(self, radius):
        """Distance maximale du centre de la balle au centre de la scène pour un arc de ce rayon."""
        return radius - self.cfg.ball_radius - self.cfg.arc_thickness / 2

    def _plan(self, ball, now, sched, v_in):
        """Choisit la trajectoire qui amène la balle sur l'arc intérieur au prochain temps fort.

        La gravité reste celle des réglages : parmi plusieurs points d'impact possibles, on garde la
        parabole qui ne sort pas du cercle et dont la vitesse de départ ressemble le plus au rebond
        physique (v_in = vitesse juste après la réflexion sur la paroi).
        """
        future = [f for f in sched if f > now]
        if not future or not self.arcs:
            # Plus de temps fort à viser : la balle continue en vol libre, elle ne s'arrête jamais
            ball.free, ball.breaking = True, False
            ball.vx, ball.vy = v_in
            if math.hypot(*v_in) < 3:
                angle = self.rng.uniform(0, 2 * math.pi)
                ball.vx, ball.vy = 6 * math.cos(angle), -6 * abs(math.sin(angle))
            return
        ball.free = False
        arrival = future[0]
        T = arrival - now
        arc = self.arcs[0]
        reach = self._reach(arc.target_radius)
        start = self._arc_start_at(arc, arrival, now)
        # En moyenne un rebond sur N traverse l'ouverture : tirage aléatoire pour que le vainqueur reste incertain
        breaking = self.rng.random() < 1 / max(1, self.cfg.beats_per_break)
        if breaking:
            angles = [start - self.gap / 2 + self.gap * 0.3 * u for u in np.linspace(-1, 1, 9)]
        else:
            margin = min(0.25, (2 * math.pi - self.gap) / 4)
            angles = list(start + np.linspace(margin, 2 * math.pi - self.gap - margin, 48))

        speed_in = math.hypot(*v_in)
        ts = np.linspace(0, T, 24)
        best = None
        for angle in angles:
            tx = self.center[0] + reach * math.cos(angle)
            ty = self.center[1] - reach * math.sin(angle)
            vx = (tx - ball.x) / T
            vy = (ty - ball.y) / T - 0.5 * self.g * T
            xs = ball.x + vx * ts - self.center[0]
            ys = ball.y + vy * ts + 0.5 * self.g * ts * ts - self.center[1]
            if np.any(np.hypot(xs, ys) > reach + 1):
                continue                                       # la parabole traverserait la paroi
            score = self.rng.uniform(0, 0.15)                  # un peu de variété d'un rebond à l'autre
            if speed_in > 0.5:
                speed = math.hypot(vx, vy)
                cos = (vx * v_in[0] + vy * v_in[1]) / (speed * speed_in + 1e-9)
                score += math.acos(max(-1.0, min(1.0, cos))) + 0.5 * abs(math.log((speed + 1e-9) / speed_in))
            if best is None or score < best[0]:
                best = (score, vx, vy, self.g)
        if best is None:
            # Aucun point atteignable sous pleine gravité dans ce délai : on l'atténue juste assez
            angle = angles[len(angles) // 2]
            tx = self.center[0] + reach * math.cos(angle)
            ty = self.center[1] - reach * math.sin(angle)
            g = self.g
            for _ in range(8):
                g *= 0.5
                vx, vy = (tx - ball.x) / T, (ty - ball.y) / T - 0.5 * g * T
                xs = ball.x + vx * ts - self.center[0]
                ys = ball.y + vy * ts + 0.5 * g * ts * ts - self.center[1]
                if np.all(np.hypot(xs, ys) <= reach + 1):
                    break
            else:
                g, vx, vy = 0.0, (tx - ball.x) / T, (ty - ball.y) / T
            best = (0, vx, vy, g)
        _, vx, vy, g = best
        ball.plan = (now, ball.x, ball.y, vx, vy, g, arrival)
        ball.breaking = breaking

    def _reflect(self, ball, vx, vy):
        """Vitesse après un rebond élastique sur la paroi circulaire, au point où se trouve la balle."""
        nx, ny = ball.x - self.center[0], ball.y - self.center[1]
        norm = math.hypot(nx, ny) or 1.0
        nx, ny = nx / norm, ny / norm
        dot = vx * nx + vy * ny
        return (vx - 2 * dot * nx, vy - 2 * dot * ny) if dot > 0 else (vx, vy)

    def _free_step(self, ball, frame):
        ball.vy += self.g
        ball.x += ball.vx
        ball.y += ball.vy
        if not self.arcs:
            return                                             # plus d'arc : la balle tombe hors de l'écran
        reach = self._reach(self.arcs[0].radius)
        dx, dy = ball.x - self.center[0], ball.y - self.center[1]
        dist = math.hypot(dx, dy)
        if dist > reach:
            ball.x = self.center[0] + dx / dist * reach
            ball.y = self.center[1] + dy / dist * reach
            ball.vx, ball.vy = self._reflect(ball, ball.vx, ball.vy)
            self.bounce_frames.append(frame)

    # --- simulation image par image ------------------------------------------------------
    def step(self, frame):
        for arc in self.arcs:
            arc.start += self.rot
            if arc.radius > arc.target_radius:              # resserrement animé après une destruction
                arc.radius = max(arc.target_radius, arc.radius - 5)

        for ball, sched in zip(self.balls, self.schedule):
            if ball.free:
                self._free_step(ball, frame)
                continue
            ball.x, ball.y = ball.position_at(frame)
            if frame == ball.plan[6]:
                self.bounce_frames.append(frame)
                v_arrival = ball.velocity_at(frame)
                if ball.breaking and self.arcs:
                    # La balle passe par l'ouverture : pas de rebond, elle garde son élan
                    self.arcs.pop(0)
                    ball.score += 1
                    for arc in self.arcs:
                        arc.target_radius -= self.cfg.arc_spacing
                    v_next = v_arrival
                else:
                    v_next = self._reflect(ball, *v_arrival)
                self._plan(ball, frame, sched, v_next)

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
    beats, music_duration = detect_beats(music_path, cfg.sensitivity, cfg.min_beat_interval, cfg.selectivity)
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
        if cfg.piano in ("mix", "solo"):
            from piano import add_piano, detect_notes
            log("🎹 Notes de piano...")
            times = [f / cfg.fps for f in scene.bounce_frames]
            track = add_piano(track, detect_notes(music_path, times), [t * 1000 for t in times], cfg.piano, cfg.piano_volume)
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
