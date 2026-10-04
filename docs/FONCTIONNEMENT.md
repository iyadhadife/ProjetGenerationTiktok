# Fonctionnement détaillé — onglet Plateformes

Ce document décrit précisément ce qui se passe entre l'envoi d'une musique et la vidéo TikTok finale,
en particulier la **génération de la partition de piano** et **la façon dont elle est jouée et synchronisée**
avec les rebonds. Le réglage par défaut est décrit : synchronisation `notes`, moteur `sheetsage2`.

```
musique.mp3
   │
   ▼
[1] Partition MIDI fournie, calée par DTW si elle correspond au morceau
    sinon : service de transcription (conteneur transcriber, Sheet Sage 2)
   │   mélodie (MIDI) + accords (MIDI) + temps + mesures + tonalité  ──► cache par morceau
   ▼
[2] Vérification de la partition sur l'audio (source/platform_render.py)
   │   ordre des notes corrigé, chaque note recalée sur son attaque réelle
   ▼
[3] Notes → rebonds (group_events)
   ▼
[4] Trajectoire de la balle (plan_path) au temps exact de chaque note
   ▼
[5] Rendu image par image (pygame, 60 ips)          [6] Bande-son : piano synthétisé (piano.py)
   └──────────────────────────────┬─────────────────────────────┘
                                  ▼
                 [7] Fusion audio + vidéo (ffmpeg) → vidéo 1080×1920
```

## 0. Parcours d'une demande

1. Le frontend React (`web/frontend`, port 8080) envoie la musique et les réglages à l'API Flask
   (`web/backend/app.py`).
2. L'API valide chaque réglage (`parse_config` : bornes, valeurs autorisées), crée une tâche et lance
   `render()` de `source/platform_render.py` en arrière-plan. Le frontend suit la progression et les messages.
3. La vidéo terminée est téléchargeable depuis l'interface.

## 1. Transcription : Sheet Sage 2

**Fichiers :** `web/transcriber/server.py`, `source/sheetsage_client.py`

