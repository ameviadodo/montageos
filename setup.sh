#!/usr/bin/env bash
# MonteurOS — installation automatique et idempotente des petites ressources.
#   bash setup.sh            # essentiel : ffmpeg, Whisper, yt-dlp, polices, bruitages
#   bash setup.sh --ai       # + google-genai (Veo / Google Flow)
#   bash setup.sh --motion   # + Hyperframes (Node ≥ 22) et ses skills
#   bash setup.sh --voix     # + espeak-ng / MBROLA (voix off hors-ligne ; en ligne, edge-tts suffit)
#   bash setup.sh --all
# Linux, macOS et Windows (Git Bash). Variable MONTEUR_WHISPER_MODEL : modèle préchargé (défaut : small).
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$PWD"
. "$ROOT/bin/_env.sh"
AI=0; MOTION=0
VOIX=0
for a in "$@"; do case "$a" in --ai) AI=1;; --motion) MOTION=1;; --voix) VOIX=1;; --all) AI=1; MOTION=1; VOIX=1;; esac; done
say() { printf '\033[1;35m[MonteurOS]\033[0m %s\n' "$*"; }
SUDO=""; [ "$MONTEUR_WIN" = 0 ] && [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null && SUDO="sudo"

# 1) ffmpeg
if ! command -v ffmpeg >/dev/null; then
  say "Installation de ffmpeg…"
  if [ "$MONTEUR_WIN" = 1 ]; then
    if command -v winget >/dev/null; then winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements || true
    elif command -v choco >/dev/null; then choco install -y ffmpeg-full || true
    elif command -v scoop >/dev/null; then scoop install ffmpeg || true; fi
    . "$ROOT/bin/_env.sh"   # winget n'actualise pas le PATH du shell courant : on le retrouve nous-mêmes
  elif command -v apt-get >/dev/null; then $SUDO apt-get update -qq && $SUDO apt-get install -y -qq ffmpeg
  elif command -v brew >/dev/null; then brew install ffmpeg
  elif command -v dnf >/dev/null; then $SUDO dnf install -y ffmpeg
  fi
  command -v ffmpeg >/dev/null || { say "⚠️  ffmpeg introuvable : installe-le (Windows : « winget install Gyan.FFmpeg »), puis rouvre le terminal."; exit 1; }
fi
ffmpeg -hide_banner -filters 2>/dev/null | awk '$2=="ass"{f=1} END{exit !f}' || say "⚠️  ffmpeg sans libass : sous-titres indisponibles (installe un ffmpeg complet)."

# 2) Python (venv local : .venv/Scripts/python.exe sous Windows, .venv/bin/python ailleurs)
if ! VPY="$(monteur_venv_python "$ROOT")"; then
  SYS_PY="$(monteur_find_python)" || { say "⚠️  Python 3.9+ introuvable. Windows : https://www.python.org/downloads/ (coche « py launcher »)."; exit 1; }
  if [ -d .venv ]; then  # venv cassé ou créé sur un autre système : on le met de côté
    say "Environnement .venv inutilisable ici, renommé en .venv.old"; rm -rf .venv.old; mv .venv .venv.old
  fi
  say "Création de l'environnement Python (.venv) avec « $SYS_PY »…"
  # shellcheck disable=SC2086
  $SYS_PY -m venv .venv 2>/dev/null || { [ "$MONTEUR_WIN" = 0 ] && $SUDO apt-get install -y -qq python3-venv && $SYS_PY -m venv .venv; }
  VPY="$(monteur_venv_python "$ROOT")" || { say "⚠️  Échec de création du venv."; exit 1; }
fi
say "Python : $VPY"
"$VPY" -m pip install -q --upgrade pip
PKGS=(faster-whisper yt-dlp "opencv-python-headless<5" edge-tts)
[ "$AI" = 1 ] && PKGS+=(google-genai)
say "Paquets Python : ${PKGS[*]}"
"$VPY" -m pip install -q --upgrade "${PKGS[@]}"
"$VPY" -c "import faster_whisper" 2>/dev/null || {
  say "⚠️  faster-whisper ne s'importe pas avec ce Python ($("$VPY" -c 'import sys;print(sys.version.split()[0])'))."
  say "   Windows : installe Python 3.12 (« winget install Python.Python.3.12 »), supprime .venv et relance setup.sh."; exit 1; }
say "Moteur Whisper installé (faster-whisper)."

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
"$ROOT/bin/monteur" sfx >/dev/null && say "Bruitages prêts dans assets/sfx/"

# 4a) Modèle Whisper préchargé (sinon téléchargé au premier « prep »)
WM="${MONTEUR_WHISPER_MODEL:-small}"
say "Préchargement du modèle Whisper « $WM » (une seule fois)…"
"$ROOT/bin/monteur" whisper --model "$WM" || say "⚠️  Modèle non téléchargé (réseau ?). Il le sera au premier « prep », ou relance : bin/monteur whisper"

# 4b) GSAP en local (aperçus des cartes animées hors-ligne)
if command -v npm >/dev/null && [ ! -s assets/vendor/gsap.min.js ]; then
  mkdir -p assets/vendor .cache/npm
  npm install --silent --no-audit --no-fund --prefix .cache/npm gsap@3.14.2 >/dev/null 2>&1 \
    && cp .cache/npm/node_modules/gsap/dist/gsap.min.js assets/vendor/ || true
fi

# 4c) Voix off hors-ligne (espeak-ng + voix françaises MBROLA)
if [ "$VOIX" = 1 ] && ! command -v espeak-ng >/dev/null; then
  if command -v apt-get >/dev/null; then $SUDO apt-get install -y -qq espeak-ng mbrola mbrola-fr1 mbrola-fr4 || true
  elif command -v brew >/dev/null; then brew install espeak-ng || true
  elif [ "$MONTEUR_WIN" = 1 ] && command -v winget >/dev/null; then winget install -e --id eSpeak-NG.eSpeak-NG --accept-source-agreements --accept-package-agreements || true
  fi
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

# 6) Commande globale « monteur » (petit relais : fonctionne aussi sous Git Bash où ln -s copie le fichier)
chmod +x bin/monteur 2>/dev/null || true
mkdir -p "$HOME/.local/bin"
printf '#!/usr/bin/env bash\nexec "%s/bin/monteur" "$@"\n' "$ROOT" > "$HOME/.local/bin/monteur"
chmod +x "$HOME/.local/bin/monteur" 2>/dev/null || true
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) say "ℹ️  Ajoute ~/.local/bin au PATH pour taper « monteur » partout (ou utilise bin/monteur)." ;; esac
[ "$MONTEUR_WIN" = 1 ] && say "ℹ️  cmd / PowerShell : utilise bin\\monteur.cmd"
say "✅ Installé. Vérification :"
"$ROOT/bin/monteur" doctor || true
