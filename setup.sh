#!/usr/bin/env bash
# MonteurOS — installation automatique et idempotente des petites ressources.
#   bash setup.sh            # essentiel : ffmpeg, Whisper, yt-dlp, polices, bruitages
#   bash setup.sh --ai       # + google-genai (Veo / Google Flow)
#   bash setup.sh --motion   # + Hyperframes (Node ≥ 22) et ses skills
#   bash setup.sh --all
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$PWD"
AI=0; MOTION=0
for a in "$@"; do case "$a" in --ai) AI=1;; --motion) MOTION=1;; --all) AI=1; MOTION=1;; esac; done
say() { printf '\033[1;35m[MonteurOS]\033[0m %s\n' "$*"; }
SUDO=""; [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null && SUDO="sudo"

# 1) ffmpeg
if ! command -v ffmpeg >/dev/null; then
  say "Installation de ffmpeg…"
  if command -v apt-get >/dev/null; then $SUDO apt-get update -qq && $SUDO apt-get install -y -qq ffmpeg
  elif command -v brew >/dev/null; then brew install ffmpeg
  elif command -v dnf >/dev/null; then $SUDO dnf install -y ffmpeg
  elif command -v winget >/dev/null; then winget install -e --id Gyan.FFmpeg
  else say "⚠️  Installe ffmpeg manuellement : https://ffmpeg.org/download.html"; exit 1; fi
fi
ffmpeg -hide_banner -filters 2>/dev/null | awk '$2=="ass"{f=1} END{exit !f}' || say "⚠️  ffmpeg sans libass : sous-titres indisponibles (installe un ffmpeg complet)."

# 2) Python (venv local)
PY=python3; command -v $PY >/dev/null || PY=python
if [ ! -x .venv/bin/python ]; then
  say "Création de l'environnement Python (.venv)…"
  $PY -m venv .venv 2>/dev/null || { $SUDO apt-get install -y -qq python3-venv && $PY -m venv .venv; }
fi
VPY="$ROOT/.venv/bin/python"
$VPY -m pip install -q --upgrade pip
PKGS="faster-whisper yt-dlp opencv-python-headless<5"
[ "$AI" = 1 ] && PKGS="$PKGS google-genai"
say "Paquets Python : $PKGS"
$VPY -m pip install -q --upgrade faster-whisper yt-dlp "opencv-python-headless<5" $([ "$AI" = 1 ] && echo google-genai)

# 3) Polices pour sous-titres et titres (OFL)
mkdir -p assets/fonts
fetch_font() { [ -s "assets/fonts/$1" ] || curl -fsSL -o "assets/fonts/$1" "$2" || say "⚠️  police $1 non téléchargée"; }
MS=https://raw.githubusercontent.com/JulietaUla/Montserrat/master/fonts/ttf
GF=https://raw.githubusercontent.com/google/fonts/main/ofl
for w in Black ExtraBold Bold SemiBold; do fetch_font "Montserrat-$w.ttf" "$MS/Montserrat-$w.ttf"; done
fetch_font Anton-Regular.ttf "$GF/anton/Anton-Regular.ttf"
fetch_font BebasNeue-Regular.ttf "$GF/bebasneue/BebasNeue-Regular.ttf"
for w in Black ExtraBold SemiBold; do fetch_font "Poppins-$w.ttf" "$GF/poppins/Poppins-$w.ttf"; done
fetch_font Bangers-Regular.ttf "$GF/bangers/Bangers-Regular.ttf"
# charte « nocturne » (titres serif italique, étiquettes mono) + cartes éditoriales
fetch_font InstrumentSerif-Italic.ttf "$GF/instrumentserif/InstrumentSerif-Italic.ttf"
fetch_font InstrumentSerif-Regular.ttf "$GF/instrumentserif/InstrumentSerif-Regular.ttf"
fetch_font SpaceMono-Regular.ttf "$GF/spacemono/SpaceMono-Regular.ttf"
fetch_font SpaceMono-Bold.ttf "$GF/spacemono/SpaceMono-Bold.ttf"
fetch_font Fraunces.ttf "$GF/fraunces/Fraunces%5BSOFT,WONK,opsz,wght%5D.ttf"

# 4) Bibliothèque de bruitages (synthétisés localement)
$VPY -m monteur sfx >/dev/null && say "Bruitages prêts dans assets/sfx/"

# 4b) GSAP en local (aperçus des cartes animées hors-ligne)
if command -v npm >/dev/null && [ ! -s assets/vendor/gsap.min.js ]; then
  mkdir -p assets/vendor .cache/npm
  npm install --silent --no-audit --no-fund --prefix .cache/npm gsap@3.14.2 >/dev/null 2>&1 \
    && cp .cache/npm/node_modules/gsap/dist/gsap.min.js assets/vendor/ || true
fi

# 5) Hyperframes (animations HTML → vidéo)
if [ "$MOTION" = 1 ]; then
  if command -v node >/dev/null && [ "$(node -p 'process.versions.node.split(".")[0]')" -ge 22 ]; then
    say "Préchargement de Hyperframes…"
    npx -y hyperframes@latest doctor || true
    npx -y skills add heygen-com/hyperframes -y 2>/dev/null || say "ℹ️  Skill Hyperframes : lance « npx skills add heygen-com/hyperframes » si besoin."
  else
    say "⚠️  Hyperframes demande Node.js ≥ 22 : https://nodejs.org (ou « nvm install 22 »)."
  fi
fi

# 6) Commande globale « monteur »
chmod +x bin/monteur
mkdir -p "$HOME/.local/bin" && ln -sf "$ROOT/bin/monteur" "$HOME/.local/bin/monteur"
say "✅ Installé. Vérification :"
"$ROOT/bin/monteur" doctor || true
