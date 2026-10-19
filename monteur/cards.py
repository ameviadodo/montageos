"""Bibliothèque de cartes animées (Hyperframes) : écrans, médaillons, surlignages, marqueurs de section, stats, titres."""
import json
import re
import shutil

from .common import ASSETS, ROOT, log

CARDS = ROOT / "library" / "cards"
META = re.compile(r"<!--meta\s*(\{.*?\})\s*-->", re.S)


def _part(src, tag):
    m = re.search(rf"<{tag}>(.*?)</{tag}>", src, re.S)
    return m.group(1).strip() if m else ""


def load(card_id):
    path = CARDS / f"{card_id}.card.html"
    if not path.exists():
        raise SystemExit(f"Carte inconnue : {card_id} (voir `monteur cartes`)")
    src = path.read_text(encoding="utf-8")
    meta = json.loads(META.search(src).group(1))
    return {"id": card_id, **meta, "css": _part(src, "style"), "body": _part(src, "template"), "js": _part(src, "script")}


def catalog():
    return [{k: v for k, v in load(p.name[:-len(".card.html")]).items() if k not in ("css", "body", "js")}
            for p in sorted(CARDS.glob("*.card.html"))]


def _fill(text, values):
    return re.sub(r"\{\{(\w+)(?:\|([^}]*))?\}\}", lambda m: str(values.get(m.group(1), m.group(2) or "")), text)


def build(card_id, values=None, W=1920, H=1080, duration=None):
    """HTML Hyperframes complet : variables {{clé|défaut}} remplacées, unité --u = 1 % du petit côté."""
    card = load(card_id)
    v = {**card.get("vars", {}), **(values or {})}
    v["DUR"] = float(duration or v.get("duration") or card.get("duration", 4))
    esc = {k: str(x).replace("<", "&lt;") for k, x in v.items()}
    base = (CARDS / "_base.html").read_text(encoding="utf-8")
    page = base.replace("{{CSS}}", _fill(card["css"], esc)).replace("{{BODY}}", _fill(card["body"], esc))
    page = page.replace("{{JS}}", card["js"]).replace("{{VARS_JSON}}", json.dumps(v, ensure_ascii=False))
    return _fill(page, {"W": W, "H": H, "U": round(min(W, H) / 100, 2), "DUR": v["DUR"], **esc}), card, v["DUR"]


def render(ws, card_id, start, values=None, W=1920, H=1080, duration=None, name=None, layout=None):
    """Rend la carte (MOV alpha si overlay, MP4 si plein cadre) et l'ajoute au plan à `start`."""
    from . import hyperframes
    html, card, dur = build(card_id, values, W, H, duration)
    name = name or f"{card_id.replace('.', '-')}-{int(start * 10):04d}"
    proj = hyperframes.new(ws, name, "portrait" if H > W else "landscape")
    (proj / "index.html").write_text(html, encoding="utf-8")
    fonts = proj / "fonts"
    fonts.mkdir(exist_ok=True)
    for f in (ASSETS / "fonts").glob("*.ttf"):
        shutil.copy(f, fonts / f.name)
    hyperframes.vendor_cdn(proj)
    full = card.get("mode") == "full"
    out = hyperframes.render(ws, name, start, start + dur, alpha=not full,
                             layout=layout or ("full" if full else "overlay"))
    log(f"Carte {card_id} ({card['label']}) posée à {start}s")
    return out
