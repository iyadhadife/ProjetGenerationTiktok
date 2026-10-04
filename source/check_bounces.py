"""
Vérifie le comportement du moteur sans générer de vidéo : temps forts retenus, gravité réellement
appliquée et vitesse minimale des balles (aucune balle ne doit rester immobile).

Usage : python check_bounces.py musique.mp3 [--fps 60] [--duration 30]
"""
import argparse
import math

import numpy as np

from beat_render import Config, Scene, detect_beats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("music")
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--duration", type=float, default=30)
    args = parser.parse_args()

    cfg = Config(fps=args.fps, seed=1)
    raw, _ = detect_beats(args.music, cfg.sensitivity, 0, 0)
    beats, music_duration = detect_beats(args.music, cfg.sensitivity, cfg.min_beat_interval, cfg.selectivity)
    duration = min(music_duration, args.duration)
    beats = [t for t in beats if t < duration]
    raw = [t for t in raw if t < duration]
    print(f"Temps forts détectés : {len(raw)} ({len(raw) / duration:.1f}/s) -> retenus : {len(beats)} ({len(beats) / duration:.1f}/s)")

    scene = Scene(cfg, beats)
    plans, reduced, speeds, prev = set(), 0, [], {}
    for frame in range(int(duration * cfg.fps)):
        scene.step(frame)
        for i, ball in enumerate(scene.balls):
            if not ball.free and ball.plan not in plans:
                plans.add(ball.plan)
                reduced += ball.plan[5] < scene.g - 1e-9
            if i in prev:
                speeds.append(math.hypot(ball.x - prev[i][0], ball.y - prev[i][1]) * cfg.fps / 60)
            prev[i] = (ball.x, ball.y)
        if not scene.arcs:
            break
    speeds = np.array(speeds)
    print(f"Trajectoires : {len(plans)}, dont {reduced} avec gravité réduite ({100 * reduced / max(len(plans), 1):.0f} %)")
    print(f"Vitesse des balles (px/image à 60 ips) : min {speeds.min():.2f}, 1er centile {np.percentile(speeds, 1):.2f}, médiane {np.median(speeds):.1f}")
    print(f"Images où une balle bouge de moins de 0,5 px : {(speeds < 0.5).sum()} sur {len(speeds)}")
    print("Scores :", {b.name: b.score for b in scene.balls}, "| arcs restants :", len(scene.arcs))


if __name__ == "__main__":
    main()
