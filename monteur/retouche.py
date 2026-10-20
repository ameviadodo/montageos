"""Retouches directes à un instant de la vidéo montée : couper, zoomer, retirer, bruiter.

Les temps sont ceux de la vidéo montée (= timeline de cut.mp4), c'est-à-dire ce que montre le lecteur des retours.
Chaque retouche modifie plan.json (et la coupe pour « couper ») ; un rendu draft suit pour la voir dans la vidéo.
"""
from .common import load_json, log, probe, save_json

TIMED = ("zooms", "broll", "motion")
NAMES = {"zooms": "zoom", "broll": "B-roll", "motion": "animation"}


def _plan(ws):
    plan = load_json(ws.plan)
    if plan is None:
        raise SystemExit("Pas encore de plan : lance d'abord « Préparer ».")
    return plan


def zoom(ws, t, kind="punch", dur=1.2, scale=None):
    plan = _plan(ws)
    end = min(plan.get("duration", t + dur), t + dur)
    plan.setdefault("zooms", []).append({"start": round(t, 3), "end": round(end, 3), "kind": kind,
                                         "scale": scale or (1.18 if kind == "pulse" else 1.14)})
    plan["zooms"].sort(key=lambda z: z["start"])
    save_json(ws.plan, plan)
    log(f"Zoom {kind} ajouté à {t:.2f}s")


def sfx(ws, t, name="whoosh"):
    plan = _plan(ws)
    plan.setdefault("sfx", []).append({"t": round(t, 3), "name": name})
    save_json(ws.plan, plan)
    log(f"Bruitage « {name} » ajouté à {t:.2f}s")


def remove(ws, t, what="tout", tol=0.15):
    """Retire ce qui est à l'image à l'instant t : zoom, B-roll, animation / carte, raccord, bruitage."""
    plan = _plan(ws)
    hit = lambda x: x["start"] - tol <= t <= x["end"] + tol
    removed = []
    for sec in TIMED:
        if what not in ("tout", sec):
            continue
        keep = []
        for x in plan.get(sec, []):
            (removed.append(f"{NAMES[sec]} {x.get('kind') or x.get('name') or x.get('type') or x.get('query', '')}")
             if hit(x) else keep.append(x))
        plan[sec] = keep
    if what in ("tout", "transitions"):
        tr = plan.get("transitions") or []
        plan["transitions"] = [x for x in tr if abs(x["t"] - t) > 0.4]
        removed += ["raccord"] * (len(tr) - len(plan["transitions"]))
    if what in ("tout", "sfx"):
        s0 = plan.get("sfx", [])
        plan["sfx"] = [x for x in s0 if abs(x["t"] - t) > 0.4]
        removed += ["bruitage"] * (len(s0) - len(plan["sfx"]))
    save_json(ws.plan, plan)
    log(f"Retiré à {t:.2f}s : {', '.join(removed) or 'rien (aucun élément à cet instant)'}")
    return removed


def shift_plan(plan, a, b):
    """Le passage [a, b] de la vidéo montée disparaît : tout ce qui suit recule de (b - a)."""
    d = b - a

    def mv(x):
        return x if x <= a else (a if x <= b else x - d)
    for sec in TIMED:
        out = []
        for x in plan.get(sec, []):
            s, e = mv(x["start"]), mv(x["end"])
            if e - s >= 0.15:  # un élément entièrement dans le passage coupé disparaît
                out.append({**x, "start": round(s, 3), "end": round(e, 3)})
        plan[sec] = out
    for sec in ("transitions", "sfx"):
        plan[sec] = [{**x, "t": round(mv(x["t"]), 3)} for x in (plan.get(sec) or []) if not a < x["t"] < b]
    plan["emphasis"] = []  # indices de mots : recalculés au besoin (les mots ont bougé)
    if plan.get("duration"):
        plan["duration"] = round(plan["duration"] - d, 3)
    return plan


def cut_range(ws, t, d):
    """Supprime [t, t + d] de la vidéo montée (ex. un blanc oublié, une phrase en trop)."""
    from .cut import remap_transcript, render_cut
    src_dur = probe(ws.source)["duration"]
    edl = load_json(ws.edl) or {"keep": [[0.0, src_dur]], "stats": {}}
    if not ws.cut_video.exists():
        edl["keep"] = [[0.0, src_dur]]
    a, b = t, t + d
    keep, off = [], 0.0
    for s, e in edl["keep"]:  # [a, b] (timeline montée) → retiré des segments source
        L = e - s
        ca, cb = max(0.0, a - off), min(L, b - off)
        if cb <= 0 or ca >= L or ca >= cb:
            keep.append([s, e])
        else:
            if ca > 0.02:
                keep.append([s, round(s + ca, 3)])
            if cb < L - 0.02:
                keep.append([round(s + cb, 3), e])
        off += L
    edl["keep"] = keep
    kept = round(sum(e - s for s, e in keep), 3)
    edl.setdefault("stats", {})
    if isinstance(edl["stats"], dict):
        edl["stats"]["kept_duration"] = kept
        edl["stats"]["segments"] = len(keep)
    edl.setdefault("manual_cuts", []).append({"t": round(t, 3), "d": round(d, 3)})
    save_json(ws.edl, edl)
    render_cut(ws.source, edl, ws.cut_video, ws.dir)
    tr = load_json(ws.transcript)
    if tr and tr.get("words"):
        save_json(ws.cut_transcript, remap_transcript(tr, keep, [r["i"] for r in edl.get("removed", [])]))
    plan = load_json(ws.plan)
    if plan:
        plan = shift_plan(plan, a, b)
        plan["duration"] = round(probe(ws.cut_video)["duration"], 3)
        save_json(ws.plan, plan)
    log(f"✂ Coupé {d:.2f}s à {t:.2f}s → vidéo montée : {kept:.2f}s")
