"""
Client du service de transcription Sheet Sage 2 (web/transcriber).

Le service tourne dans son propre conteneur ; son adresse est donnée par la variable TRANSCRIBER_URL
(http://transcriber:5001 dans docker-compose). Les notes sont renvoyées sous la forme
[début, fin, note MIDI, intensité 0-1].
"""
import os

import requests

TRANSCRIBER_URL = os.environ.get("TRANSCRIBER_URL", "http://localhost:5001")


def sheetsage_transcribe(music_path, duration):
    """Mélodie, accords, temps, mesures, tonalité et structure des `duration` premières secondes.

    Le service peut renvoyer plus que demandé (il transcrit par blocs de 60 s) : on coupe ici.
    """
    with open(music_path, "rb") as f:
        response = requests.post(
            f"{TRANSCRIBER_URL}/transcribe",
            files={"audio": (os.path.basename(music_path), f)},
            data={"duration": duration},
            timeout=3600,
        )
    if response.status_code != 200:
        try:
            message = response.json().get("error")
        except ValueError:
            message = response.text[:200]
        raise RuntimeError(f"Service de transcription indisponible ou en erreur : {message}")
    result = response.json()
    for key in ("melody", "chords"):
        result[key] = [n for n in result[key] if n[0] < duration]
    for key in ("beats", "downbeats"):
        result[key] = [t for t in result[key] if t < duration]
    result["chord_labels"] = [c for c in result["chord_labels"] if c[0] < duration]
    return result
