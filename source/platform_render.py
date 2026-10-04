"""
Mode « Plateformes » : une balle tombe sous gravité et rebondit sur des plateformes qui surgissent
au bon endroit, exactement sur le tempo de la musique.

1. Synchronisation (sync) :
   - "tempo"  : librosa suit la pulsation du morceau (beat tracking). La balle rebondit tous les k temps,
                k étant choisi pour respecter l'écart minimum, et la phase est calée sur les temps les plus forts.
   - "onsets" : les meilleurs temps forts (attaques) du morceau, comme le mode Arcs.
2. Entre deux rebonds, la trajectoire est une parabole sous gravité constante. La plateforme est orientée
   pour transformer la vitesse d'arrivée en vitesse de départ vers le point de chute suivant.
3. Effets : apparition des plateformes, flash + onde de choc + particules à l'impact, traînée, caméra qui suit
   la balle avec tremblement, fond qui pulse sur chaque temps et petit zoom au début de chaque mesure.

Ligne de commande : python platform_render.py musique.mp3 --output ../VideoResult/plateformes.mp4
"""
import argparse
import colorsys
import math
import os
import random
import subprocess
import tempfile
from collections import deque
from dataclasses import dataclass, asdict

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import imageio_ffmpeg
import numpy as np
import pygame
from pydub import AudioSegment

from beat_render import BOUNCE_SOUND, detect_beats, hex_to_rgb
from piano import add_piano, detect_notes, note_name

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1080, 1920


@dataclass
class PlatformConfig:
    # Vidéo
    fps: int = 30
    max_duration: float = 60.0
    title: str = ""
    # Synchronisation
    sync: str = "tempo"                 # "tempo" (pulsation) ou "onsets" (attaques les plus fortes)
    min_beat_interval: float = 0.4      # secondes minimum entre deux rebonds
    selectivity: float = 0.45           # mode onsets : part des attaques les plus faibles ignorées
    sensitivity: float = 0.07           # mode onsets : seuil de détection
    beat_pulse: bool = True             # le fond pulse sur chaque temps
    bar_zoom: bool = True               # petit zoom au début de chaque mesure (4 temps)
    # Balle et trajectoire
    ball_color: str = "#ffffff"
    ball_radius: int = 26
    jump_height: int = 275              # hauteur de saut typique (pixels) : règle la gravité
    spread: int = 280                   # écart horizontal moyen entre deux plateformes
    trail_length: int = 14
    # Plateformes et couleurs
    platform_length: int = 170
    start_hue: int = 200                # teinte de la première plateforme (0-360)
    hue_step: float = 16.0              # décalage de teinte d'une plateforme à la suivante
    saturation: float = 0.75
    # Effets d'impact
    particles: int = 26
    shake: float = 14.0
    flash: bool = True
    bounce_sound: bool = False
    bounce_volume: float = -10.0
    # Piano : chaque rebond joue la note dominante de la musique à cet instant
    piano: str = "mix"                  # "off", "mix" (avec la musique) ou "solo" (piano seul)
    piano_volume: float = -4.0
    color_by_note: bool = True          # couleur de la plateforme = note jouée (une teinte par note)
    show_note_names: bool = True
    seed: int | None = None


def detect_tempo_beats(music_path, min_interval):
    """Temps de la pulsation retenus pour les rebonds, la durée du morceau et le tempo (BPM).

    On rebondit tous les k temps (k = plus petit entier respectant l'écart minimum), en choisissant
    le décalage de départ qui tombe sur les temps les plus forts.
    """
    import librosa
    y, sr = librosa.load(music_path, sr=22050, mono=True)
    envelope = librosa.onset.onset_strength(y=y, sr=sr)
    tempo, frames = librosa.beat.beat_track(onset_envelope=envelope, sr=sr)
    tempo = float(np.atleast_1d(tempo)[0])
    times = librosa.frames_to_time(frames, sr=sr)
    if len(times) < 2:
        return [], [], len(y) / sr, tempo
    period = float(np.median(np.diff(times)))
    k = max(1, math.ceil(min_interval / period - 1e-6))
    strengths = envelope[frames]
    phase = max(range(k), key=lambda p: strengths[p::k].mean() if len(strengths[p::k]) else 0)
    return [float(t) for t in times[phase::k]], [float(t) for t in times], len(y) / sr, tempo


