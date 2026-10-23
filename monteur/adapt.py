"""Analyse d'une vidéo source avant montage : y a-t-il une voix ? quel format, quel rythme ? → style conseillé,
format conseillé, et ce qu'il faut demander à l'utilisateur (voix off, script) avant de monter.

Résultat écrit dans <rush>.monteur/analyse.json et lu par Claude (skill monteuros, étape « Brief »).
"""
from .common import STYLES, active_style, load_json, log, probe, save_json


def speech_ratio(video, dur):
    """Part du rush où le son dépasse le bruit de fond (≈ parole ou musique)."""
    from .cut import detect_silences
    sil = detect_silences(video, -38, 0.35)
    return round(1 - sum(e - s for s, e in sil) / max(dur, 0.1), 3)


def analyse(ws, brief=""):
    from .cli import silent
    from .render import aspect_of
    from .style_clone import scene_cuts
    from .voixoff import settings as vo_settings
    info = probe(ws.source)
    dur = info["duration"]
    has_audio = info["has_audio"] and not silent(ws.source)
    ratio = speech_ratio(ws.source, dur) if has_audio else 0.0
    tr = load_json(ws.transcript) or {}
    words = len(tr.get("words", [])) if tr.get("source") != "voixoff" else 0
    try:
        cpm = round(len(scene_cuts(ws.source)) / max(dur, 1) * 60, 1)
    except Exception:
        cpm = None
    aspect = aspect_of(info["width"], info["height"])
    vertical = info["height"] > info["width"]
    vo = vo_settings(ws)
    # voix : mots transcrits si on les a, sinon proportion de son « actif » (une musique seule compte aussi : prudence)
    voice = words / max(dur, 1) * 60 > 40 if words else ratio > 0.45
    b = brief.lower()

    def want(*k):
        return any(x in b for x in k)

    if want("pub", "promo", "publicité", "annonce"):
        style = "pub"
    elif want("ugc", "témoignage", "avis client"):
        style = "ugc"
    elif want("docu", "reportage"):
        style = "documentaire"
    elif want("formation", "cours", "tuto"):
        style = "formation"
    elif want("produit", "packshot", "e-commerce"):
        style = "produit"
    elif not voice:
        style = "produit" if dur <= 45 else "documentaire"
    elif vertical or dur <= 75:
        style = "hormozi" if (cpm or 0) < 20 else "createur-kinetic"
    else:
        style = "formation" if dur > 300 else "intro-youtube"
    if not (STYLES / f"{style}.json").exists():
        style = "default"
    ask = []
    if not voice and not vo:
        ask.append({"id": "voix_off", "question": "La vidéo n'a pas de voix : as-tu un fichier de voix off (WAV/MP3) ? "
                    "Sinon, donne-moi le script (ou le sujet, je l'écris) et je génère la voix "
                    "(ElevenLabs, Inworld ou Edge gratuit).",
                    "commande": "bin/monteur voixoff RUSH --fichier voix.mp3 [--script script.txt]  |  "
                                "bin/monteur voixoff RUSH --script script.txt [--moteur elevenlabs|inworld|edge]"})
    if style in ("pub", "ugc", "produit") and not voice and not vo:
        ask.append({"id": "script", "question": "Pour une pub : quel produit, quelle promesse, quelle offre (CTA) ? "
                    "Je rédige un script de 15-30 s (accroche 3 s → bénéfice → preuve → CTA).",
                    "commande": "claude-projects/scripts-pubs-ugc/instructions.md"})
    res = {"video": ws.source.name, "duree": round(dur, 2), "largeur": info["width"], "hauteur": info["height"],
           "format_source": aspect, "voix": voice, "part_sonore": ratio, "mots_transcrits": words,
           "coupes_par_minute": cpm, "voix_off": bool(vo), "style_actif": active_style(),
           "style_conseille": style, "format_conseille": "9:16" if (vertical or style in ("pub", "ugc", "produit", "hormozi"))
           else "16:9", "a_demander": ask,
           "conseil": ("Rush parlé : prep direct, la voix est nettoyée (blancs, euh, répétitions)." if voice else
                       "Pas de voix : voix off (fichier ou script) d'abord, la vidéo n'est pas coupée, "
                       "sous-titres et habillage se calent sur la voix off.")}
    save_json(ws.dir / "analyse.json", res)
    log(f"Analyse : {'voix détectée' if voice else 'PAS de voix'} · {aspect} · {dur:.1f}s · style conseillé « {style} »"
        + (f" · à demander : {', '.join(a['id'] for a in ask)}" if ask else ""))
    return res
