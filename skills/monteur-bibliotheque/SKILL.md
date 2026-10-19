---
name: monteur-bibliotheque
description: Bibliothèques MonteurOS — formats de reel (Split carte, Avant/après, Recréer ce contenu viral), styles de référence (palette, polices, cartes), ta charte, et cartes animées Hyperframes prêtes à poser (écrans 3D, rail des étapes, médaillon nom, liste surlignée, marqueurs de section, boot « étape », stat courbe + compteur, titre barre, programme/chapitres, citation). Utiliser pour « fais un split », « format avant/après », « ajoute une carte / une infographie / un chiffre animé », « quels styles as-tu », ou pour créer une nouvelle carte ou un nouveau format.
---

# Bibliothèques

Tout est visible dans le Studio → **Bibliothèques** (aperçus animés, « Voir en grand »).

## Formats de reel (`library/formats/*.md`)
| # | Format | Commande |
|---|---|---|
| 01 | **Split carte** — animations en haut, orateur en bas | `--style split-carte` ; les B-roll `full` et les cartes vont dans le panneau |
| 02 | **Avant/après** — titre, transformé, original | `bin/monteur avant-apres transforme.mp4 original.mp4 --title "…" --out compare.mp4` |
| 03 | **Recréer ce contenu viral** | skill `monteur-copie-style` puis prep avec le style copié |
Lis le `.md` du format (structure, mesures) avant de monter.

## Cartes animées (`library/cards/*.card.html`)
```bash
bin/monteur cartes                                   # catalogue + variables
bin/monteur carte RUSH.mp4 stat.courbe --start 12.4 --set value=125 --set suffix=K --set unit=abonnés
```
→ composition Hyperframes remplie, rendue (MOV transparent si overlay, MP4 si plein cadre), ajoutée à `plan.motion`.
Règles : une carte toutes les 4–8 s max, texte ≤ 8 mots par ligne, couleur `accent` = celle de la charte, jamais pendant le hook si un titre est déjà là.

### Créer une carte
Copie une carte existante : en-tête `<!--meta {label, category, mode: overlay|full, duration, vars, usage}-->`, puis `<style>`, `<template>` (HTML, variables `{{clé|défaut}}`), `<script>` (timeline GSAP `tl`, valeurs dans `V`, durée `V.DUR`). Unité : `var(--u)` = 1 % du petit côté. Règles Hyperframes : pas de `Math.random`/`Date.now`, tout est seekable. Vérifie l'aperçu dans le Studio, puis un rendu test.

## Références (`styles/*.json` → bloc `library`)
`etat`, `palette`, `fonts {display, body, mono}`, `cards` (ids de cartes associées). Le style `nocturne` porte la charte relevée sur la vidéo de référence (bleu nuit, jaune #FFD935, serif italique, mono capitales).

## Ta charte (`ui/themes/*.json`)
Thème de l'interface ; activable depuis le Studio. Skill `monteur-charte` pour en extraire une nouvelle.
