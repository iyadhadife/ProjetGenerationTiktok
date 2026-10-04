# Service de transcription Sheet Sage 2 : image séparée, car le modèle exige ses propres versions
# (PyTorch 2.8, transformers 4.45, numpy 1.24) incompatibles avec le reste de l'application.
FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir torch==2.8.0 torchaudio==2.8.0 --extra-index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Code et poids de Sheet Sage 2 (~220 Mo) ; le modèle parent MERT-v2 est téléchargé au premier lancement
# puis gardé dans le volume /cache (HF_HOME)
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('m-a-p/SheetSage2', local_dir='/models/SheetSage2')"

ENV HF_HOME=/cache/huggingface RESULT_CACHE=/cache/results PYTHONUNBUFFERED=1
WORKDIR /app
COPY server.py .
EXPOSE 5001
# Un seul processus : le modèle reste chargé en mémoire ; les transcriptions longues ont un délai large
CMD ["gunicorn", "-w", "1", "--threads", "4", "-b", "0.0.0.0:5001", "--timeout", "3600", "server:app"]
