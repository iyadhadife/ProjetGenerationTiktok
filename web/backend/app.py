"""
API du générateur : reçoit une musique et des paramètres, lance le rendu en arrière-plan
et sert la vidéo une fois prête.

POST /api/render            multipart : music (fichier audio), mode (arcs | platforms), params (JSON),
                            score (partition .mid facultative, mode platforms)  -> {id}
GET  /api/jobs/<id>         état du rendu : queued | running | done | error, progression, logs
GET  /api/jobs/<id>/video   la vidéo .mp4 (?download=1 pour la télécharger)
GET  /api/defaults          paramètres par défaut de chaque mode (pour pré-remplir les formulaires)
"""
import json
import os
import queue
import shutil
import sys
import threading
import time
import uuid
from dataclasses import asdict, fields

from flask import Flask, jsonify, request, send_file

sys.path.insert(0, os.environ.get("RENDER_SOURCE", os.path.join(os.path.dirname(__file__), "..", "..", "source")))
from beat_render import Config, render  # noqa: E402
from platform_render import PlatformConfig, render as render_platforms  # noqa: E402

MODES = {"arcs": (Config, render), "platforms": (PlatformConfig, render_platforms)}

JOBS_DIR = os.environ.get("JOBS_DIR", os.path.join(os.path.dirname(__file__), "jobs"))
ALLOWED_AUDIO = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac"}
MAX_JOBS_KEPT = 20

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 Mo

jobs = {}
pending = queue.Queue()
os.makedirs(JOBS_DIR, exist_ok=True)


def parse_config(raw, config_class=Config):
    """Construit la configuration du mode en ne gardant que les champs connus, convertis au bon type."""
    data = json.loads(raw or "{}")
    defaults = asdict(config_class())
    values = {}
    for f in fields(config_class):
        if f.name not in data or data[f.name] in (None, ""):
            continue
        value, default = data[f.name], defaults[f.name]
        if isinstance(default, bool):
            values[f.name] = bool(value)
        elif isinstance(default, int):
            values[f.name] = int(value)
        elif isinstance(default, float):
            values[f.name] = float(value)
        elif isinstance(default, list):
            values[f.name] = [str(v) for v in value][:4]
        elif f.name == "seed":
            values[f.name] = int(value)
        else:
            values[f.name] = str(value)[:60]
    cfg = config_class(**values)
    # Garde-fous : un rendu trop long ou trop lourd bloquerait la file d'attente
    cfg.fps = 30 if cfg.fps <= 30 else 60
    cfg.max_duration = min(max(cfg.max_duration, 3), 180)
    cfg.piano = cfg.piano if cfg.piano in ("off", "mix", "solo") else "off"
    cfg.piano_voicing = cfg.piano_voicing if cfg.piano_voicing in ("chord", "note") else "chord"
    if config_class is Config:
        cfg.arc_count = min(max(cfg.arc_count, 1), 40)
        cfg.ball_names = cfg.ball_names[:4] or ["Ball"]
    else:
        cfg.sync = cfg.sync if cfg.sync in ("notes", "tempo", "onsets") else "notes"
        cfg.particles = min(max(cfg.particles, 0), 80)
        cfg.playback_speed = min(max(cfg.playback_speed, 0.25), 1.0)
        cfg.visual_lead = min(max(cfg.visual_lead, -0.2), 0.2)
        cfg.score_max_cost = min(max(cfg.score_max_cost, 0.05), 1.0)
        cfg.piano_content = cfg.piano_content if cfg.piano_content in ("melody", "melody_chords", "all") else "melody_chords"
        cfg.engine = cfg.engine if cfg.engine in ("sheetsage2", "basic_pitch") else "sheetsage2"
    return cfg


def worker():
    while True:
        job_id = pending.get()
        job = jobs[job_id]
        job.update(status="running", started=time.time())
        folder = os.path.join(JOBS_DIR, job_id)
        try:
            job["result"] = MODES[job["mode"]][1](
                job["music"], os.path.join(folder, "tiktok.mp4"), job["config"],
                progress=lambda done, total: job.update(progress=round(done / max(total, 1), 3)),
                log=lambda message: job["logs"].append(message),
            )
            job.update(status="done", progress=1)
        except Exception as error:  # l'erreur est renvoyée à l'interface
            job.update(status="error", error=str(error))
        finally:
            job["finished"] = time.time()
            cleanup()


def cleanup():
    """Ne garde que les derniers rendus sur le disque."""
    finished = sorted((j for j in jobs.values() if j.get("finished")), key=lambda j: j["finished"])
    for job in finished[:-MAX_JOBS_KEPT]:
        shutil.rmtree(os.path.join(JOBS_DIR, job["id"]), ignore_errors=True)
        jobs.pop(job["id"], None)


threading.Thread(target=worker, daemon=True).start()


@app.get("/api/defaults")
def defaults():
    return jsonify({mode: asdict(config_class()) for mode, (config_class, _) in MODES.items()})


@app.post("/api/render")
def create_job():
    music = request.files.get("music")
    if not music or not music.filename:
        return jsonify(error="Ajoute un fichier audio."), 400
    ext = os.path.splitext(music.filename)[1].lower()
    if ext not in ALLOWED_AUDIO:
        return jsonify(error=f"Format non pris en charge ({ext}). Formats acceptés : {', '.join(sorted(ALLOWED_AUDIO))}"), 400
    mode = request.form.get("mode", "arcs")
    if mode not in MODES:
        return jsonify(error=f"Mode inconnu : {mode}"), 400
    try:
        cfg = parse_config(request.form.get("params"), MODES[mode][0])
    except (ValueError, TypeError) as error:
        return jsonify(error=f"Paramètres invalides : {error}"), 400

    job_id = uuid.uuid4().hex[:12]
    folder = os.path.join(JOBS_DIR, job_id)
    os.makedirs(folder)
    path = os.path.join(folder, "music" + ext)
    music.save(path)
    score = request.files.get("score")
    if mode == "platforms":
        cfg.score_path = ""                                  # jamais un chemin venant du client
        if score and score.filename:
            if os.path.splitext(score.filename)[1].lower() not in (".mid", ".midi"):
                shutil.rmtree(folder, ignore_errors=True)
                return jsonify(error="La partition doit être un fichier MIDI (.mid ou .midi)."), 400
            cfg.score_path = os.path.join(folder, "score.mid")
            score.save(cfg.score_path)
    jobs[job_id] = {"id": job_id, "status": "queued", "progress": 0, "logs": [], "music": path,
                    "config": cfg, "mode": mode, "created": time.time(), "name": music.filename}
    pending.put(job_id)
    return jsonify(id=job_id), 202


@app.get("/api/jobs/<job_id>")
def job_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify(error="Rendu introuvable"), 404
    position = list(pending.queue).index(job_id) + 1 if job["status"] == "queued" and job_id in pending.queue else 0
    return jsonify({k: job.get(k) for k in ("id", "status", "progress", "logs", "error", "result", "name", "mode")}
                   | {"queue_position": position})


@app.get("/api/jobs/<job_id>/video")
def job_video(job_id):
    job = jobs.get(job_id)
    if not job or job["status"] != "done":
        return jsonify(error="Vidéo pas encore prête"), 404
    name = os.path.splitext(job["name"])[0] + "_tiktok.mp4"
    return send_file(os.path.join(JOBS_DIR, job_id, "tiktok.mp4"), mimetype="video/mp4",
                     as_attachment=request.args.get("download") == "1", download_name=name)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
