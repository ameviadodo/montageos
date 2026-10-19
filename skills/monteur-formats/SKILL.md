---
name: monteur-formats
description: Recettes de montage par type de contenu — publicités (ads Meta/TikTok), UGC, documentaires, intros YouTube, formations/tutos, visuels produits (packshots, diaporamas produit). Donne la structure narrative, le style MonteurOS à utiliser, les animations et les visuels IA adaptés. Utiliser dès que l'utilisateur dit « fais une pub », « vidéo UGC », « mini-documentaire », « intro pour ma chaîne », « module de formation », « vidéo produit ».
---

# Formats de contenu

Chaque format = un style (`styles/<nom>.json`) + une structure que **tu** imposes via `plan.json`.

## Pub (`--style pub`, 9:16, 15–45 s)
Structure : **Hook (0–2 s) → Problème → Solution/produit → Preuve (chiffre, avis, démo) → Offre → CTA**.
- Titre d'accroche = la douleur ou le bénéfice en ≤ 5 mots. Callout sur chaque chiffre.
- B-roll très dense (≈ 9/min) : produit en action ; plans IA Higgsfield pour le « wow ».
- CTA auto (`motion.cta`) : adapte `text`/`subtext` (offre, code promo).
- Si le rush dépasse 45 s, propose 2-3 variantes de hook (A/B) en dupliquant le plan.

## UGC (`--style ugc`, 9:16)
Authenticité > effets : cartouches de sous-titres façon TikTok natif, zooms rares, B-roll produit en PiP, pas de titre plein écran. Structure : « J'ai testé… » → usage → résultat → recommandation. Garder les respirations naturelles (coupe moins serrée).

## Documentaire (`--style documentaire`, 16:9)
Coupe posée, poussées lentes, letterbox 2.39, étalonnage ciné + grain, archives (Wikimedia, avec crédits) et plans larges, `lower_third` pour chaque intervenant, `chapter` entre les actes, musique −16 LUFS. Structure en actes : situation → tension → révélation → résolution.

## Intro YouTube (`--style intro-youtube`, 16:9, 20–60 s)
Hook dans les 5 premières secondes, promesse claire, **aperçu** rapide (flash-forward en B-roll des meilleurs moments), puis carton/logo animé Hyperframes (`motion-new … intro`) et transition vers le contenu. Zéro temps mort.

## Formation (`--style formation`, 16:9)
Clarté : `chapter` à chaque nouvelle notion (« 01 — Les bases »), `callout` pour les règles clés, captures d'écran en `pip`, infographies Hyperframes (listes, schémas), sous-titres phrase. Pas d'effets gratuits ; un `click` discret sur les zooms.

## Visuels produits (`--style produit`, 9:16 / 1:1)
Sans rush : photos → vidéo.
```bash
bin/monteur upscale photo1.jpg --scale 2x            # Magnific, si photos basse déf
bin/monteur slideshow photo1.jpg photo2.jpg photo3.jpg --out produit.mp4 --per 2 --aspect 9:16 [--audio voix.mp3]
bin/monteur prep produit.mp4 --style produit --no-broll
```
Puis ajoute dans `plan.motion` : `title` (nom produit), `callout` par bénéfice (1 par image), `cta`. Plans animés en plus : Higgsfield image→vidéo à partir des photos, puis `attach`. Musique : `--music`.

## Déclinaisons
Un même rush peut sortir en 16:9 (YouTube) + 9:16 (Shorts) : `--aspect 9:16 --workdir RUSH.short.monteur`.
