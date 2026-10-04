# ProjetGenerationTiktok

Générateur de vidéos verticales (format TikTok, 1080×1920, 60 ips) à partir d'une simulation physique écrite en Python avec Pygame.

Deux balles rebondissent à l'intérieur de 20 arcs de cercle concentriques qui tournent. Chaque fois qu'une balle passe par l'ouverture d'un arc, elle le détruit, marque un point, et les arcs restants se resserrent. La vidéo finale est exportée en `.mp4`, avec la musique et un son de rebond à chaque collision.

## Démo

<p align="center">
  <img src="docs/demo.gif" alt="Démo : deux balles détruisent des arcs de cercle concentriques" width="320">
</p>

Chaque rebond tombe sur un temps fort de la musique. Version avec le son : [docs/demo.mp4](docs/demo.mp4)

## Application web : rebonds synchronisés sur ta musique

Une interface React permet d'importer n'importe quelle musique et de régler les paramètres. La vidéo TikTok est ensuite générée automatiquement :

```bash
docker compose up -d --build
```

Ouvre ensuite http://localhost:8080.

1. Glisse ta musique (mp3, wav, ogg, flac ou m4a, 50 Mo maximum).
2. Règle les paramètres. Un aperçu animé se met à jour en direct.
   - **Synchronisation** : sensibilité de détection, sélectivité (garder seulement les temps les plus forts), écart minimum entre deux rebonds, fréquence de destruction des arcs, son de rebond.
   - **Vidéo** : titre, durée maximale, 30 ou 60 ips, couleur de fond.
   - **Arcs** : nombre, rayon, espacement, ouverture, vitesse de rotation, épaisseur, dégradé de couleurs.
   - **Balles** : 1 à 4 balles, avec nom et couleur, taille, gravité, graine aléatoire.
3. Clique sur **Générer la vidéo**. Une barre de progression s'affiche, puis la vidéo apparaît avec un bouton de téléchargement.

**Comment les rebonds suivent la musique** ([`source/beat_render.py`](source/beat_render.py)) :
- librosa détecte les temps forts (*onsets*) du morceau et mesure leur force. Sur un morceau rapide, seuls les meilleurs sont gardés : les plus faibles sont écartés (**sélectivité**), et quand deux temps sont trop proches, le plus fort l'emporte (**écart minimum**). Les balles se partagent ensuite les temps retenus à tour de rôle.
- Après chaque rebond, la balle repart sous l'effet de la gravité. Parmi des dizaines de points d'impact possibles, le moteur choisit la parabole qui touche l'arc exactement au temps suivant et ressemble le plus au vrai rebond physique (réflexion sur la paroi).
- La gravité est adaptée au tempo pour que les vols soient de vraies paraboles. Le réglage de gravité sert de maximum.
- Quand il n'y a plus de temps fort à viser, les balles continuent en vol libre avec rebonds : elles ne s'arrêtent jamais.
- `python source/check_bounces.py musique.mp3` affiche, sans générer de vidéo, le nombre de temps retenus, la part de trajectoires sous gravité réelle et la vitesse minimale des balles.
- En moyenne un rebond sur N (par tirage aléatoire), la balle vise l'ouverture : elle traverse l'arc, le détruit et marque un point.

Le moteur s'utilise aussi en ligne de commande :

```bash
cd source
python beat_render.py ma_musique.mp3 --max-duration 30 --title "Qui va gagner ?"
```

### Mode « Plateformes »

Deuxième onglet de l'interface : une balle tombe sous gravité et rebondit sur des plateformes qui apparaissent au bon endroit, **sur le tempo du morceau** ([`source/platform_render.py`](source/platform_render.py)).

- **Rythme :** librosa détecte la pulsation (BPM). La balle rebondit tous les 1, 2 ou 4 temps selon l'écart minimum choisi, calée sur les temps les plus forts. Un mode « attaques » suit plutôt les temps forts les plus marqués.
- **Plateformes :** chacune est orientée pour renvoyer la balle vers la suivante. La trajectoire est une vraie parabole sous gravité constante.
- **Effets :** apparition des plateformes avec ralenti de fin de mouvement, puis flash, onde de choc, particules et tremblement à l'impact. S'y ajoutent la traînée lumineuse, la caméra qui suit la balle, le fond qui pulse sur chaque temps, un petit zoom à chaque mesure et des couleurs en dégradé.
- **Réglages :** tous ces effets se règlent dans l'onglet.

```bash
cd source
python platform_render.py ma_musique.mp3 --max-duration 30
```

### Notes de piano

Chaque rebond peut jouer une note de piano qui suit la musique ([`source/piano.py`](source/piano.py)). Cette option est disponible dans les deux onglets.

- **Choix de la note :** à l'instant du rebond, une transformée à Q constant (CQT) repère la note la plus présente dans le morceau, entre C3 et C6. C'est en général la mélodie ou l'accord en cours, donc le piano joue dans la tonalité du morceau. L'octave retenue est la plus proche de la note précédente, pour que la ligne reste liée.
- **Son :** le piano est synthétisé (harmoniques, attaque de marteau, aigus plus courts). Il ne demande aucun fichier de sons.
- **Trois réglages :** désactivé, piano + musique, ou piano seul.
- **Dans l'onglet Plateformes :** chaque plateforme prend la couleur de sa note (une teinte par note) et peut afficher son nom (C4, F#5…).

| Service | Rôle |
|---|---|
| `frontend` | React (Vite) servi par nginx sur le port 8080, qui redirige `/api` vers l'API |
| `api` | Flask + gunicorn : reçoit la musique, met les rendus en file d'attente, sert les vidéos (les 20 dernières sont conservées) |

## Rendu simple en ligne de commande (Docker)

Ce mode rejoue la simulation d'origine, sans synchronisation sur la musique. Il n'y a ni écran ni carte son à configurer : la vidéo est calculée image par image dans le conteneur.

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
├── docker-compose.yml          # application web (frontend + api)
├── Dockerfile                  # image de rendu headless (ligne de commande)
├── web/
│   ├── backend/                # API Flask (file d'attente des rendus)
│   └── frontend/               # interface React + aperçu animé
├── requirements-render.txt     # dépendances minimales du rendu (Docker)
├── requirements.txt            # dépendances du script interactif d'origine
├── bin/                        # musique et son de rebond
├── docs/                       # démo (GIF et MP4)
└── source/
    ├── beat_render.py          # mode Arcs, synchronisé sur la musique (utilisé par l'API)
    ├── platform_render.py      # mode Plateformes, synchronisé sur le tempo (utilisé par l'API)
    ├── piano.py                # détection des notes et piano synthétisé
    ├── check_bounces.py        # mesures du mode Arcs sans générer de vidéo
    ├── render.py               # rendu de la simulation d'origine sans écran
    ├── gen_vidéo_IA.py         # version interactive d'origine (fenêtre + enregistrement)
    ├── bouncing1v1/            # physique : balles et arcs
    ├── audio_image_scripts/    # dégradés de couleurs, fusion audio/vidéo
    └── musicbouncing/          # détection des temps forts de la musique (librosa)
```

## Technologies

Python, Pygame, librosa, NumPy, pydub, ffmpeg (imageio-ffmpeg), Flask, React, Vite, nginx, Docker Compose
