#!/usr/bin/env bash
# MonteurOS — installation automatique et idempotente des petites ressources.
#   bash setup.sh            # essentiel : ffmpeg, Whisper, yt-dlp, polices, bruitages
#   bash setup.sh --ai       # + google-genai (Veo / Google Flow)
#   bash setup.sh --motion   # + Hyperframes (Node ≥ 22) et ses skills
#   bash setup.sh --voix     # + espeak-ng / MBROLA (voix off hors-ligne ; en ligne, edge-tts suffit)
#   bash setup.sh --leger    # minimum pour le tuto / la voix off : ffmpeg, edge-tts, polices, bruitages (sans Whisper)
#   bash setup.sh --all
# Linux, macOS et Windows (Git Bash). Variable MONTEUR_WHISPER_MODEL : modèle préchargé (défaut : small).
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$PWD"
. "$ROOT/bin/_env.sh"
AI=0; MOTION=0
VOIX=0; LEGER=0
for a in "$@"; do case "$a" in --ai) AI=1;; --motion) MOTION=1;; --voix) VOIX=1;; --leger) LEGER=1;; --all) AI=1; MOTION=1; VOIX=1;; esac; done
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
pyver() { "$1" -c 'import sys;print("%d.%d" % sys.version_info[:2])' 2>/dev/null; }
whisper_ok_ver() { case "$1" in 3.9|3.10|3.11|3.12|3.13) return 0;; *) return 1;; esac; }
make_venv() {
  SYS_PY="$(monteur_find_python)" || { say "⚠️  Python 3.9+ introuvable. Windows : « winget install Python.Python.3.12 » (ou python.org, coche « py launcher »)."; exit 1; }
  if [ -d .venv ]; then say "Ancien .venv mis de côté (.venv.old)"; rm -rf .venv.old; mv .venv .venv.old; fi
  say "Création de l'environnement Python (.venv) avec « $SYS_PY »…"
  # shellcheck disable=SC2086
  $SYS_PY -m venv .venv 2>/dev/null || { [ "$MONTEUR_WIN" = 0 ] && $SUDO apt-get install -y -qq python3-venv && $SYS_PY -m venv .venv; }
  VPY="$(monteur_venv_python "$ROOT")" || { say "⚠️  Échec de création du venv."; exit 1; }
}
if ! VPY="$(monteur_venv_python "$ROOT")"; then
  make_venv
elif [ "$LEGER" = 0 ] && ! whisper_ok_ver "$(pyver "$VPY")" && ! "$VPY" -c "import faster_whisper" 2>/dev/null; then
  # venv créé avec un Python trop récent pour Whisper : on le refait si un Python compatible existe
  if CAND="$(monteur_find_python)" && whisper_ok_ver "$($CAND -c 'import sys;print("%d.%d" % sys.version_info[:2])' 2>/dev/null)"; then
    say "Le .venv utilise Python $(pyver "$VPY"), trop récent pour Whisper : recréation avec « $CAND »."
    make_venv
  fi
fi
PYV="$(pyver "$VPY")"
say "Python : $VPY ($PYV)"
"$VPY" -m pip install -q --upgrade pip
# Paquets légers d'abord (voix off, téléchargement, vision) : ils ne doivent pas dépendre de Whisper
PKGS=(edge-tts)
[ "$LEGER" = 0 ] && PKGS+=(yt-dlp "opencv-python-headless<5")
[ "$AI" = 1 ] && PKGS+=(google-genai)
say "Paquets Python : ${PKGS[*]}"
"$VPY" -m pip install -q --upgrade --prefer-binary "${PKGS[@]}" || say "⚠️  Certains paquets n'ont pas pu s'installer (voir ci-dessus)."
WHISPER=0
install_whisper() {
  "$VPY" -m pip install -q --upgrade --only-binary=av,ctranslate2,tokenizers "${MONTEUR_WHISPER_PKG:-faster-whisper}" \
    && "$VPY" -c "import faster_whisper" 2>/dev/null
}
# Python 3.12 dédié à MonteurOS via uv (téléchargé dans le cache uv, ton Python système n'est pas modifié)
venv_with_uv() {
  [ -n "${MONTEUR_NO_UV:-}" ] && return 1
  say "Installation d'un Python 3.12 dédié à MonteurOS (uv) — une seule fois, ~30 Mo…"
  "$VPY" -m pip install -q --upgrade uv || return 1
  rm -rf .venv.new
  # uv réutilise un Python 3.12 déjà présent, sinon le télécharge (python-build-standalone)
  "$VPY" -m uv venv --seed --python 3.12 .venv.new >/dev/null || return 1
  local c NEWPY=""
  for c in "$ROOT/.venv.new/Scripts/python.exe" "$ROOT/.venv.new/bin/python"; do [ -x "$c" ] && NEWPY="$c"; done
  [ -n "$NEWPY" ] || return 1
  rm -rf .venv.old; mv .venv .venv.old && mv .venv.new .venv
  VPY="$(monteur_venv_python "$ROOT")" || return 1
  PYV="$(pyver "$VPY")"
  say "Nouveau Python : $VPY ($PYV)"
  "$VPY" -m pip install -q --upgrade --prefer-binary "${PKGS[@]}" || true
}
if [ "$LEGER" = 0 ]; then
  say "Moteur Whisper (faster-whisper)…"
  if [ -z "${MONTEUR_FORCE_UV:-}" ] && install_whisper; then
    WHISPER=1
  elif venv_with_uv && install_whisper; then
    WHISPER=1
  fi
  if [ "$WHISPER" = 1 ]; then
    say "Moteur Whisper installé (faster-whisper, Python $PYV)."
  else
    say "⚠️  Whisper local n'a pas pu s'installer (Python $PYV)."
    say "   Solutions : 1) vérifie ta connexion et relance « bash setup.sh » ;"
    say "               2) importe une transcription : « bin/monteur transcription RUSH.mp4 fichier.srt --prep »"
    say "                  (ou bouton « Importer une transcription » du Studio ; export SRT de WhisperAI, style verbatim)."
    say "   Le reste de MonteurOS (rendu, voix off, tuto, cartes…) fonctionne sans Whisper."
  fi
fi

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
if [ "$WHISPER" = 1 ]; then
  WM="${MONTEUR_WHISPER_MODEL:-small}"
  say "Préchargement du modèle Whisper « $WM » (une seule fois)…"
  "$ROOT/bin/monteur" whisper --model "$WM" || say "⚠️  Modèle non téléchargé (réseau ?). Il le sera au premier « prep », ou relance : bin/monteur whisper"
fi

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
