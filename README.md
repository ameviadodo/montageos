# 🎬 MontageOS (MonteurOS)

Agent composé de skills Claude qui réalise un montage professionnel à partir d'une vidéo brute. Il utilise Hyperframes, Higgsfield, Magnific et Google Flow.

Un agent monteur vidéo pour Claude. Tu lui donnes un rush brut, il te rend une vidéo montée.

| Étape | Ce que fait MonteurOS |
|---|---|
| ✂️ Coupe | Supprime les blancs, les « euh / hum », les bégaiements (« je pense que je pense que ») et les prises ratées (seule la dernière prise est gardée) |
| 🖼️ Illustrations | Cherche les B-roll et photos tout seul (Pexels, Pixabay, Wikimedia) ou les génère avec l'IA (Higgsfield, Google Flow/Veo, Magnific) |
| 🔍 Zooms | Zooms rapides avant-arrière : *punch*, *pulse*, poussée douce |
| ✨ Animations | Titre d'accroche, lower-third, callout, chapitres, CTA, motion design **Hyperframes** |
| 💬 Sous-titres | Karaoké mot par mot, pop, mots-clés colorés, cartouche TikTok |
| 🔊 Son | Whoosh, pop, ding, impact, riser, musique avec ducking, normalisation LUFS |
| 🎨 Style | Copie le style d'une vidéo YouTube ou d'un MP4 ; extrait une charte graphique |
| 🧩 Formats | Pub, UGC, documentaire, intro YouTube, formation, visuels produits |

## Installation (automatique)
```bash
bash setup.sh            # ffmpeg, Whisper, yt-dlp, polices, bruitages
bash setup.sh --all      # + Hyperframes (Node ≥ 22) + Veo/Google Flow
cp .env.example .env     # clés API facultatives
```
**Windows** : ouvre **Git Bash** dans le dossier et lance les mêmes commandes. Le venv est créé dans `.venv\Scripts\` et détecté automatiquement. Depuis cmd ou PowerShell, utilise `bin\monteur.cmd`. Il faut Python 3.12 (`winget install Python.Python.3.12`) et ffmpeg (`winget install Gyan.FFmpeg`, installé tout seul par `setup.sh` s'il manque).
Pour précharger ou tester le moteur de transcription : `bin/monteur whisper --model small`.
Dans Claude Code, un hook de démarrage lance l'installation si elle manque, et Claude répare lui-même ce qui manque (skill `monteur-setup`).

## Utilisation avec Claude
Ouvre le dossier dans Claude Code (ou installe-le comme plugin), puis :
> « Monte `rush.mp4` en pub 9:16, ajoute une musique et un CTA "-20 % avec le code LANCEMENT". »

> « Copie le style de https://youtu.be/… et applique-le à `interview.mp4`. »

## Utilisation manuelle
```bash
bin/monteur run rush.mp4 --style pub --aspect 9:16 --music fond.mp3      # tout d'un coup
bin/monteur prep rush.mp4 --style formation   # transcription, coupe, plan, B-roll
#   → édite rush.monteur/plan.json (ou dans le Studio)
bin/monteur render rush.mp4 --out final.mp4
bin/monteur style "https://youtu.be/XXXX" ref.mp4 --name mon-style
bin/monteur slideshow p1.jpg p2.jpg p3.jpg --out produit.mp4 && bin/monteur prep produit.mp4 --style produit
bin/monteur studio --root ~/Videos            # interface → http://127.0.0.1:8765
```

## Interface MonteurOS Studio
> 🎥 Tuto vidéo de prise en main : voir [`docs/tuto/`](docs/tuto/) (script d'enregistrement et de montage inclus).

Une interface web locale : liste des rushs, cartes des 6 formats, lecteur Rush/Coupé/Final, timeline (zooms, B-roll, animations), inspecteur pour retoucher le plan, copie de style et sélecteur de charte. Les couleurs, polices et coins arrondis viennent de `ui/themes/<nom>.json`.

### Inspiré d'EditingOS
La vidéo de référence a été analysée image par image (détail : [`docs/editingos-analyse.md`](docs/editingos-analyse.md)). MonteurOS en reprend :
- **les menus** Projets · Studio · Bibliothèques · Activité ;
- **les retours frame par frame** (−1 img / +1 img, « Copier pour Claude », « Envoyer au montage ») ;
- **le « Rendu draft + vérif »** et les livrables versionnés ;
- **les formats de reel** Split carte et Avant/après ;
- **les cartes animées** : écrans 3D, rail des étapes, médaillon, surlignage, marqueurs de section, stat + compteur, programme ;
- **la charte « nocturne »** : bleu nuit, jaune #FFD935, serif italique et mono.

```bash
bin/monteur render rush.mp4 --draft                 # brouillon + vérification automatique
bin/monteur retours rush.mp4                        # retours frame par frame laissés dans le Studio
bin/monteur cartes                                  # catalogue des cartes animées
bin/monteur carte rush.mp4 stat.courbe --start 12 --set value=125 --set suffix=K
bin/monteur avant-apres transforme.mp4 original.mp4 --title "Avant / après" --out compare.mp4
bin/monteur prep rush.mp4 --style split-carte       # format Split carte
```

### Bibliothèque : styles viraux, formats, chartes, cuts
- **Cloner un style qui cartonne** : Studio → Bibliothèques → Références → liens YouTube/TikTok/Instagram ou MP4 →
  « Cloner le style » ; le style est rangé (état *Copié*) et peut être **activé** pour tous les nouveaux projets.
- **Tous les formats** : 9:16, 16:9, 1:1, 4:5, 3:4, 2:3, 21:9 — filtre *Format* dans la bibliothèque, `--aspect` partout.
- **Nouvelles chartes** depuis un lien vidéo ou un petit extrait MP4 → thème du Studio + style vidéo assorti.
- **Recherche de cartes** animées (17 cartes : prix promo, avis étoiles, mot punch, intro logo, lieu/date, volet…).
- **Types de cut** entre les plans : zoom cut, flash, passage au noir, whip, glitch, fondu, mix.

```bash
bin/monteur style "https://youtu.be/XXXX" --name viral --activer   # clone + active
bin/monteur styles                                                  # bibliothèque (● = actif)
bin/monteur charte "https://youtu.be/YYYY" extrait.mp4 --name ma-marque
bin/monteur cartes --cherche prix
bin/monteur render rush.mp4 --aspect 4:5 --cuts mix --draft
```

## Architecture
- `skills/` : 13 skills Claude (un chef d'orchestre et 12 métiers). Le dossier sert aussi de plugin (`.claude-plugin/`) et de skills de projet (`.claude/skills`).
- `claude-projects/` : 4 projets claude.ai (directeur artistique, scripts pub/UGC, prompts studio IA, analyste de style).
- `monteur/` : moteur Python + ffmpeg (aucune dépendance lourde).
- `library/` : formats de reel (`formats/*.md`) et cartes animées Hyperframes (`cards/*.card.html`).
- `styles/` : `default`, `hormozi`, `minimal`, `pub`, `ugc`, `documentaire`, `intro-youtube`, `formation`, `produit` et tes styles copiés.
- `.mcp.json` : connecteur Higgsfield.
