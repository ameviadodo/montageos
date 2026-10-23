"""Habillage automatique Hyperframes : cartes animées posées d'après ce qui est dit.

- un chiffre (« 30 % », « 125 000 abonnés », « 49 € ») → carte stat.courbe (compteur + courbe) ;
- le mot le plus fort de la première moitié → mot.punch / titre.barre (si le style les utilise) ;
- le nom de l'orateur (--nom) → médaillon au début.
Les cartes viennent de la bibliothèque du style (library.cards) quand c'est possible. Sans Hyperframes (Node ≥ 22),
ou si un rendu échoue, on contourne : animation texte native (callout) à la place, le montage n'est jamais bloqué.
Les éléments posés ici portent "auto": true dans plan.json et sont remplacés au prochain habillage.
"""
import json
import re
import shutil

from .common import load_json, log, run, save_json
from .cut import norm
from .plan import STOP

MULT = {"k": "K", "mille": "K", "million": "M", "millions": "M", "milliard": "Md", "milliards": "Md"}
UNIT = {"%": "%", "pourcent": "%", "pourcents": "%", "€": "€", "euro": "€", "euros": "€", "deuros": "€",
        "$": "$", "dollar": "$", "dollars": "$"}


def hyperframes_ok():
    if not shutil.which("npx") or not shutil.which("node"):
        return False
    try:
        major = int(run(["node", "-p", "process.versions.node.split('.')[0]"], capture=True).stdout.strip())
    except Exception:
        return False
    return major >= 22


