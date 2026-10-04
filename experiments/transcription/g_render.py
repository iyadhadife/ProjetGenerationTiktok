import sys, pretty_midi
sys.path.insert(0, "/app/source")
from pydub import AudioSegment
from piano import add_transcription, note_name
from transcribe import Note
d = "/out/G_sheetsage2_out"
def load(name, gain):
    m = pretty_midi.PrettyMIDI(f"{d}/{name}")
    return [Note(n.start, n.end, n.pitch, gain * n.velocity / 127) for i in m.instruments for n in i.notes]
melody = load("melody_instrumental.mid", 1.0) + load("melody_vocal.mid", 1.0)
chords = load("chords.mid", 0.45)
track = AudioSegment.silent(duration=60000, frame_rate=44100)
add_transcription(track, melody + chords, "solo", -4.0).export("/out/G_sheetsage2.mp3", format="mp3", bitrate="192k")
print(f"=== G_sheetsage2 : {len(melody)} notes de mélodie ({len(melody)/60:.1f}/s), {len(chords)} notes d'accords")
print("    extrait 20-30 s :", " ".join(note_name(n.midi) for n in sorted(melody, key=lambda n: n.start) if 20 <= n.start < 30))
