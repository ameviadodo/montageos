---
name: monteur-voix-off
description: Voix off d'un montage MonteurOS — fichier de voix enregistrée fourni par l'utilisateur, ou script lu par ElevenLabs, Inworld, Edge (gratuit) ou espeak (hors-ligne), avec sous-titres calés mot à mot sur la voix. Utiliser quand la vidéo source n'a pas de voix (produit, B-roll, écran, slideshow), quand l'utilisateur dit « ajoute une voix off », « fais lire ce script », « avec ElevenLabs / Inworld », « voici ma voix off », ou pour une pub/UGC à partir d'images muettes.
---

# Voix off

## Quand demander quoi (toi, avant de monter)
`bin/monteur analyse RUSH.mp4 [--brief "pub"]` → `a_demander` dit ce qui manque. Si la vidéo n'a **pas de voix** :
1. Demande d'abord : « As-tu un fichier de voix off (WAV/MP3) ? » — une voix humaine est toujours meilleure.
2. Sinon demande le **script** — ou propose de l'écrire (sujet, produit, promesse, offre, durée visée). Pub/UGC : accroche 3 s → bénéfice → preuve → appel à l'action, ~2,5 mots/s (15 s ≈ 35 mots). Méthode : `claude-projects/scripts-pubs-ugc/instructions.md`. Fais valider le script avant de synthétiser.
3. Moteur : ElevenLabs ou Inworld si une clé est configurée (`bin/monteur cles`), sinon Edge (gratuit, en ligne). **Demande avant** d'utiliser ElevenLabs / Inworld (crédits payants).
Ne demande rien si le rush est parlé : la voix du rush est nettoyée normalement (skill `monteur-decoupe`).

## Commandes
```bash
bin/monteur voixoff RUSH.mp4 --fichier voix.mp3 --script script.txt --prep     # voix fournie + texte → sous-titres exacts
bin/monteur voixoff RUSH.mp4 --fichier voix.mp3 --prep                         # sans script : Whisper si installé, sinon pas de sous-titres
bin/monteur voixoff RUSH.mp4 --script script.txt --moteur elevenlabs --voix <ID> --prep
bin/monteur voixoff RUSH.mp4 --script "Une phrase. Une autre." --moteur edge --prep
bin/monteur voixoff RUSH.mp4 --original 0     # son du rush coupé sous la voix (défaut 0.15 = ambiance)
bin/monteur voixoff RUSH.mp4 --retire         # retour au son du rush
bin/monteur prep RUSH.mp4 --brief "pub" --voix-off voix.mp3 --script script.txt --hyperframes   # tout d'un coup
bin/monteur voix --liste-voix [--moteur elevenlabs|inworld|edge]   # voix disponibles
```
Script : un fichier `.txt` (une réplique par ligne, `#` = commentaire) ou du texte entre guillemets. Chaque réplique est synthétisée à part puis enchaînée (0,35 s de pause) : le rythme reste naturel et les sous-titres sont calés réplique par réplique.

## Ce que fait la chaîne
- La voix devient la piste principale ; le son du rush passe dessous (`original`), la musique est mise en ducking sous la voix.
- La vidéo **n'est pas coupée** (rien à nettoyer) ; si la voix est plus longue que la vidéo, la dernière image est prolongée.
- Horodatage des mots : ElevenLabs (`with-timestamps`) et Inworld (`timestampType: WORD`) le donnent ; sinon les mots sont répartis sur la parole réelle (les pauses détectées sont sautées). Sous-titres, zooms, B-roll et habillage Hyperframes suivent.
- `--moteur auto` : ElevenLabs → Inworld → Edge → espeak ; un moteur en panne (clé refusée, réseau coupé) est contourné par le suivant, le journal le dit.
- Réglages : `RUSH.monteur/voixoff.json` et `plan.json["voiceover"]` (`gain`, `original`, `start` ; `null` = coupée). Script gardé dans `RUSH.monteur/voixoff/script.txt`.

## Clés
`bin/monteur cles --set ELEVENLABS_API_KEY=… [--set ELEVENLABS_VOICE_ID=…]`, `--set INWORLD_API_KEY=…` (clé « Basic » du portail Inworld, ou `id:secret`), `[--set INWORLD_VOICE=…]` ; `bin/monteur cles --test`. Dans le Studio : Activité › Connexions. Page projet › Voix off pour déposer un fichier ou écrire le script.
