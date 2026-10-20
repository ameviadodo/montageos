# Tuto vidéo « Prise en main de MonteurOS Studio »

Vidéo d'environ 2 min 30 : intro, puis captation réelle du Studio avec un bandeau d'explications, outro et écran « Pour commencer ».
Elle couvre 6 étapes : Projets · Le projet (draft + vérif) · Retours frame par frame · Studio (timeline et cartes) · Bibliothèques · Activité.

**Avec une voix neuronale (Internet requis)**, à partir du kit (captation, repères, intro, outro) :
```bash
bash docs/tuto/faire-tuto.sh <dossier_du_kit> [fr-FR-DeniseNeural|fr-FR-HenriNeural] [edge|espeak]
```

Pour la régénérer après une évolution de l'interface :
```bash
bin/monteur studio --root <dossier_de_démo> --port 8770 &
PLAYWRIGHT=$(npm root -g)/playwright node docs/tuto/record.js http://127.0.0.1:8770 <dossier_tuto>/rec
# intro / outro : cartes section.stage et citation.surligne (voir compose.py, attendu dans <dossier_tuto>/tuto.monteur/assets/motion/)
"$(. bin/_env.sh; echo "${MONTEUR_PY[0]}")" docs/tuto/compose.py <dossier_tuto>      # → <dossier_tuto>/MonteurOS-tuto.mp4
```
Voix off française : la liste `VOICE` de `compose.py` (une réplique par étape, calée sur les repères). Moteur `--moteur auto|edge|espeak` et voix `--voix fr-FR-DeniseNeural` ; `--sans-voix` pour la version muette. Chez toi, avec Internet, `edge` donne une voix neuronale naturelle.

`record.js` pilote le navigateur et affiche un curseur jaune visible ; il note dans `marks.json` le moment de chaque étape. `compose.py` cale le bandeau sur ces repères : il suffit de modifier la liste `STEPS` pour changer les textes.
