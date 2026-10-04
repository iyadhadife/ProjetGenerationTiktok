"""
Version D : le moment des notes vient de Demucs (piste séparée), la hauteur vient du morceau complet.

Pour chaque note de la mélodie trouvée sur la piste séparée :
  1. on cherche, dans une transcription sensible du morceau complet, les notes qui sonnent à ce moment ;
  2. on garde celle dont la hauteur est la plus proche de ce que Demucs a entendu (à l'octave près) ;
  3. à défaut, on prend le pic du spectre du morceau complet le plus proche, en favorisant la tonalité.
"""
import os
import sys
import time

import numpy as np
import librosa
from pydub import AudioSegment

sys.path.insert(0, "/app/source")
from piano import DIATONIC, add_transcription, estimate_key, note_name
from platform_render import accompaniment
from transcribe import Note, _smooth_octaves, extract_melody, transcribe

out = sys.argv[1]
length = 60.0
clip = os.path.join(out, "extrait.wav")
stems = os.path.join(out, "sep", "htdemucs", "extrait")


def sensitive_transcription(path):
    """Basic Pitch avec des seuils plus bas que par défaut : il rate moins de notes."""
    from basic_pitch import ICASSP_2022_MODEL_PATH
    from basic_pitch.inference import predict
    model = os.path.join(os.path.dirname(ICASSP_2022_MODEL_PATH), "nmp.onnx")
    _, _, raw = predict(path, model, onset_threshold=0.3, frame_threshold=0.2, minimum_note_length=60)
    return [Note(float(s), float(e), int(p), float(a)) for s, e, p, a, *_ in raw]


t0 = time.time()
mix_notes = sensitive_transcription(clip)
stem_notes = transcribe(os.path.join(stems, "other.wav"))
timing = extract_melody(stem_notes, min_gap=0.12, selectivity=0.0)

# Tonalité et spectre (partie harmonique) du morceau complet, pour les cas sans note transcrite
y, sr = librosa.load(clip, sr=22050)
harmonic = librosa.effects.harmonic(y, margin=3.0)
tuning = librosa.estimate_tuning(y=harmonic, sr=sr)
cqt = np.abs(librosa.cqt(harmonic, sr=sr, hop_length=512, fmin=librosa.midi_to_hz(36), n_bins=60, tuning=tuning))
histogram = np.zeros(12)
for n in mix_notes:
    histogram[n.midi % 12] += n.velocity * (n.end - n.start)
tonic, mode = estimate_key(histogram)
scale = {(tonic + d) % 12 for d, _ in DIATONIC[mode]} | {(tonic + 11) % 12 if mode == "minor" else tonic}


def octave_distance(a, b):
    d = abs(a - b) % 12
    return min(d, 12 - d)


melody, from_mix, from_spectrum = [], 0, 0
previous = None
for note in timing:
    # Notes du morceau complet qui sonnent à ce moment, dans la tessiture de la mélodie
    sounding = [n for n in mix_notes if 48 <= n.midi <= 88 and n.start <= note.start + 0.10 and n.end >= note.start - 0.05]
    if sounding:
        def score(n):
            loudness = n.velocity * min(n.end - n.start, 0.8) ** 0.5 * (1.0 - abs(n.midi - 66) / 60)
            jump = octave_distance(n.midi, previous) if previous is not None else 0
            agrees = 0.05 if octave_distance(n.midi, note.midi) == 0 else 0.0     # léger bonus si Demucs est d'accord
            in_key = 0.05 if n.midi % 12 in scale else 0.0
            return loudness + agrees + in_key - 0.02 * max(0, jump - 2)
        best = max(sounding, key=score)
        melody.append(Note(note.start, note.end, best.midi, max(note.velocity, best.velocity)))
        previous = best.midi
        from_mix += 1
        continue
    # Sinon : pic du spectre du morceau complet, dans la tonalité
    a = librosa.time_to_frames(note.start + 0.02, sr=sr, hop_length=512)
    b = librosa.time_to_frames(note.start + 0.15, sr=sr, hop_length=512)
    energy = cqt[:, a:max(a + 1, b)].mean(axis=1)
    energy = energy / (energy.max() + 1e-9)
    candidates = [36 + i for i in range(len(energy)) if energy[i] > 0.25 and (36 + i) % 12 in scale and 48 <= 36 + i <= 88]
    if candidates:
        midi = max(candidates, key=lambda m: energy[m - 36] - (0.03 * octave_distance(m, previous) if previous is not None else 0))
        melody.append(Note(note.start, note.end, midi, note.velocity))
        previous = midi
        from_spectrum += 1
melody = _smooth_octaves(melody)
elapsed = time.time() - t0

track = AudioSegment.silent(duration=int(length * 1000), frame_rate=44100)
audio = add_transcription(track, melody + accompaniment(mix_notes, melody), "solo", -4.0)
audio.export(os.path.join(out, "D_hybride.mp3"), format="mp3", bitrate="192k")
changed = sum(1 for m, d in zip(melody, timing) if m.midi % 12 != d.midi % 12)
print(f"=== D_hybride : {len(melody)} notes de mélodie ({len(melody) / length:.1f}/s), calcul {elapsed:.0f} s "
      f"(+ séparation Demucs déjà faite)")
print(f"    hauteur prise sur le morceau complet : {from_mix} transcrites, {from_spectrum} lues dans le spectre ; "
      f"{changed} notes de Demucs corrigées")
print("    extrait 20-30 s :", " ".join(note_name(n.midi) for n in melody if 20 <= n.start < 30))
print("    Demucs seul      :", " ".join(note_name(n.midi) for n in timing if 20 <= n.start < 30))
