---
numero: 09
nom: Vidéo réponse / FAQ
etat: Prêt
squelette: scaffold
style: ugc
ratios: 9:16, 4:5
description: Tu réponds à un commentaire : bulle « Réponse à @… », réponse en 3 points, sondage pour relancer les commentaires.
---
# Format 09 — Vidéo réponse (FAQ)

**Pourquoi** : la vidéo réponse à un commentaire est le format qui relance le mieux les échanges sur TikTok / Reels.

1. **0–3 s** : carte `question.reponse` (le commentaire en bulle + le début de la réponse).
2. **Réponse** : 2–3 points, `surlignage.liste` ou `ecran.rail` ; zoom cut à chaque point.
3. **Relance** : `sondage.choix` (« Et toi ? ») ou question finale → commentaires.

```bash
bin/monteur prep RUSH.mp4 --style ugc
bin/monteur carte RUSH.mp4 question.reponse --start 0.2 --set user="@lea.mrt" \
  --set question="Ça marche pour les débutants ?" --set answer="Oui, voici comment"
bin/monteur carte RUSH.mp4 sondage.choix --start 14 --set question="Tu l'as déjà essayé ?" --set a="Oui" --set b="Pas encore" --set pa=38 --set pb=62
bin/monteur render RUSH.mp4 --draft
```
