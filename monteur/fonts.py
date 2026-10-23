"""Polices : la police du style choisi est VRAIMENT utilisée (sous-titres, titres, cartes animées).

- `resolve(nom)` : nom exact d'une police installée dans assets/fonts (famille, nom complet ou famille + graisse) ;
  sinon téléchargée depuis Google Fonts (TTF statique de la bonne graisse) ; sinon la plus proche installée, avec
  un avertissement — avant, libass remplaçait en silence par Arial et les cartes restaient en Montserrat.
- `style_fonts(style)` : polices du style résolues (sous-titres, titres, display, body, mono).
"""
import json
import re
import struct
import urllib.parse
import urllib.request
from pathlib import Path

from .common import ASSETS, log

FONTS = ASSETS / "fonts"
WEIGHTS = {"thin": 100, "hairline": 100, "extralight": 200, "ultralight": 200, "light": 300, "regular": 400,
           "normal": 400, "book": 400, "medium": 500, "semibold": 600, "demibold": 600, "bold": 700,
           "extrabold": 800, "ultrabold": 800, "black": 900, "heavy": 900}
WNAME = {100: "Thin", 200: "ExtraLight", 300: "Light", 400: "Regular", 500: "Medium", 600: "SemiBold", 700: "Bold",
         800: "ExtraBold", 900: "Black"}
_cache, _failed, _warned = {}, set(), set()


def _names(path):
    """Noms d'une police TTF/OTF (table « name ») : famille, sous-famille, nom complet, famille typographique."""
    try:
        data = Path(path).read_bytes()
        n = struct.unpack(">H", data[4:6])[0]
        table = next(struct.unpack(">4sIII", data[12 + 16 * i:28 + 16 * i]) for i in range(n)
                     if data[12 + 16 * i:16 + 16 * i] == b"name")
        off = table[2]
        _, count, strings = struct.unpack(">HHH", data[off:off + 6])
        out = {}
        for i in range(count):
            pid, eid, lang, nid, length, soff = struct.unpack(">HHHHHH", data[off + 6 + 12 * i:off + 18 + 12 * i])
            if nid not in (1, 2, 4, 16, 17):
                continue
            raw = data[off + strings + soff:off + strings + soff + length]
            txt = raw.decode("utf-16-be", "ignore") if pid in (0, 3) else raw.decode("latin-1", "ignore")
            if txt and (nid not in out or (pid == 3 and lang == 0x409)):
                out[nid] = txt
        return out
    except Exception:
        return {}


def installed():
    """{nom en minuscules sans espaces: (nom à donner à libass / CSS, famille, graisse, fichier)}."""
    if _cache:
        return _cache
    for f in sorted(FONTS.glob("*.[ot]tf")):
        nm = _names(f)
        fam = nm.get(16) or nm.get(1)
        sub = nm.get(17) or nm.get(2) or "Regular"
        if not fam:
            continue
        w = next((v for k, v in WEIGHTS.items() if k == re.sub(r"[\s-]", "", sub.lower()).replace("italic", "")), 400)
        full = nm.get(4) or f"{fam} {sub}"
        for name in {fam if sub.lower() in ("regular", "normal") else None, full, f"{fam} {sub}", nm.get(1)} - {None}:
            key = re.sub(r"\s+", "", name.lower())
            # le nom complet (« Montserrat Black ») prime sur la famille seule
            if key not in _cache or name == full:
                _cache[key] = (full if name != fam else fam, fam, w, f)
    return _cache


def split_weight(name):
    """« Plus Jakarta Sans ExtraBold » → (« Plus Jakarta Sans », 800, italique?)."""
    words = name.split()
    italic = bool(words) and words[-1].lower() == "italic"
    if italic:
        words = words[:-1]
    weight = None
    if words and re.sub("-", "", words[-1].lower()) in WEIGHTS:
        weight = WEIGHTS[re.sub("-", "", words[-1].lower())]
        words = words[:-1]
    if len(words) > 1 and (words[-2] + words[-1]).lower() in WEIGHTS:  # « Extra Bold »
        weight = WEIGHTS[(words[-2] + words[-1]).lower()]
        words = words[:-2]
    return " ".join(words), weight, italic


