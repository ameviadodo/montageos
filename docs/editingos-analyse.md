# Analyse de la vidéo de référence « EditingOS » → MonteurOS

Source : MP4 fourni par l'utilisateur (6 min 29, 1266×706), analysé image par image (≈ 70 images, dont 14 en pleine résolution). Rien n'est copié tel quel (ni nom, ni logo, ni contenus de tiers) : on reprend l'**ergonomie**, la **logique** et la **direction artistique**, réimplémentées pour MonteurOS.

## Interface
| Vu dans EditingOS | Dans MonteurOS |
|---|---|
| Navigation en pastilles : Projets · Studio · Bibliothèques · Activité · Actualiser | `ui/index.html`, mêmes menus |
| Compteurs : projets, avec un rendu, rendus périmés (rouge), disque rendus | Projets › bandeau de stats (`/api/projects`) |
| « Le système de fichiers fait foi. Relevé il y a … en … ms » | même principe : tout est relu depuis `<rush>.monteur/` |
| Filtres : familles, types, formats, états, modifié récemment, périmés seuls, masquer l'utilitaire | Projets › barre de filtres |
| Cartes projet : titre, date, tags (Ads / Ugc, talking-head), badges MASTER + 9:16, « prêt à relire », « livré », « rendu il y a 3 jours », livrables, retours | `monteur/project.py` + cartes du tableau de bord |
| Page projet : livrables versionnés (`renders/…-v04-master.mp4`), lecteur, taille · format · durée, « Apporter des modifications », « Ouvrir le Studio », « Ouvrir dans un onglet » | Projet (`renders/` versionné par `render.py`) |
| Actions « Pendant le montage » → « Rendu draft + vérif » (brouillon ~1 min puis contrôle du fichier : mots coupés, phrases…) | `render --draft` + `monteur/verify.py` |
| Retours frame par frame : −1s / −1 img / ▶ / +1 img / +1s, timecode + n° de frame, « Ton retour sur cette frame… », Ajouter, Espace / ← → / ↑, « Copier pour Claude », « Télécharger .json », « Envoyer au montage », enregistré dans `review/` | vue Retours + `monteur/review.py` + skill `monteur-retours` |
| Bibliothèques : Formats de reel (Split carte, Avant/après, Recréer ce contenu viral) avec état, squelette, aperçu | `library/formats/*.md`, `styles/split-carte.json`, `monteur/layouts.py` |
| Ta charte (palette, polices, nb de cartes) | `ui/themes/nocturne.json` (activable) |
| Références : styles avec état Draft, nb de cartes, palette, polices display/body/mono | bloc `library` des `styles/*.json` (6 références génériques + formats existants) |
| Page style : description, palette, catégories Écrans / Médaillons / Surlignage / Marqueurs de section, cartes `style.t1.section.circle`, « Voir en grand », Rejouer / Onglet / Fermer, « Masquer les variantes », « Tout ouvrir » | vue Style + `library/cards/*.card.html` + modale |
| Timeline « EDITING OS · MONTAGE EN COURS » : VO · VIDÉO (coupes rouges), TXT · SOUS-TITRES, SFX · SONS, B-ROLL · ILLUS, tête de lecture jaune ; panneau `transcript.json · N mots · ce que le système lit` | vue Studio (pistes + transcript synchronisé) |
| Exemple rendu vs reel publié de référence | vue Format (`library/formats/exemples/<id>.mp4` si présent) |

## Direction artistique (charte « nocturne »)
Bleu nuit, panneaux sombres à bord fin, **jaune #FFD935** pour l'actif (pastilles, boutons, chiffres clés), vert « prêt à relire », rouge « périmé » ; titres de page en **serif italique** (Instrument Serif), corps **Montserrat**, étiquettes/chiffres en **mono capitales espacées** (Space Mono).

## Ressources animées vues dans la vidéo → cartes MonteurOS
| Vu | Carte |
|---|---|
| Panneau de verre dépoli en perspective à côté de l'orateur (« Où en est chaque projet ? ») | `ecran.push3d` |
| « Le rail des 9 étapes » avec cadre lumineux | `ecran.rail` |
| Bandeau nom + fonction de l'orateur | `medaillon.nom` |
| « Il s'occupe de tout » : lignes gris → jaune surlignées | `surlignage.liste` |
| Cartons crème éditoriaux (titre serif + pastille, mots sur marqueurs, cadre photo) | `section.cercle`, `section.marqueurs` |
| Écran de boot « STAGE 1 » | `section.stage` |
| Courbe + compteur « 125K learners » | `stat.courbe` |
| `gsap.to(".barre")…` barre + point + mot | `titre.barre` |
| « le programme » 01–04 avec chapitre actif | `programme.chapitres` |
| « Le montage vidéo n'est plus jamais ce qui t'arrête » | `citation.surligne` |
| Format Split carte / Avant-après (« Transformé » / « Originale ») | `styles/split-carte.json`, `monteur avant-apres` |

## Conseils de la vidéo intégrés
- Le montage = **une chaîne unique** pilotée par Claude, à partir de `transcript.json` (ce que le système lit).
- **Draft d'abord**, vérification automatique, puis retours précis **à la frame** avant le master.
- Une **bibliothèque de styles et une charte** que Claude réutilise (formats de reel, cartes, palettes).
- « Une animation, c'est du code » → cartes Hyperframes/GSAP paramétrables.
- « Le dossier prêt : l'interface, la bibliothèque de styles, ta charte — tu le donnes à Claude, il l'installe » → ce dépôt + `setup.sh` + hook de démarrage.
