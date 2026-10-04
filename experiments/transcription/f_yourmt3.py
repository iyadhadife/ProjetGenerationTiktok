"""
Version F : YourMT3+ (modèle « YPTF.MoE+Multi (noPS) ») transcrit chaque instrument séparément.
On choisit l'instrument qui porte la mélodie, puis on en tire la ligne principale.
"""
import os
import sys
import time

import pretty_midi
import torch
import torchaudio

# Checkpoint officiel des auteurs (dépôt Hugging Face mimbres) au format PyTorch d'avant 2.6 :
# il contient des objets Python, on autorise donc le chargement complet, dans ce conteneur de test uniquement
_torch_load = torch.load
torch.load = lambda *a, **k: _torch_load(*a, **{**k, "weights_only": False})

# Les versions récentes de torchaudio n'ont plus info() et chargent l'audio autrement : on passe par soundfile
import soundfile as sf


def _load(uri, *args, **kwargs):
    data, rate = sf.read(uri, always_2d=True, dtype="float32")
    return torch.from_numpy(data.T.copy()), rate


torchaudio.load = _load

out = sys.argv[1]
length = 60.0
clip = os.path.abspath(os.path.join(out, "extrait.wav"))

os.chdir("/t/ymt3")                                # les chemins des checkpoints sont relatifs au dépôt
sys.path.insert(0, "/t/ymt3/amt/src")
sys.path.insert(0, "/t/ymt3")
from model_helper import load_model_checkpoint, transcribe as ymt3_transcribe  # noqa: E402

checkpoint = "mc13_256_g4_all_v7_mt3f_sqr_rms_moe_wf4_n8k2_silu_rope_rp_b36_nops@last.ckpt"
args = [checkpoint, "-p", "2024", "-tk", "mc13_full_plus_256", "-dec", "multi-t5", "-nl", "26", "-enc", "perceiver-tf",
        "-sqr", "1", "-ff", "moe", "-wf", "4", "-nmoe", "8", "-kmoe", "2", "-act", "silu", "-epe", "rope",
        "-rp", "1", "-ac", "spec", "-hop", "300", "-atc", "1", "-pr", "32"]
t0 = time.time()
model = load_model_checkpoint(args=args)
# Sur processeur avec peu de mémoire : un segment audio à la fois au lieu de 8
_inference = model.inference_file
model.inference_file = lambda bsz=8, audio_segments=None, **kw: _inference(bsz=1, audio_segments=audio_segments, **kw)
torch.set_grad_enabled(False)
midi_path = ymt3_transcribe(model, {"filepath": clip, "track_name": "extrait_yourmt3"})
elapsed = time.time() - t0

sys.path.insert(0, "/app/source")
from pydub import AudioSegment  # noqa: E402
from piano import add_transcription, note_name  # noqa: E402
from platform_render import accompaniment  # noqa: E402
from transcribe import Note, extract_melody  # noqa: E402

midi = pretty_midi.PrettyMIDI(midi_path)
midi.write(os.path.join(out, "F_yourmt3_tous_instruments.mid"))
print(f"\n[YourMT3+] calcul {elapsed:.0f} s pour {length:.0f} s de musique ; instruments trouvés :")
everything, scores = [], []
for inst in midi.instruments:
    if inst.is_drum:
        continue
    notes = [Note(n.start, n.end, n.pitch, n.velocity / 127) for n in inst.notes]
    everything += notes
    name = pretty_midi.program_to_instrument_name(inst.program) if not inst.is_drum else "batterie"
    is_bass = 32 <= inst.program <= 39
    # « Mélodicité » : présence (intensité × durée) dans la tessiture chantée, hors basses
    presence = sum(n.velocity * (n.end - n.start) for n in notes if 55 <= n.midi <= 88)
    scores.append((0 if is_bass else presence, name, notes))
    print(f"   - {name:28s} {len(notes):4d} notes, présence médium-aigu {presence:6.1f}")

scores.sort(key=lambda s: s[0], reverse=True)
_, lead_name, lead_notes = scores[0]
melody = extract_melody(lead_notes, min_gap=0.12, selectivity=0.0)
print(f"   -> mélodie prise sur : {lead_name}")

track = AudioSegment.silent(duration=int(length * 1000), frame_rate=44100)
add_transcription(track, melody + accompaniment(everything, melody), "solo", -4.0).export(
    os.path.join(out, "F_yourmt3.mp3"), format="mp3", bitrate="192k")
print(f"=== F_yourmt3 : {len(melody)} notes de mélodie ({len(melody) / length:.1f}/s)")
print("    extrait 20-30 s :", " ".join(note_name(n.midi) for n in melody if 20 <= n.start < 30))
