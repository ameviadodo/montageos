# shellcheck shell=bash
# Environnement commun à setup.sh et bin/monteur : OS, Python (venv ou système), ffmpeg, encodage.
# À sourcer depuis la racine du dépôt (ou avec ROOT défini). Fournit : MONTEUR_WIN, monteur_venv_python, monteur_find_python, MONTEUR_PY (tableau).
ROOT="${ROOT:-$PWD}"

case "$(uname -s 2>/dev/null)" in
  MINGW*|MSYS*|CYGWIN*) MONTEUR_WIN=1 ;;
  *) MONTEUR_WIN=0 ;;
esac

# Python du venv : .venv/Scripts/python.exe (Windows) ou .venv/bin/python (Linux/macOS)
monteur_venv_python() {
  local c
  if [ "$MONTEUR_WIN" = 1 ]; then set -- "$1/.venv/Scripts/python.exe" "$1/.venv/bin/python"
  else set -- "$1/.venv/bin/python" "$1/.venv/Scripts/python.exe"; fi
  for c in "$@"; do [ -x "$c" ] && { printf '%s\n' "$c"; return 0; }; done
  return 1
}

# Python système ≥ 3.9 (sous Windows : lanceur « py », en évitant le faux python du Microsoft Store)
monteur_find_python() {
  local c
  # Whisper (faster-whisper → PyAV, ctranslate2) n'a de paquets prêts que pour Python 3.9–3.13 : 3.12 d'abord
  if [ "$MONTEUR_WIN" = 1 ]; then set -- "py -3.12" "py -3.11" "py -3.13" "py -3.10" "py -3" python python3
  else set -- python3.12 python3.11 python3.13 python3.10 python3 python; fi
  for c in "$@"; do
    # shellcheck disable=SC2086
    if $c -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
      printf '%s\n' "$c"; return 0
    fi
  done
  return 1
}

# ffmpeg installé par winget / choco / scoop mais absent du PATH du shell courant
if [ "$MONTEUR_WIN" = 1 ] && ! command -v ffmpeg >/dev/null 2>&1; then
  _la="${LOCALAPPDATA:-}"; command -v cygpath >/dev/null 2>&1 && [ -n "$_la" ] && _la="$(cygpath -u "$_la")"
  for _d in "$_la/Microsoft/WinGet/Links" "$_la"/Microsoft/WinGet/Packages/Gyan.FFmpeg*/ffmpeg-*/bin \
            /c/ProgramData/chocolatey/bin "$HOME/scoop/shims" "/c/Program Files/ffmpeg/bin" /c/ffmpeg/bin; do
    [ -x "$_d/ffmpeg.exe" ] && { PATH="$_d:$PATH"; export PATH; break; }
  done
fi

# Commande Python à utiliser (tableau, sûr avec les espaces dans les chemins)
MONTEUR_PY=()
if _vp="$(monteur_venv_python "$ROOT")"; then MONTEUR_PY=("$_vp")
elif _sp="$(monteur_find_python)"; then read -r -a MONTEUR_PY <<< "$_sp"; fi

# Chemins et encodage lisibles par un Python Windows natif
_pyroot="$ROOT"; _sep=":"
if [ "$MONTEUR_WIN" = 1 ] && command -v cygpath >/dev/null 2>&1; then _pyroot="$(cygpath -w "$ROOT")"; _sep=";"; fi
export PYTHONPATH="$_pyroot${PYTHONPATH:+$_sep$PYTHONPATH}"
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8 HF_HUB_DISABLE_SYMLINKS_WARNING=1
unset _la _d _vp _sp _pyroot _sep
