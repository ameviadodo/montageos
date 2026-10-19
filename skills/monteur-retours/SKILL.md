---
name: monteur-retours
description: Boucle de relecture MonteurOS — rendu draft + vérification automatique, retours frame par frame laissés dans le Studio (ou collés dans la conversation), application des corrections puis rendu master versionné. Utiliser quand l'utilisateur dit « j'ai laissé des retours », colle un bloc « Retours frame par frame », demande « corrige à 00:12 », « refais le rendu », « vérifie le montage », ou veut livrer.
---

# Relecture : draft → retours → master

## 1. Draft + vérification (le geste courant)
```bash
bin/monteur render RUSH.mp4 --draft      # demi-résolution, ~4× plus rapide → renders/RUSH-vNN-draft.mp4
```
La vérification tourne seule (`monteur verif` pour la relancer) et écrit `renders/…verif.json` :
durée vs plan, écrans noirs, blancs oubliés > 1,2 s, saturation audio, **mots coupés** par une coupe, illustrations manquantes.
Corrige toute ❌ avant de montrer ; explique les ⚠️ restants.

## 2. Lire les retours
- L'utilisateur relit dans le Studio → **Projets › projet › Apporter des modifications** (lecteur −1s / −1 img / +1 img / +1s, ↑ pour noter).
- Il clique **Envoyer au montage** (statut `envoyé`) ou **Copier pour Claude** (bloc collé dans le chat).
- Toi : `bin/monteur retours RUSH.mp4` liste les retours non appliqués : `#id [mm:ss.cc · fNNNN] texte (rendu …)`. Fichier : `RUSH.monteur/review/feedback.json`.

## 3. Appliquer chaque retour
Les temps sont ceux du **rendu** (= timeline coupée de `plan.json`, sauf en draft où l'échelle est identique).
| Retour type | Où agir |
|---|---|
| « coupe trop tôt / mot mangé » | `style.cut.padding` ↑ ou retirer l'index du mot de `edl.removed` → `monteur cut` puis `plan` |
| « enlève / décale ce zoom » | `plan.zooms[i]` (supprimer, `start`, `kind`, `scale`) |
| « mauvaise illustration » | `plan.broll[i].query` / `provider` → `monteur broll` ou `attach` |
| « faute dans le sous-titre » | `transcript_cut.json → words[i].w` |
| « titre trop long / autre accroche » | `plan.motion[type=title].text` |
| « mets un chiffre animé ici » | `monteur carte RUSH.mp4 stat.courbe --start T --set value=…` |
| « son trop fort » | `plan.sfx[…].gain`, `style.sfx.volume`, `style.audio.music_volume` |
Puis nouveau draft, et marque : `bin/monteur retours RUSH.mp4 --applique 1 2 3`.

## 4. Livrer
`bin/monteur render RUSH.mp4 --verif` (master versionné + `final.mp4`), QC visuel (planche lue avec Read), puis `bin/monteur projet RUSH.mp4 --etat livré`.
Un rendu est **périmé** (pastille rouge) quand le plan, le style ou le rush a changé après lui : re-rends.
