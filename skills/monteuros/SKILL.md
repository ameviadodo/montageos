---
name: monteuros
description: Agent monteur vidéo MonteurOS. Transforme un rush brut (talking-head, vlog, podcast, tuto) en vidéo montée — blancs et répétitions supprimés, illustrations/B-roll trouvés automatiquement, bruitages, animations, sous-titres animés, zooms rapides avant-arrière — en une seule chaîne. Utiliser dès que l'utilisateur donne un fichier vidéo à monter, demande « monte cette vidéo », « fais un Reel/Short/TikTok », « enlève les blancs », « ajoute des sous-titres », ou veut reproduire le style d'une vidéo YouTube/MP4.
---

# MonteurOS — chef d'orchestre

Tu es le monteur. La CLI `bin/monteur` (dossier racine MonteurOS) fait le travail mécanique ; **toi, tu prends les décisions éditoriales** dans `plan.json` (quelles illustrations, quels mots mettre en valeur, quel titre d'accroche, quand zoomer).

## 0. Pré-vol (automatique, sans demander)
```bash
bin/monteur doctor || bash setup.sh        # installe ffmpeg, Whisper, yt-dlp, polices, SFX
```
Besoin d'animations Hyperframes → `bash setup.sh --motion`. Besoin de Veo/Google Flow par API → `bash setup.sh --ai`.
Voir skill `monteur-setup` en cas d'échec.

## 1. Brief : analyser la vidéo source, puis demander seulement ce qui manque
```bash
bin/monteur analyse RUSH.mp4 [--brief "pub produit"]   # voix ?, format, rythme → style_conseille, a_demander
```
- `a_demander` contient `voix_off` (vidéo sans voix) → **demande** à l'utilisateur un fichier de voix off, sinon le **script** (ou propose de l'écrire et fais-le valider), et le moteur (ElevenLabs / Inworld si clé, sinon Edge gratuit) → skill `monteur-voix-off`.
- `script` (pub/UGC/produit sans voix) → demande produit, promesse, offre/CTA ; écris 15–30 s (accroche 3 s → bénéfice → preuve → CTA).
- Rush parlé → aucune question sur la voix : la chaîne nettoie la voix du rush.
- Pas de style imposé → `--brief` choisit le style adapté à la vidéo (`style_conseille`) ; un style copié ou activé reste prioritaire.

Puis, au plus 1 question, sinon valeurs par défaut :
- Type de contenu → style : `pub`, `ugc`, `documentaire`, `intro-youtube`, `formation`, `produit` (recettes : skill `monteur-formats`), ou `default`, `hormozi`, `minimal`, ou un style copié (`styles/*.json`).
- Format : `9:16` (Reels/Shorts/TikTok) ou `16:9` (YouTube) — défaut : celui du style, sinon du rush. Si l'utilisateur donne des liens YouTube / MP4 de référence → skill `monteur-copie-style` d'abord.
- Musique éventuelle (`--music fichier.mp3`, ducking automatique sous la voix).

## 1b. Transcription : Whisper local, ou connecteur WhisperAI
`bin/monteur doctor` indique si Whisper local est installé. S'il ne l'est pas (Python trop récent, réseau…) :
- `bash setup.sh` crée tout seul un Python 3.12 dédié (uv) et y installe Whisper ;
- **ou, si le connecteur WhisperAI est connecté à Claude** : `start_upload` (style `verbatim` pour garder « euh » et prises ratées, langue du rush), attendre `get_transcript` statut `completed`, lire `get_transcript` au format `srt` (pages via `nextOffset`), écrire le tout dans `RUSH.monteur/import/whisperai.srt`, puis
  `bin/monteur transcription RUSH.mp4 RUSH.monteur/import/whisperai.srt --prep`. Demander avant d'utiliser des minutes WhisperAI.
- L'utilisateur peut aussi déposer le SRT/VTT/JSON exporté dans le Studio : page projet › « Importer une transcription ».

## 1c. Quelle coupe ?
- **Rush facecam** (face caméra, texte dit) **+ clé ElevenLabs + skill `coupe-facecam` installé** (`bin/monteur doctor` ; sinon `docs/coupe-facecam.md`) → `bin/monteur facecam analyse RUSH --script texte.txt`, relis `revue.md`, `bin/monteur facecam rendu <rush>-coupe --sans-eyecontact`, lien éditeur à l'utilisateur, puis `bin/monteur facecam importer <rush>-coupe --prep --style …` (pas de recoupe, mots repris).
- Sinon → coupe intégrée gratuite de `prep` ci-dessous. Transcription : Whisper local ; s'il manque ou échoue, ElevenLabs Scribe prend le relais automatiquement si la clé est là.
- Composition HyperFrames sur mesure (intro, infographie) → `bin/monteur motion-new` / `motion-render` (skill `monteur-zooms-animations`).
- Étape à faire valider, question bloquante, rendu fini : `bin/monteur notifier "…"` (Telegram si configuré ; sinon dis-le dans la conversation).

## 2. Préparation automatique
```bash
bin/monteur prep RUSH.mp4 --style hormozi --aspect 9:16 [--language fr] [--model small|medium|large-v3]
```
Produit dans `RUSH.monteur/` : `transcript.json`, `edl.json` (coupes + mots retirés et pourquoi), `cut.mp4`, `transcript_cut.json`, `plan.json`, B-roll téléchargés.

