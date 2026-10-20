---
name: monteur-copie-style
description: Copie le style de montage de vidéos de référence (liens YouTube/Shorts/TikTok ou fichiers MP4) — rythme de coupe, durée des plans, fréquence des zooms, densité de B-roll, format, loudness, étalonnage, typographie et couleurs des sous-titres — et le transforme en style MonteurOS réutilisable. Utiliser pour « monte comme cette vidéo », « copie le style de ce youtubeur », « même style que ce Reel ».
---

# Copie de style

## 1. Mesurer (automatique)
```bash
bin/monteur style "https://youtu.be/XXXX" "https://www.tiktok.com/@x/video/…" ref2.mp4 --name nom-du-style [--transcribe] [--activer]
```
Depuis le Studio : **Bibliothèques → Références → Cloner un style viral** (liens YouTube/Shorts/TikTok/Instagram/Vimeo
et/ou MP4 déposés, case « Activer après la copie »). Le style apparaît aussitôt dans la bibliothèque (état **Copié**,
sources cliquables) et devient le style par défaut des nouveaux projets s'il est activé.
Télécharge (yt-dlp, ≤1080p) et mesure : coupes/min, durée moyenne/médiane des plans, ratio de silence, LUFS, luminance/saturation, format ; `--transcribe` ajoute les mots/min.
Le brouillon est déjà utilisable : couleurs vives lisibles relevées sur l'image → `subtitles.highlight/emphasis`, `motion.accent` ;
rythme → `cut.transition` (`mix` si ≥ 30 coupes/min, `zoomcut` si ≥ 15, sinon `hard`), mots par bloc, cartes de la bibliothèque (`library.cards`), ratio le plus proche (`9:16 16:9 1:1 4:5 3:4 2:3 21:9`).
Sorties : `styles/refs/<nom>/<vidéo>/profile.json`, planches `contact_sheet.png` (30 images), `burst.png` (rafale 4 i/s → zooms, pops, transitions), `frame_1..3.png` (pleine définition → typo). Brouillon : `styles/<nom>.json`.

## 1 bis. Affiner (automatique, enchaîné après la copie)
`bin/monteur affiner <nom>` (ou bouton **Affiner automatiquement** sur la page du style dans le Studio ; `--sans-affinage` pour sauter) :
- **cuts réels** à chaque coupe : flash (pic de luminance), passage au noir, whip (image floue), zoom cut (même plan recadré) → `cut.transition`, `transition_every` ;
- **zooms dans les plans** (ORB + similitude, 12 i/s) : punch-in ou poussée lente → `zoom.every_s`, `scale`, `pattern` ;
- **sous-titres incrustés** : bande de l'image (texte clair/vif bordé de sombre, concentré et qui change), taille (étalonnée sur un rendu MonteurOS), mots par bloc, blanc + couleur d'accent → `subtitles.position`, `margin_v`, `size`, `max_words`, `primary`, `highlight`. Pas de sous-titres dans la référence → ceux du style sont gardés.
Rapport dans `reference.affinage`, planche `styles/refs/<nom>/<vidéo>/affinage.png` (bande détectée en jaune), état **Affiné**.
Validé sur des rendus de style connu (hormozi : taille 0,075, marge 0,35, 2 mots, jaune, flash — retrouvés). Limites : la **police exacte**, les majuscules et la cartouche restent à vérifier à l'œil (étape 2 ; bouton « Copier pour Claude »).

## 2. Regarder (toi — obligatoire)
Ouvre les PNG avec l'outil Read et complète `styles/<nom>.json` :
- **subtitles** : police la plus proche dans `assets/fonts/` (sinon télécharge l'OFL équivalente depuis github.com/google/fonts dans `assets/fonts/`), taille relative, couleurs (`primary`, `highlight`, `emphasis` en hex), majuscules, mots par bloc, position, cartouche (`box`), contour.
- **zoom** : la rafale montre-t-elle des punch-ins ? fréquence ? amplitude ?
- **broll** : proportion d'images de coupe vs face caméra, plein écran ou PiP.
- **motion** : titres, emojis, lower-thirds, CTA ; couleur d'accent.
- **look** : `eq` (`contrast=…:saturation=…`), `curves` (`vintage`, `increase_contrast`…), `vignette`, `grain`, `letterbox`.
- **sfx** : son présent sur chaque zoom ? musique permanente ?
- **cut.transition** : la rafale montre-t-elle des flashs blancs (`flash`), des filés (`whip`), du glitch RGB (`glitch`), des passages au noir (`dip`), un plan serré un sur deux (`zoomcut`) ? `transition_every` : 1 = chaque coupe.
- **library.cards** : cartes de la bibliothèque qui ressemblent aux habillages vus (`bin/monteur cartes --cherche …`) ; s'il en manque une, crée-la (skill `monteur-bibliotheque`).
Supprime la clé `_todo_claude` une fois rempli. Ajoute une `description` d'une phrase.

## 3. Appliquer
`bin/monteur prep RUSH.mp4 --style nom-du-style` puis rendu, puis compare côte à côte (planche du rendu vs `contact_sheet.png`) et itère une fois.

Limites : on copie un **style**, pas le contenu — pas de réutilisation des images/musiques de la référence. Si YouTube bloque le téléchargement, demande le MP4 ou des captures.
