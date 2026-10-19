---
name: monteur-zooms-animations
description: Zooms rapides avant-arrière (punch-in, pulse, poussée douce), titres d'accroche animés, lower-thirds, callouts, cartons de chapitres, CTA de fin et animations HTML/GSAP via Hyperframes (intros, infographies, graphiques, logos animés). Utiliser pour « ajoute des zooms », « jump zoom », « anime le titre », « fais une intro animée », « ajoute un graphique animé », « motion design ».
---

# Zooms & animations

## Zooms (`plan.zooms`)
| `kind` | rendu | usage |
|---|---|---|
| `punch` | zoom avant instantané, tenu, retour sec | changement d'idée, cache une coupe |
| `pulse` | avant-arrière rapide (~0,5 s) | punchline, mot fort |
| `ease` | poussée douce (smoothstep) | émotion, documentaire |
`scale` 1.05–1.25. Cadrage : `style.zoom.focus: "auto"` (défaut) détecte le visage (OpenCV) — le recadrage 16:9 → 9:16 **suit l'orateur** (transitions douces de 0,8 s) et les zooms se centrent sur lui ; cache dans `RUSH.monteur/focus.json` (supprime-le pour recalculer). `focus: "fixe"` + `focus_x/focus_y` (0.5/0.4) pour un cadrage manuel (plusieurs personnes, produit). Rendu en 2× interne (pas de tremblement). Ne jamais enchaîner deux `punch` à moins de 1,5 s.

## Animations texte natives (`plan.motion`, rendues en ASS)
- `title` : accroche plein centre, apparition en rebond (`text`, `y`).
- `lower_third` : bandeau nom/fonction glissé depuis la gauche.
- `callout` : chiffre ou mot-clé en haut d'écran.
- `chapter` : carton de chapitre (`number`, `text`) — formations, documentaires.
- `cta` : appel à l'action de fin (`text`, `subtext`) — automatique si `style.motion.cta`.
Police/couleurs : `style.motion.font/color/accent`.

## Cartes animées prêtes à l'emploi
`bin/monteur cartes` puis `bin/monteur carte RUSH.mp4 <id> --start T --set clé=valeur` (écran 3D, rail des étapes, médaillon nom, liste surlignée, marqueurs de section, boot « étape », stat courbe + compteur, titre barre, programme/chapitres, citation). Détails : skill `monteur-bibliotheque`.

## Hyperframes (motion design HTML → vidéo)
Pour tout ce qui dépasse le texte : intro de chaîne, graphique qui se dessine, liste à puces animée, logo, mockup produit.
```bash
bash setup.sh --motion                                       # une fois (Node ≥ 22)
bin/monteur motion-new RUSH.mp4 intro                        # scaffold (résolution = format du montage)
# édite RUSH.monteur/hyperframes/intro/index.html (suis le skill officiel « hyperframes » ; GSAP est embarqué en local)
npx -y hyperframes@latest lint RUSH.monteur/hyperframes/intro
npx -y hyperframes@latest snapshot RUSH.monteur/hyperframes/intro   # vérifie des images clés
bin/monteur motion-render RUSH.mp4 intro --start 0              # MOV transparent → overlay
bin/monteur motion-render RUSH.mp4 outro --start 58 --opaque    # MP4 plein écran (carton)
```
Le rendu est ajouté au plan (`type: "hyperframes"`). Fond transparent par défaut (le rush reste dessous). Variables : `--variables '{"title":"…"}'` côté CLI Hyperframes si la composition déclare `data-composition-variables`.
Recettes Hyperframes : barres de stats qui montent pour un chiffre clé, compteur qui défile, texte kinétique mot par mot sur l'intro, carte produit 3D, logo final.
