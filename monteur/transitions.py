"""Types de cut entre les plans gardés : cut sec, zoom cut, flash, passage au noir, whip, glitch, fondu, mix.

Les points de coupe viennent de edl.json (fin de chaque segment gardé, sur la timeline de cut.mp4).
plan.json["transitions"] = [{"t": 3.42, "kind": "flash"}, …] — généré par le plan, modifiable à la main.
"""
from .common import load_json

KINDS = {
    "hard": "Cut sec (jump cut)",
    "zoomcut": "Zoom cut : un plan sur deux recadré plus serré",
    "flash": "Flash blanc",
    "dip": "Passage au noir",
    "whip": "Whip : filé rapide + whoosh",
    "glitch": "Glitch RGB",
    "fondu": "Fondu rapide (images mêlées)",
    "mix": "Mix dynamique : alterne zoom cut, whip, flash, glitch",
}
MIX = ["zoomcut", "whip", "zoomcut", "flash", "zoomcut", "glitch"]
SFX = {"whip": "whoosh", "glitch": "glitch", "flash": "camera"}


def cut_points(ws):
    """Instants des coupes dans la vidéo coupée (vide si le rush n'a pas été coupé)."""
    if not ws.cut_video.exists():
        return []
    keep = (load_json(ws.edl) or {}).get("keep") or []
    pts, acc = [], 0.0
    for s, e in keep[:-1]:
        acc += e - s
        pts.append(round(acc, 3))
    return pts


def phrase_points(ws, pause=0.35):
    """Débuts de phrase (après une pause) sur la timeline montée : points de raccord quand il y a peu de coupes."""
    words = (ws.base_transcript() or {}).get("words") or []
    return [round(w["start"] - 0.02, 3) for i, w in enumerate(words)
            if i and (w["start"] - words[i - 1]["end"] >= pause or words[i - 1]["w"].rstrip()[-1:] in ".!?")]


def auto_transitions(ws, style, dur=None):
    """Transitions déduites du style : cut.transition, cut.transition_every (1 = chaque coupe), cut.transition_gap."""
    c = style.get("cut", {})
    kind = c.get("transition", "hard")
    if kind == "hard" or kind not in KINDS:
        return []
    every = max(1, int(c.get("transition_every", 1)))
    gap = float(c.get("transition_gap", 1.2))
    out, last = [], -99.0
    pts = cut_points(ws)
    if dur and len(pts) < dur / 8:  # trop peu de coupes (vidéo déjà coupée, voix off…) : on marque aussi les phrases
        pts = sorted(set(pts) | {p for p in phrase_points(ws) if all(abs(p - q) > 0.4 for q in pts)})
    for i, t in enumerate(pts):
        if i % every or t - last < gap or t < 0.5 or (dur and t > dur - 0.3):
            continue
        out.append({"t": t, "kind": MIX[len(out) % len(MIX)] if kind == "mix" else kind})
        last = t
    return out


def _tri(t, amp, half):
    return f"{amp:.3f}*max(0,1-abs(t-{t:.3f})/{half:.3f})"


def zooms(trans, dur, scale=1.12):
    """Zooms ajoutés au zoompan : plan serré après un zoom cut (un sur deux), pointe brève pour le whip."""
    out, punch = [], False
    times = [x["t"] for x in trans] + [dur]
    for k, x in enumerate(trans):
        if x["kind"] == "zoomcut":
            punch = not punch
            if punch:
                out.append({"start": x["t"], "end": min(dur, times[k + 1], x["t"] + 6), "kind": "punch",
                            "scale": x.get("scale", scale)})
        elif x["kind"] == "whip":
            out.append({"start": x["t"] - 0.12, "end": x["t"] + 0.12, "kind": "pulse", "scale": 1.28})
    return out


def filters(trans, width=1080):
    """Filtres vidéo sans état (sur la timeline finale) : éclat / noir via eq, glitch via rgbashift, filé via flou
    horizontal. Le fondu (images mêlées) demande un tampon d'images : voir fondu_graph()."""
    bright = [_tri(x["t"], 0.55, 0.07) for x in trans if x["kind"] == "flash"]
    bright += [_tri(x["t"], -0.95, 0.16) for x in trans if x["kind"] == "dip"]
    out = []
    if bright:
        out.append(f"eq=brightness='{'+'.join(bright)}':eval=frame")
    win = lambda x, a, b: f"between(t,{x['t'] - a:.3f},{x['t'] + b:.3f})"
    g = [x for x in trans if x["kind"] == "glitch"]
    if g:
        en = "+".join(win(x, 0.04, 0.12) for x in g)
        out.append(f"rgbashift=rh=-14:bh=14:gv=4:enable='{en}'")
        out.append(f"rgbashift=rh=8:bv=-6:enable='{'+'.join(win(x, -0.04, 0.08) for x in g)}'")
    # whip : filé horizontal. Pas de tmix ici : activé par « enable », son tampon démarre vide (vert en YUV)
    # et chaque whip affichait un flash vert au lieu du filé.
    w = [x for x in trans if x["kind"] == "whip"]
    if w:
        out.append(f"avgblur=sizeX={max(8, int(width * 0.045))}:sizeY=1:enable='{'+'.join(win(x, 0.08, 0.08) for x in w)}'")
    return out


def fondu_graph(src, dst, trans):
    """Fondu (images mêlées) : tmix tourne en continu sur une branche, superposée seulement pendant le raccord."""
    sel = [x for x in trans if x["kind"] == "fondu"]
    if not sel:
        return None
    en = "+".join(f"between(t,{x['t'] - 0.14:.3f},{x['t'] + 0.14:.3f})" for x in sel)
    return f"[{src}]split[fd_a][fd_b];[fd_b]tmix=frames=7[fd_m];[fd_a][fd_m]overlay=0:0:enable='{en}'[{dst}]"


def sfx_events(trans, cfg=None):
    names = {**SFX, **((cfg or {}).get("on_transition") or {})}
    return [{"t": x["t"] - (0.12 if names.get(x["kind"]) in ("whoosh", "swoosh") else 0.02),
             "name": x.get("sfx", names.get(x["kind"]))} for x in trans if x.get("sfx", names.get(x["kind"]))]
