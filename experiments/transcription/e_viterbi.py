"""
Version E : comme D (moments de Demucs, hauteurs du morceau complet), mais la ligne mélodique est
choisie d'un seul bloc par l'algorithme de Viterbi au lieu de note par note.

À chaque moment, plusieurs notes candidates (transcription sensible du morceau complet, pics du spectre,
note entendue par Demucs). Le chemin retenu maximise sur toute la phrase :
  présence de la note dans le morceau + note de l'accord en cours + note de la tonalité
  + probabilité de l'intervalle avec la note précédente (notes répétées et petits pas fréquents, grands sauts rares).
"""
import math
import os
import sys
import time

import numpy as np
import librosa
from pydub import AudioSegment

sys.path.insert(0, "/app/source")
from piano import CHORD_TYPES, DIATONIC, add_transcription, estimate_key, note_name
from platform_render import accompaniment
from transcribe import Note, chords_under, extract_melody, transcribe

out = sys.argv[1]
length = 60.0
clip = os.path.join(out, "extrait.wav")
stems = os.path.join(out, "sep", "htdemucs", "extrait")
LOW, HIGH = 48, 88

# Probabilité d'un intervalle mélodique (en demi-tons, valeur absolue), d'après les statistiques usuelles
# des mélodies occidentales : beaucoup de notes répétées et de secondes, peu de grands sauts.
INTERVAL = {0: 0.13, 1: 0.15, 2: 0.22, 3: 0.12, 4: 0.10, 5: 0.08, 7: 0.06, 12: 0.03}
OBSERVATION_WEIGHT = 2.0   # ce qu'on entend dans le morceau compte plus que la régularité de la ligne


def interval_logp(a, b):
    d = abs(a - b)
    p = INTERVAL.get(d, 0.04 if d <= 7 else 0.008 if d != 12 else INTERVAL[12])
    return math.log(p)


def sensitive_transcription(path):
    from basic_pitch import ICASSP_2022_MODEL_PATH
    from basic_pitch.inference import predict
    model = os.path.join(os.path.dirname(ICASSP_2022_MODEL_PATH), "nmp.onnx")
    _, _, raw = predict(path, model, onset_threshold=0.3, frame_threshold=0.2, minimum_note_length=60)
    return [Note(float(s), float(e), int(p), float(a)) for s, e, p, a, *_ in raw]


t0 = time.time()
mix_notes = sensitive_transcription(clip)
timing = extract_melody(transcribe(os.path.join(stems, "other.wav")), min_gap=0.12, selectivity=0.0)

y, sr = librosa.load(clip, sr=22050)
harmonic = librosa.effects.harmonic(y, margin=3.0)
tuning = librosa.estimate_tuning(y=harmonic, sr=sr)
cqt = np.abs(librosa.cqt(harmonic, sr=sr, hop_length=512, fmin=librosa.midi_to_hz(LOW), n_bins=HIGH - LOW + 1,
                         tuning=tuning))
histogram = np.zeros(12)
for n in mix_notes:
    histogram[n.midi % 12] += n.velocity * (n.end - n.start)
tonic, mode = estimate_key(histogram)
scale = {(tonic + d) % 12 for d, _ in DIATONIC[mode]}
chords = chords_under(mix_notes, [n.start for n in timing])

# --- candidats et score d'observation pour chaque moment --------------------------------------
steps = []
for note, chord in zip(timing, chords):
    a = librosa.time_to_frames(note.start + 0.02, sr=sr, hop_length=512)
    b = librosa.time_to_frames(note.start + 0.18, sr=sr, hop_length=512)
    spectrum = cqt[:, a:max(a + 1, b)].mean(axis=1)
    spectrum = spectrum / (spectrum.max() + 1e-9)
    presence = {}
    for n in mix_notes:                                    # notes transcrites qui sonnent à ce moment
        if LOW <= n.midi <= HIGH and n.start <= note.start + 0.10 and n.end >= note.start - 0.05:
            presence[n.midi] = max(presence.get(n.midi, 0), n.velocity)
    for i, e in enumerate(spectrum):                       # pics nets du spectre
        if e > 0.35 and (i == 0 or e >= spectrum[i - 1]) and (i == len(spectrum) - 1 or e >= spectrum[i + 1]):
            presence[LOW + i] = max(presence.get(LOW + i, 0), 0.6 * e)
    if LOW <= note.midi <= HIGH:
        presence.setdefault(note.midi, 0.15)               # la note de Demucs reste possible, mais faible
    chord_tones = {(chord[0] + i) % 12 for i in CHORD_TYPES[chord[1]]} if chord else set()
    candidates = []
    for midi, p in presence.items():
        score = math.log(p + 0.02)
        score += math.log(1.6) if midi % 12 in chord_tones else 0.0
        score += math.log(1.3) if midi % 12 in scale else math.log(0.5)
        score -= abs(midi - 67) / 40                         # léger avantage au médium
        candidates.append((midi, OBSERVATION_WEIGHT * score))
    steps.append(candidates)

# --- Viterbi ---------------------------------------------------------------------------------------
best = [{m: (s, None) for m, s in steps[0]}]
for k in range(1, len(steps)):
    layer = {}
    for midi, score in steps[k]:
        prev, value = max(((p, v[0] + interval_logp(p, midi)) for p, v in best[-1].items()), key=lambda x: x[1])
        layer[midi] = (value + score, prev)
    best.append(layer)
path = [max(best[-1], key=lambda m: best[-1][m][0])]
for k in range(len(best) - 1, 0, -1):
    path.append(best[k][path[-1]][1])
path.reverse()

melody = [Note(n.start, n.end, midi, n.velocity) for n, midi in zip(timing, path)]
elapsed = time.time() - t0
track = AudioSegment.silent(duration=int(length * 1000), frame_rate=44100)
add_transcription(track, melody + accompaniment(mix_notes, melody), "solo", -4.0).export(
    os.path.join(out, "E_viterbi.mp3"), format="mp3", bitrate="192k")

jumps = np.abs(np.diff(path))
print(f"=== E_viterbi : {len(melody)} notes ({len(melody) / length:.1f}/s), calcul {elapsed:.0f} s, tonalité "
      f"{note_name(tonic)[:-1]}{'m' if mode == 'minor' else ''}")
print(f"    intervalles : répétées {np.mean(jumps == 0):.0%}, pas de 1-2 demi-tons {np.mean((jumps >= 1) & (jumps <= 2)):.0%}, "
      f"sauts > quinte {np.mean(jumps > 7):.0%} ; hors tonalité {np.mean([m % 12 not in scale for m in path]):.0%}")
print("    extrait 20-30 s :", " ".join(note_name(n.midi) for n in melody if 20 <= n.start < 30))