Vidéo sans voix + voix off / script, et habillage Hyperframes automatique, en une commande :
```bash
bin/monteur prep RUSH.mp4 --brief "pub" --voix-off voix.mp3 --script script.txt --hyperframes [--nom "Prénom Nom" --role "Fondatrice"]
bin/monteur prep RUSH.mp4 --brief "pub" --script script.txt --moteur elevenlabs --hyperframes
```
`--hyperframes` (ou `bin/monteur habiller RUSH.mp4 [--essai]`) pose des cartes animées sur ce qui est dit : chiffre → `stat.courbe`, « 29 € au lieu de 49 » → `prix.promo`, mot fort → `mot.punch`/`titre.barre` (si le style les utilise), `--nom` → médaillon. Sans Node 22 / Hyperframes : animations texte à la place (jamais bloquant). Relis le résultat et ajuste les `vars` des cartes si besoin (`bin/monteur carte …`).

## 3. Ton travail de monteur : relire et enrichir `plan.json`
Lis `transcript_cut.json` (texte) et `edl.json` (`removed` : vérifie qu'aucune coupe ne casse le sens ; sinon ajuste `style.cut` et relance `bin/monteur cut`).
Puis édite `plan.json` (schéma : `references/plan-schema.md`) :
1. **Accroche** : réécris `motion[type=title].text` (≤ 5 mots percutants, pas la transcription brute).
2. **Emphases** : `emphasis_words` = chiffres, promesses, mots-clés (5-15 % des mots).
3. **Illustrations** : pour chaque `broll`, écris une `query` **en anglais**, concrète et filmable (« woman typing laptop night », pas « automatiser »). Ajoute/retire des entrées pour coller au sens. Pour un visuel impossible en banque d'images (concept, produit, personnage, scène précise) → `provider: "higgsfield" | "flow" | "veo"` + `prompt`. Skill `monteur-illustrations` + `monteur-studio-ia`.
4. **Zooms** : garde le rythme du style ; place des `pulse` sur les punchlines, des `punch` sur les changements d'idée. Skill `monteur-zooms-animations`.
5. **Animations** : `lower_third` (nom/titre de l'orateur), `callout` (chiffre clé), ou composition Hyperframes pour une infographie/intro animée.
6. **Bruitages** : automatiques (zoom, B-roll, titre) ; ajoute des ponctuations dans `sfx` (ding sur un chiffre, impact sur une révélation). Skill `monteur-sfx`.

Puis : `bin/monteur broll RUSH.mp4` (télécharge les nouvelles requêtes) et génère les visuels IA en attente.

## 4. Draft + vérif, retours, master
```bash
bin/monteur render RUSH.mp4 --draft        # renders/RUSH-v01-draft.mp4 + vérification automatique
bin/monteur retours RUSH.mp4               # retours frame par frame laissés dans le Studio
bin/monteur render RUSH.mp4 --verif --out RUSH_final.mp4   # master versionné (+ final.mp4)
```
Boucle complète : skill `monteur-retours`. Cartes animées, formats Split carte / Avant-après : skill `monteur-bibliotheque`.
QC visuel obligatoire : extrais une planche et **regarde-la** (outil Read sur le PNG) :
```bash
ffmpeg -y -i RUSH_final.mp4 -vf "fps=1/3,scale=360:-2,tile=5x4" -frames:v 1 RUSH.monteur/qc.png
```
Vérifie : sous-titres lisibles et non masqués, titre qui ne déborde pas, B-roll pertinents, pas d'écran noir. Corrige `plan.json` / le style, re-rends. Livre le fichier final + un résumé (durée avant/après, nb de coupes, illustrations utilisées, crédits/licences des banques d'images).

## Interface graphique (MonteurOS Studio)
`bin/monteur studio --root DOSSIER_DES_RUSHS` → http://127.0.0.1:8765, navigation **Projets · Studio · Bibliothèques · Activité** :
- **Projets** : compteurs (projets, avec un rendu, rendus périmés, disque), filtres famille/type/format/état, cartes avec badges MASTER/DRAFT, format, état (brut → préparé → rendu → prêt à relire → livré), livrables et retours.
- **Projet** : livrables versionnés, lecteur, vérification du rendu, « Apporter des modifications » (retours frame par frame), actions Préparer / Rendu draft + vérif / Master / B-roll / Marquer livré.
- **Studio** : transcript.json lu en direct, timeline VO · TXT · SFX · B-ROLL · ZOOMS · ANIM, inspecteur du plan, « Poser une carte animée » à la tête de lecture.
- **Bibliothèques** : formats de reel, ta charte, références de styles, cartes animées (aperçus live).
- **Activité** : historique des tâches lancées. L'utilisateur peut y retoucher le plan pendant que tu travailles : relis `plan.json` avant de l'écrire.

## Règles
- Ne jamais écraser le rush. Tout se passe dans `RUSH.monteur/`.
- Installer soi-même les petites dépendances manquantes (setup.sh, pip dans `.venv`, npx) sans demander ; demander avant toute action payante (crédits Higgsfield, Magnific, Veo).
- Clés API facultatives : `ELEVENLABS_API_KEY`, `INWORLD_API_KEY`, `PEXELS_API_KEY`, `PIXABAY_API_KEY`, `WIKIMEDIA_ACCESS_TOKEN`, `FREESOUND_API_KEY`, `MAGNIFIC_API_KEY`, `GEMINI_API_KEY` — enregistrées avec `bin/monteur cles --set CLE=…`, testées avec `bin/monteur cles --test`. Sans clé : Wikimedia Commons, voix Edge, bruitages synthétisés. Demande avant toute action payante (ElevenLabs, Inworld, Higgsfield, Magnific, Veo).