def _phrase(words, i, span=12):
    a = max(0, i - span // 2)
    return " ".join(w["w"] for w in words[a:a + span])


def numbers(words):
    """[(t, valeurs de carte stat.courbe, texte court)] pour chaque chiffre parlé."""
    out = []
    for i, w in enumerate(words):
        m = re.match(r"^[+\-]?(\d{1,3}(?:[ \u202f.]\d{3})+|\d+(?:[.,]\d+)?)\s*(%|€|\$|[kK])?", w["w"])
        if not m or w["w"][m.end():].strip(".,!?;:»\u202f"):  # « 3h », « 2e » : pas un chiffre à animer
            continue
        raw = re.sub(r"[ \u202f.](?=\d{3}\b)", "", m.group(1))
        j = i + 1
        while not m.group(2) and j < len(words) and re.fullmatch(r"\d{3}[.,!?;:]?", words[j]["w"]):
            raw, j = raw + words[j]["w"][:3], j + 1  # « 125 000 » transcrit en deux mots
        if i and re.fullmatch(r"\d{1,3}", words[i - 1]["w"]) and re.fullmatch(r"\d{3}\W*", w["w"]):
            continue  # le « 000 » de « 125 000 » : déjà compté
        tail = (m.group(2) or "").lower()
        mult, cur = MULT.get(tail, ""), UNIT.get(tail, "")
        while j < len(words) and j <= i + 3:  # « 30 pour cent », « 3 millions d'euros »
            t = norm(words[j]["w"]).replace("'", "") or words[j]["w"].strip(".,!?;:")
            if t == "pour" and j + 1 < len(words) and norm(words[j + 1]["w"]) == "cent":
                cur, j = "%", j + 2
            elif t in MULT and not mult:
                mult, j = MULT[t], j + 1
            elif t in UNIT and not cur:
                cur, j = UNIT[t], j + 1
            else:
                break
        suffix = mult + (("\u202f" if mult else "") + cur if cur else "")
        value = raw.replace(",", ".")
        if not suffix and (len(raw) == 4 and raw.startswith(("19", "20"))):  # une année : pas un compteur
            continue
        if not suffix and float(value) < 3:  # « 1 », « 2 » : trop banal pour une carte
            continue
        unit = next((x["w"].strip(".,!?;:") for x in words[j:j + 2]
                     if norm(x["w"]) not in STOP and len(norm(x["w"])) > 2 and not re.search(r"\d", x["w"])), "")
        label = " ".join(x["w"].strip(".,!?;:") for x in words[max(0, i - 3):i] if norm(x["w"]) not in STOP)[:28]
        out.append((w["start"], {"value": value, "suffix": suffix, "unit": unit[:18], "label": label or "En chiffres",
                                 "caption": _phrase(words, i)[:90]}, f"{value}{suffix}"))
    return out


NAME_INTRO = [("moi", "c'est"), ("je", "m'appelle"), ("je", "suis"), ("ici",), ("c'est",)]
NOT_NAMES = {"un", "une", "le", "la", "les", "pas", "très", "trop", "ici", "là", "content", "contente", "heureux",
             "heureuse", "ravi", "ravie", "en", "de", "du", "vraiment", "sûr", "sûre", "désolé", "désolée"}
LIST_MARKERS = {"premièrement": 1, "deuxièmement": 2, "troisièmement": 3, "quatrièmement": 4, "cinquièmement": 5,
                "d'abord": 1, "ensuite": 2, "puis": 2, "enfin": 9, "finalement": 9, "primo": 1, "secundo": 2,
                "tertio": 3}
MAX_D = {"medaillon.nom": 2.8, "mot.punch": 1.6, "titre.barre": 2.6}  # un nom ou un mot ne reste pas 4 s
PREFER = {"name": ["medaillon.nom"], "list": ["surlignage.liste", "ecran.rail", "classement.top", "programme.chapitres"],
          "number": ["stat.courbe"], "price": ["prix.promo"], "punch": ["mot.punch", "titre.barre"]}


def _clean(w):
    return w.strip(".,!?;:«»\"'…")


def detect_name(words):
    """« Bienvenue, moi c'est Soprador » / « je m'appelle Léa Martin » → (t, « Soprador »)."""
    toks = [norm(w["w"]).replace("'", "'") for w in words[:40]]
    raw = [w["w"].lower().replace("’", "'") for w in words[:40]]
    for i in range(len(raw)):
        for pat in NAME_INTRO:
            if tuple(_clean(x) for x in raw[i:i + len(pat)]) == pat:
                j = i + len(pat)
                name = []
                while j < len(words) and len(name) < 3:
                    w = _clean(words[j]["w"])
                    if not w or not w[0].isupper() or norm(w) in NOT_NAMES:
                        break
                    name.append(w)
                    if words[j]["w"].rstrip()[-1:] in ".,!?":
                        break
                    j += 1
                if name and (len(pat) > 1 or i == 0):
                    return words[i]["start"], " ".join(name)
    return None


def detect_list(words):
    """Énumération parlée → (début, fin, [éléments], accroche) ; None s'il y a moins de 2 éléments."""
    marks = [(i, LIST_MARKERS[_clean(w["w"].lower().replace("’", "'"))]) for i, w in enumerate(words)
             if _clean(w["w"].lower().replace("’", "'")) in LIST_MARKERS]
    if len(marks) < 2:
        return None
    first = marks[0][0]
    marks = [m for m in marks if words[m[0]]["start"] - words[first]["start"] < 40][:5]
    items = []
    for k, (i, _) in enumerate(marks):
        stop = marks[k + 1][0] if k + 1 < len(marks) else len(words)
        it = []
        for w in words[i + 1:stop]:
            it.append(_clean(w["w"]))
            if w["w"].rstrip()[-1:] in ".!?" or len(it) >= 5:
                break
        if it:
            items.append(" ".join(x for x in it if x)[:38])
    if len(items) < 2:
        return None
    lead = [w for w in words[:first] if w["start"] > words[first]["start"] - 6]
    kicker = " ".join(_clean(w["w"]) for w in lead[-5:]) if lead else "Les étapes"
    last = marks[-1][0]
    end = next((w["end"] for w in words[last:] if w["w"].rstrip()[-1:] in ".!?"), words[min(last + 5, len(words) - 1)]["end"])
    return words[first]["start"], end, items, kicker[:40]


def _pick(kind, pref, known):
    """Carte du style pour ce type de moment (sinon la carte par défaut de la bibliothèque)."""
    return next((c for c in pref if c in PREFER[kind]), None) or next((c for c in PREFER[kind] if c in known), None)


def plan_cards(words, plan, style, nom=None, role=None, max_cards=4, gap=6.0):
    """Choix des cartes et de leurs instants (sans rien rendre)."""
    from .cards import catalog
    known = {c["id"]: c for c in catalog()}
    pref = [c for c in (style.get("library", {}).get("cards") or []) if c in known]
    dur = plan.get("duration") or (words[-1]["end"] if words else 0)
    picks = []
    found = None if nom else detect_name(words)
    if nom or found:
        who = nom or found[1]
        t_name = found[0] if found else 2.4
        picks.append((5, t_name, _pick("name", pref, known), {"name": who.upper(), "role": role or ""}, who))
    lst = detect_list(words)
    if lst:
        cid = _pick("list", pref, known)
        picks.append((4, lst[0], cid, {"items": ";".join(lst[2]), "kicker": lst[3], "title": lst[3]},
                      " / ".join(lst[2]), lst[1] - lst[0] + 1.2))
    nums = numbers(words)
    used = set()
    # « 29 € au lieu de 49 » (+ « 40 % ») → carte prix promo
    for k, (t, v, txt) in enumerate(nums):
        nxt = next((n for n in nums[k + 1:k + 3] if n[0] - t < 4), None)
        between = " ".join(w["w"].lower() for w in words if t <= w["start"] <= (nxt[0] if nxt else t))
        if nxt and "€" in v["suffix"] + nxt[1]["suffix"] and ("au lieu" in between or "au lieu" in v["caption"].lower()):
            pct = next((n for n in nums if abs(n[0] - t) < 6 and n[1]["suffix"] == "%"), None)
            cur = "€"
            picks.append((3, t, _pick("price", pref, known), {"price": f"{v['value']} {cur}", "old": f"{nxt[1]['value']} {cur}",
                                                "badge": f"-{pct[1]['value']} %" if pct else "PROMO",
                                                "caption": "Offre de lancement"}, f"{v['value']} € au lieu de {nxt[1]['value']} €"))
            used |= {k, nums.index(nxt)} | ({nums.index(pct)} if pct else set())
    for k, (t, vals, txt) in enumerate(nums):
        if k not in used:
            picks.append((2, t, _pick("number", pref, known), vals, txt))
    punch = next((c for c in ("mot.punch", "titre.barre") if c in pref), None)
    if punch and words:
        emph = [i for i in plan.get("emphasis", []) if i < len(words) and words[i]["start"] < dur / 2]
        for i in emph[:2]:
            w = words[i]["w"].strip(".,!?;:«»\"'")
            picks.append((1, words[i]["start"], punch, {"word": w.upper() if punch == "mot.punch" else w}, w))
    busy = [(m["start"], m["end"]) for m in plan.get("motion", []) if not m.get("auto") and m.get("type") in
            ("title", "cta", "hyperframes", "chapter")]
    # seuls les B-roll trouvés occupent l'image (un B-roll sans fichier n'apparaîtra pas)
    busy += [(b["start"], b["end"]) for b in plan.get("broll", []) if b.get("file")
             and b.get("layout", "full") in ("full", "fullscreen")]
    title_end = max([m["end"] for m in plan.get("motion", []) if m.get("type") == "title"] or [0])
    chosen = []
    for prio, t, cid, vals, txt, *want in sorted(picks, key=lambda p: (-p[0], p[1])):
        if not cid:
            continue
        if cid == "medaillon.nom" and t < title_end + 0.15:  # le nom arrive juste après le titre d'accroche
            t = title_end + 0.2
        t = round(max(0.2, t - 0.15), 2)
        for c in chosen:  # une carte déjà posée laisse la place si elle a eu le temps d'être lue (≥ 1,5 s)
            if c["start"] + 1.5 <= t < c["end"] + gap / 6:
                old_iv = (c["start"] - gap / 6, c["end"] + gap / 6)
                c["end"] = round(t - gap / 6, 2)
                c["duration"] = round(c["end"] - c["start"], 2)
                busy[busy.index(old_iv)] = (c["start"] - gap / 6, c["end"] + gap / 6)
        if any(s <= t < e for s, e in busy):  # pas de chevauchement (titre, CTA, autre carte, B-roll plein cadre)
            continue
        room = min([s for s, _ in busy if s > t] + [dur - 0.3]) - t  # carte raccourcie pour tenir dans le créneau
        base_d = min(float(known[cid].get("duration", 4)), MAX_D.get(cid, 99))
        d = min(max(base_d, want[0] if want else 0), room)
        if d < min(2.5, base_d):
            continue
        chosen.append({"start": t, "end": round(t + d, 2), "card": cid, "vars": vals, "text": txt, "duration": round(d, 2)})
        busy.append((t - gap / 6, round(t + d, 2) + gap / 6))  # un souffle entre deux cartes
        if len(chosen) >= max_cards:
            break
    return sorted(chosen, key=lambda c: c["start"])


def dress(ws, style, nom=None, role=None, max_cards=4, use_hyperframes=True, dry=False):
    from .cards import render as card_render
    from .common import probe
    from .render import out_size
    plan = load_json(ws.plan)
    if plan is None:
        raise SystemExit("Pas encore de plan : lance d'abord « prep ».")
    words = (ws.base_transcript() or {}).get("words", [])
    if not words and not nom:
        log("Habillage : pas de transcription (ni voix off) → rien à illustrer automatiquement.")
        return []
    # on repart propre : les éléments du dernier habillage automatique disparaissent
    plan["motion"] = [m for m in plan.get("motion", []) if not m.get("auto")]
    save_json(ws.plan, plan)
    chosen = plan_cards(words, plan, style, nom, role, max_cards)
    if dry or not chosen:
        for c in chosen:
            log(f"  {c['start']:6.2f}s  {c['card']:<14} {c['text']}")
        if not chosen:
            log("Habillage : aucun moment adapté (chiffre, mot fort, nom) — pose des cartes à la main (monteur carte).")
        return chosen
    hf = use_hyperframes and hyperframes_ok()
    if use_hyperframes and not hf:
        log("Hyperframes indisponible (Node ≥ 22 + npx : bash setup.sh --motion) → animations texte à la place.")
    W, H = out_size(probe(ws.base_video()), style["format"])
    layout = None
    if style["format"].get("layout") == "split":
        H, layout = int(H * style["format"].get("split", 0.42)) // 2 * 2, "panel"
    done = []
    import hashlib
    from .cards import theme
    th = theme(style)
    for c in chosen:
        ok = False
        if hf:
            try:
                # même carte, mêmes textes, même style → même fichier : pas de nouveau rendu à chaque préparation
                sig = hashlib.sha1(json.dumps([c["card"], c["vars"], W, H, c.get("duration"), th],
                                              sort_keys=True, default=str).encode()).hexdigest()[:8]
                name = f"auto-{c['card'].replace('.', '-')}-{sig}"
                ready = next((p for p in (ws.dir / "assets" / "motion").glob(name + ".*") if p.suffix in (".mov", ".mp4")),
                             None) if (ws.dir / "assets" / "motion").exists() else None
                if ready:
                    from .cards import load as card_load
                    full = card_load(c["card"]).get("mode") == "full"
                    plan = load_json(ws.plan)
                    plan["motion"].append({"type": "hyperframes", "name": name, "file": str(ready), "start": c["start"],
                                           "end": c["end"], "layout": layout or ("full" if full else "overlay"),
                                           "auto": True, "card": c["card"]})
                    save_json(ws.plan, plan)
                else:
                    card_render(ws, c["card"], c["start"], c["vars"], W, H, c.get("duration"), name=name, layout=layout,
                                style=style)
                    plan = load_json(ws.plan)
                    for m in plan["motion"]:
                        if m.get("name") == name:
                            m["auto"], m["card"] = True, c["card"]
                    save_json(ws.plan, plan)
                ok = True
            except (Exception, SystemExit) as e:
                log(f"⚠️  Carte {c['card']} à {c['start']}s : rendu Hyperframes impossible ({str(e).splitlines()[0][:120]})"
                    " → animation texte.")
        if not ok:  # repli natif (ASS), adapté au type de moment : jamais de montage bloqué
            plan = load_json(ws.plan)
            if c["card"] == "medaillon.nom":
                role = c["vars"].get("role")
                plan["motion"].append({"start": c["start"], "end": c["end"], "type": "lower_third", "auto": True,
                                       "text": f"{c['text']} — {role}" if role else c["text"]})
            elif "items" in c["vars"]:  # liste : un callout par élément, au fil de l'énumération
                items = c["vars"]["items"].split(";")
                step = (c["end"] - c["start"]) / max(1, len(items))
                for k, it in enumerate(items):
                    plan["motion"].append({"start": round(c["start"] + k * step, 2),
                                           "end": round(c["start"] + (k + 1) * step - 0.1, 2), "type": "callout",
                                           "text": f"{k + 1}. {it}".upper(), "auto": True})
            else:
                plan["motion"].append({"start": c["start"], "end": c["end"], "type": "callout", "auto": True,
                                       "text": c["text"].upper()})
            save_json(ws.plan, plan)
        done.append({**c, "hyperframes": ok})
        log(f"  ✓ {c['start']:6.2f}s {c['card']:<16} {'Hyperframes' if ok else 'texte'} — {c['text']}")
    log(f"Habillage : {len(done)} carte(s) posée(s), dont {sum(d['hyperframes'] for d in done)} Hyperframes.")
    return done
