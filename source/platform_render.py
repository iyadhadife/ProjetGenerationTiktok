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
from piano import add_piano, add_transcription, detect_chords, detect_notes, note_name

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1080, 1920


@dataclass
class PlatformConfig:
    # Vidéo
    fps: int = 60
    max_duration: float = 60.0
    title: str = ""
    # Synchronisation
    sync: str = "notes"                 # "notes" (chaque note / accord transcrit), "tempo" (pulsation) ou "onsets"
    # Mode notes : moteur de transcription. "sheetsage2" (précis, ~2 min de calcul par minute de musique,
    # licence non commerciale) ou "basic_pitch" (rapide, moins précis sur les morceaux à plusieurs instruments)
    engine: str = "sheetsage2"
    note_min_gap: float = 0.07          # mode notes : écart minimum entre deux rebonds (notes plus proches regroupées)
    min_beat_interval: float = 0.4      # modes tempo / onsets : secondes minimum entre deux rebonds
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
    # Piano : chaque rebond joue l'accord (ou la note) détecté dans la musique à cet instant
    piano: str = "solo"                 # "off", "mix" (avec la musique) ou "solo" (piano seul, sans la musique)
    piano_voicing: str = "chord"        # "chord" (accord détecté + basse) ou "note" (note dominante seule)
    piano_volume: float = -4.0
    color_by_note: bool = True          # couleur de la plateforme = note ou fondamentale de l'accord
    show_note_names: bool = True
    # Mode notes : ce que joue le piano (et donc les rebonds)
    piano_content: str = "melody_chords"   # "melody" (mélodie seule), "melody_chords" (+ accords doux) ou "all"
    melody_selectivity: float = 0.1        # part des notes de mélodie les moins marquantes ignorées
    # Vitesse de lecture : 0.5 = deux fois plus lent (notes, rebonds et musique ralentis, sans changer la hauteur)
    playback_speed: float = 1.0
    # Avance de l'image sur le son (s) : l'œil perçoit le rebond un peu après le contact, et l'impact est
    # arrondi à l'image près ; montrer le contact légèrement en avance le fait tomber pile sur la note
    visual_lead: float = 0.06
    # Partition MIDI fournie (chemin, rempli par l'API) : utilisée si elle colle à l'enregistrement
    score_path: str = ""
    score_max_cost: float = 0.35         # au-delà, la partition est jugée différente du morceau
    seed: int | None = None


def slowed_music(music_path, speed, folder):
    """Copie ralentie (ou accélérée) du morceau, à hauteur constante (filtre atempo de ffmpeg)."""
    if abs(speed - 1) < 1e-3:
        return music_path
    filters, rest = [], speed
    while rest < 0.5:                                       # atempo accepte 0.5 à 2 : on enchaîne si besoin
        filters.append("atempo=0.5")
        rest /= 0.5
    filters.append(f"atempo={rest:.4f}")
    path = os.path.join(folder, "music_slow.wav")
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", music_path,
                    "-filter:a", ",".join(filters), path], check=True)
    return path


def accompaniment(all_notes, melody):
    """Accords doux sous la mélodie : l'accord de l'ensemble, rejoué seulement quand il change."""
    from piano import CHORD_TYPES, _voice
    from transcribe import Note, chords_under
    times = [n.start for n in melody]
    chords = chords_under(all_notes, times)
    changes = [(t, c) for i, (t, c) in enumerate(zip(times, chords)) if c and (i == 0 or c != chords[i - 1])]
    result, previous = [], None
    for k, (t, (root, quality)) in enumerate(changes):
        end = min(changes[k + 1][0] if k + 1 < len(changes) else t + 2.0, t + 2.5)
        voicing = _voice([(root + i) % 12 for i in CHORD_TYPES[quality]], previous)
        previous = voicing
        # Accords dans le grave-médium, sous la mélodie, et plus doux qu'elle
        for midi in [36 + (root - 36) % 12] + [m - 12 for m in voicing]:
            result.append(Note(t, end, midi, 0.3))
    return result


