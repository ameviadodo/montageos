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


def _norm(text):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", str(text).lower()) if unicodedata.category(c) != "Mn")


def search(query=None, category=None):
    """Cartes dont l'id, le nom, la catégorie, l'usage, les tags ou les variables contiennent tous les mots cherchés."""
    words = _norm(query or "").split()
    out = []
    for c in catalog():
        if category and _norm(c.get("category")) != _norm(category):
            continue
        hay = _norm(" ".join([c["id"], c.get("label", ""), c.get("category", ""), c.get("usage", ""),
                              " ".join(c.get("tags", [])), " ".join(f"{k} {v}" for k, v in c.get("vars", {}).items())]))
        if all(w in hay for w in words):
            out.append(c)
    return out


def _fill(text, values):
    return re.sub(r"\{\{(\w+)(?:\|([^}]*))?\}\}", lambda m: str(values.get(m.group(1), m.group(2) or "")), text)


def theme(style):
    """Habillage de la carte aux couleurs et polices du style choisi (accent, encre, display / body / mono)."""
    if not style:
        return {}
    from .fonts import WEIGHTS, download, installed, split_weight, style_fonts
    sf = style_fonts(style)
    out = {"accent": style["motion"].get("accent"), "ink": style["motion"].get("color")}
    faces, fams = [], {}
    for role in ("body", "display", "mono"):
        fam = split_weight(sf[role] or "")[0]
        if not fam:
            continue
        fams[role] = fam
        have = {v[2] for v in installed().values() if v[1] == fam}
        if role == "body" and have and not have & {700, 800, 900}:  # cartes en gras : graisses lourdes au besoin
            for w in (800, 900):
                download(fam, w)
    seen = set()
    for name, fam, w, f in installed().values():
        if fam in fams.values() and f.name not in seen:
            seen.add(f.name)
            ital = "italic" in f.stem.lower()
            faces.append(f'@font-face{{font-family:"{fam}";font-weight:{w};'
                         f'{"font-style:italic;" if ital else ""}src:url(fonts/{f.name})}}')
    out["FONT_FACES"] = "\n".join(faces)
    if fams.get("body"):
        out["FONT_BODY"] = f'"{fams["body"]}"'
    if fams.get("display") and fams["display"] != fams.get("body"):
        out["FONT_SERIF"] = f'"{fams["display"]}"'  # titres éditoriaux (.serif) dans la police display du style
    if fams.get("mono"):
        out["FONT_MONO"] = f'"{fams["mono"]}"'
    return {k: v for k, v in out.items() if v}


def build(card_id, values=None, W=1920, H=1080, duration=None, style=None):
    """HTML Hyperframes complet : variables {{clé|défaut}} remplacées, unité --u = 1 % du petit côté.
    `style` : la carte prend l'accent, l'encre et les polices du style (les valeurs passées restent prioritaires)."""
    card = load(card_id)
    th = theme(style)
    v = {**card.get("vars", {}), **{k: x for k, x in th.items() if k in ("accent", "ink")}, **(values or {})}
    v["DUR"] = float(duration or v.get("duration") or card.get("duration", 4))
    esc = {k: str(x).replace("<", "&lt;") for k, x in v.items()}
    raw = {k: x for k, x in th.items() if k.startswith("FONT_")}  # CSS de confiance (pas d'échappement)
    base = (CARDS / "_base.html").read_text(encoding="utf-8")
    page = base.replace("{{CSS}}", _fill(card["css"], esc)).replace("{{BODY}}", _fill(card["body"], esc))
    page = page.replace("{{JS}}", card["js"]).replace("{{VARS_JSON}}", json.dumps(v, ensure_ascii=False))
    return _fill(page, {"W": W, "H": H, "U": round(min(W, H) / 100, 2), "DUR": v["DUR"], **esc, **raw}), card, v["DUR"]


def render(ws, card_id, start, values=None, W=1920, H=1080, duration=None, name=None, layout=None, style=None):
    """Rend la carte (MOV alpha si overlay, MP4 si plein cadre) aux couleurs du style et l'ajoute au plan à `start`."""
    from . import hyperframes
    html, card, dur = build(card_id, values, W, H, duration, style)
    name = name or f"{card_id.replace('.', '-')}-{int(start * 10):04d}"
    proj = hyperframes.new(ws, name, "portrait" if H > W else "landscape")
    (proj / "index.html").write_text(html, encoding="utf-8")
    fonts = proj / "fonts"
    fonts.mkdir(exist_ok=True)
    for f in (ASSETS / "fonts").glob("*.[ot]tf"):
        shutil.copy(f, fonts / f.name)
    hyperframes.vendor_cdn(proj)
    full = card.get("mode") == "full"
    out = hyperframes.render(ws, name, start, start + dur, alpha=not full,
                             layout=layout or ("full" if full else "overlay"))
    log(f"Carte {card_id} ({card['label']}) posée à {start}s")
    return out
