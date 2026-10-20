---
numero: 10
nom: Top / classement
etat: Prêt
squelette: scaffold
style: createur-kinetic
ratios: 9:16, 16:9, 1:1
description: « Top 3 / Top 5 » : classement révélé du dernier au premier, un chapitre par entrée, le n°1 en dernier.
---
# Format 10 — Top / classement

1. **Hook** : `classement.top` en aperçu flou ou le titre seul (« Le n°1 va te surprendre »).
2. **Une entrée par chapitre** : du dernier au premier ; `section.cercle` ou `transition.volet` entre les entrées, `whip` comme cut.
3. **Le n°1** : `mot.punch` + `stat.courbe` si un chiffre le justifie.
4. **Récap** : `classement.top` complet (3–5 lignes), puis `sondage.choix` (« Tu es d'accord ? »).

```bash
bin/monteur prep RUSH.mp4 --style createur-kinetic --cuts whip
bin/monteur carte RUSH.mp4 classement.top --start 40 --set title="TOP 3 des outils" --set items="CapCut;Premiere Pro;DaVinci Resolve"
bin/monteur render RUSH.mp4 --draft
```
