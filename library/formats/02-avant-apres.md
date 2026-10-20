---
numero: 02
nom: Avant/après
etat: Exemple
squelette: scaffold
style: pub
ratios: 9:16, 4:5, 1:1, 16:9
description: Format comparaison avant / après.
---
# Format 02 — Avant / après

**Structure** (9:16) : titre + accroche en haut, version **transformée** au milieu, **originale** en bas, mêmes timings.
Idéal pour démontrer un outil IA (relighting, nettoyage, effet), un montage, un produit.

```bash
bin/monteur avant-apres transforme.mp4 originale.mp4 --title "L'IA change la lumière\nde ta vidéo" \
  --subtitle "sans rien retourner" --out compare.mp4
bin/monteur prep compare.mp4 --style pub --no-cut   # sous-titres, SFX, CTA par-dessus
bin/monteur render compare.mp4
```
**Mesures** : titre ≤ 2 lignes, ≤ 8 mots ; étiquettes « Transformé » / « Originale » ; les deux clips doivent être synchronisés (même départ).

## Autres ratios
En 16:9 et 1:1, les deux versions sont posées **côte à côte** sous le titre :
`bin/monteur avant-apres APRES.mp4 AVANT.mp4 --out comparaison.mp4 --aspect 16:9`
