---
numero: 04
nom: Talking-head YouTube
etat: Prêt
squelette: scaffold
style: intro-youtube
ratios: 16:9, 21:9
description: Vidéo longue YouTube en 16:9 : intro logo, chapitres, zooms doux, whip entre les parties.
---
# Format 04 — Talking-head YouTube (16:9)

**Structure** : hook 0–15 s → intro logo 3 s → chapitres → récap → CTA abonnement.

1. **Hook** : la promesse en une phrase, `mot.punch` sur le mot-clé.
2. **Intro** : carte plein cadre `intro.logo` (nom de chaîne + épisode).
3. **Chapitres** : `programme.chapitres` au début, `section.cercle` ou `transition.volet` à chaque partie.
4. **Corps** : zooms doux (`ease`) toutes les 6–8 s, B-roll 16:9 plein cadre, `medaillon.nom` pour un invité.
5. **Fin** : `cta` + écran de fin (laisser 20 s pour les cartes YouTube).

**Cuts** : `whip` entre les parties, `hard` ailleurs (`--cuts whip` ou `cut.transition`).

```bash
bin/monteur prep RUSH.mp4 --style intro-youtube --aspect 16:9
bin/monteur carte RUSH.mp4 intro.logo --start 12 --set name="MA CHAÎNE" --set tagline="Épisode 12"
bin/monteur render RUSH.mp4 --draft && bin/monteur verif RUSH.mp4
```

Version cinéma : `--aspect 21:9` (bandes noires naturelles, idéal documentaire / vlog voyage).
