"""
Transforme les rebonds en piano qui suit la musique : une note, ou un accord détecté dans le morceau.

1. detect_notes : note la plus présente juste après chaque rebond (CQT sur la tessiture C3–C6).
2. detect_chords : sur l'intervalle entre deux rebonds, l'énergie des 12 notes (chroma) est comparée aux
   24 accords majeurs et mineurs ; l'accord le plus proche est joué, avec sa basse. Les renversements sont
   choisis pour que les voix bougent le moins possible d'un accord au suivant (enchaînement fluide).
3. piano_note : son de piano synthétisé (harmoniques légèrement inharmoniques, attaque de marteau).
4. add_piano : place les notes ou accords sur la bande-son, avec ou sans la musique d'origine.
5. add_transcription : rejoue toutes les notes transcrites du morceau (voir transcribe.py).
"""
import itertools

import numpy as np
from pydub import AudioSegment
from pydub.effects import normalize

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
# Tonalités qui s'écrivent avec des bémols (F, B♭, E♭, A♭, D♭ majeur ; Dm, Gm, Cm, Fm, B♭m mineur)
FLAT_KEYS = {(5, "major"), (10, "major"), (3, "major"), (8, "major"), (1, "major"),
             (2, "minor"), (7, "minor"), (0, "minor"), (5, "minor"), (10, "minor")}
LOW, HIGH = 48, 84          # tessiture de la détection de notes : C3 à C6
SR = 44100
CHORD_TYPES = {"": (0, 4, 7), "m": (0, 3, 7)}   # majeur, mineur


def note_name(midi):
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


def chord_name(root, quality, flats=False):
    return (FLAT_NAMES if flats else NOTE_NAMES)[root] + quality


HARMONIC_MIN_RATIO = 0.2   # en dessous, le morceau n'a pas assez d'harmonie (batterie seule, voix parlée...)
# Progression de repli (la mineur : Am – F – C – G) quand aucune harmonie n'est détectable
FALLBACK_PROGRESSION = [(9, "m"), (5, ""), (0, ""), (7, "")]


def _cqt(music_path):
    """CQT de la partie harmonique du morceau (batterie retirée) et part d'énergie harmonique."""
    import librosa
    y, sr = librosa.load(music_path, sr=22050, mono=True)
    hop = 512
    # Les percussions (grosse caisse, caisse claire) brouillent la détection des notes : on les retire
    harmonic = librosa.effects.harmonic(y, margin=3.0)
    ratio = float(np.sqrt(np.mean(harmonic ** 2)) / (np.sqrt(np.mean(y ** 2)) + 1e-9))
    y = harmonic
    # Beaucoup d'enregistrements ne sont pas accordés exactement sur La 440 : sans correction,
    # l'énergie déborde sur la note voisine (C au lieu de C#)
    tuning = librosa.estimate_tuning(y=y, sr=sr)
    cqt = np.abs(librosa.cqt(y, sr=sr, hop_length=hop, fmin=librosa.midi_to_hz(LOW - 12), tuning=tuning,
                             n_bins=HIGH - LOW + 12, bins_per_octave=12))   # C2 à B5 : 4 octaves complètes
    to_frame = lambda t: int(librosa.time_to_frames(t, sr=sr, hop_length=hop))
    return cqt, to_frame, ratio


def detect_notes(music_path, times, window=0.12):
    """Note MIDI dominante juste après chaque instant (on laisse passer l'attaque, plus bruitée)."""
    if not times:
        return []
    cqt, to_frame, _ = _cqt(music_path)
    cqt = cqt[12:]                               # on ne garde que C3–C6 pour la mélodie
    notes = []
    for t in times:
        start = min(to_frame(t + 0.03), cqt.shape[1] - 1)
        end = max(start + 1, min(to_frame(t + 0.03 + window), cqt.shape[1]))
        energy = cqt[:, start:end].mean(axis=1)
        chroma = np.array([energy[i::12].sum() for i in range(12)])
        pitch_class = int(np.argmax(chroma))
        candidates = list(range(pitch_class, len(energy), 12))
        strongest = max(energy[i] for i in candidates)
        # Parmi les octaves bien présentes, la plus proche de la note précédente : la mélodie reste liée
        strong = [i for i in candidates if energy[i] >= 0.5 * strongest]
        previous = notes[-1] - LOW if notes else 12
        notes.append(LOW + min(strong, key=lambda i: abs(i - previous)))
    return notes


