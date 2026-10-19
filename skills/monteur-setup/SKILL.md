---
name: monteur-setup
description: Installe et répare automatiquement les ressources de MonteurOS (ffmpeg avec libass, Python/faster-whisper, yt-dlp, polices de sous-titres, bibliothèque de bruitages, Node 22 + Hyperframes, google-genai). Utiliser quand `bin/monteur doctor` échoue, à la première utilisation, ou sur une erreur « module introuvable », « ffmpeg not found », police absente, etc.
---

# Installation automatique MonteurOS

Tu as l'autorisation d'installer seul les **petites ressources gratuites** nécessaires. Ne demande pas, fais-le, puis résume ce qui a été installé.

## Procédure
1. `bin/monteur doctor` → liste ✅/❌.
2. `bash setup.sh` (idempotent) : ffmpeg (apt/brew/dnf/winget), `.venv` + `faster-whisper` + `yt-dlp`, polices OFL dans `assets/fonts/`, bruitages synthétisés dans `assets/sfx/`, lien `~/.local/bin/monteur`.
3. Options : `--motion` (Hyperframes : Node ≥ 22 requis, skill officielle `npx skills add heygen-com/hyperframes`), `--ai` (`google-genai` pour Veo), `--all`.
4. Relance `bin/monteur doctor`.

## Dépannage
| Symptôme | Correctif |
|---|---|
| `ffmpeg sans libass` | installer un ffmpeg complet (`apt install ffmpeg`, `brew install ffmpeg`, build static johnvansickle / gyan.dev) |
| Modèle Whisper qui ne se télécharge pas | réseau vers huggingface.co ; essayer `--model base` ; ou `HF_HUB_OFFLINE=1` avec modèle en cache |
| Whisper lent sur CPU | `--model base` ou `small` ; GPU NVIDIA : `pip install nvidia-cublas-cu12 nvidia-cudnn-cu12` dans `.venv` |
| Node < 22 | `nvm install 22` (ou installeur nodejs.org) |
| Hyperframes : script CDN bloqué | `monteur motion-new` embarque GSAP en local ; pour d'autres libs, copier le fichier dans `vendor/` du projet |
| Police manquante dans les sous-titres | déposer le `.ttf` dans `assets/fonts/` et mettre son nom de famille dans le style |
| yt-dlp « Sign in to confirm » / 403 | `.venv/bin/pip install -U yt-dlp` ; sinon demander le MP4 à l'utilisateur |

## Clés API (facultatives — à demander seulement si la fonction est voulue)
`PEXELS_API_KEY`, `PIXABAY_API_KEY` (B-roll vidéo gratuits), `FREESOUND_API_KEY` (bruitages réels), `MAGNIFIC_API_KEY` (upscale), `GEMINI_API_KEY` (Veo). À mettre dans `.env` à la racine (chargé par `bin/monteur`) ou dans l'environnement. Higgsfield passe par le connecteur MCP (pas de clé).
