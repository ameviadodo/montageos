# Installer le skill coupe-facecam (facultatif)

`coupe-facecam` (kit **Agence Agentique**) coupe un rush facecam au mot près : transcription ElevenLabs Scribe,
écoute Silero VAD, la dernière prise gagne, regard caméra Descript, relecture dans l'Agentique Editor.
Sa licence réserve le kit aux membres : il **n'est pas publié** avec MonteurOS (`skills/coupe-facecam/` est dans
`.gitignore`). Sans lui, la coupe intégrée de `bin/monteur prep` fonctionne normalement.

## Installation
1. Copie ton dossier `coupe-facecam/` dans `skills/` : `skills/coupe-facecam/SKILL.md`, `scripts/coupe.py`,
   `models/silero_vad.onnx`, `editeur/`, `config/cles.env`.
2. `bash setup.sh` (installe numpy, onnxruntime, requests dans `.venv`), puis `bin/monteur doctor`.
3. `bin/monteur cles --set ELEVENLABS_API_KEY=sk_…` (la même clé sert à la voix off et à la transcription).

La version adaptée à MonteurOS (Windows/Linux, ffmpeg 6 ou 7, clés lues dans le `.env` de MonteurOS, éditeur
non bloquant sans Node) est celle livrée dans le zip MonteurOS de ton espace de travail, pas sur GitHub.

## Utilisation
```bash
bin/monteur facecam analyse rush.MOV --script texte.txt
bin/monteur facecam rendu rush-coupe --sans-eyecontact      # éditeur : http://127.0.0.1:50012
bin/monteur facecam importer rush-coupe --prep --style hormozi
```