class PitchSalience:
    """Présence de chaque note (MIDI) dans le morceau au cours du temps, pour vérifier la partition.

    Spectre à demi-ton près (CQT) sur la partie harmonique du morceau (sans la batterie), en dB.
    `attack(midi, t)` mesure combien la note se renforce juste après t : élevé si la note y est attaquée.
    """
    LOW = 24                                                 # C1

    def __init__(self, music_path, span):
        import librosa
        self.sr, self.hop = 22050, 256
        y, _ = librosa.load(music_path, sr=self.sr, mono=True, duration=span + 1)
        harmonic = librosa.effects.harmonic(y, margin=2.0)
        cqt = np.abs(librosa.cqt(harmonic, sr=self.sr, hop_length=self.hop, fmin=librosa.midi_to_hz(self.LOW),
                                 n_bins=84, bins_per_octave=12))
        self.db = librosa.amplitude_to_db(cqt, ref=np.max)
        self.onsets = librosa.onset.onset_detect(y=y, sr=self.sr, hop_length=self.hop, units="time")

    def _band(self, midi, t0, t1):
        b = int(midi) - self.LOW
        if not 0 <= b < self.db.shape[0]:
            return -80.0
        f0, f1 = int(t0 * self.sr / self.hop), int(t1 * self.sr / self.hop)
        f0, f1 = max(f0, 0), min(max(f1, f0 + 1), self.db.shape[1])
        return float(self.db[b, f0:f1].mean()) if f1 > f0 else -80.0

    def attack(self, midi, t, width=0.07):
        return self._band(midi, t + 0.01, t + width) - self._band(midi, t - width, t - 0.01)

    def presence(self, midi, t, width=0.1):
        return self._band(midi, t + 0.01, t + width)


def refine_melody(sal, notes, window=0.12, min_gap=0.085):
    """Recale la mélodie sur l'audio, note par note, en tenant compte de sa hauteur.

    Sheet Sage 2 aligne ses notes sur une grille de doubles croches déduite des temps : quand cette grille
    dérive, une note arrive en retard, ou deux notes voisines sont jouées dans le mauvais ordre.
    1. Ordre : si deux notes successives « collent » mieux à l'audio échangées, on les échange.
    2. Moment : chaque note va sur l'attaque réelle voisine (±window) où SA hauteur apparaît le plus nettement,
       sans jamais s'approcher à moins de min_gap de ses voisines (les traits rapides restent distincts).
    """
    notes = sorted(notes, key=lambda n: n.start)
    swapped = 0
    for i in range(len(notes) - 1):
        a, b = notes[i], notes[i + 1]
        if a.midi == b.midi or b.start - a.start > 0.4:
            continue
        keep = sal.presence(a.midi, a.start) + sal.presence(b.midi, b.start)
        swap = sal.presence(b.midi, a.start) + sal.presence(a.midi, b.start)
        if swap > keep + 6:                                  # nettement mieux échangées (6 dB)
            notes[i] = type(a)(a.start, a.end, b.midi, a.velocity)
            notes[i + 1] = type(b)(b.start, b.end, a.midi, b.velocity)
            swapped += 1
    moved, result = 0, []
    starts = [n.start for n in notes]
    for i, n in enumerate(notes):
        before = result[-1].start if result else -math.inf
        after = starts[i + 1] if i + 1 < len(notes) else math.inf
        candidates = [t for t in sal.onsets if abs(t - n.start) <= window
                      and t - before >= min_gap and after - t >= min_gap]
        best, best_score = n.start, sal.attack(n.midi, n.start) - 1.0   # petit bonus à ne pas bouger
        for t in candidates:
            score = sal.attack(n.midi, t) - 20 * abs(t - n.start)        # préfère l'attaque la plus proche
            if score > best_score:
                best, best_score = t, score
        moved += abs(best - n.start) > 0.02
        shift = best - n.start
        result.append(type(n)(best, max(n.end + shift, best + 0.05), n.midi, n.velocity))
    return result, moved, swapped


def snap_to_onsets(sal, notes, window=0.08):
    """Recale des accords sur l'attaque réelle la plus proche (toutes les notes d'un accord ensemble)."""
    if not len(sal.onsets):
        return notes
    result, shifts = [], {}
    for n in notes:
        key = round(n.start, 2)
        if key not in shifts:
            nearest = sal.onsets[np.argmin(np.abs(sal.onsets - n.start))]
            shifts[key] = nearest - n.start if abs(nearest - n.start) <= window else 0.0
        shift = shifts[key]
        result.append(type(n)(n.start + shift, max(n.end + shift, n.start + shift + 0.05), n.midi, n.velocity))
    return result


