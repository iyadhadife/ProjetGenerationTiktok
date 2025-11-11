# Utiliser Python 3.10 comme base
FROM python:3.10

# Installer les dépendances système nécessaires à PyAudio et MoviePy
RUN apt-get update && apt-get install -y portaudio19-dev ffmpeg && rm -rf /var/lib/apt/lists/*

# Définir le répertoire de travail
WORKDIR /app/source

# Copier tous les fichiers du projet
COPY . /app

# Installer les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Définir le point d'entrée (dossier source)
WORKDIR /app/source

# Exécuter le programme principal
CMD ["python", "gen_vidéo_IA.py"]
