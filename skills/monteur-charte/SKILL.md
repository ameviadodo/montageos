---
name: monteur-charte
description: Applique une charte graphique à MonteurOS Studio (l'interface web) et aux vidéos — extrait couleurs, typographies, rayons, ambiance depuis des captures d'écran, une vidéo ou un lien YouTube (ex. l'interface « EditingOS » montrée dans une vidéo), puis génère le thème `ui/themes/<nom>.json` et aligne les styles vidéo (sous-titres, accents). Utiliser pour « reprends la charte de… », « mets l'interface aux couleurs de… », « même look que l'interface de la vidéo ».
---

# Charte graphique

## 1. Extraire
```bash
bin/monteur charte capture1.png capture2.png [video.mp4] ["https://youtube.com/watch?v=…"] --name editingos
```
→ `ui/themes/editingos.json` (palette dominante, rôles de couleurs proposés) + captures dans `ui/themes/editingos/`. Pour une vidéo YouTube, le moment où l'interface apparaît compte : si l'utilisateur donne un horodatage, découpe d'abord : `ffmpeg -ss 03:12 -t 20 -i video.mp4 extrait.mp4`.

## 2. Affiner (toi, en regardant les captures avec Read)
Dans `ui/themes/<nom>.json` :
- `colors` : `bg` (fond), `surface`/`surface2` (panneaux), `text`, `muted`, `accent` (boutons, sélection), `accent2` (états secondaires). Contraste texte/fond ≥ 4,5:1.
- `fonts.display` / `fonts.body` : police la plus proche (installe l'OFL dans `assets/fonts/` si besoin ; le Studio utilise les polices système/installées).
- `radius` (coins en px), `layout_notes` : disposition observée (barre latérale, timeline, cartes de formats, panneau d'inspection…).
Si la disposition diffère fortement de `ui/index.html`, adapte la mise en page (grille CSS en tête de fichier) en gardant toutes les fonctions et les appels `/api/*`.

## 3. Activer
Sélecteur « Charte » en haut à droite du Studio, ou `ui/settings.json` → `{"theme": "editingos"}`.
Aligne aussi les vidéos : reporte `accent` dans `styles/*.json` (`subtitles.highlight`, `motion.accent`) si l'utilisateur veut une identité commune.

## Règle
On s'inspire d'une charte (couleurs, typo, ergonomie) ; on ne copie ni logo ni nom de marque tiers dans l'interface.
