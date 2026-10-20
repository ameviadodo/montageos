"""Plan de montage automatique (zooms, B-roll, animations, emphases) — éditable par Claude."""
import re

from .common import log, probe, save_json
from .cut import norm, phrases

STOP = set("""
a à au aux avec ce ces cet cette c ça dans de des du elle elles en est et être eu il ils je j l la le les leur lui
ma mais me même mes moi mon ne nos notre nous on ou où par pas pour qu que qui sa se ses son sur ta te tes toi ton
tu un une vos votre vous y d n s t m alors donc bon voilà ok oui non très plus moins tout tous toute toutes faire fait
avoir ai as avons avez ont suis es sommes êtes sont était c'est cest j'ai jai comme aussi bien quand quoi comment
pourquoi parce juste vraiment chose choses truc genre là ici après avant encore déjà peut veux veut vais va
the a an and or but if of to in on at by for with from is are was were be been being it its this that these those i
you he she we they me my your our their so just really very like what when where why how can will would do does did
have has had not no yes get got gonna want thing things there here then than also about into out up down
""".split())


def keywords(text_words, k=3):
    cands = []
    for i, w in enumerate(text_words):
        t = norm(w)
        if (len(t) < 4 and not t.isdigit()) or t in STOP:
            continue
        score = len(t) + (3 if i and w[:1].isupper() else 0) + (4 if re.search(r"\d", w) else 0)
        cands.append((score, w.strip(".,!?;:«»\"'")))
    seen, out = set(), []
    for _, w in sorted(cands, reverse=True):
        if norm(w) not in seen:
            seen.add(norm(w))
            out.append(w)
    return out[:k]


def emphasis_words(words, ratio=0.12):
    scored = []
    for i, w in enumerate(words):
        t = norm(w["w"])
        if not t or t in STOP:
            continue
        s = len(t) + (6 if re.search(r"\d", w["w"]) else 0) + (3 if w["w"].endswith("!") else 0)
        scored.append((s, i))
    n = max(1, int(len(words) * ratio))
    return sorted(i for _, i in sorted(scored, reverse=True)[:n])


def auto_plan(ws, style, transcript):
    video = ws.base_video()
    dur = probe(video)["duration"]
    words = transcript["words"] if transcript else []
    ph = phrases(words) if words else []
    plan = {"version": 1, "duration": round(dur, 3), "zooms": [], "broll": [], "motion": [], "sfx": [],
            "emphasis": emphasis_words(words) if words else [], "notes": ""}

    zc = style["zoom"]
    if zc.get("enabled") and ph:
        last, pi = -99.0, 0
        for p in ph:
            t0 = words[p[0]]["start"]
            if t0 - last < zc["every_s"] or t0 > dur - 1:
                continue
            kind = zc["pattern"][pi % len(zc["pattern"])]
            pi += 1
            if kind == "pulse":
                mid = words[p[min(len(p) - 1, 1)]]["start"]
                z = {"start": round(mid - 0.08, 3), "end": round(mid + 0.42, 3), "kind": "pulse",
                     "scale": zc["pulse_scale"]}
            else:
                end = min(dur, t0 + zc["hold_s"] * (1.6 if kind == "ease" else 1))
                z = {"start": round(t0, 3), "end": round(end, 3), "kind": kind, "scale": zc["scale"]}
            plan["zooms"].append(z)
            last = t0
    elif zc.get("enabled"):
        # Sans transcription : zooms sur les points de coupe (masquent les jump cuts), sinon à intervalle régulier
        from .common import load_json
        keep = (load_json(ws.edl) or {}).get("keep") or []
        cuts, acc = [], 0.0
        for s0, e0 in keep[:-1]:
            acc += e0 - s0
            cuts.append(acc)
        t, starts = 1.0, []
        while t < dur - 1:
            near = [c for c in cuts if t - zc["every_s"] / 2 <= c < t + zc["every_s"] / 2]
            starts.append(round(near[0] if near else t, 3))
            t = starts[-1] + zc["every_s"]
        for k, t0 in enumerate(starts):
            kind = zc["pattern"][k % len(zc["pattern"])]
            if kind == "pulse":
                plan["zooms"].append({"start": t0, "end": round(t0 + 0.5, 3), "kind": "pulse", "scale": zc["pulse_scale"]})
            else:
                plan["zooms"].append({"start": t0, "end": round(min(dur, t0 + zc["hold_s"]), 3), "kind": kind,
                                      "scale": zc["scale"]})

    bc = style["broll"]
    if bc.get("enabled") and ph and dur > 6:
        n = max(1, int(round(bc["per_minute"] * dur / 60)))
        step = (dur - 3) / n
        used = set()
        for k in range(n):
            target = 3 + step * (k + 0.5)
            best = min((p for p in ph if words[p[0]]["start"] >= 2.5 and id(p) not in used),
                       key=lambda p: abs(words[p[0]]["start"] - target), default=None)
            if not best:
                break
            used.add(id(best))
            txt = [words[i]["w"] for i in best]
            s = words[best[0]]["start"]
            plan["broll"].append({
                "start": round(s, 3), "end": round(min(dur, s + bc["duration"]), 3),
                "query": " ".join(keywords(txt)), "context": " ".join(txt),
                "provider": bc["provider"], "kind": "video", "layout": bc["layout"], "file": None})

    mc = style["motion"]
    if mc.get("enabled") and mc.get("hook_title") and ph:
        first = [words[i]["w"] for i in ph[0]][:5]
        plan["motion"].append({"start": 0.15, "end": min(dur, 2.3), "type": "title",
                               "text": " ".join(first).strip(" ,.").upper()})
    cta = mc.get("cta")
    if mc.get("enabled") and cta and dur > 5:
        plan["motion"].append({"start": round(dur - cta.get("duration", 2.5), 3), "end": round(dur, 3),
                               "type": "cta", "text": cta.get("text", "ABONNE-TOI"),
                               "subtext": cta.get("subtext", ""), "sfx": "ding"})
    plan["mode"] = style.get("mode", style.get("name"))
    save_json(ws.plan, plan)
    log(f"Plan : {len(plan['zooms'])} zooms, {len(plan['broll'])} B-roll, {len(plan['motion'])} animations → {ws.plan}")
    return plan