def download(family, weight=None, italic=False):
    """TTF statique depuis Google Fonts (polices libres). Renvoie le fichier, ou None (hors ligne, inconnue)."""
    key = (family.lower(), weight, italic)
    if key in _failed:
        return None
    axis = f":ital,wght@1,{weight or 400}" if italic else f":wght@{weight or 400}"
    url = "https://fonts.googleapis.com/css2?family=" + urllib.parse.quote_plus(family) + axis
    try:  # vieil agent → Google renvoie du TrueType (et non du woff2, illisible par libass)
        css = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/4.0"}),
                                     timeout=12).read().decode("utf-8")
        src = re.search(r"url\((https://[^)]+\.ttf)\)", css).group(1)
        dest = FONTS / (re.sub(r"\W+", "", family) + "-" + WNAME.get(weight or 400, "Regular")
                        + ("Italic" if italic else "") + ".ttf")
        FONTS.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(src, dest)
        _cache.clear()
        log(f"Police « {family} » {WNAME.get(weight or 400)} téléchargée (Google Fonts) → {dest.name}")
        return dest
    except Exception:
        _failed.add(key)
        return None


def _fallback(name, weight):
    low = name.lower()
    if any(k in low for k in ("mono", "code", "courier")):
        base = "Space Mono"
    elif any(k in low for k in ("serif", "fraunces", "playfair", "garamond", "georgia", "times", "lora", "merriweather")):
        base = "Instrument Serif"
    elif any(k in low for k in ("anton", "bebas", "oswald", "league gothic", "impact", "condensed")):
        base = "Anton"
    elif any(k in low for k in ("bangers", "luckiest", "comic", "marker")):
        base = "Bangers"
    else:
        w = weight or 800
        base = "Montserrat " + (WNAME[min(WNAME, key=lambda k: abs(k - w))] if w >= 600 else "SemiBold")
    got = installed().get(re.sub(r"\s+", "", base.lower()))
    return got[0] if got else base


def resolve(name, default_weight=None):
    """Nom utilisable par libass et par le CSS des cartes pour la police demandée (téléchargée au besoin)."""
    if not name:
        return None
    key = re.sub(r"\s+", "", name.lower())
    inst = installed()
    family, weight, italic = split_weight(name)
    if key in inst and (weight or not default_weight or inst[key][2] >= 600):
        return inst[key][0]
    weight = weight or default_weight  # « Plus Jakarta Sans » pour un titre : la graisse épaisse, pas la Regular
    if weight and re.sub(r"\s+", "", f"{family} {WNAME.get(weight, '')}".lower()) in inst:
        return inst[re.sub(r"\s+", "", f"{family} {WNAME[weight]}".lower())][0]
    f = download(family, weight, italic)
    if f:
        nm = _names(f)
        return nm.get(4) or nm.get(1) or family
    if key in inst:  # la graisse épaisse n'existe pas pour cette police (ex. Instrument Serif) : la police telle quelle
        return inst[key][0]
    fb = _fallback(name, weight)
    if name not in _warned:
        _warned.add(name)
        log(f"⚠️  Police « {name} » introuvable (ni installée, ni téléchargeable) → « {fb} ». "
            f"Dépose son .ttf dans assets/fonts/ pour l'avoir exactement.")
    return fb


def file_of(resolved):
    got = installed().get(re.sub(r"\s+", "", (resolved or "").lower()))
    return got[3] if got else None


def style_fonts(style):
    """Polices du style, résolues : sous-titres, titres (display), corps et mono (cartes)."""
    lib = (style.get("library") or {}).get("fonts") or {}
    sub = style["subtitles"].get("font")
    title = style["motion"].get("font") or lib.get("display") or sub
    return {"sub": resolve(sub, 800), "title": resolve(title, 800),
            "display": resolve(lib.get("display") or title, 800 if not lib.get("display") else None),
            "body": resolve(lib.get("body") or sub, None), "mono": resolve(lib.get("mono") or "Space Mono", None)}


def is_bold_face(resolved):
    got = installed().get(re.sub(r"\s+", "", (resolved or "").lower()))
    return bool(got and got[2] >= 600)


if __name__ == "__main__":  # pragma: no cover
    print(json.dumps({k: v[0] for k, v in installed().items()}, indent=1, ensure_ascii=False))
