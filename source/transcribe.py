"""
Transcription de la musique en notes (Basic Pitch, Spotify), puis regroupement en événements :
un événement = une note seule ou un accord (notes qui commencent ensemble) = un rebond.

Sur un morceau à plusieurs instruments, extract_melody garde seulement la mélodie principale
et chords_under donne l'accord joué par l'ensemble, pour un accompagnement léger.

Le piano rejoue ensuite toutes les notes transcrites, avec leur vraie durée et leur intensité :
la musique reste reconnaissable.
"""
import os
from dataclasses import dataclass, field

import numpy as np

from piano import CHORD_TYPES, chord_name, note_name


@dataclass
class Note:
    start: float
    end: float
    midi: int
    velocity: float            # 0 à 1


@dataclass
class Event:
    time: float
    notes: list = field(default_factory=list)      # notes MIDI qui démarrent sur ce rebond
    velocity: float = 0.0
    label: str = ""
    root: int = 0                                   # classe de note pour la couleur (0 = C)


def transcribe(music_path):
    """Toutes les notes du morceau, triées par début (modèle ONNX : pas besoin de TensorFlow)."""
    from basic_pitch import ICASSP_2022_MODEL_PATH
    from basic_pitch.inference import predict
    model = os.path.join(os.path.dirname(ICASSP_2022_MODEL_PATH), "nmp.onnx")
    _, _, raw = predict(music_path, model, minimum_note_length=80)
    notes = [Note(float(s), float(e), int(p), float(a)) for s, e, p, a, *_ in raw]
    notes.sort(key=lambda n: (n.start, n.midi))
    return notes


def _label(midis):
    """Nom de l'accord si les notes en forment un, sinon nom de la note la plus aiguë (souvent la mélodie)."""
    classes = {m % 12 for m in midis}
    if len(classes) >= 3:
        best, best_score = None, 0
        for root in range(12):
            for quality, intervals in CHORD_TYPES.items():
                chord = {(root + i) % 12 for i in intervals}
                score = len(chord & classes) - 0.5 * len(classes - chord)
                if score > best_score:
                    best, best_score = (root, quality), score
        if best and best_score >= 2.5:
            return chord_name(*best), best[0]
    top = max(midis)
    return note_name(top), top % 12


def group_events(notes, together=0.06, min_gap=0.15):
    """Regroupe les notes en rebonds.

    - Les notes qui commencent à moins de `together` secondes d'écart forment un accord.
    - Deux rebonds sont séparés d'au moins `min_gap` secondes : sinon la balle n'aurait pas le temps de
      faire un vrai saut ; les notes trop rapprochées rejoignent le rebond précédent (elles restent jouées
      à leur vrai moment dans la bande-son).
    """
    events = []
    for note in notes:
        if events and (note.start - events[-1].time < together or note.start - events[-1].time < min_gap):
            events[-1].notes.append(note.midi)
            events[-1].velocity = max(events[-1].velocity, note.velocity)
        else:
            events.append(Event(note.start, [note.midi], note.velocity))
    for event in events:
        event.label, event.root = _label(event.notes)
    return events


MELODY_LOW, MELODY_HIGH = 48, 88      # tessiture où l'on cherche la mélodie : C3 à E6 (les cordes graves comprises)


