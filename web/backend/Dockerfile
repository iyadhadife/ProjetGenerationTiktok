# API de rendu : à construire depuis la racine du dépôt (voir docker-compose.yml)
FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY web/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bin ./bin
COPY source ./source
COPY web/backend/app.py ./api/app.py

ENV SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PYTHONUNBUFFERED=1 \
    RENDER_SOURCE=/app/source JOBS_DIR=/data/jobs
WORKDIR /app/api
EXPOSE 5000

# Un seul worker : les rendus sont mis en file d'attente dans le processus
CMD ["gunicorn", "-w", "1", "--threads", "8", "-b", "0.0.0.0:5000", "--timeout", "120", "app:app"]
