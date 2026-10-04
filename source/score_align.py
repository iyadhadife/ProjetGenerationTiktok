"""
Partition fournie par l'utilisateur (fichier MIDI) calée sur l'enregistrement.

Une vraie partition donne les bonnes notes, mais pas les bons instants : l'interprétation enregistrée accélère,
ralentit, commence après une introduction... On aligne donc la partition sur l'audio par DTW (Dynamic Time
Warping) sur les chromagrammes CENS (énergie des 12 notes, lissée sur ~1 s : robuste aux timbres et aux
nuances) : pour chaque instant de la partition, on trouve l'instant correspondant du morceau, puis on déplace
chaque note en conséquence. L'alignement est global : la partition doit couvrir tout le morceau, depuis le début.
Le recalage fin de chaque note sur son attaque est ensuite fait par refine_melody (platform_render.py).

Si l'alignement est mauvais (partition d'un autre morceau, autre arrangement...), on le signale pour revenir
à la transcription automatique.
"""
import numpy as np

from transcribe import Note

SR = 22050
MAX_ALIGN = 480                                               # s : au-delà, la matrice d'alignement serait trop lourde
MELODY_NAMES = ("melod", "lead", "vocal", "voice", "voix", "chant", "solo", "flute", "violin", "trumpet")


def _unit(chroma):
    chroma = chroma + 1e-3                                    # silences : évite les vecteurs nuls (cosinus indéfini)
    return chroma / np.linalg.norm(chroma, axis=0, keepdims=True)


def _chroma_audio(music_path, duration, hop):
    import librosa
    y, _ = librosa.load(music_path, sr=SR, mono=True, duration=duration)
    harmonic = librosa.effects.harmonic(y, margin=2.0)        # sans la batterie
    return _unit(librosa.feature.chroma_cens(y=harmonic, sr=SR, hop_length=hop))


def _chroma_score(midi, hop):
    from scipy.ndimage import uniform_filter1d
    chroma = midi.get_chroma(fs=SR / hop)                     # directement depuis les notes
    width = max(3, int(round(0.95 * SR / hop)) | 1)           # même lissage (~1 s) que les chromas CENS
    return _unit(uniform_filter1d(chroma, width, axis=1))


def split_melody(notes_by_instrument):
    """Sépare la mélodie du reste.

    - une piste dont le nom évoque la mélodie (lead, vocal, flute...) est prise telle quelle ;
    - sinon, ligne la plus aiguë (« skyline ») : à chaque attaque, la note la plus haute.
    """
    for name, notes in notes_by_instrument:
        if any(k in name.lower() for k in MELODY_NAMES) and notes:
            melody = sorted(notes, key=lambda n: n.start)
            others = [n for other, ns in notes_by_instrument if other != name for n in ns]
            return melody, others
    every = sorted((n for _, ns in notes_by_instrument for n in ns), key=lambda n: (n.start, -n.midi))
    melody, others, last = [], [], None
    for n in every:
        if last is not None and abs(n.start - last.start) < 0.03:
            others.append(n)                                  # note plus grave du même accord
        elif last is not None and n.start < last.end - 0.05 and n.midi < last.midi:
            others.append(n)                                  # sous une note de mélodie encore tenue
        else:
            melody.append(n)
            last = n
    return melody, others


def load_aligned_score(score_path, music_path, span, log=print, align_duration=None):
    """Partition calée sur l'audio : {melody, chords, beats, downbeats, cost} ou None si inutilisable.

    `cost` : distance moyenne (cosinus, 0 = identique) le long du chemin d'alignement. Au-delà de ~0.35 la
    partition ne correspond pas à l'enregistrement.
    """
    import librosa
    import pretty_midi
    try:
        midi = pretty_midi.PrettyMIDI(score_path)
    except Exception as error:
        log(f"   partition illisible ({error}) : transcription automatique")
        return None
    pitched = [i for i in midi.instruments if not i.is_drum and i.notes]
    if not pitched:
        log("   la partition ne contient aucune note : transcription automatique")
        return None
    midi.instruments = pitched

    duration = min(librosa.get_duration(path=music_path), MAX_ALIGN) if align_duration is None else align_duration
    hop = 512 if duration <= 120 else 1024                    # morceau long : grille plus grossière (mémoire)
    coverage = midi.get_end_time() / duration
    if not 0.6 <= coverage <= 1.6:
        log(f"   la partition dure {midi.get_end_time():.0f} s pour {duration:.0f} s de musique : elle doit couvrir "
            "tout le morceau, transcription automatique")
        return None
    audio = _chroma_audio(music_path, duration, hop)
    score = _chroma_score(midi, hop)
    D, path = librosa.sequence.dtw(X=audio, Y=score, metric="cosine")
    path = path[::-1]
    cost = float(D[-1, -1] / len(path))
    audio_t = path[:, 0] * hop / SR
    score_t = path[:, 1] * hop / SR
    # Fonction monotone partition -> audio (moyenne des instants audio associés à un même instant de partition)
    keys, inverse = np.unique(score_t, return_inverse=True)
    values = np.bincount(inverse, weights=audio_t) / np.bincount(inverse)
    values = np.maximum.accumulate(values)

    def warp(t):
        return float(np.interp(t, keys, values, left=np.nan, right=np.nan))

    tracks = []
    for inst in pitched:
        notes = []
        for n in inst.notes:
            s, e = warp(n.start), warp(n.end)
            if np.isnan(s) or s >= span:
                continue
            e = s + 0.2 if np.isnan(e) or e <= s else e
            notes.append(Note(s, e, int(n.pitch), n.velocity / 127))
        tracks.append((inst.name or pretty_midi.program_to_instrument_name(inst.program), notes))
    melody, others = split_melody(tracks)
    beats = [b for b in (warp(t) for t in midi.get_beats()) if not np.isnan(b) and b < span]
    downbeats = [b for b in (warp(t) for t in midi.get_downbeats()) if not np.isnan(b) and b < span]
    # Les notes de la mélodie s'entendent-elles vraiment ? Part des notes dont la classe (do, ré...) est parmi
    # les 3 plus présentes de l'audio à cet instant (~25 % au hasard, bien plus pour la bonne partition)
    heard = [int(n.midi % 12 in np.argsort(audio[:, min(int(n.start * SR / hop), audio.shape[1] - 1)])[-3:])
             for n in melody]
    match = float(np.mean(heard)) if heard else 0.0
    return {"match": match, "melody": melody, "chords": [Note(n.start, n.end, n.midi, n.velocity * 0.45) for n in others],
            "beats": beats, "downbeats": downbeats, "cost": cost, "key": _key_name(midi)}


def _key_name(midi):
    if midi.key_signature_changes:
        import pretty_midi
        return pretty_midi.key_number_to_key_name(midi.key_signature_changes[0].key_number)
    return "?"
