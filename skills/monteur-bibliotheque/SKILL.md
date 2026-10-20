---
name: monteur-bibliotheque
description: Bibliothèques MonteurOS — formats de reel en 9:16, 16:9, 1:1, 4:5, 3:4, 2:3, 21:9 (Split carte, Avant/après, Recréer ce contenu viral, YouTube 16:9, Carré feed, Portrait 4:5, Tuto écran), styles de référence (palette, polices, cartes, type de cut, style actif), ta charte, et cartes animées Hyperframes cherchables (écrans 3D, rail des étapes, médaillon nom, liste surlignée, marqueurs de section, stat courbe, titre barre, mot punch, prix promo, avis étoiles, lieu/date, intro logo, volet de transition…). Utiliser pour « fais un split », « format avant/après », « en carré / en 16:9 », « ajoute une carte / un chiffre animé / un avis », « cherche une carte », « quels styles as-tu », « active ce style », ou pour créer une nouvelle carte ou un nouveau format.
---

# Bibliothèques

Tout est visible dans le Studio → **Bibliothèques** (aperçus animés, « Voir en grand »).

## Formats de reel (`library/formats/*.md`)
| # | Format | Commande |
|---|---|---|
| 01 | **Split carte** — animations en haut, orateur en bas | `--style split-carte` ; les B-roll `full` et les cartes vont dans le panneau |
| 02 | **Avant/après** — titre, transformé, original | `bin/monteur avant-apres transforme.mp4 original.mp4 --title "…" --out compare.mp4` |
| 03 | **Recréer ce contenu viral** | skill `monteur-copie-style` puis prep avec le style copié |
| 04 | **Talking-head YouTube** (16:9, 21:9) | `--style intro-youtube --aspect 16:9`, carte `intro.logo` |
| 05 | **Carré feed** (1:1) | `--style pub --aspect 1:1 --cuts zoomcut` |
| 06 | **Portrait feed** (4:5, 3:4, 2:3) | `--style ugc --aspect 4:5`, cartes `avis.etoiles`, `prix.promo` |
| 07 | **Tuto écran + facecam** (16:9, 9:16) | `--style formation`, captures en B-roll `full` ou `pip` |
| 08 | **Comparatif produit** (9:16, 4:5, 1:1, 16:9) | `--style produit`, cartes `comparatif.tableau`, `prix.promo`, `compte.rebours` |
| 09 | **Vidéo réponse / FAQ** (9:16, 4:5) | `--style ugc`, cartes `question.reponse`, `sondage.choix` |
| 10 | **Top / classement** (9:16, 16:9, 1:1) | `--style createur-kinetic --cuts whip`, carte `classement.top` |
Lis le `.md` du format (structure, mesures) avant de monter. Chaque format déclare ses `ratios:` (front matter) ;
le Studio les filtre avec les pastilles **Format**. Tout style se rend dans n'importe quel ratio avec `--aspect`
(`9:16 16:9 1:1 4:5 3:4 2:3 21:9`) ; Split carte passe en côte à côte (panneau à droite) en paysage, Avant/après aussi.

## Cartes animées (`library/cards/*.card.html`)
```bash
bin/monteur cartes                                   # catalogue + variables
bin/monteur cartes --cherche "avis"                  # recherche (id, nom, catégorie, usage, tags, variables ; sans accents)
bin/monteur carte RUSH.mp4 stat.courbe --start 12.4 --set value=125 --set suffix=K --set unit=abonnés
```
Cartes « engagement / vente » : `compte.rebours` (3-2-1 + mot final), `sondage.choix` (A/B + %), `question.reponse` (bulle « Réponse à @… »),
`comparatif.tableau` (nous vs les autres, ✓/✕ ; variables `rows`, `l_marks`, `r_marks` séparées par `;`), `classement.top` (du dernier au n°1).
Pendant une carte chargée, `"hide_subs": true` sur l'entrée `motion` masque les sous-titres.
Dans le Studio : chaque carte de la bibliothèque a « ＋ Poser sur une vidéo » (projet, instant choisi dans la vidéo,
textes, draft refait automatiquement) ; dans la page Studio d'un projet : « Poser à la tête de lecture ».
→ composition Hyperframes remplie, rendue (MOV transparent si overlay, MP4 si plein cadre), ajoutée à `plan.motion`.
Règles : une carte toutes les 4–8 s max, texte ≤ 8 mots par ligne, couleur `accent` = celle de la charte, jamais pendant le hook si un titre est déjà là.

### Créer une carte
Copie une carte existante : en-tête `<!--meta {label, category, mode: overlay|full, duration, vars, tags, usage}-->` (`tags` = mots de recherche), puis `<style>`, `<template>` (HTML, variables `{{clé|défaut}}`), `<script>` (timeline GSAP `tl`, valeurs dans `V`, durée `V.DUR`). Unité : `var(--u)` = 1 % du petit côté. Règles Hyperframes : pas de `Math.random`/`Date.now`, tout est seekable (Hyperframes rend image par image avec `seek(t, false)` : les `tl.call` passent ; mets `immediateRender: false` sur un `fromTo` placé tard dans la timeline, sinon l'élément reste invisible jusque-là). Vérifie l'aperçu dans le Studio, puis un rendu test.

## Références (`styles/*.json` → bloc `library`)
`etat` (Prêt, Draft, Copié, Charte…), `palette`, `fonts {display, body, mono}`, `cards` (ids de cartes associées — **chaque style doit en avoir**, vérifié par les tests), `ratios`, `sources` (liens des vidéos copiées). Le style `nocturne` porte la charte relevée sur la vidéo de référence (bleu nuit, jaune #FFD935, serif italique, mono capitales).

**Style actif** : bouton « Activer » (Studio) ou `bin/monteur activer <style>` → `ui/settings.json` `style` ; utilisé par tout nouveau projet sans `--style`. `bin/monteur styles` liste la bibliothèque (● = actif).
**Cloner un style viral** depuis le Studio (Références → liens ou MP4 déposés → « Cloner le style ») = `bin/monteur style … --activer` (skill `monteur-copie-style`).

## Ta charte (`ui/themes/*.json`)
Thème de l'interface ; activable depuis le Studio. **Ajouter une charte** (Studio → Ta charte → liens vidéo ou petits extraits MP4 / captures) = `bin/monteur charte … --name <nom>` : thème `ui/themes/<nom>.json` + style vidéo assorti `styles/<nom>.json`. Skill `monteur-charte` pour l'affiner.
