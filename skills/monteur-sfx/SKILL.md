---
name: monteur-sfx
description: Bruitages et sound design du montage — whoosh sur les zooms et transitions, pop sur les apparitions de texte, ding sur les chiffres, impact sur les révélations, riser avant le titre, musique de fond avec ducking automatique sous la voix, normalisation LUFS. Utiliser pour « ajoute des sound effects », « sound design », « mets une musique », « le son est trop fort/faible ».
---

# Sound design

## Bibliothèque
`bin/monteur sfx` liste les sons. Fournis d'office (synthétisés, libres de droits) : `whoosh swoosh pop click ding impact riser glitch camera`.
- Remplacer un son : déposer `assets/sfx/whoosh.mp3` (même nom) → prioritaire.
- Télécharger un vrai son : `bin/monteur sfx --search "cash register" --name cash` (Freesound, `FREESOUND_API_KEY`).

## Automatique (`style.sfx`)
- `on_zoom` : `{"punch": "pop", "pulse": "whoosh", "ease": null}` (whoosh/swoosh anticipés de 0,12 s).
- `on_broll` : son à l'entrée d'un visuel. `on_motion` : son avant le titre (riser anticipé de 0,9 s).
- `volume` : gain global des bruitages (0.25 discret · 0.45 très présent).
- Couper un son précis : `"sfx": null` sur le zoom/B-roll/animation concerné.

## Ponctuation manuelle (toi)
`plan.json → sfx: [{"t": 12.4, "name": "ding", "gain": 0.4}]` — ding sur un chiffre, impact sur une révélation, camera sur une photo, glitch sur un « mais… ». Maximum 1 ponctuation toutes les 3–4 s, sinon c'est fatigant.

## Musique & mix
`--music fond.mp3` (ou `plan.music`). Boucle automatique, fondu de fin 2 s, ducking (sidechain) sous la voix. `style.audio.music_volume` 0.08–0.16 (voix), 0.4–0.6 (produit sans voix). Sortie normalisée à `style.audio.lufs` (−14 réseaux sociaux, −16 YouTube long / documentaire).
