---
name: monteur-copie-style
description: Copie le style de montage de vidéos de référence (liens YouTube/Shorts/TikTok ou fichiers MP4) — rythme de coupe, durée des plans, fréquence des zooms, densité de B-roll, format, loudness, étalonnage, typographie et couleurs des sous-titres — et le transforme en style MonteurOS réutilisable. Utiliser pour « monte comme cette vidéo », « copie le style de ce youtubeur », « même style que ce Reel ».
---

# Copie de style

## 1. Mesurer (automatique)
```bash
bin/monteur style "https://youtu.be/XXXX" ref2.mp4 --name nom-du-style [--transcribe]
```
Télécharge (yt-dlp, ≤1080p) et mesure : coupes/min, durée moyenne/médiane des plans, ratio de silence, LUFS, luminance/saturation, format ; `--transcribe` ajoute les mots/min.
Sorties : `styles/refs/<nom>/<vidéo>/profile.json`, planches `contact_sheet.png` (30 images), `burst.png` (rafale 4 i/s → zooms, pops, transitions), `frame_1..3.png` (pleine définition → typo). Brouillon : `styles/<nom>.json`.

## 2. Regarder (toi — obligatoire)
Ouvre les PNG avec l'outil Read et complète `styles/<nom>.json` :
- **subtitles** : police la plus proche dans `assets/fonts/` (sinon télécharge l'OFL équivalente depuis github.com/google/fonts dans `assets/fonts/`), taille relative, couleurs (`primary`, `highlight`, `emphasis` en hex), majuscules, mots par bloc, position, cartouche (`box`), contour.
- **zoom** : la rafale montre-t-elle des punch-ins ? fréquence ? amplitude ?
- **broll** : proportion d'images de coupe vs face caméra, plein écran ou PiP.
- **motion** : titres, emojis, lower-thirds, CTA ; couleur d'accent.
- **look** : `eq` (`contrast=…:saturation=…`), `curves` (`vintage`, `increase_contrast`…), `vignette`, `grain`, `letterbox`.
- **sfx** : son présent sur chaque zoom ? musique permanente ?
Supprime la clé `_todo_claude` une fois rempli. Ajoute une `description` d'une phrase.

## 3. Appliquer
`bin/monteur prep RUSH.mp4 --style nom-du-style` puis rendu, puis compare côte à côte (planche du rendu vs `contact_sheet.png`) et itère une fois.

Limites : on copie un **style**, pas le contenu — pas de réutilisation des images/musiques de la référence. Si YouTube bloque le téléchargement, demande le MP4 ou des captures.