- Le modèle [Sheet Sage 2](https://huggingface.co/m-a-p/SheetSage2) tourne dans son propre conteneur
  (versions précises de PyTorch / transformers). Il est chargé **une seule fois** au démarrage du service.
- Il s'appuie sur MERT, un modèle de représentation musicale pré-entraîné, et produit une **partition
  simplifiée façon « lead sheet »** :
  - `melody` : la ligne mélodique principale (voix ou instrument), en notes MIDI `[début, fin, hauteur, intensité]` ;
  - `chords` : les accords d'accompagnement, en notes MIDI ;
  - `beats` / `downbeats` : les temps et les débuts de mesure ;
  - `chord_labels` : le nom des accords dans le temps (`D:min`, `Bb:maj7`…) ;
  - `key` : la tonalité.
- Contrairement à une transcription « toutes les notes » (Basic Pitch, YourMT3…), Sheet Sage ne garde que
  ce qu'on écrirait sur une partition de chanson : c'est ce qui rend la mélodie reconnaissable. Le carnet
  `experiments/transcription/comparaison_transcription.ipynb` compare les 7 approches testées.
- **Extrait et cache :** le service ne transcrit que le début utile du morceau, par blocs de 60 s
  (mono 24 kHz). Le résultat est mis en cache selon l'empreinte SHA-256 du fichier : relancer le même morceau
  avec d'autres couleurs, une autre vitesse ou une autre durée (dans la partie déjà transcrite) est immédiat.
  Compter environ 2 min de calcul par minute de musique la première fois.
- Le client coupe ensuite tout ce qui dépasse la durée demandée.

**Limite connue :** Sheet Sage place ses notes sur une **grille de doubles croches** calculée à partir des
temps détectés. Si cette grille dérive légèrement, des notes arrivent en retard, ou deux notes voisines sont
inversées. C'est ce que corrige l'étape suivante.

## 1 bis. Partition fournie (fichier MIDI, facultatif)

**Fichier :** `source/score_align.py`

Si tu as la partition du morceau (fichier `.mid`, par exemple téléchargé sur MuseScore et exporté en MIDI),
elle remplace la transcription automatique : **ses notes sont exactes**, il ne reste qu'à les caler sur
l'enregistrement.

1. **Lecture** (pretty_midi) : les pistes de batterie sont ignorées.
2. **Alignement global par DTW** (Dynamic Time Warping) :
   - audio : chroma CENS (énergie des 12 notes do, do#… lissée sur ~1 s) de la partie harmonique ;
   - partition : chroma calculé directement depuis les notes, avec le même lissage ;
   - la DTW trouve le chemin qui fait correspondre chaque instant de la partition à un instant de
     l'enregistrement (tempo différent, ralentis, introduction…). Chaque note est déplacée le long de ce chemin.
   - Mesuré sur un test (partition jouée 8 % plus lentement et décalée de 2 s) : erreur médiane de 71 ms,
     ensuite corrigée par le recalage sur les attaques (étape 2, fenêtre élargie à ±0,2 s).
3. **Mélodie** : une piste nommée comme une mélodie (`melody`, `lead`, `vocal`, `flute`, `violin`…) est prise
   telle quelle ; sinon on prend la note la plus aiguë à chaque instant. Tout le reste devient l'accompagnement.
4. **Contrôles : la partition est utilisée seulement si elle est bonne**
   - elle doit couvrir le morceau (entre 60 % et 160 % de sa durée) ;
   - écart moyen d'alignement ≤ 0,35 (`score_max_cost`) ;
   - au moins 50 % des notes de la mélodie doivent **s'entendre** dans l'audio à leur instant : leur note
     (do, ré…) doit être parmi les 3 plus présentes. Au hasard, on obtient ~25 %.
     Test : bonne partition 59 %, partition transposée 38 %, donc rejetée.
   - Sinon : message dans le journal et retour automatique à Sheet Sage 2.

## 2. Vérification de la partition sur l'audio

**Fichier :** `source/platform_render.py` (`PitchSalience`, `refine_melody`, `snap_to_onsets`)

On confronte la partition à l'enregistrement lui-même :

1. **Carte des hauteurs (`PitchSalience`)**
   - Séparation harmonique / percussive (HPSS) : on retire la batterie, qui brouillerait les hauteurs.
   - Transformée à Q constant (CQT) : énergie de chaque demi-ton (de C1 à B7) toutes les 11,6 ms, en dB.
   - Détection des **attaques** (onsets) : les instants où un son commence vraiment dans l'audio.
   - `presence(note, t)` : énergie de la note juste après t.
     `attack(note, t)` : combien cette note se renforce à t (après moins avant), élevé si elle y est attaquée.
2. **Ordre des notes** : pour deux notes successives proches (< 0,4 s), on compare l'audio avec l'ordre
   transcrit et avec l'ordre inversé. Si l'ordre inversé correspond **nettement** mieux (+6 dB), on échange
   les deux hauteurs.
3. **Moment de chaque note** : parmi les attaques réelles à ±120 ms, on choisit celle où **la hauteur de
   cette note** apparaît le plus nettement, avec une légère préférence pour l'attaque la plus proche et un
   petit bonus pour ne pas bouger. Deux notes successives ne sont jamais rapprochées à moins de l'écart
   minimum entre rebonds : les traits rapides restent distincts.
4. **Accords** : chaque accord est déplacé en bloc sur l'attaque la plus proche (±80 ms).

Le journal affiche par exemple : `29 notes recalées, 6 paires remises dans l'ordre`.

## 3. Des notes aux rebonds

**Fichier :** `source/transcribe.py` (`group_events`)

- Chaque note de la **mélodie** devient un rebond. Les accords sont joués mais ne créent pas de plateforme.
- Des notes qui commencent à moins de 60 ms d'écart forment un seul rebond (une note double ou un accord).
- Deux rebonds sont séparés d'au moins `note_min_gap` (0,07 s par défaut, réglable jusqu'à 0,04 s) ;
  une note plus proche rejoint le rebond précédent, mais **reste jouée à son vrai moment** dans la bande-son.
- Chaque rebond reçoit le nom de sa note la plus aiguë (affiché sur la plateforme) et la fondamentale de
  l'accord en cours, qui donne la couleur de la plateforme (12 couleurs, une par note).
- Le fond pulse sur chaque temps, et la caméra zoome brièvement à chaque début de mesure.

## 4. Trajectoire de la balle

**Fichier :** `source/platform_render.py` (`plan_path`, `ball_position`)

- La balle suit des **paraboles** (gravité constante). La gravité est réglée pour que le saut typique du
  morceau ait la hauteur `jump_height`.
- Chaque rebond est placé au **temps exact de la note**, en images fractionnaires (ex. image 26,4) :
  le contact n'est pas arrondi à l'image la plus proche. Chaque image montre donc la balle à sa vraie position,
  juste avant ou juste après le choc.
- `visual_lead` (0,06 s par défaut) avance légèrement l'image sur le son : l'œil perçoit un rebond un peu après
  le contact physique. Réglable de −0,2 à +0,2 s dans l'interface.
- Entre deux rebonds, la vitesse de départ est calculée pour atteindre la plateforme suivante pile au bon
  moment ; la plateforme est orientée selon le changement de vitesse, comme un vrai rebond.
- Un rebond rapide fait un petit saut, un rebond lent un grand ; les plateformes alternent gauche / droite.
- Pendant une pause de la musique, des **rebonds silencieux** (plateformes discrètes, sans note) sont ajoutés
  pour que la balle ne sorte pas de l'écran. Après le dernier rebond, la balle continue sa course.

## 5. Rendu image

- pygame sans écran (SDL « dummy »), 1080×1920, **60 images/s** par défaut (30 possible).
- Les plateformes apparaissent 0,45 s avant leur rebond et s'effacent ensuite. Au contact : flash blanc,
  halo, onde, particules et léger tremblement de caméra ; la caméra suit la balle en douceur.
- Les images sont envoyées une à une à l'encodeur H.264 (imageio-ffmpeg).

## 6. Comment la partition est jouée

**Fichier :** `source/piano.py` (`piano_wave`, `add_transcription`)

- **Contenu joué** (`piano_content`) : `melody` (mélodie seule), `melody_chords` (mélodie + accords plus
  doux, à 45 % d'intensité, par défaut) ou `all`.
- **Synthèse** : aucun échantillon n'est utilisé ; chaque note est calculée :
  - 8 harmoniques, de plus en plus faibles, avec la légère **inharmonicité** des cordes de piano ;
  - attaque de 4 ms et petit bruit de **marteau** au début de la note ;
  - décroissance exponentielle, plus rapide pour les aigus ;
  - durée = durée de la note transcrite (entre 0,15 et 3 s) + 0,35 s de résonance, avec un fondu final pour
    éviter les clics ;
  - intensité tirée de l'intensité transcrite.
- **Mixage** : toutes les notes sont additionnées dans un seul tampon numpy, chacune à son **temps exact**
  (à l'échantillon près), y compris celles qui partagent un rebond.
- **Mode `solo`** (par défaut) : la musique d'origine est retirée, seul le piano reste, puis il est normalisé.
  Le mode `mix` le superpose à la musique.
- **Vitesse de lecture** (`playback_speed`) : la transcription est faite sur le morceau original, puis tous
  les temps (notes, rebonds, temps, mesures) sont étirés de 1/vitesse. La musique d'origine éventuelle est
  ralentie sans changer la hauteur (filtre `atempo` de ffmpeg). La partition reste donc la même, plus lente.

## 7. Fusion

ffmpeg assemble la vidéo muette et la bande-son (AAC 192 kb/s) dans le MP4 final. Les deux pistes démarrent
à 0 : la synchronisation repose entièrement sur les temps calculés aux étapes 2 à 6.

## Autres modes

- Moteur `basic_pitch` : transcription de toutes les notes (Basic Pitch), puis extraction de la mélodie par
  programmation dynamique (Viterbi) et accords déduits avec la tonalité (`source/transcribe.py`).
- Synchronisation `tempo` ou `onsets` : rebonds sur la pulsation (tempo variable dans le temps) ou sur les
  attaques fortes ; la note de chaque rebond est alors devinée dans l'audio (`detect_notes`, `detect_chords`).
- L'onglet **Arcs** (`source/beat_render.py`) garde l'animation d'origine : balles qui rebondissent dans des arcs.

## Limites actuelles

- Sans partition, les passages très denses (beaucoup d'instruments ensemble) restent les plus difficiles :
  Sheet Sage 2 a été entraîné sur de la pop (HookTheory) et peut s'y tromper de note. La vérification sur
  l'audio ne corrige que l'ordre et le moment, pas une hauteur fausse. **Fournir la partition MIDI** règle ce
  problème.
- La partition doit couvrir tout le morceau, depuis le début (pas un extrait).
- Sheet Sage 2 est sous licence CC BY-NC 4.0 : usage non commercial uniquement.
