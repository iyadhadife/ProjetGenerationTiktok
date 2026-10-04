"""
Service de transcription Sheet Sage 2 (m-a-p/SheetSage2, licence CC BY-NC 4.0 : usage non commercial).

Tourne dans son propre conteneur, car il demande des versions précises de PyTorch / transformers / numpy.
Le modèle est chargé une seule fois. Les résultats sont mis en cache par morceau (empreinte du fichier) :
le service transcrit par blocs de 60 s à partir du début, et toute demande déjà couverte (quels que soient la
vitesse, la durée ou les réglages de la vidéo) est servie immédiatement.

POST /transcribe   multipart : audio (fichier), duration (s, optionnel : durée utile depuis le début)
                   -> {melody, chords, beats, downbeats, key, chord_labels, sections, elapsed, cached}
GET  /health
"""
import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile
import threading
import time

from flask import Flask, jsonify, request

MODEL_DIR = os.environ.get("SHEETSAGE_DIR", "/models/SheetSage2")
CACHE_DIR = os.environ.get("RESULT_CACHE", "/cache/results")
os.makedirs(CACHE_DIR, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 60 * 1024 * 1024
_model = None
_lock = threading.Lock()          # une transcription à la fois (mémoire et processeur limités)


def model():
    global _model
    if _model is None:
        import torch
        from transformers import AutoModel
        # transformers ne recopie pas tous les modules du modèle dans son cache : on le fait nous-mêmes
        modules = os.path.join(os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface")),
                               "modules", "transformers_modules", os.path.basename(MODEL_DIR))
        os.makedirs(modules, exist_ok=True)
        for name in os.listdir(MODEL_DIR):
            if name.endswith(".py"):
                shutil.copy(os.path.join(MODEL_DIR, name), modules)
        open(os.path.join(modules, "__init__.py"), "a").close()
        torch.set_num_threads(max(1, os.cpu_count() or 1))
        _model = AutoModel.from_pretrained(MODEL_DIR, trust_remote_code=True).eval().to("cpu")
    return _model


def read_lab(path, columns):
    rows = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= columns:
                    rows.append(parts)
    return rows


def read_midi(path, gain=1.0):
    import pretty_midi
    if not os.path.exists(path):
        return []
    midi = pretty_midi.PrettyMIDI(path)
    return [[round(n.start, 4), round(n.end, 4), int(n.pitch), round(gain * n.velocity / 127, 3)]
            for inst in midi.instruments for n in inst.notes]


def transcribe_file(path):
    with tempfile.TemporaryDirectory() as out:
        started = time.time()
        model().transcribe(path, output_dir=out, dtype="fp32")
        melody = read_midi(os.path.join(out, "melody_vocal.mid")) + read_midi(os.path.join(out, "melody_instrumental.mid"))
        return {
            "melody": sorted(melody),
            "chords": sorted(read_midi(os.path.join(out, "chords.mid"))),
            "beats": [float(r[0]) for r in read_lab(os.path.join(out, "beat.lab"), 1)],
            "downbeats": [float(r[0]) for r in read_lab(os.path.join(out, "downbeat.lab"), 1)],
            "chord_labels": [[float(r[0]), float(r[1]), r[2]] for r in read_lab(os.path.join(out, "chord.lab"), 3)],
            "key": (read_lab(os.path.join(out, "key.lab"), 3) or [[0, 0, ""]])[0][2],
            "sections": [[float(r[0]), float(r[1]), r[2]] for r in read_lab(os.path.join(out, "structure.lab"), 3)],
            "elapsed": round(time.time() - started, 1),
        }


@app.get("/health")
def health():
    return jsonify(status="ok", model_loaded=_model is not None)


@app.post("/transcribe")
def transcribe():
    audio = request.files.get("audio")
    if not audio:
        return jsonify(error="fichier audio manquant"), 400
    wanted = float(request.form.get("duration", 0) or 0)
    data = audio.read()
    key = hashlib.sha256(data).hexdigest()[:24]
    cached = os.path.join(CACHE_DIR, key + ".json")
    if os.path.exists(cached):
        with open(cached, encoding="utf-8") as f:
            previous = json.load(f)
        if previous.get("covered", 0) >= wanted > 0 or previous.get("complete"):
            return jsonify({**previous, "cached": True})
    # Blocs de 60 s : une petite variation de durée ou de vitesse ne relance pas la transcription
    duration = math.ceil(wanted / 60) * 60 if wanted > 0 else 0

    with tempfile.TemporaryDirectory() as tmp:
        source = os.path.join(tmp, "source" + os.path.splitext(audio.filename or "")[1])
        with open(source, "wb") as f:
            f.write(data)
        # On ne transcrit que l'extrait utile (gain de temps : ~2 min de calcul par minute de musique)
        clip = os.path.join(tmp, "clip.wav")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", source]
        if duration > 0:
            cmd += ["-t", str(duration)]
        subprocess.run(cmd + ["-ac", "1", "-ar", "24000", clip], check=True)
        with _lock:
            try:
                result = transcribe_file(clip)
                total = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                              "csv=p=0", source], capture_output=True, text=True).stdout or 0)
                result["covered"] = duration or total
                result["complete"] = duration == 0 or duration >= total
            except Exception as error:  # l'erreur est renvoyée à l'API
                return jsonify(error=f"Sheet Sage 2 : {error}"), 500
    with open(cached, "w", encoding="utf-8") as f:
        json.dump(result, f)
    return jsonify({**result, "cached": False})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
