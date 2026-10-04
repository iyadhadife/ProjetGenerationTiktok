"""
Transforme les rebonds en notes de piano qui suivent la musique.

1. detect_notes : pour chaque rebond, on prend la note la plus présente dans le morceau à cet instant
   (transformée à Q constant, CQT, sur la tessiture C3–C6) : c'est souvent la mélodie ou l'accord en cours.
2. piano_note : un son de piano synthétisé (harmoniques légèrement inharmoniques, attaque de marteau,
   décroissance plus rapide dans les aigus).
3. add_piano : place chaque note sur la bande-son, avec ou sans la musique d'origine.
"""
import numpy as np
from pydub import AudioSegment

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
LOW, HIGH = 48, 84          # tessiture retenue : C3 à C6
SR = 44100


def note_name(midi):
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


def detect_notes(music_path, times, window=0.12):
    """Note MIDI dominante juste après chaque instant (on laisse passer l'attaque, plus bruitée)."""
    import librosa
    if not times:
        return []
    y, sr = librosa.load(music_path, sr=22050, mono=True)
    hop = 512
    fmin = librosa.midi_to_hz(LOW)
    cqt = np.abs(librosa.cqt(y, sr=sr, hop_length=hop, fmin=fmin, n_bins=HIGH - LOW + 1, bins_per_octave=12))
    notes = []
    for t in times:
        start = librosa.time_to_frames(t + 0.03, sr=sr, hop_length=hop)
        end = max(start + 1, librosa.time_to_frames(t + 0.03 + window, sr=sr, hop_length=hop))
        energy = cqt[:, min(start, cqt.shape[1] - 1):min(end, cqt.shape[1])].mean(axis=1)
        # Une note est renforcée par ses octaves voisines (harmoniques) : on favorise la classe de note
        # la plus présente, puis on garde son octave la plus forte
        chroma = np.array([energy[i::12].sum() for i in range(12)])
        pitch_class = int(np.argmax(chroma))
        candidates = list(range(pitch_class, len(energy), 12))
        strongest = max(energy[i] for i in candidates)
        # Parmi les octaves bien présentes, la plus proche de la note précédente : la mélodie reste liée
        strong = [i for i in candidates if energy[i] >= 0.5 * strongest]
        previous = notes[-1] - LOW if notes else 12
        notes.append(LOW + min(strong, key=lambda i: abs(i - previous)))
    return notes


def piano_note(midi, duration=1.6, velocity=0.8):
    """Son de piano synthétisé (mono, 16 bits)."""
    freq = 440.0 * 2 ** ((midi - 69) / 12)
    t = np.arange(int(SR * duration)) / SR
    decay = 1.2 * 2 ** (-(midi - 60) / 24)       # les aigus s'éteignent plus vite
    wave = np.zeros_like(t)
    for k in range(1, 9):
        partial = freq * k * np.sqrt(1 + 0.0004 * k * k)   # légère inharmonicité des cordes
        if partial > SR / 2:
            break
        wave += (1 / k ** 1.4) * np.exp(-t * k / decay) * np.sin(2 * np.pi * partial * t)
    attack = np.minimum(1.0, t / 0.004)
    hammer = np.random.default_rng(midi).normal(0, 1, len(t)) * np.exp(-t * 90) * 0.08
    signal = (wave * attack + hammer) * np.exp(-t * 0.6 / decay)
    signal = signal / (np.abs(signal).max() + 1e-9) * velocity
    fade = np.minimum(1.0, (duration - t) / 0.05)          # pas de clic en fin de note
    pcm = (signal * fade * 32767 * 0.9).astype(np.int16)
    return AudioSegment(pcm.tobytes(), frame_rate=SR, sample_width=2, channels=1)


def add_piano(track, notes, positions_ms, mode="mix", volume=-4.0):
    """Ajoute les notes à la bande-son. mode : "mix" (avec la musique) ou "solo" (piano seul)."""
    if mode == "solo":
        track = AudioSegment.silent(duration=len(track), frame_rate=SR)
    track = track.set_frame_rate(SR)
    cache = {}
    for midi, position in zip(notes, positions_ms):
        if midi not in cache:
            cache[midi] = piano_note(midi) + volume
        track = track.overlay(cache[midi], position=int(position))
    return track
