import cv2
import numpy as np
from pydub import AudioSegment
from pydub.playback import play
import pyaudio, wave
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips
import os   

# Audio parameters
FORMAT = pyaudio.paInt16
CHANNELS = 2
RATE = 44100
CHUNK = 1024

# Fonction d’enregistrement audio avec PyAudio
def record_audio(stop_event, output_path):
    p = pyaudio.PyAudio()

    # 🔎 Trouver l’index du périphérique "Stereo Mix" ou loopback
    stereo_index = 1

    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    input_device_index=stereo_index,
                    frames_per_buffer=CHUNK)

    frames = []
    print("🎙️ Enregistrement audio...")
    while not stop_event.is_set():
        data = stream.read(CHUNK)
        frames.append(data)

    stream.stop_stream()
    stream.close()
    p.terminate()

    wf = wave.open(output_path, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()
    print("✅ Audio sauvegardé :", output_path)

# Charger la vidéo
def charger_video(audio_path, video_path):
    # Charger la vidéo
    video_clip = VideoFileClip(video_path)

    # Charger l'audio
    audio_clip = AudioFileClip(audio_path)

    # Ajuster l'audio à la durée de la vidéo
    audio_clip = audio_clip.subclip(0, video_clip.duration)

    # Ajouter l'audio à la vidéo
    final_clip = video_clip.set_audio(audio_clip)

    # Exporter la vidéo finale
    final_clip.write_videofile(r"C:\Users\ihadi\Desktop\VideoResultTikTok\my_simulation_audio_video.mp4", codec="libx264", audio_codec="aac")

    print("Fusion audio + vidéo terminée !")
