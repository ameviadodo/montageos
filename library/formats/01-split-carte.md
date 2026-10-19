---
numero: 01
nom: Split carte
etat: Exemple
squelette: scaffold
style: split-carte
description: Moi en bas, tête détourée, je parle, et au-dessus il y a des animations.
---
# Format 01 — Split carte

**Structure** (9:16) : panneau d'animations en haut (≈ 42 % de la hauteur), orateur en bas, sous-titres à la jonction.

1. **Hook (0–2 s)** : carte `section.stage` ou `titre.barre` dans le panneau.
2. **Corps** : chaque idée = une carte (`ecran.rail`, `surlignage.liste`, `stat.courbe`) ou un B-roll — tout B-roll `full` atterrit automatiquement dans le panneau.
3. **Fin** : `cta` dans le panneau.

```bash
bin/monteur prep RUSH.mp4 --style split-carte
bin/monteur carte RUSH.mp4 ecran.rail --start 3.2 --set title="Les 3 étapes" --set items="Couper;Illustrer;Publier"
bin/monteur render RUSH.mp4 --draft && bin/monteur verif RUSH.mp4
```
**Mesures** : panneau `format.split` 0.38–0.45 ; une carte toutes les 4–6 s ; jamais le panneau vide plus de 3 s.