# Profils de Krumhansl-Kessler : importance de chaque degré dans une tonalité majeure / mineure
MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
# Accords naturels de la tonalité (degré, type) : majeur I ii iii IV V vi ; mineur i III iv v V VI VII
DIATONIC = {"major": [(0, ""), (2, "m"), (4, "m"), (5, ""), (7, ""), (9, "m")],
            "minor": [(0, "m"), (3, ""), (5, "m"), (7, "m"), (7, ""), (8, ""), (10, "")]}


def estimate_key(chroma):
    """Tonalité du morceau (tonique, "major" | "minor") d'après son chroma moyen."""
    best = max(((tonic, mode, np.corrcoef(np.roll(profile, tonic), chroma)[0, 1])
                for tonic in range(12) for mode, profile in (("major", MAJOR_PROFILE), ("minor", MINOR_PROFILE))),
               key=lambda k: k[2])
    return best[0], best[1]


def _voice(pitch_classes, previous):
    """Place les 3 notes de l'accord autour de C4 en minimisant le déplacement depuis l'accord précédent."""
    options = []
    for inversion in itertools.permutations(pitch_classes):
        voicing, low = [], 55                    # les voix commencent au-dessus de G3
        for pc in inversion:
            midi = low + (pc - low) % 12
            voicing.append(midi)
            low = midi + 1
        if voicing[-1] <= 79:                    # pas plus haut que G5
            options.append(voicing)
    if not previous:
        return min(options, key=lambda v: abs(sum(v) / 3 - 64))
    return min(options, key=lambda v: sum(abs(a - b) for a, b in zip(sorted(v), sorted(previous))))


def _peak_chroma(energy):
    """Chroma construit uniquement sur les vrais pics du spectre.

    Une note déborde sur ses voisines (surtout dans le grave et sur les notes courtes) : on ne garde que
    les notes plus fortes que leurs deux voisines et assez présentes, ce qui évite les accords décalés.
    """
    energy = energy / (energy.max() + 1e-9)
    padded = np.pad(energy, 1)
    peaks = (energy >= padded[:-2]) & (energy >= padded[2:]) & (energy >= 0.15)
    kept = np.where(peaks, np.sqrt(energy), 0.0)
    return np.array([kept[i::12].sum() for i in range(12)])


