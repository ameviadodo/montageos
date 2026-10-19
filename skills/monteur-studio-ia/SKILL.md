---
name: monteur-studio-ia
description: Collaboration de MonteurOS avec les outils IA créatifs — Higgsfield (connecteur MCP : vidéos/images Veo, Kling, Sora, Seedance, Soul…), Magnific (upscale/relight d'images), Google Flow (Veo, scènes cinématiques) et Hyperframes (motion design HTML). Utiliser pour générer des B-roll impossibles à trouver, des plans produit, des avatars/scènes UGC, des intros, upscaler une photo floue, ou quand l'utilisateur cite Higgsfield, Magnific, Flow, Veo ou Hyperframes.
---

# Studio IA

Avant toute génération **payante** (crédits), annonce le nombre de visuels et le modèle, et attends un « ok ».

## Higgsfield (MCP)
1. Connecteur : `.mcp.json` du projet déclare `https://mcp.higgsfield.ai` (sur claude.ai : Réglages → Connecteurs → ajouter l'URL). Charge les outils avec `ToolSearch` (« higgsfield »).
2. Pour chaque `broll` en `provider: "higgsfield"` : génère à partir de `prompt` (texte → vidéo, ou image → vidéo à partir d'une photo produit / capture du rush). Format = celui du montage (9:16 / 16:9), durée ≥ `end - start`.
3. Télécharge le résultat dans `RUSH.monteur/assets/broll/` puis `bin/monteur attach RUSH.mp4 <i> fichier`.
Bons usages : plans produit cinématiques, scènes métaphoriques (« une fusée décolle d'un ordinateur portable »), personnage UGC tenant le produit, transitions.

## Google Flow / Veo
- **API (automatisable)** : `bash setup.sh --ai`, `GEMINI_API_KEY`, puis
  `bin/monteur veo "prompt" --out RUSH.monteur/assets/broll/03_veo.mp4 --aspect 9:16 [--image ref.png]` → `attach`. Modèle par défaut `veo-3.1-generate-preview` (surcharge : `VEO_MODEL`).
- **Interface Flow (labs.google/flow)** : si l'utilisateur préfère Flow (scènes, extensions, ingrédients), pilote-la via le navigateur (skill chrome-browser / built-in-browser) ou donne-lui les prompts prêts à coller, puis récupère les MP4 téléchargés.

## Magnific
- Upscale d'une photo produit, d'une capture ou d'une frame IA avant usage plein écran :
  `bin/monteur upscale photo.jpg --scale 2x --mode precision` (fidèle) ou `--mode creative --prompt "…"` (ajoute du détail). Clé `MAGNIFIC_API_KEY` ; base/entête configurables (`MAGNIFIC_API_BASE`, `MAGNIFIC_API_HEADER`) si l'API change.
- Si un connecteur Magnific est disponible (`ToolSearch` « magnific »), préfère-le.

## Hyperframes
Voir `monteur-zooms-animations`. Idéal pour intros YouTube, infographies de formation, cartes produit, CTA animés.

## Prompts : formule
`[sujet précis] + [action] + [décor] + [lumière] + [caméra/objectif] + [style] + [format]`
Ex. : « flacon de sérum ambré sur pierre mouillée, gouttes qui tombent au ralenti, salle de bain minérale, lumière douce latérale, macro 100 mm, travelling lent, publicité cosmétique premium, vertical 9:16 ».
Cohérence : garde la même palette/lumière que le style (`look`) et réutilise une image de référence pour tous les plans d'un même produit.
