# ProjetGenerationTiktok

Générateur de vidéos verticales (format TikTok, 1080×1920, 60 ips) à partir d'une simulation physique écrite en Python avec Pygame.

Deux balles rebondissent à l'intérieur de 20 arcs de cercle concentriques qui tournent. Chaque fois qu'une balle passe par l'ouverture d'un arc, elle le détruit, marque un point, et les arcs restants se resserrent. La vidéo finale est exportée en `.mp4`, avec la musique et un son de rebond à chaque collision.

## Démo

<p align="center">
  <img src="docs/demo.gif" alt="Démo : deux balles détruisent des arcs de cercle concentriques" width="320">
</p>

Version complète, avec le son : [docs/demo.mp4](docs/demo.mp4)

## Lancer avec Docker (recommandé)

Il n'y a ni écran ni carte son à configurer : la vidéo est calculée image par image dans le conteneur.

```bash
docker build -t tiktok-generator .
docker run --rm -v "$(pwd)/VideoResult:/app/VideoResult" tiktok-generator
```

La vidéo est écrite dans `VideoResult/tiktok.mp4`.

Options disponibles :

```bash
docker run --rm -v "$(pwd)/VideoResult:/app/VideoResult" tiktok-generator \
  --duration 20 --seed 7 --output /app/VideoResult/ma_video.mp4
```

| Option | Rôle | Défaut |
|---|---|---|
| `--duration` | Durée maximale en secondes. La vidéo s'arrête 1 s après la destruction du dernier arc. | `30` |
| `--seed` | Graine aléatoire pour reproduire exactement la même vidéo | aléatoire |
| `--output` | Chemin du fichier `.mp4` | `VideoResult/tiktok.mp4` |

> Sous Windows PowerShell, remplace `$(pwd)` par `${PWD}`.

## Lancer sans Docker

Il faut Python 3.10 et ffmpeg installé sur la machine.

```bash
pip install -r requirements-render.txt
cd source
python render.py
```

Le script d'origine `source/gen_vidéo_IA.py` reste disponible. Il affiche la simulation dans une fenêtre et l'enregistre en temps réel, ce qui demande un écran, une carte son et le périphérique « Stereo Mix ». Ses dépendances sont dans `requirements.txt`.

## Comment ça marche

1. **Simulation** ([`source/bouncing1v1`](source/bouncing1v1)) :
   - `Ball` gère la gravité, les rebonds et les collisions élastiques entre les deux balles (calcul d'impulsion le long de la normale).
   - `ArcWall` détecte si une balle touche l'arc ou passe par son ouverture.
2. **Rendu headless** ([`source/render.py`](source/render.py)) : Pygame dessine chaque image hors écran (`SDL_VIDEODRIVER=dummy`), puis les images sont envoyées directement à ffmpeg (H.264).
3. **Bande-son** : chaque rebond est noté avec son numéro d'image. La musique est ensuite reconstruite avec pydub, en superposant le son de rebond au moment exact de chaque collision. Le son est donc parfaitement synchronisé avec l'image, sans enregistrer la carte son.
4. **Fusion** : ffmpeg assemble la vidéo et l'audio dans le fichier final.

## Structure

```
.
├── Dockerfile                  # image de rendu headless
├── requirements-render.txt     # dépendances minimales du rendu (Docker)
├── requirements.txt            # dépendances du script interactif d'origine
├── bin/                        # musique et son de rebond
├── docs/                       # démo (GIF et MP4)
└── source/
    ├── render.py               # point d'entrée : génère la vidéo sans écran
    ├── gen_vidéo_IA.py         # version interactive d'origine (fenêtre + enregistrement)
    ├── bouncing1v1/            # physique : balles et arcs
    ├── audio_image_scripts/    # dégradés de couleurs, fusion audio/vidéo
    └── musicbouncing/          # détection des temps forts de la musique (librosa)
```

## Technologies

Python, Pygame, NumPy, pydub, ffmpeg (imageio-ffmpeg), Docker
