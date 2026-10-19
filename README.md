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
Une interface web locale : liste des rushs, cartes des 6 formats, lecteur Rush/Coupé/Final, timeline (zooms, B-roll, animations), inspecteur pour retoucher le plan, copie de style et sélecteur de charte. Les couleurs, polices et coins arrondis viennent de `ui/themes/<nom>.json`.

### Reprendre la charte « EditingOS » de la vidéo de référence
Pendant la création, YouTube n'était pas accessible depuis le serveur, donc la charte n'a pas pu être extraite. Pour le faire sur ta machine :
```bash
bin/monteur charte "https://www.youtube.com/watch?v=yY_spHjq1vk" --name editingos
```
Ensuite, demande à Claude : « affine le thème editingos à partir des captures » (skill `monteur-charte`). Choisis enfin `editingos` dans le sélecteur « Charte » du Studio. Des captures d'écran de l'interface marchent encore mieux : `bin/monteur charte capture1.png capture2.png --name editingos`.

Pour copier aussi le style de montage de cette vidéo :
```bash
bin/monteur style "https://www.youtube.com/watch?v=yY_spHjq1vk" --name video-reference --transcribe
```

## Architecture
- `skills/` : 11 skills Claude (un chef d'orchestre et 10 métiers). Le dossier sert aussi de plugin (`.claude-plugin/`) et de skills de projet (`.claude/skills`).
- `claude-projects/` : 4 projets claude.ai (directeur artistique, scripts pub/UGC, prompts studio IA, analyste de style).
- `monteur/` : moteur Python + ffmpeg (aucune dépendance lourde).
- `styles/` : `default`, `hormozi`, `minimal`, `pub`, `ugc`, `documentaire`, `intro-youtube`, `formation`, `produit` et tes styles copiés.
- `.mcp.json` : connecteur Higgsfield.