def _chord_roots(chord_labels):
    """[(début, fin, classe de la fondamentale)] à partir des étiquettes « D:min », « Bb:maj7/5 »..."""
    names = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    roots = []
    for start, end, label in chord_labels:
        root = label.split(":")[0]
        if root and root[0] in names:
            pc = names[root[0]] + root[1:].count("#") - root[1:].count("b")
            roots.append((start, end, pc % 12))
    return roots


def detect_tempo_beats(music_path, min_interval):
    """Temps de la pulsation retenus pour les rebonds, la durée du morceau et le tempo médian (BPM).

    Le tempo est estimé au cours du temps : la grille de temps suit les accélérations et ralentissements.
    On rebondit environ tous les k temps (pour respecter l'écart minimum), en partant du décalage qui tombe
    sur les temps les plus forts.
    """
    import librosa
    y, sr = librosa.load(music_path, sr=22050, mono=True)
    envelope = librosa.onset.onset_strength(y=y, sr=sr)
    tempo_curve = librosa.feature.tempo(onset_envelope=envelope, sr=sr, aggregate=None, std_bpm=4.0)
    # Lissage sur ~4 s : on suit les vrais changements de tempo sans réagir à chaque fill de batterie
    window = max(1, int(4 * sr / 512))
    tempo_curve = np.convolve(np.pad(tempo_curve, window // 2, mode="edge"), np.ones(window) / window, "valid")[:len(envelope)]
    _, frames = librosa.beat.beat_track(onset_envelope=envelope, sr=sr, bpm=tempo_curve)
    times = librosa.frames_to_time(frames, sr=sr)
    tempo = float(np.median(tempo_curve))
    if len(times) < 2:
        return [], [], len(y) / sr, tempo
    period = float(np.median(np.diff(times)))
    k = max(1, math.ceil(min_interval / period - 1e-6))
    strengths = envelope[frames]
    phase = max(range(k), key=lambda p: strengths[p::k].mean() if len(strengths[p::k]) else 0)
    # Le tempo pouvant varier, on garde un temps dès que l'écart minimum est respecté (à 10 % près)
    bounces, last = [], -math.inf
    for t in times[phase:]:
        if t - last >= min_interval * 0.9:
            bounces.append(float(t))
            last = t
    return bounces, [float(t) for t in times], len(y) / sr, tempo


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
    """Trajectoire de la balle (segments de parabole) et plateformes (position, orientation, couleur).

    Chaque plateforme garde l'indice du rebond d'origine ("index") pour retrouver ses notes.
    Les instants sont en images *fractionnaires* : le contact a lieu à l'instant exact de la note, et non à
    l'image la plus proche ; chaque image montre la balle à sa vraie position, juste avant ou après le choc.
    """
    indexed, last = [], 0
    for i, t in enumerate(bounce_times):
        f = (t - cfg.visual_lead) * cfg.fps
        if t > 0.3 and f >= last + 2:                        # au moins 2 images entre deux rebonds
            indexed.append((i, f))
            last = f
    if not indexed:
        return [], [], 0.0
    frames = [f for _, f in indexed]
    gaps = np.diff([0] + frames)
    typical = float(np.median(gaps))
    g = 8 * cfg.jump_height / typical ** 2                   # sommet d'une parabole de durée T : g·T²/8

    # Pendant une pause de la musique, un seul saut enverrait la balle hors de l'écran : on ajoute des
    # rebonds silencieux (index None, plateformes discrètes, sans note) pour garder un rythme naturel
    filled, previous = [], 0
    for index, f in indexed:
        gap = f - previous
        if previous and gap > 1.8 * typical:
            pieces = math.ceil(gap / (1.2 * typical))
            for k in range(1, pieces):
                filled.append((None, previous + gap * k / pieces))
        filled.append((index, f))
        previous = f
    indexed = filled

    p, v = np.zeros(2), np.zeros(2)
    t0, side = 0, 1
    segments, hits = [], []
    for k, (index, f) in enumerate(indexed):
        T = f - t0
        if k == 0:
            target = np.array([0.0, 0.5 * g * T * T])          # chute libre jusqu'à la première plateforme
            v_start = np.zeros(2)
        else:
            side = -side if rng.random() < 0.7 else side
            # Un rebond rapide fait un petit saut, un rebond lent un grand : la vitesse reste naturelle
            scale = float(np.clip(T / typical, 0.35, 1.6))
            target = p + np.array([side * rng.uniform(0.6, 1.35) * cfg.spread, rng.uniform(60, 260)]) * scale
            v_start = (target - p) / T - np.array([0.0, 0.5 * g * T])
            n = v_start - v                                    # normale de la plateforme précédente
            if np.linalg.norm(n) > 1e-6:
                hits[-1]["normal"] = n / np.linalg.norm(n)
        segments.append((t0, p.copy(), v_start.copy(), g, f))
        v = v_start + np.array([0.0, g * T])
        p = target
        t0 = f
        hits.append({"frame": f, "index": index, "pos": p.copy(), "normal": np.array([0.0, -1.0]),
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
    if cfg.sync != "notes":
        log("🎵 Analyse du rythme...")
    cfg.piano_voicing = cfg.piano_voicing if cfg.piano_voicing in ("chord", "note") else "chord"
    tempo = None
    notes, events = [], []
    bar_times = None
    speed = min(max(cfg.playback_speed, 0.25), 1.0)
    if cfg.sync == "notes" and cfg.engine == "sheetsage2":
        import librosa
        from sheetsage_client import sheetsage_transcribe
        from transcribe import Event, Note, group_events
        music_duration = librosa.get_duration(path=music_path)
        span = min(music_duration, cfg.max_duration * speed)
        sheet = None
        if cfg.score_path:
            from score_align import load_aligned_score
            log("📄 Partition fournie : alignement sur l'enregistrement...")
            aligned = load_aligned_score(cfg.score_path, music_path, span, log=log)
            if aligned and aligned["cost"] <= cfg.score_max_cost and aligned["match"] >= 0.5 and aligned["melody"]:
                log(f"   partition utilisée (écart d'alignement {aligned['cost']:.2f}, "
                    f"{aligned['match']:.0%} des notes retrouvées dans l'audio)")
                sheet = {**aligned, "chord_labels": [], "source": "partition"}
                melody, chord_notes = aligned["melody"], aligned["chords"]
            elif aligned:
                log(f"   la partition ne correspond pas assez au morceau (écart {aligned['cost']:.2f}, "
                    f"{aligned['match']:.0%} des notes retrouvées) : transcription automatique")
        if sheet is None:
            log(f"🎼 Transcription Sheet Sage 2 de {span:.0f} s de musique (environ {max(1, round(span * 2 / 60))} min "
                "la première fois, immédiat ensuite)...")
            sheet = sheetsage_transcribe(music_path, span)
            melody = [Note(*n) for n in sheet["melody"]]
            chord_notes = [Note(s, e, m, v * 0.45) for s, e, m, v in sheet["chords"]]
        log("   vérification de la partition sur l'audio (ordre et moment de chaque note)...")
        sal = PitchSalience(music_path, span)
        # Partition : notes justes mais calage plus approximatif (±0,2 s) ; transcription : l'inverse (±0,12 s)
        melody, moved, swapped = refine_melody(sal, melody, window=0.2 if sheet.get("source") else 0.12,
                                               min_gap=max(cfg.note_min_gap, 2 / cfg.fps) + 0.015)
        chord_notes = snap_to_onsets(sal, chord_notes)
        status = ("partition alignée" if sheet.get("source") else
                  "résultat en cache" if sheet.get("cached") else f"transcrit en {sheet.get('elapsed')} s")
        log(f"   {status} : tonalité {sheet.get('key', '?')}, {len(melody)} notes de mélodie, "
            f"{len(sheet['chord_labels']) or len({round(n.start, 1) for n in chord_notes})} accords, {moved} notes recalées, {swapped} paires remises dans l'ordre")
        min_gap = max(cfg.note_min_gap, 2 / cfg.fps) * speed
        events = group_events(melody, min_gap=min_gap)
        roots = _chord_roots(sheet["chord_labels"])
        for event in events:
            # Plateforme : nom de la note jouée, couleur de l'accord en cours
            event.label = note_name(max(event.notes))
            event.root = next((r for s, e, r in roots if s <= event.time < e), event.notes[0] % 12)
        if cfg.piano_content == "all":
            notes = melody + [Note(s, e, m, v / 0.45) for s, e, m, v in chord_notes]
        else:
            notes = melody + (chord_notes if cfg.piano_content == "melody_chords" else [])
        bounce_times = [e.time for e in events]
        pulse_times = list(sheet["beats"]) or bounce_times
        bar_times = list(sheet["downbeats"]) or None
        log(f"   {len(events)} rebonds")
    elif cfg.sync == "notes":
        import librosa
        from transcribe import Event, extract_melody, group_events, transcribe
        log("🎼 Transcription des notes et accords (Basic Pitch)...")
        music_duration = librosa.get_duration(path=music_path)
        all_notes = [n for n in transcribe(music_path) if n.start < min(music_duration, cfg.max_duration * speed)]
        # Écart mesuré dans la vidéo finale : ralentir sépare donc des notes qui partageaient un rebond
        min_gap = max(cfg.note_min_gap, 2 / cfg.fps) * speed
        if cfg.piano_content == "all":
            notes = all_notes
            events = group_events(notes, min_gap=min_gap)
        else:
            melody = extract_melody(all_notes, min_gap=min_gap, selectivity=cfg.melody_selectivity)
            events = [Event(n.start, [n.midi], n.velocity, note_name(n.midi), n.midi % 12) for n in melody]
            notes = list(melody)
            if cfg.piano_content == "melody_chords":
                notes += accompaniment(all_notes, melody)
            log(f"   mélodie extraite : {len(melody)} notes sur {len(all_notes)} transcrites")
        bounce_times = [e.time for e in events]
        # Le fond pulse sur les notes et accords les plus appuyés (le quart le plus fort)
        loud = np.percentile([e.velocity for e in events], 75) if events else 0
        pulse_times = [e.time for e in events if e.velocity >= loud]
        log(f"   {len(notes)} notes regroupées en {len(events)} rebonds")
    elif cfg.sync == "onsets":
        bounce_times, music_duration = detect_beats(music_path, cfg.sensitivity, cfg.min_beat_interval * speed, cfg.selectivity)
        pulse_times = bounce_times
    else:
        bounce_times, pulse_times, music_duration, tempo = detect_tempo_beats(music_path, cfg.min_beat_interval * speed)
    if speed != 1.0:
        # Tout est étiré dans le temps : la vidéo dure 1/speed fois plus longtemps
        stretch = 1 / speed
        bounce_times = [t * stretch for t in bounce_times]
        pulse_times = [t * stretch for t in pulse_times]
        bar_times = [t * stretch for t in bar_times] if bar_times else None
        notes = [type(n)(n.start * stretch, n.end * stretch, n.midi, n.velocity) for n in notes]
        music_duration *= stretch
        tempo = tempo * speed if tempo else tempo
        log(f"   lecture à ×{speed:g}")
    duration = min(music_duration, cfg.max_duration)
    bounce_times = [t for t in bounce_times if t < duration - 0.2]
    if not bounce_times:
        raise ValueError("Aucun temps détecté dans ce morceau.")
    if not events:
        log(f"   {len(bounce_times)} rebonds" + (f" à {tempo:.0f} BPM" if tempo else ""))

    segments, hits, _ = plan_path(cfg, bounce_times, rng)
    if events:
        for h in hits:
            if h["index"] is None:                         # rebond silencieux pendant une pause
                h["silent"] = True
                h["color"] = tuple(int(c * 0.45) for c in h["color"])
                continue
            event = events[h["index"]]
            h["notes"], h["label"] = event.notes, event.label
            if cfg.color_by_note:
                h["color"] = hue_color(cfg.start_hue + 30 * event.root, cfg.saturation)
    elif cfg.piano != "off" or cfg.color_by_note or cfg.show_note_names:
        times = [h["frame"] / cfg.fps + cfg.visual_lead for h in hits]
        if cfg.piano_voicing == "chord":
            log("🎹 Détection des accords...")
            for h, chord in zip(hits, detect_chords(music_path, times)):
                h["notes"], h["label"] = chord["notes"], chord["name"]
                if cfg.color_by_note:
                    h["color"] = hue_color(cfg.start_hue + 30 * chord["root"], cfg.saturation)
        else:
            log("🎹 Détection des notes...")
            for h, midi in zip(hits, detect_notes(music_path, times)):
                h["notes"], h["label"] = [midi], note_name(midi)
                if cfg.color_by_note:
                    # 12 notes réparties sur le cercle des couleurs ; les octaves aiguës sont plus claires
                    h["color"] = hue_color(cfg.start_hue + 30 * (midi % 12), cfg.saturation * (1.1 - (midi - 48) / 72))
    pulse_frames = {round((t - cfg.visual_lead) * cfg.fps) for t in pulse_times}
    bar_frames = {round((t - cfg.visual_lead) * cfg.fps) for t in (bar_times if bar_times else pulse_times[::4])}

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
                quiet = h.get("silent", False)
                for _ in range(cfg.particles // 3 if quiet else cfg.particles):
                    a = rng.uniform(0, 2 * math.pi)
                    s = rng.uniform(4, 16) * decay
                    particles.append([h["pos"].copy(), np.array([math.cos(a) * s, math.sin(a) * s]) + h["normal"] * 6 * decay,
                                      rng.uniform(0.5, 1.0), h["color"]])
                hit_index += 1
                if quiet:
                    continue                                   # rebond discret : ni onde, ni flash, ni tremblement
                rings.append([h["pos"].copy(), 0.0, h["color"]])
                shake = cfg.shake
                if cfg.flash:
                    flash = 1.0
            if cfg.beat_pulse and frame in pulse_frames:
                pulse = 1.0
            if cfg.bar_zoom and frame in bar_frames:
                zoom_kick = 1.0

            # Caméra : suit la balle en douceur ; zoom bref au début de chaque mesure
            cam += (ball + np.array([0.0, 120.0]) - cam) * min(1.0, 0.25 * decay)
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
                white = 0 <= dt < 0.12 and not h.get("silent")
                color = tuple(int((255 if white else c) * fade) for c in h["color"])
                width = max(2, int(14 * zoom))
                pygame.draw.line(screen, color, to_screen(mid - half), to_screen(mid + half), width)
                for end in (mid - half, mid + half):
                    pygame.draw.circle(screen, color, to_screen(end), width // 2)
                if cfg.show_note_names and "label" in h and grow > 0.5:
                    label = note_font.render(h["label"], True, tuple(int(c * fade) for c in h["color"]))
                    screen.blit(label, label.get_rect(center=to_screen(mid - n * 46)))
                if 0 <= dt < 0.4 and not h.get("silent"):
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
        track = AudioSegment.from_file(slowed_music(music_path, speed, tmp))[:int(duration * 1000)]
        if cfg.piano in ("mix", "solo") and notes:
            log("🎹 Piano : toutes les notes transcrites...")
            track = add_transcription(track, notes, cfg.piano, cfg.piano_volume)
        elif cfg.piano in ("mix", "solo"):
            sounding = [h for h in hits if "notes" in h]
            track = add_piano(track, [h["notes"] for h in sounding], [(h["frame"] / cfg.fps + cfg.visual_lead) * 1000 for h in sounding],
                              cfg.piano, cfg.piano_volume)
        if cfg.bounce_sound:
            bounce = AudioSegment.from_file(BOUNCE_SOUND) + cfg.bounce_volume
            for h in hits:
                if not h.get("silent"):
                    track = track.overlay(bounce, position=int((h["frame"] / cfg.fps + cfg.visual_lead) * 1000))
        track.export(audio, format="wav")

        log("🎬 Fusion audio + vidéo...")
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", silent, "-i", audio,
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", output], check=True)
    progress(total, total)
    return {"beats": len(bounce_times), "bounces": sum(1 for h in hits if not h.get("silent")), "duration": total / cfg.fps,
            "tempo": round(tempo) if tempo else None, "scores": {},
            "notes": [h["label"] for h in hits if "label" in h][:200]}


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
