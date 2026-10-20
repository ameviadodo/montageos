---
numero: 06
nom: Portrait feed 4:5
etat: Prêt
squelette: scaffold
style: ugc
ratios: 4:5, 3:4, 2:3
description: Le format pub Instagram / Facebook le plus rentable : 4:5, visage au tiers haut, preuve sociale.
---
# Format 06 — Portrait feed (4:5)

**Pourquoi** : 4:5 = la plus grande surface autorisée dans le feed Meta, sans être recadré comme le 9:16.
Variantes : **3:4** et **2:3** (Pinterest).

1. **Hook visage** : regard caméra, recadrage suivi du visage (automatique).
2. **Problème → solution** : zoom cut à chaque phrase (`--cuts zoomcut`).
3. **Preuve** : `avis.etoiles`, puis `prix.promo` si c'est une pub.
4. **CTA** : `cta` + son `ding`.

```bash
bin/monteur prep RUSH.mp4 --style ugc --aspect 4:5
bin/monteur carte RUSH.mp4 avis.etoiles --start 6 --set quote="Je ne m'en passe plus" --set author="Léa"
bin/monteur render RUSH.mp4 --draft
```
