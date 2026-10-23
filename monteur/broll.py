"""Illustrations automatiques : banques gratuites (Pexels, Pixabay, Wikimedia) ou IA (Higgsfield, Magnific, Flow/Veo)."""
import json
import os
import re
import urllib.parse
import urllib.request

from .common import load_json, log, save_json

UA = {"User-Agent": "MonteurOS/1.0"}


def _get(url, headers=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _download(url, dest):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        while chunk := r.read(1 << 16):
            f.write(chunk)
    return dest


def pexels(query, kind, portrait):
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return None
    orient = "portrait" if portrait else "landscape"
    q = urllib.parse.quote(query)
    if kind == "video":
        res = _get(f"https://api.pexels.com/videos/search?query={q}&per_page=5&orientation={orient}",
                   {"Authorization": key})
        for v in res.get("videos", []):
            files = sorted((f for f in v["video_files"] if f.get("height") and f["height"] <= 1920),
                           key=lambda f: -f["height"])
            if files:
                return files[0]["link"], "mp4"
    res = _get(f"https://api.pexels.com/v1/search?query={q}&per_page=5&orientation={orient}", {"Authorization": key})
    for p in res.get("photos", []):
        return p["src"]["large2x"], "jpg"
    return None


def pixabay(query, kind, portrait):
    key = os.environ.get("PIXABAY_API_KEY")
    if not key:
        return None
    q = urllib.parse.quote(query)
    if kind == "video":
        res = _get(f"https://pixabay.com/api/videos/?key={key}&q={q}&per_page=5")
        for h in res.get("hits", []):
            v = h["videos"].get("large") or h["videos"].get("medium")
            if v and v.get("url"):
                return v["url"], "mp4"
    res = _get(f"https://pixabay.com/api/?key={key}&q={q}&image_type=photo&per_page=5"
               f"&orientation={'vertical' if portrait else 'horizontal'}")
    for h in res.get("hits", []):
        return h["largeImageURL"], "jpg"
    return None


def wikimedia(query, kind, portrait):
    q = urllib.parse.urlencode({"action": "query", "format": "json", "generator": "search",
                                "gsrsearch": f"filetype:bitmap {query}", "gsrnamespace": 6, "gsrlimit": 5,
                                "prop": "imageinfo", "iiprop": "url|size", "iiurlwidth": 1920})
    from .keys import wikimedia_headers  # jeton facultatif (quota plus large), Wikimedia marche sans
    res = _get(f"https://commons.wikimedia.org/w/api.php?{q}", wikimedia_headers())
    pages = sorted(res.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
    for p in pages:
        ii = (p.get("imageinfo") or [{}])[0]
        if ii.get("width", 0) >= 800:
            return ii.get("thumburl") or ii["url"], "jpg"
    return None


STOCK = {"pexels": pexels, "pixabay": pixabay, "wikimedia": wikimedia}
GENERATIVE = {"higgsfield", "magnific", "flow", "veo"}


def fetch(ws, portrait=False):
    plan = load_json(ws.plan) or {"broll": []}
    if not plan.get("broll"):
        log("Aucune illustration prévue dans le plan (pas de transcription ou plan vide) : rien à chercher.")
    out_dir = ws.dir / "assets" / "broll"
    out_dir.mkdir(parents=True, exist_ok=True)
    pending = []
    for i, b in enumerate(plan.get("broll", [])):
        if b.get("file"):
            continue
        prov = b.get("provider", "auto")
        if prov in GENERATIVE:
            pending.append((i, prov, b))
            continue
        order = ["pexels", "pixabay", "wikimedia"] if prov == "auto" else [prov]
        kinds = [b.get("kind", "video"), "image"]
        hit = None
        for p in order:
            for k in dict.fromkeys(kinds):
                try:
                    hit = STOCK[p](b["query"], k, portrait)
                except Exception as e:  # réseau, quota…
                    log(f"  {p} échec : {e}")
                if hit:
                    break
            if hit:
                b["provider_used"] = p
                break
        if not hit:
            log(f"  Aucun visuel pour « {b['query']} » — à générer (Higgsfield/Magnific/Flow) ou à remplacer.")
            continue
        url, ext = hit
        slug = re.sub(r"\W+", "_", b["query"].lower())[:40]
        dest = out_dir / f"{i:02d}_{slug}.{ext}"
        _download(url, dest)
        b["file"], b["kind"] = str(dest), "video" if ext == "mp4" else "image"
        log(f"  B-roll {i} « {b['query']} » → {dest.name} ({b['provider_used']})")
    save_json(ws.plan, plan)
    if pending:
        log(f"{len(pending)} illustration(s) à générer par IA :")
        for i, prov, b in pending:
            log(f"  #{i} [{prov}] « {b.get('prompt') or b['query']} » {b['start']}s→{b['end']}s")
    return plan, pending
