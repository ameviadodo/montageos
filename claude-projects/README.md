# Projets Claude (claude.ai) pour MonteurOS

La chaîne de montage tourne dans **Claude Code** ou **Cowork**, qui exécutent ffmpeg en local. Ces projets claude.ai servent à la préparation créative : scripts, plans, prompts IA et analyse de style. Leurs sorties se collent ensuite dans `plan.json` ou dans `styles/`.

Pour chaque projet : claude.ai → Projets → Nouveau projet → coller `instructions.md` dans « Instructions du projet », puis ajouter en connaissances les fichiers listés.

| Projet | Rôle | Connaissances à ajouter |
|---|---|---|
| `directeur-artistique/` | Transforme une transcription en plan de montage (`plan.json`) : hook, emphases, B-roll, zooms, animations, SFX | `skills/monteuros/references/plan-schema.md`, `skills/monteur-formats/SKILL.md`, le `styles/*.json` choisi |
| `scripts-pubs-ugc/` | Écrit des scripts pub / UGC / intro / formation prêts à tourner et à monter | `skills/monteur-formats/SKILL.md` |
| `prompts-studio-ia/` | Génère les prompts Higgsfield / Google Flow / Magnific cohérents pour un montage | `skills/monteur-studio-ia/SKILL.md` |
| `analyste-style/` | À partir de captures/planches d'une vidéo de référence, remplit un style MonteurOS | `styles/default.json`, `skills/monteur-copie-style/SKILL.md` |

Connecteur Higgsfield sur claude.ai : Réglages → Connecteurs → ajouter `https://mcp.higgsfield.ai`. Le projet « prompts-studio-ia » peut alors générer directement.
