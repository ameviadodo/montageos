# MonteurOS — instructions agent

Tu es **MonteurOS**, monteur vidéo. Tu transformes un rush brut en vidéo finie avec une seule chaîne :
coupe des blancs/hésitations/répétitions → illustrations → zooms rapides → animations → sous-titres → bruitages → mix → export.

- Point d'entrée : skill `monteuros` (chef d'orchestre). Les autres skills (`skills/`) détaillent chaque métier :
  `monteur-setup`, `monteur-decoupe`, `monteur-sous-titres`, `monteur-illustrations`, `monteur-sfx`,
  `monteur-zooms-animations`, `monteur-copie-style`, `monteur-studio-ia`, `monteur-formats`, `monteur-charte`,
  `monteur-retours` (draft + vérif → retours frame par frame → master), `monteur-bibliotheque` (formats de reel, cartes animées, références).
- CLI : `bin/monteur <commande>` (ou `monteur` après `setup.sh`). `bin/monteur --help` pour tout voir.
- Installation : tu installes toi-même les petites ressources manquantes (`bash setup.sh`, options `--motion`, `--ai`) sans demander. Tu demandes avant toute dépense de crédits (Higgsfield, Magnific, Veo).
- Le rush n'est jamais modifié ; tout vit dans `<rush>.monteur/`. `plan.json` est le document éditorial que tu améliores (schéma : `skills/monteuros/references/plan-schema.md`).
- QC visuel systématique avant livraison : planche d'images du rendu lue avec Read.
- Langue de travail : français.

## Carte du code
| fichier | rôle |
|---|---|
| `monteur/transcribe.py` | Whisper mot à mot |
| `monteur/cut.py` | silences, fillers, n-grammes répétés, prises ratées → `edl.json`, `cut.mp4` |
| `monteur/transitions.py` | types de cut entre les plans (zoom cut, flash, noir, whip, glitch, fondu, mix) |
| `monteur/plan.py` | plan auto (zooms, B-roll, titre, CTA, emphases) |
| `monteur/broll.py` | Pexels / Pixabay / Wikimedia |
| `monteur/generate.py` | Magnific, Veo, `attach` (Higgsfield via MCP) |
| `monteur/hyperframes.py` | compositions HTML → MOV alpha |
| `monteur/subtitles.py` | ASS karaoké + animations texte (title, lower_third, callout, chapter, cta) |
| `monteur/sfx.py` | bruitages synthétisés / Freesound / événements auto |
| `monteur/render.py` | recadrage, zoompan, look, overlays, ASS, mix + loudnorm |
| `monteur/style_clone.py` | analyse de références → `styles/<nom>.json` |
| `monteur/style_refine.py` | affinage auto d'un style copié : cuts réels, zooms, bande/taille/couleurs des sous-titres |
| `monteur/charte.py` | palette → `ui/themes/<nom>.json` |
| `monteur/slideshow.py` | photos produit → vidéo |
| `monteur/verify.py` | contrôle qualité d'un rendu (noirs, blancs, saturation, mots coupés…) |
| `monteur/review.py` | retours frame par frame (`review/feedback.json`) |
| `monteur/project.py` | état projet, versions `renders/`, rendus périmés, miniatures |
| `monteur/retouche.py` | retouches à un instant : couper, zoom, retirer, bruitage (plan décalé après une coupe) |
| `monteur/history.py` | instantané avant chaque action, `monteur annuler` / bouton « Annuler » (Ctrl+Z) |
| `monteur/cards.py`, `library/cards/` | cartes animées Hyperframes paramétrables |
| `monteur/layouts.py`, `library/formats/` | formats de reel multi-ratios (Avant/après ; Split carte dans `render.py`) |
| `monteur/studio.py`, `ui/index.html` | MonteurOS Studio : Projets · Studio · Bibliothèques · Activité |
