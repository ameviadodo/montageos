---
numero: 08
nom: Comparatif produit
etat: Prêt
squelette: scaffold
style: produit
ratios: 9:16, 4:5, 1:1, 16:9
description: « Nous vs les autres » : problème, tableau comparatif animé, preuve, offre avec compte à rebours.
---
# Format 08 — Comparatif produit

**Structure** (20–40 s) : on montre pourquoi ton produit gagne, sans citer de marque concurrente.

1. **Hook (0–2 s)** : la question que se pose l'acheteur — `mot.punch` sur le mot-clé (« ENFIN », « VRAIMENT ? »).
2. **Problème** : ce qui ne va pas avec les solutions habituelles (B-roll, zoom cut).
3. **Comparatif** : carte `comparatif.tableau` (4 lignes max, une idée par ligne).
4. **Preuve** : `avis.etoiles` ou `stat.courbe`.
5. **Offre** : `prix.promo`, puis `compte.rebours` si l'offre est limitée ; CTA.

**Cuts** : `flash` sur les révélations, `zoomcut` ailleurs (style `produit`).

```bash
bin/monteur prep RUSH.mp4 --style produit --aspect 4:5
bin/monteur carte RUSH.mp4 comparatif.tableau --start 6 --set left="Nous" --set right="Les autres" \
  --set rows="Livraison 24 h;Garantie 2 ans;Prix juste" --set l_marks="1;1;1" --set r_marks="0;1;0"
bin/monteur carte RUSH.mp4 compte.rebours --start 18 --set from=3 --set label="Offre terminée dans" --set end="J-3"
bin/monteur render RUSH.mp4 --draft
```
Règle : pas de logo ni de nom de concurrent sans droit ; reste factuel.
