---
name: monteur-illustrations
description: Trouve et place automatiquement les illustrations / B-roll d'un montage — vidéos et photos libres (Pexels, Pixabay, Wikimedia Commons) ou visuels générés par IA (Higgsfield, Google Flow/Veo, Magnific) — calés sur ce qui est dit. Utiliser pour « ajoute des illustrations », « mets du B-roll », « trouve des images pour illustrer », remplacer un visuel, ou incruster une capture/photo fournie.
---

# Illustrations automatiques

## 1. Choisir les moments (toi)
Dans `plan.json → broll`, l'auto-plan propose N moments selon `style.broll.per_minute`. Améliore :
- Illustre les **noms concrets** (objet, lieu, action) et les **chiffres** ; jamais pendant le hook (0–2,5 s) ni pendant une émotion face caméra.
- Durée 1,2–2,5 s (rythmé) ; 3–5 s (documentaire).
- `query` en **anglais**, 2–4 mots visuels : « entrepreneur counting cash », « empty office night », « instagram app scrolling phone ».
- `layout`: `full` (cutaway) ou `pip` (incrustation, l'orateur reste visible — formations, UGC).

## 2. Télécharger (automatique)
```bash
bin/monteur broll RUSH.mp4
```
Ordre `provider: auto` : Pexels → Pixabay → Wikimedia (sans clé). Orientation déduite du format. Fichiers dans `RUSH.monteur/assets/broll/`. Les entrées sans résultat restent `file: null` → reformule ou passe en IA.

## 3. Visuels IA (quand la banque ne suffit pas)
Mets `provider` = `higgsfield` / `flow` / `veo` / `magnific` + `prompt` détaillé, puis suis le skill `monteur-studio-ia`. Une fois le fichier obtenu :
```bash
bin/monteur attach RUSH.mp4 <index> chemin/visuel.mp4    # ou .png
```

## 4. Fichiers de l'utilisateur
Captures d'écran, photos produit, logos : `bin/monteur attach RUSH.mp4 <i> fichier`. Une image reçoit un mouvement Ken Burns automatique.

## Licences
Pexels/Pixabay : libres d'usage commercial, sans attribution obligatoire (mentionner reste une bonne pratique). Wikimedia : **vérifier la licence** de chaque fichier (CC BY/BY-SA → crédit obligatoire) et la lister dans le résumé de livraison.
