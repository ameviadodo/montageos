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

## Transcription « pour de bon »
1. `bash setup.sh` : si Whisper ne s'installe pas avec le Python du venv (ex. 3.14), setup.sh installe `uv`, crée un **Python 3.12 dédié** (`.venv`, l'ancien devient `.venv.old`) et y installe faster-whisper. `MONTEUR_NO_UV=1` pour l'empêcher.
2. Sans Whisper local : `bin/monteur transcription RUSH.mp4 fichier.srt --prep` importe une transcription faite ailleurs (export SRT/VTT/JSON de WhisperAI — connecteur Claude —, sous-titres, OpenAI…).
3. La préparation ne bloque jamais : sans transcription, elle coupe les silences et place les zooms sur les coupes.

## Windows (Git Bash)
- Lancer depuis **Git Bash** : `bash setup.sh`. Le venv est en `.venv/Scripts/python.exe` (détecté automatiquement par `bin/_env.sh`) ; cmd/PowerShell : `bin\monteur.cmd`.
- Python : le lanceur `py` est préféré (3.12 > 3.11 > 3) ; le faux `python` du Microsoft Store est ignoré. S'il manque : `winget install Python.Python.3.12`.
- ffmpeg : `winget install Gyan.FFmpeg` ; même si le terminal n'a pas rechargé le PATH, MonteurOS le retrouve (WinGet\Links, choco, scoop).
- `$'\r': command not found` → fins de ligne Windows : `git config core.autocrlf false`, puis `git checkout -- .` (le dépôt force LF via `.gitattributes`).
- Whisper sur GPU NVIDIA sans cuDNN : bascule automatique sur CPU. Modèle préchargé par `bin/monteur whisper --model small`.
- Venv créé sur un autre système (ex. dossier copié depuis WSL) : `setup.sh` le renomme en `.venv.old` et en recrée un.

## Dépannage
| Symptôme | Correctif |
|---|---|
| `ffmpeg sans libass` | installer un ffmpeg complet (`apt install ffmpeg`, `brew install ffmpeg`, build static johnvansickle / gyan.dev) |
| Modèle Whisper qui ne se télécharge pas | réseau vers huggingface.co ; essayer `--model base` ; ou `HF_HUB_OFFLINE=1` avec modèle en cache |
| Whisper lent sur CPU | `--model base` ou `small` ; GPU NVIDIA : `pip install nvidia-cublas-cu12 nvidia-cudnn-cu12` dans `.venv` |
| Node < 22 | `nvm install 22` (ou installeur nodejs.org) |
| Hyperframes : script CDN bloqué | `monteur motion-new` embarque GSAP en local ; pour d'autres libs, copier le fichier dans `vendor/` du projet |
| Police manquante dans les sous-titres | déposer le `.ttf` dans `assets/fonts/` et mettre son nom de famille dans le style |
| yt-dlp « Sign in to confirm » / 403 | `bin/monteur doctor` puis `<python du venv> -m pip install -U yt-dlp` ; sinon demander le MP4 à l'utilisateur |

## Clés API (facultatives — à demander seulement si la fonction est voulue)
| Clé | Service | Usage |
|---|---|---|
| `ELEVENLABS_API_KEY` (+ `ELEVENLABS_VOICE_ID`, `ELEVENLABS_MODEL`) | ElevenLabs | voix off, mots horodatés |
| `INWORLD_API_KEY` (+ `INWORLD_VOICE`, `INWORLD_MODEL`) | Inworld TTS | voix off (clé « Basic » du portail, ou `id:secret`) |
| `PEXELS_API_KEY`, `PIXABAY_API_KEY` | Pexels, Pixabay | B-roll vidéo / photo gratuits |
| `WIKIMEDIA_ACCESS_TOKEN` | Wikimedia Commons | facultatif (Wikimedia marche sans clé) |
| `FREESOUND_API_KEY`, `MAGNIFIC_API_KEY`, `GEMINI_API_KEY` | Freesound, Magnific, Veo | bruitages, upscale, clips IA |

L'utilisateur te donne une clé → enregistre-la toi-même puis teste :
```bash
bin/monteur cles --set ELEVENLABS_API_KEY=sk_…      # écrit .env (jamais affiché en clair ensuite)
bin/monteur cles --test                             # ✅ / ❌ par service (clé refusée, réseau…)
bin/monteur cles                                    # état
```
Ne recopie jamais une clé dans un message, un commit ou un fichier autre que `.env` (ignoré par git). Studio : Activité › Connexions.
Sans aucune clé, tout marche quand même (contournement automatique) : B-roll Wikimedia, voix Edge gratuite puis espeak hors-ligne, bruitages synthétisés. Higgsfield passe par le connecteur MCP (pas de clé).