def extract_melody(notes, min_gap=0.15, selectivity=0.1):
    """Mélodie principale : une seule note à la fois, la plus marquante, en gardant une ligne cohérente.

    Pour chaque groupe de notes qui démarrent ensemble, on note chaque candidate :
      importance = intensité × durée (plafonnée) × poids de tessiture (le chant est plutôt médium-aigu)
      - une pénalité pour les grands sauts depuis la note précédente (une mélodie avance par petits pas).
    Les groupes dont la meilleure note est trop faible (le `selectivity` le plus faible) sont ignorés :
    ce sont des notes d'accompagnement ou des erreurs de transcription.
    """
    candidates = [n for n in notes if MELODY_LOW <= n.midi <= MELODY_HIGH and n.end - n.start >= 0.08]
    if not candidates:
        candidates = list(notes)

    def importance(n):
        register = 1.0 - abs(n.midi - 66) / 60                  # léger avantage au médium (autour de F#4)
        return n.velocity * min(n.end - n.start, 0.8) ** 0.5 * register

    groups, current = [], []
    for n in sorted(candidates, key=lambda n: n.start):
        if current and n.start - current[0].start >= 0.06:
            groups.append(current)
            current = []
        current.append(n)
    if current:
        groups.append(current)
    if not groups:
        return []

    threshold = np.quantile([max(importance(n) for n in g) for g in groups], selectivity)
    melody, previous = [], None
    for group in groups:
        def score(n):
            jump = abs(n.midi - previous.midi) if previous else 0
            return importance(n) - 0.03 * max(0, jump - 2)     # petits intervalles gratuits, grands sauts pénalisés
        best = max(group, key=score)
        if importance(best) < threshold:
            continue
        if melody and best.start - melody[-1].start < min_gap:
            # Trop proche de la note précédente pour un rebond : on garde la plus marquante des deux
            if importance(best) > importance(melody[-1]):
                melody[-1] = best
                previous = best
            continue
        # Une note de mélodie s'arrête quand la suivante commence (ligne monophonique)
        if melody:
            last = melody[-1]
            melody[-1] = Note(last.start, min(last.end, best.start), last.midi, last.velocity)
        melody.append(best)
        previous = best
    return _smooth_octaves(melody)


def _smooth_octaves(melody, center=64):
    """Ramène chaque note à l'octave la plus proche de la précédente.

    Un thème joué à la fois par des instruments graves et aigus est transcrit tantôt à une octave, tantôt
    à l'autre : la mélodie sauterait sans arrêt de registre. On garde la note (sa classe) et on choisit
    l'octave qui prolonge la ligne, avec un léger rappel vers le médium pour ne pas dériver.
    """
    result, previous = [], None
    for n in melody:
        reference = center if previous is None else 0.8 * previous + 0.2 * center
        options = [n.midi % 12 + 12 * k for k in range(3, 8) if 50 <= n.midi % 12 + 12 * k <= 86]
        midi = min(options, key=lambda m: abs(m - reference))
        result.append(Note(n.start, n.end, midi, n.velocity))
        previous = midi
    return result


def chords_under(notes, times, window=0.5):
    """Accord joué par l'ensemble des instruments à chaque instant (fondamentale, type), ou None.

    Les accords de la tonalité du morceau (estimée sur toutes les notes) sont favorisés : les instruments
    qui passent par des notes de passage ne font pas apparaître d'accords hors sujet.
    """
    from piano import DIATONIC, estimate_key
    histogram = np.zeros(12)
    for n in notes:
        histogram[n.midi % 12] += n.velocity * (n.end - n.start)
    tonic, mode = estimate_key(histogram)
    in_key = {((tonic + degree) % 12, quality) for degree, quality in DIATONIC[mode]}
    result = []
    for t in times:
        weights = np.zeros(12)
        for n in notes:
            if n.start <= t + window and n.end >= t:
                weights[n.midi % 12] += n.velocity * (min(n.end, t + window) - max(n.start, t))
        if weights.sum() <= 0:
            result.append(None)
            continue
        best, best_score = None, 0.0
        for root in range(12):
            for quality, intervals in CHORD_TYPES.items():
                chord = [(root + i) % 12 for i in intervals]
                score = weights[chord].sum() - 0.5 * np.delete(weights, chord).sum()
                if (root, quality) in in_key:
                    score += 0.25 * weights.sum()
                if score > best_score:
                    best, best_score = (root, quality), score
        result.append(best)
    return result


def summary(notes, events):
    duration = max((n.end for n in notes), default=0)
    return {"notes": len(notes), "events": len(events),
            "events_per_second": round(len(events) / duration, 1) if duration else 0}