def hue_color(hue_degrees, saturation, value=1.0):
    r, g, b = colorsys.hsv_to_rgb((hue_degrees / 360) % 1, saturation, value)
    return int(r * 255), int(g * 255), int(b * 255)


def glow_sprite(radius, color, strength=0.45):
    """Halo radial pour un collage additif (le mode additif ignore la transparence)."""
    size = radius * 4
    surf = pygame.Surface((size, size))
    for i in range(radius * 2, 0, -2):
        k = strength * (1 - i / (radius * 2)) ** 2
        pygame.draw.circle(surf, tuple(int(c * k) for c in color), (size // 2, size // 2), i)
    return surf


def plan_path(cfg, bounce_times, rng):
    """Trajectoire de la balle (segments de parabole) et plateformes (position, orientation, couleur)."""
    frames = [round(t * cfg.fps) for t in bounce_times if t > 0.6]
    if not frames:
        return [], [], 0.0
    gaps = np.diff([0] + frames)
    g = 8 * cfg.jump_height / float(np.median(gaps)) ** 2     # sommet d'une parabole de durée T : g·T²/8

    p, v = np.zeros(2), np.zeros(2)
    t0, side = 0, 1
    segments, hits = [], []
    for k, f in enumerate(frames):
        T = f - t0
        if k == 0:
            target = np.array([0.0, 0.5 * g * T * T])          # chute libre jusqu'à la première plateforme
            v_start = np.zeros(2)
        else:
            side = -side if rng.random() < 0.7 else side
            target = p + np.array([side * rng.uniform(0.6, 1.35) * cfg.spread, rng.uniform(60, 260)])
            v_start = (target - p) / T - np.array([0.0, 0.5 * g * T])
            n = v_start - v                                    # normale de la plateforme précédente
            if np.linalg.norm(n) > 1e-6:
                hits[-1]["normal"] = n / np.linalg.norm(n)
        segments.append((t0, p.copy(), v_start.copy(), g, f))
        v = v_start + np.array([0.0, g * T])
        p = target
        t0 = f
        hits.append({"frame": f, "pos": p.copy(), "normal": np.array([0.0, -1.0]),
                     "color": hue_color(cfg.start_hue + cfg.hue_step * k, cfg.saturation)})
    # Après le dernier rebond, la balle repart et continue de tomber (elle ne s'arrête jamais)
    last = hits[-1]["normal"]
    segments.append((t0, p.copy(), v - 2 * np.dot(v, last) * last, g, math.inf))
    return segments, hits, g


def ball_position(segments, frame):
    for t0, p, v, g, t1 in segments:
        if frame <= t1:
            t = frame - t0
            return p + v * t + np.array([0.0, 0.5 * g * t * t])
    return segments[-1][1]


def render(music_path, output, cfg: PlatformConfig, progress=lambda done, total: None, log=print):
    rng = random.Random(cfg.seed)
    log("🎵 Analyse du tempo...")
    tempo = None
    if cfg.sync == "onsets":
        bounce_times, music_duration = detect_beats(music_path, cfg.sensitivity, cfg.min_beat_interval, cfg.selectivity)
        pulse_times = bounce_times
    else:
        bounce_times, pulse_times, music_duration, tempo = detect_tempo_beats(music_path, cfg.min_beat_interval)
    duration = min(music_duration, cfg.max_duration)
    bounce_times = [t for t in bounce_times if t < duration - 0.2]
    if not bounce_times:
        raise ValueError("Aucun temps détecté dans ce morceau.")
    log(f"   {len(bounce_times)} rebonds" + (f" à {tempo:.0f} BPM" if tempo else ""))

    segments, hits, _ = plan_path(cfg, bounce_times, rng)
    if cfg.piano != "off" or cfg.color_by_note or cfg.show_note_names:
        log("🎹 Détection des notes...")
        for h, midi in zip(hits, detect_notes(music_path, [h["frame"] / cfg.fps for h in hits])):
            h["note"] = midi
            if cfg.color_by_note:
                # 12 notes réparties sur le cercle des couleurs ; les octaves aiguës sont plus claires
                h["color"] = hue_color(cfg.start_hue + 30 * (midi % 12), cfg.saturation * (1.1 - (midi - 48) / 72))
    pulse_frames = {round(t * cfg.fps) for t in pulse_times}
    bar_frames = {round(t * cfg.fps) for t in pulse_times[::4]}

    pygame.init()
    screen = pygame.display.set_mode((W, H))
    title_font = pygame.font.SysFont("Arial", 72, bold=True)
    note_font = pygame.font.SysFont("Arial", 40, bold=True)
    ball_rgb = hex_to_rgb(cfg.ball_color)
    ball_glow = glow_sprite(cfg.ball_radius, ball_rgb)
    platform_glows = {}
    trail = deque(maxlen=max(1, cfg.trail_length))
    particles, rings = [], []
    cam = np.array([0.0, 0.0])
    shake = flash = pulse = zoom_kick = 0.0
    hit_index = 0
    total = int(duration * cfg.fps)

    with tempfile.TemporaryDirectory() as tmp:
        silent = os.path.join(tmp, "video.mp4")
        audio = os.path.join(tmp, "audio.wav")
        writer = imageio_ffmpeg.write_frames(silent, (W, H), fps=cfg.fps, codec="libx264", pix_fmt_out="yuv420p",
                                             quality=7, macro_block_size=1)
        writer.send(None)
        decay = 30 / cfg.fps                                   # les effets durent pareil à 30 ou 60 ips
        for frame in range(total):
            ball = ball_position(segments, frame)

            while hit_index < len(hits) and hits[hit_index]["frame"] <= frame:
                h = hits[hit_index]
                for _ in range(cfg.particles):
                    a = rng.uniform(0, 2 * math.pi)
                    s = rng.uniform(4, 16) * decay
                    particles.append([h["pos"].copy(), np.array([math.cos(a) * s, math.sin(a) * s]) + h["normal"] * 6 * decay,
                                      rng.uniform(0.5, 1.0), h["color"]])
                rings.append([h["pos"].copy(), 0.0, h["color"]])
                shake = cfg.shake
                if cfg.flash:
                    flash = 1.0
                hit_index += 1
            if cfg.beat_pulse and frame in pulse_frames:
                pulse = 1.0
            if cfg.bar_zoom and frame in bar_frames:
                zoom_kick = 1.0

            # Caméra : suit la balle en douceur ; zoom bref au début de chaque mesure
            cam += (ball + np.array([0.0, 120.0]) - cam) * (0.12 * decay)
            zoom = 1 + 0.06 * zoom_kick
            jitter = np.array([rng.uniform(-1, 1), rng.uniform(-1, 1)]) * shake
            center = np.array([W / 2, H / 2])

            def to_screen(q):
                s = (q - cam) * zoom + center + jitter
                return int(s[0]), int(s[1])

            shake *= 0.82 ** decay
            flash *= 0.85 ** decay
            pulse *= 0.8 ** decay
            zoom_kick *= 0.82 ** decay

            current = hits[max(hit_index - 1, 0)]["color"]
            hue, _, _ = colorsys.rgb_to_hsv(*(c / 255 for c in current))
            screen.fill(hue_color(hue * 360, 0.6, 0.08 + 0.10 * flash + 0.05 * pulse))

            for h in hits:
                dt = (frame - h["frame"]) / cfg.fps
                if dt < -0.45 or dt > 2.5:
                    continue
                grow = 1 - (1 - min(1.0, (dt + 0.45) / 0.45)) ** 3
                fade = 1.0 if dt < 0.6 else max(0.0, 1 - (dt - 0.6) / 1.9)
                n = h["normal"]
                tangent = np.array([-n[1], n[0]])
                mid = h["pos"] - n * (cfg.ball_radius + 7)
                half = tangent * cfg.platform_length / 2 * grow
                white = 0 <= dt < 0.12
                color = tuple(int((255 if white else c) * fade) for c in h["color"])
                width = max(2, int(14 * zoom))
                pygame.draw.line(screen, color, to_screen(mid - half), to_screen(mid + half), width)
                for end in (mid - half, mid + half):
                    pygame.draw.circle(screen, color, to_screen(end), width // 2)
                if cfg.show_note_names and "note" in h and grow > 0.5:
                    label = note_font.render(note_name(h["note"]), True, tuple(int(c * fade) for c in h["color"]))
                    screen.blit(label, label.get_rect(center=to_screen(mid - n * 46)))
                if 0 <= dt < 0.4:
                    glow = platform_glows.setdefault(h["color"], glow_sprite(60, h["color"]))
                    screen.blit(glow, glow.get_rect(center=to_screen(mid)), special_flags=pygame.BLEND_ADD)

            for ring in rings:
                ring[1] += decay
                alpha = max(0.0, 1 - ring[1] / 14)
                if alpha > 0:
                    pygame.draw.circle(screen, tuple(int(c * alpha) for c in ring[2]), to_screen(ring[0]),
                                       int((30 + ring[1] * 14) * zoom), 4)
            rings[:] = [r for r in rings if r[1] < 14]

            for part in particles:
                part[0] += part[1]
                part[1] = part[1] * 0.92 ** decay + np.array([0.0, 0.6 * decay * decay])
                part[2] -= 0.04 * decay
                if part[2] > 0:
                    pygame.draw.circle(screen, tuple(int(c * part[2]) for c in part[3]), to_screen(part[0]),
                                       max(1, int(6 * part[2] * zoom)))
            particles[:] = [p for p in particles if p[2] > 0]

            trail.appendleft(ball.copy())
            for i, q in enumerate(trail):
                k = 1 - i / len(trail)
                pygame.draw.circle(screen, tuple(int(c * k * 0.6) for c in ball_rgb), to_screen(q),
                                   max(2, int(cfg.ball_radius * k * zoom)))
            screen.blit(ball_glow, ball_glow.get_rect(center=to_screen(ball)), special_flags=pygame.BLEND_ADD)
            pygame.draw.circle(screen, ball_rgb, to_screen(ball), int(cfg.ball_radius * zoom))

            if cfg.title:
                text = title_font.render(cfg.title, True, (255, 255, 255))
                screen.blit(text, text.get_rect(center=(W / 2, 260)))

            writer.send(pygame.image.tostring(screen, "RGB"))
            if (frame + 1) % cfg.fps == 0:
                progress(frame + 1, total)
        writer.close()
        pygame.quit()

        log("🔊 Bande-son...")
        track = AudioSegment.from_file(music_path)[:int(duration * 1000)]
        if cfg.piano in ("mix", "solo"):
            track = add_piano(track, [h["note"] for h in hits], [h["frame"] * 1000 / cfg.fps for h in hits],
                              cfg.piano, cfg.piano_volume)
        if cfg.bounce_sound:
            bounce = AudioSegment.from_file(BOUNCE_SOUND) + cfg.bounce_volume
            for h in hits:
                track = track.overlay(bounce, position=int(h["frame"] * 1000 / cfg.fps))
        track.export(audio, format="wav")

        log("🎬 Fusion audio + vidéo...")
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", silent, "-i", audio,
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", output], check=True)
    progress(total, total)
    return {"beats": len(bounce_times), "bounces": len(hits), "duration": total / cfg.fps,
            "tempo": round(tempo) if tempo else None, "scores": {},
            "notes": [note_name(h["note"]) for h in hits if "note" in h][:200]}


def main():
    parser = argparse.ArgumentParser(description="Vidéo TikTok : balle qui rebondit sur des plateformes au tempo.")
    parser.add_argument("music")
    parser.add_argument("--output", default=os.path.join(os.path.dirname(HERE), "VideoResult", "plateformes.mp4"))
    for name, value in asdict(PlatformConfig()).items():
        if isinstance(value, (int, float, str)) and not isinstance(value, bool):
            parser.add_argument("--" + name.replace("_", "-"), type=type(value), default=value)
    parser.add_argument("--seed", type=int, default=None)
    args = vars(parser.parse_args())
    music, output = args.pop("music"), args.pop("output")
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    print(render(music, output, PlatformConfig(**args), progress=lambda d, t: print(f"   {d}/{t} images", end="\r")))


if __name__ == "__main__":
    main()
