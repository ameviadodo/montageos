---
numero: 07
nom: Tuto écran + facecam
etat: Prêt
squelette: scaffold
style: formation
ratios: 16:9, 9:16
description: Visage + captures d'écran (plein cadre pendant les démos, ou en incrustation) ; étapes numérotées, zooms.
---
# Format 07 — Tuto écran + facecam

**Structure** (16:9) : l'orateur explique, la capture d'écran prend le plein cadre pendant chaque démo
(`"layout": "full"` dans plan.json) ou s'incruste en haut à droite pour garder le visage (`"layout": "pip"`).

1. **Programme** : `programme.chapitres` (ce qu'on va voir).
2. **Étapes** : `ecran.rail` pour la liste, `ecran.push3d` pour présenter l'écran d'une app.
3. **Zooms** : `punch` à chaque clic important.
4. **Récap** : `surlignage.liste`.

**Cuts** : `hard` (un tuto doit rester lisible). En 9:16, prends `split-carte` : écran en haut, visage en bas.

```bash
bin/monteur prep RUSH.mp4 --style formation --aspect 16:9
bin/monteur attach RUSH.mp4 0 capture-ecran.mp4 --kind video     # puis "layout": "full" ou "pip"
bin/monteur render RUSH.mp4 --draft
```
