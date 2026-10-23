---
name: monteur-sous-titres
description: Sous-titres animés incrustés (ASS/libass) — karaoké mot par mot, pop d'apparition, mots-clés colorés, cartouche style TikTok, majuscules, position haut/centre/bas. Utiliser pour « ajoute des sous-titres », « captions style Hormozi / MrBeast / TikTok », changer police, couleur, taille, nombre de mots par ligne, ou exporter un .srt.
---

# Sous-titres animés

Générés au rendu depuis `transcript_cut.json` → `RUSH.monteur/subtitles.ass`, incrustés par ffmpeg (`ass=`), polices dans `assets/fonts/`.

## Réglages (`style.subtitles`)
| clé | effet | exemples |
|---|---|---|
| `font` | nom de famille installé | `Montserrat Black`, `Montserrat ExtraBold`, `Anton`, `Bebas Neue`, `Poppins SemiBold`, `Bangers` |
| `size` | fraction du petit côté | 0.04 sobre · 0.065 standard · 0.08 énorme |
| `primary` / `highlight` / `emphasis` | blanc / mot en cours / mots-clés | `#FFFFFF` / `#FFD400` / `#00E676` |
| `uppercase`, `max_words`, `max_chars` | découpe des blocs | Hormozi : `true, 2` · formation : `false, 7, 40` |
| `position`, `margin_v` | `lower` / `center` / `upper`, marge en fraction de hauteur | Reels : `center, 0.33` |
| `karaoke`, `pop` | surlignage mot par mot, rebond d'apparition | |
| `box`, `box_color`, `box_text` | cartouche TikTok natif | UGC |
| `outline_w`, `shadow` | contour / ombre | |
| `hide_during_title` | masque pendant titre & CTA | défaut `true` |

## Polices (respectées à l'identique)
- `subtitles.font` et `motion.font` (titres) sont résolues dans `assets/fonts/` par famille, nom complet ou famille + graisse ; une police absente est **téléchargée depuis Google Fonts** dans la bonne graisse (ex. « Plus Jakarta Sans ExtraBold ») ; sinon, la plus proche installée est utilisée et le journal le dit (`⚠️ Police « … » introuvable`). Dépose le .ttf exact dans `assets/fonts/` pour une police non Google.
- Sans `motion.font`, les titres prennent `library.fonts.display` du style (styles copiés, chartes) ; les cartes animées prennent `display`, `body` et `mono`.
- Les élisions et traits d'union découpés par Whisper (« C 'EST », « PEUT -ÊTRE ») sont recollés.

## Ce que tu décides (plan.json)
- `emphasis_words` : chiffres, bénéfices, mots émotionnels. 1 mot fort par bloc max, sinon plus rien ne ressort.
- `broll[i].hide_subs: true` sur un visuel déjà textuel.
- Corrige les fautes de transcription (noms propres, marques) directement dans `transcript_cut.json` (`words[i].w`) avant le rendu.

## Zones de sécurité
9:16 : garder le texte entre 20 % et 75 % de la hauteur (interface TikTok/Reels en bas et à droite). 16:9 : `margin_v` ≈ 0.07–0.1.

## Export .srt (si demandé)
```bash
"$(. bin/_env.sh; echo "${MONTEUR_PY[0]}")" - <<'PY'   # python du venv, Linux/macOS ou Windows
import json;t=json.load(open("RUSH.monteur/transcript_cut.json"))["words"]
f=lambda s:"%02d:%02d:%02d,%03d"%(s//3600,s%3600//60,s%60,s*1000%1000)
out=[];g=[t[i:i+7] for i in range(0,len(t),7)]
for n,b in enumerate(g,1): out.append(f"{n}\n{f(b[0]['start'])} --> {f(b[-1]['end'])}\n{' '.join(w['w'] for w in b)}\n")
open("RUSH.srt","w").write("\n".join(out))
PY
```
