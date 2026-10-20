#!/usr/bin/env bash
# Régénère le tuto avec une voix off neuronale (Edge TTS, Internet requis).
#   bash docs/tuto/faire-tuto.sh <dossier_du_kit> [voix] [moteur]
#   voix   : fr-FR-DeniseNeural (défaut, femme) · fr-FR-HenriNeural (homme) · fr-FR-VivienneMultilingualNeural · fr-FR-RemyMultilingualNeural
#   moteur : edge (défaut) · espeak (hors-ligne)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
KIT="${1:?Indique le dossier du kit, ex. : bash docs/tuto/faire-tuto.sh ~/Downloads/MonteurOS-tuto-kit}"
VOIX="${2:-}"
MOTEUR="${3:-edge}"
# Tolérant : voix collée dans les guillemets (« …kit fr-FR-HenriNeural »)
if [[ "$KIT" =~ ^(.*)[[:space:]]+([a-z]{2}-[A-Z]{2}-[A-Za-z]+Neural)[[:space:]]*$ ]]; then
  KIT="${BASH_REMATCH[1]}"; VOIX="${VOIX:-${BASH_REMATCH[2]}}"
fi
VOIX="${VOIX:-fr-FR-DeniseNeural}"
KIT="${KIT%"${KIT##*[![:space:]]}"}"   # espaces de fin
KIT="${KIT%/}"
# … chemin de screen.webm ou du dossier rec/ au lieu du dossier du kit
case "$KIT" in */rec/screen.webm) KIT="${KIT%/rec/screen.webm}";; */rec) KIT="${KIT%/rec}";; esac
# … dossier dézippé en double (MonteurOS-tuto-kit/MonteurOS-tuto-kit)
if [ ! -f "$KIT/rec/screen.webm" ]; then
  for c in "$KIT"/*/; do [ -f "${c}rec/screen.webm" ] && { KIT="${c%/}"; break; }; done
fi
[ -f "$KIT/rec/screen.webm" ] || { echo "Kit introuvable : aucun rec/screen.webm dans « $KIT »." >&2
  echo "Exemple : bash docs/tuto/faire-tuto.sh \"/c/Users/<toi>/Downloads/MonteurOS-tuto-kit\" fr-FR-HenriNeural" >&2; exit 1; }
echo "Kit : $KIT — voix : $VOIX ($MOTEUR)"
cd "$ROOT"
. bin/_env.sh
monteur_venv_python "$ROOT" >/dev/null || bash setup.sh
. bin/_env.sh
"${MONTEUR_PY[@]}" -c "import edge_tts" 2>/dev/null || "${MONTEUR_PY[@]}" -m pip install -q edge-tts
[ "$MOTEUR" = espeak ] && VOIX_ARG=() || VOIX_ARG=(--voix "$VOIX")
"${MONTEUR_PY[@]}" docs/tuto/compose.py "$KIT" --moteur "$MOTEUR" "${VOIX_ARG[@]}"
echo "✅ Tuto prêt : $KIT/MonteurOS-tuto.mp4"
