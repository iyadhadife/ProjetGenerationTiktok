# Utiliser Python 3.10 comme base
FROM python:3.10

# Définir le répertoire de travail dans le container
WORKDIR /app

# Copier les fichiers du projet
COPY . /app

# Installer les dépendances système nécessaires à PyAudio
RUN apt-get update && apt-get install -y portaudio19-dev ffmpeg && rm -rf /var/lib/apt/lists/*

# Installer les dépendances si le fichier requirements.txt existe
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Exécuter le programme principal
CMD ["python", "gen_vidéo_IA.py"]