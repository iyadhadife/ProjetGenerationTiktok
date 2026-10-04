# Rendu headless de la vidéo : pas d'écran ni de carte son nécessaires
FROM python:3.10-slim

# ffmpeg : encodage vidéo et décodage des mp3 (pydub)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements-render.txt .
RUN pip install --no-cache-dir -r requirements-render.txt

COPY bin ./bin
COPY source ./source

WORKDIR /app/source
ENV SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PYTHONUNBUFFERED=1

# La vidéo est écrite dans /app/VideoResult : monter ce dossier pour la récupérer
ENTRYPOINT ["python", "render.py"]
CMD ["--duration", "30"]
