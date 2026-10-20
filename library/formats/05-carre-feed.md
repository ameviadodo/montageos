---
numero: 05
nom: Carré feed 1:1
etat: Prêt
squelette: scaffold
style: pub
ratios: 1:1
description: Vidéo carrée pour le feed (Facebook, LinkedIn, Instagram) : sous-titres centrés, gros texte, lisible sans le son.
---
# Format 05 — Carré feed (1:1)

**Pourquoi** : le carré occupe plus d'écran que le 16:9 dans un feed et se lit sans le son.

1. **0–2 s** : titre en haut (`titre.barre`) — l'utilisateur doit comprendre le sujet sans le son.
2. **Corps** : sous-titres au centre, 2–3 mots, mots-clés colorés ; un zoom cut toutes les 2–3 phrases.
3. **Preuve** : `stat.courbe` ou `avis.etoiles`.
4. **Fin** : `cta` court (1,5 s) — la boucle repart.

```bash
bin/monteur prep RUSH.mp4 --style pub --aspect 1:1 --cuts zoomcut
bin/monteur render RUSH.mp4 --draft
```
