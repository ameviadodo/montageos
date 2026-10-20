---
name: monteur-decoupe
description: Coupe automatique d'un rush — supprime les blancs/silences, les hésitations (euh, hum…), les bégaiements (« je pense que je pense que ») et les prises ratées/répétées en gardant la dernière prise. Utiliser pour « enlève les blancs », « jump cuts », « supprime les répétitions », ou pour ajuster une coupe trop serrée/trop lâche.
---

# Découpe : blancs, hésitations, répétitions

```bash
bin/monteur transcribe RUSH.mp4 [--language fr] [--model small]   # si pas encore fait
bin/monteur cut RUSH.mp4 --style <style>
```

## Ce que fait l'algorithme (`monteur/cut.py`)
1. Transcription mot à mot (faster-whisper, horodatage par mot).
2. Mots retirés :
   - `filler` : liste `style.cut.fillers` (euh, heu, hum, um, uh, bah, ben…).
   - `repeat` : n-gramme (1 à 5 mots) répété immédiatement → la 1ʳᵉ occurrence part.
   - `retake` : phrase reprise dans les 3 phrases suivantes (similarité ≥ `retake_similarity`) → la prise ratée part, la dernière reste.
3. Les mots gardés deviennent des segments (± `padding`), fusionnés si l'écart < `min_silence`, puis les silences ffmpeg (`silence_db`) sont soustraits.
4. Rendu `cut.mp4` (micro-fondus audio de 12 ms anti-clic) + `transcript_cut.json` re-synchronisé.

## Ton contrôle
- Lis `edl.json` → `stats` et `removed` (`{w, t, why}`). Si un mot utile a été retiré (ex. « ben » nom propre, répétition volontaire « très très »), ajuste le style : retirer le filler de la liste, baisser `remove_retakes`, ou monter `retake_similarity` à 0.85.
- Rythme : `min_silence` 0.25 = très nerveux (TikTok), 0.45 = dynamique, 0.7 = posé. `padding` 0.05–0.15 s.
- Rush sans parole (B-roll, musique) : la coupe se fait sur les silences audio uniquement.
- Après une recoupe, relance `bin/monteur plan` (les temps du plan changent) — ou garde le plan si seuls de petits réglages ont bougé et vérifie au QC.

## Types de cut entre les plans (`monteur/transitions.py`)
`bin/monteur cuts` liste : `hard` (jump cut sec), `zoomcut` (un plan sur deux recadré plus serré — masque les jump cuts),
`flash` (éclat blanc + son appareil photo), `dip` (passage au noir), `whip` (filé + zoom + whoosh), `glitch` (décalage RGB + son),
`fondu` (images mêlées), `mix` (alterne zoom cut, whip, flash, glitch).
- Style : `cut.transition`, `cut.transition_every` (1 = chaque coupe, 2 = une sur deux), `cut.transition_gap` (écart mini, 1,2 s).
- Ligne de commande : `bin/monteur render RUSH.mp4 --cuts flash` (réécrit `plan.transitions`).
- Studio : panneau **Cuts entre les plans** + piste **CUT** de la timeline.
- À la main : `plan.json` → `"transitions": [{"t": 3.42, "kind": "whip", "sfx": null}]`.
Repères : pub/Hormozi `mix`, UGC `zoomcut`, intro YouTube `whip`, documentaire `fondu`, produit `flash`, formation `hard`.
Pour un raccord plus graphique, pose la carte `transition.volet` centrée sur la coupe.

Réglages dans `styles/<style>.json` → section `cut` (voir `styles/default.json`).
