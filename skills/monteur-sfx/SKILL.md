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

## Placement et volume (automatiques, à vérifier)
- **Placés avec discernement** : chaque événement visuel propose un son (raccord > carte / titre / CTA > B-roll > zoom) ; on garde les plus utiles avec `sfx.min_gap` (1,1 s) entre deux sons et `sfx.max_per_minute` (14). Un zoom ne sonne que s'il tombe sur une attaque de phrase ou un mot fort. Pas de riser coupé à 0 s : s'il n'a pas la place avant le titre, c'est un pop.
- **Volume mesuré sous la voix** : `sfx.under_db` (17 dB sous le niveau médian de la parole, −3 dB s'il tombe sur un mot). Avec un gain fixe, sur une prise de téléphone calme, les sons sortaient 7 à 10 dB au-dessus de la voix.
- Le rendu liste chaque son retenu et pourquoi (`🔊 2.25s swoosh (apparition hyperframes, gain …)`) ; la piste SFX du Studio aussi. Écoute le draft et ajuste `under_db` / `min_gap` dans le style, ou retire un son (`bin/monteur retouche RUSH --retire T`).
- Les sons de `plan.sfx` (posés à la main ou par le bouton « Bruitage ») passent toujours.
- Sons synthétisés (whoosh filtré qui « passe », riser qui monte, pop sans clic…), refaits automatiquement à chaque nouvelle version ; un `assets/sfx/<nom>.mp3` perso les remplace.

## Ponctuation manuelle (toi)
`plan.json → sfx: [{"t": 12.4, "name": "ding", "gain": 0.4}]` — ding sur un chiffre, impact sur une révélation, camera sur une photo, glitch sur un « mais… ». Maximum 1 ponctuation toutes les 3–4 s, sinon c'est fatigant.

## Voix off française
```bash
bin/monteur voix "Étape un : les projets." --out vo.wav            # une réplique
bin/monteur voix --fichier script.txt --out voix/                     # une réplique par ligne → vo_00.wav…
bin/monteur voix --liste                                              # moteurs disponibles
```
Moteurs (`--moteur auto` essaie dans l'ordre) : **edge** = voix neuronales Microsoft Edge (`fr-FR-DeniseNeural`, `fr-FR-HenriNeural`…, en ligne, installé par setup.sh) ; **espeak** = espeak-ng + MBROLA (`mb-fr1` homme, `mb-fr4` femme, hors-ligne, `bash setup.sh --voix`). Le lexique de `monteur/voiceover.py` corrige la prononciation des mots anglais (frame, draft, reel…). Pour une voix humaine ou clonée (ElevenLabs, Higgsfield…), dépose le WAV et place-le comme musique/SFX ou via `plan.sfx`.
Mix : voix à −16 LUFS, musique en ducking dessous.

## Musique & mix
`--music fond.mp3` (ou `plan.music`). Boucle automatique, fondu de fin 2 s, ducking (sidechain) sous la voix. `style.audio.music_volume` 0.08–0.16 (voix), 0.4–0.6 (produit sans voix). Sortie normalisée à `style.audio.lufs` (−14 réseaux sociaux, −16 YouTube long / documentaire).
