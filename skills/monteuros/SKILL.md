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

## 1. Brief (1 question max, sinon valeurs par défaut)
- Type de contenu → style : `pub`, `ugc`, `documentaire`, `intro-youtube`, `formation`, `produit` (recettes : skill `monteur-formats`), ou `default`, `hormozi`, `minimal`, ou un style copié (`styles/*.json`).
- Format : `9:16` (Reels/Shorts/TikTok) ou `16:9` (YouTube) — défaut : celui du style, sinon du rush. Si l'utilisateur donne des liens YouTube / MP4 de référence → skill `monteur-copie-style` d'abord.
- Musique éventuelle (`--music fichier.mp3`, ducking automatique sous la voix).

## 2. Préparation automatique
```bash
bin/monteur prep RUSH.mp4 --style hormozi --aspect 9:16 [--language fr] [--model small|medium|large-v3]
```
Produit dans `RUSH.monteur/` : `transcript.json`, `edl.json` (coupes + mots retirés et pourquoi), `cut.mp4`, `transcript_cut.json`, `plan.json`, B-roll téléchargés.

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
- Clés API facultatives : `PEXELS_API_KEY`, `PIXABAY_API_KEY`, `FREESOUND_API_KEY`, `MAGNIFIC_API_KEY`, `GEMINI_API_KEY`. Sans clé : Wikimedia Commons + bruitages synthétisés.
