"""
Comparaison de trois façons d'obtenir la partition de piano d'un morceau, sur le même extrait.

A. actuel    : Basic Pitch sur le mélange complet -> mélodie principale + accords doux
B. demucs    : séparation (voix / basse / autres / batterie) puis Basic Pitch sur chaque piste utile
C. pop2piano : reprise au piano générée directement depuis l'audio (Transformer)

Usage : python compare.py musique.mp3 dossier_sortie [début_s] [durée_s]
"""
import os
import subprocess
import sys
import time

import numpy as np
import soundfile as sf
import librosa
from pydub import AudioSegment

sys.path.insert(0, "/app/source")
from piano import add_transcription, note_name
from platform_render import accompaniment
from transcribe import Note, extract_melody, transcribe

src, out = sys.argv[1], sys.argv[2]
start = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
length = float(sys.argv[4]) if len(sys.argv) > 4 else 60.0
os.makedirs(out, exist_ok=True)

clip = os.path.join(out, "extrait.wav")


def export(name, notes, seconds):
    track = AudioSegment.silent(duration=int(length * 1000), frame_rate=44100)
    audio = add_transcription(track, notes, "solo", -4.0)
    path = os.path.join(out, f"{name}.mp3")
    audio.export(path, format="mp3", bitrate="192k")
    melody = sorted((n for n in notes if n.velocity > 0.31), key=lambda n: n.start)
    print(f"\n=== {name} : {len(notes)} notes au total ({len(notes) / length:.1f}/s), calcul {seconds:.0f} s -> {path}")
    print("    extrait 20-30 s :", " ".join(note_name(n.midi) for n in melody if 20 <= n.start < 30))


# --- C. Pop2Piano ------------------------------------------------------------------------
t = time.time()
from transformers import Pop2PianoForConditionalGeneration, Pop2PianoProcessor
model = Pop2PianoForConditionalGeneration.from_pretrained("sweetcocoa/pop2piano")
processor = Pop2PianoProcessor.from_pretrained("sweetcocoa/pop2piano")
audio, rate = librosa.load(clip, sr=44100)
inputs = processor(audio=audio, sampling_rate=rate, return_tensors="pt")
generated = model.generate(input_features=inputs["input_features"], composer="composer1")
midi = processor.batch_decode(token_ids=generated, feature_extractor_output=inputs)["pretty_midi_objects"][0]
cover = [Note(n.start, n.end, n.pitch, n.velocity / 127) for inst in midi.instruments for n in inst.notes]
# Pour l'extrait affiché, on prend la note la plus aiguë de chaque instant (la main droite, la mélodie)
export("C_pop2piano", cover, time.time() - t)
midi.write(os.path.join(out, "C_pop2piano.mid"))
