#!/usr/bin/env bash
# Régénère le tuto avec une voix off neuronale (Edge TTS, Internet requis).
#   bash docs/tuto/faire-tuto.sh <dossier_du_kit> [voix] [moteur]
#   voix   : fr-FR-DeniseNeural (défaut, femme) · fr-FR-HenriNeural (homme) · fr-FR-VivienneMultilingualNeural · fr-FR-RemyMultilingualNeural
#   moteur : edge (défaut) · espeak (hors-ligne)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
KIT="${1:?Indique le dossier du kit, ex. : bash docs/tuto/faire-tuto.sh ~/Downloads/MonteurOS-tuto-kit}"
VOIX="${2:-fr-FR-DeniseNeural}"
MOTEUR="${3:-edge}"
[ -f "$KIT/rec/screen.webm" ] || { echo "Kit incomplet : $KIT/rec/screen.webm introuvable." >&2; exit 1; }
cd "$ROOT"
. bin/_env.sh
monteur_venv_python "$ROOT" >/dev/null || bash setup.sh
. bin/_env.sh
"${MONTEUR_PY[@]}" -c "import edge_tts" 2>/dev/null || "${MONTEUR_PY[@]}" -m pip install -q edge-tts
[ "$MOTEUR" = espeak ] && VOIX_ARG=() || VOIX_ARG=(--voix "$VOIX")
"${MONTEUR_PY[@]}" docs/tuto/compose.py "$KIT" --moteur "$MOTEUR" "${VOIX_ARG[@]}"
echo "✅ Tuto prêt : $KIT/MonteurOS-tuto.mp4"