def detect_chords(music_path, times):
    """Accord (nom, notes MIDI avec la basse, fondamentale) pour chaque intervalle entre deux rebonds,
    et la tonalité estimée du morceau dans detect_chords.key."""
    if not times:
        return []
    cqt, to_frame, ratio = _cqt(music_path)
    detect_chords.harmonic = ratio >= HARMONIC_MIN_RATIO
    if not detect_chords.harmonic:
        # Pas d'harmonie exploitable : progression de repli, un accord toutes les 4 rebonds
        chords, previous = [], None
        for i in range(len(times)):
            root, quality = FALLBACK_PROGRESSION[(i // 4) % len(FALLBACK_PROGRESSION)]
            voicing = _voice([(root + k) % 12 for k in CHORD_TYPES[quality]], previous)
            previous = voicing
            chords.append({"name": chord_name(root, quality), "root": root, "notes": [36 + (root - 36) % 12] + voicing})
        detect_chords.key = "Am (par défaut)"
        return chords
    templates = []
    for root in range(12):
        for quality, intervals in CHORD_TYPES.items():
            vector = np.zeros(12)
            for k, interval in enumerate(intervals):
                vector[(root + interval) % 12] = 1.0 if k != 1 else 0.8   # la tierce compte un peu moins
            templates.append((root, quality, vector / np.linalg.norm(vector)))

    # Les accords de la tonalité du morceau sont légèrement favorisés : moins d'erreurs isolées
    tonic, mode = estimate_key(np.mean([_peak_chroma(frame) for frame in cqt[:, ::8].T], axis=0))
    in_key = {((tonic + degree) % 12, quality) for degree, quality in DIATONIC[mode]}

    chords, previous, current = [], None, None
    ends = list(times[1:]) + [times[-1] + 0.8]
    for t, end_t in zip(times, ends):
        start = min(to_frame(t + 0.03), cqt.shape[1] - 1)
        end = max(start + 1, min(to_frame(min(end_t, t + 1.2)), cqt.shape[1]))
        chroma = _peak_chroma(cqt[:, start:end].mean(axis=1))
        chroma = chroma / (np.linalg.norm(chroma) + 1e-9)
        scores = {(r, q): float(v @ chroma) + (0.04 if (r, q) in in_key else 0.0) for r, q, v in templates}
        best = max(scores, key=scores.get)
        # On ne change d'accord que si le nouveau l'emporte nettement (évite les allers-retours)
        if current is None or scores[best] > scores[current] + 0.03:
            current = best
        root, quality = current
        pitch_classes = [(root + i) % 12 for i in CHORD_TYPES[quality]]
        voicing = _voice(pitch_classes, previous)
        previous = voicing
        bass = 36 + (root - 36) % 12             # basse entre C2 et B2
        chords.append({"name": chord_name(root, quality, (tonic, mode) in FLAT_KEYS), "root": root,
                       "notes": [bass] + voicing})
    detect_chords.key = chord_name(tonic, "" if mode == "major" else "m", (tonic, mode) in FLAT_KEYS)
    return chords


def piano_wave(midi, duration=1.6, velocity=0.8):
    """Son de piano synthétisé : tableau numpy mono, valeurs entre -1 et 1."""
    freq = 440.0 * 2 ** ((midi - 69) / 12)
    t = np.arange(int(SR * duration)) / SR
    decay = 1.2 * 2 ** (-(midi - 60) / 24)       # les aigus s'éteignent plus vite
    wave = np.zeros_like(t)
    for k in range(1, 9):
        partial = freq * k * np.sqrt(1 + 0.0004 * k * k)   # légère inharmonicité des cordes
        if partial > SR / 2:
            break
        wave += (1 / k ** 1.4) * np.exp(-t * k / decay) * np.sin(2 * np.pi * partial * t)
    attack = np.minimum(1.0, t / 0.004)
    hammer = np.random.default_rng(midi).normal(0, 1, len(t)) * np.exp(-t * 90) * 0.08
    signal = (wave * attack + hammer) * np.exp(-t * 0.6 / decay)
    signal = signal / (np.abs(signal).max() + 1e-9) * velocity
    fade = np.minimum(1.0, (duration - t) / 0.05)          # pas de clic en fin de note
    return signal * fade * 0.9


def piano_note(midi, duration=1.6, velocity=0.8):
    """Son de piano synthétisé (AudioSegment mono, 16 bits)."""
    pcm = (piano_wave(midi, duration, velocity) * 32767).astype(np.int16)
    return AudioSegment(pcm.tobytes(), frame_rate=SR, sample_width=2, channels=1)


def add_transcription(track, notes, mode="solo", volume=-4.0):
    """Rejoue au piano toutes les notes transcrites, avec leur durée et leur intensité réelles.

    Le mélange est fait en numpy (un seul tampon audio) : avec pydub, chaque note recopierait toute la
    bande-son, ce qui serait beaucoup trop lent pour les milliers de notes d'un morceau.
    """
    track = track.set_frame_rate(SR).set_sample_width(2)
    channels = track.channels
    length = int(len(track) * SR / 1000)
    piano = np.zeros(length)
    gain = 10 ** (volume / 20)
    cache = {}
    for note in notes:
        duration = round(min(max(note.end - note.start, 0.15), 3.0) + 0.35, 1)   # + résonance après relâchement
        velocity = round(0.25 + 0.6 * note.velocity, 1)
        key = (note.midi, duration, velocity)
        if key not in cache:
            cache[key] = piano_wave(note.midi, duration, velocity)
        wave = cache[key]
        start = int(note.start * SR)
        end = min(length, start + len(wave))
        if start < end:
            piano[start:end] += wave[:end - start] * gain

    if mode == "solo":
        mixed = np.repeat(piano[:, None], channels, axis=1)
    else:
        music = np.array(track.get_array_of_samples(), dtype=np.float64).reshape(-1, channels) / 32768
        music = music[:length]
        mixed = music + piano[:len(music), None]
    peak = np.abs(mixed).max()
    if peak > 0.95 or mode == "solo":
        mixed *= 0.9 / (peak + 1e-9)                        # pas de saturation, piano seul à bon volume
    pcm = (mixed * 32767).astype(np.int16)
    return AudioSegment(pcm.tobytes(), frame_rate=SR, sample_width=2, channels=channels)


def add_piano(track, notes, positions_ms, mode="solo", volume=-4.0):
    """Ajoute les notes à la bande-son.

    notes : une note MIDI ou une liste de notes (accord) par rebond.
    mode : "mix" (avec la musique) ou "solo" (piano seul, sans la musique d'origine).
    """
    solo = mode == "solo"
    if solo:
        track = AudioSegment.silent(duration=len(track), frame_rate=SR)
    track = track.set_frame_rate(SR)
    cache = {}
    for item, position in zip(notes, positions_ms):
        chord = item if isinstance(item, (list, tuple)) else [item]
        for midi in chord:
            # Chaque voix d'un accord est un peu plus douce pour que l'ensemble ne sature pas
            key = (midi, len(chord))
            if key not in cache:
                cache[key] = piano_note(midi, velocity=0.8 if len(chord) == 1 else 0.45) + volume
            track = track.overlay(cache[key], position=int(position))
    return normalize(track, headroom=1.0) if solo else track
