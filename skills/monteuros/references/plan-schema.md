# Schéma de `plan.json`

Toutes les durées sont en secondes **sur la timeline coupée** (`cut.mp4`).

```jsonc
{
  "duration": 61.4,
  "zooms": [
    {"start": 3.2, "end": 5.4, "kind": "punch", "scale": 1.12},   // zoom avant sec, tenu, retour sec
    {"start": 9.9, "end": 10.4, "kind": "pulse", "scale": 1.18},  // avant-arrière rapide (punchline)
    {"start": 20, "end": 24, "kind": "ease", "scale": 1.08, "sfx": null} // poussée douce ; sfx: null = muet
  ],
  "broll": [
    {"start": 12.1, "end": 14.3, "query": "stock market chart green", "context": "phrase dite",
     "provider": "auto|pexels|pixabay|wikimedia|higgsfield|flow|veo|magnific",
     "prompt": "prompt IA si provider génératif", "kind": "video|image",
     "layout": "full|pip", "hide_subs": false, "file": null, "fade": 0.15, "sfx": "swoosh"}
  ],
  "motion": [
    {"start": 0.15, "end": 2.3, "type": "title", "text": "DOUBLE TES VENTES", "y": 0.42},
    {"start": 5, "end": 8, "type": "lower_third", "text": "Isidore — Expert Marketing"},
    {"start": 30, "end": 31.5, "type": "callout", "text": "+212 %"},
    {"start": 40, "end": 46, "type": "hyperframes", "name": "graph", "file": "…/graph.mov", "layout": "overlay|full|panel"},
    {"start": 50, "end": 52, "type": "chapter", "number": "02", "text": "L'installer chez toi"}
  ],
  "transitions": [{"t": 3.42, "kind": "flash"}, {"t": 7.9, "kind": "whip", "sfx": null}],
                     // raccords sur les coupes : hard|zoomcut|flash|dip|whip|glitch|fondu (absent = déduit de style.cut.transition)
  "sfx": [{"t": 30.0, "name": "ding", "gain": 0.4}],   // en plus des bruitages automatiques
  "emphasis": [12, 57],                                  // indices de mots (transcript_cut)
  "emphasis_words": ["ventes", "gratuit", "30"],         // ou par texte (insensible à la casse)
  "music": null,                                         // chemin musique (sinon style.audio.music)
  "voiceover": {"file": "voixoff/voix.wav", "start": 0, "duration": 11.0, "gain": 1.0, "original": 0.15}
                     // voix off (bin/monteur voixoff) : piste principale, son du rush à `original` ; null = coupée
}
```

- `file` à `null` = à trouver (`monteur broll`) ou à générer (IA puis `monteur attach`).
- `layout: "pip"` = incrustation en haut à droite ; `full` = plein écran (la voix continue) — en format Split carte, `full` va dans le panneau du haut ; `fullscreen` force le plein cadre.
- `hide_subs: true` masque les sous-titres pendant un B-roll très chargé.
- `"auto": true` (motion) = posé par `monteur habiller` : remplacé au prochain habillage. Retire la clé pour garder l'élément.
- Les bruitages automatiques découlent de `style.sfx` (`on_zoom`, `on_broll`, `on_motion`, `on_transition`).
