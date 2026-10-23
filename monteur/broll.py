"""Illustrations automatiques : banques gratuites (Pexels, Pixabay, Wikimedia) ou IA (Higgsfield, Magnific, Flow/Veo)."""
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path

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
    """Candidats [(url, ext)] — plusieurs, pour pouvoir écarter ceux qui montrent une personne."""
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return []
    orient = "portrait" if portrait else "landscape"
    q = urllib.parse.quote(query)
    if kind == "video":
        res = _get(f"https://api.pexels.com/videos/search?query={q}&per_page=8&orientation={orient}",
                   {"Authorization": key})
        out = []
        for v in res.get("videos", []):
            files = sorted((f for f in v["video_files"] if f.get("height") and f["height"] <= 1920),
                           key=lambda f: -f["height"])
            if files:
                out.append((files[0]["link"], "mp4"))
        return out
    res = _get(f"https://api.pexels.com/v1/search?query={q}&per_page=8&orientation={orient}", {"Authorization": key})
    return [(p["src"]["large2x"], "jpg") for p in res.get("photos", [])]


def pixabay(query, kind, portrait):
    key = os.environ.get("PIXABAY_API_KEY")
    if not key:
        return []
    q = urllib.parse.quote(query)
    if kind == "video":
        res = _get(f"https://pixabay.com/api/videos/?key={key}&q={q}&per_page=8")
        out = []
        for h in res.get("hits", []):
            v = h["videos"].get("large") or h["videos"].get("medium")
            if v and v.get("url"):
                out.append((v["url"], "mp4"))
        return out
    res = _get(f"https://pixabay.com/api/?key={key}&q={q}&image_type=photo&per_page=8"
               f"&orientation={'vertical' if portrait else 'horizontal'}")
    return [(h["largeImageURL"], "jpg") for h in res.get("hits", [])]


def wikimedia(query, kind, portrait):
    q = urllib.parse.urlencode({"action": "query", "format": "json", "generator": "search",
                                "gsrsearch": f"filetype:bitmap {query}", "gsrnamespace": 6, "gsrlimit": 8,
                                "prop": "imageinfo", "iiprop": "url|size", "iiurlwidth": 1920})
    from .keys import wikimedia_headers  # jeton facultatif (quota plus large), Wikimedia marche sans
    res = _get(f"https://commons.wikimedia.org/w/api.php?{q}", wikimedia_headers())
    pages = sorted(res.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
    out = []
    for p in pages:
        ii = (p.get("imageinfo") or [{}])[0]
        if ii.get("width", 0) >= 800:
            out.append((ii.get("thumburl") or ii["url"], "jpg"))
    return out


STOCK = {"pexels": pexels, "pixabay": pixabay, "wikimedia": wikimedia}
GENERATIVE = {"higgsfield", "magnific", "flow", "veo"}


def shows_person(path, min_area=0.004):
    """Vrai si l'image (ou 3 images de la vidéo) montre un visage : on n'incruste jamais une AUTRE personne
    par-dessus l'orateur (photos de banque, portraits Wikimedia). OpenCV absent → rien n'est écarté."""
    from . import faces
    if not faces.available():
        return False
    import subprocess
    import cv2
    import numpy as np
    frames = []
    if str(path).lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
        img = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)  # chemins accentués (Windows)
        if img is not None:
            frames.append(img)
    else:
        for frac in (0.15, 0.5, 0.85):
            raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(frac * 3), "-i", str(path), "-frames:v", "1",
                                  "-vf", "scale=640:-2", "-f", "image2pipe", "-vcodec", "png", "-"],
                                 capture_output=True).stdout
            if raw:
                img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
                if img is not None:
                    frames.append(img)
    for img in frames:
        if max(img.shape[:2]) > 960:
            k = 960 / max(img.shape[:2])
            img = cv2.resize(img, (int(img.shape[1] * k), int(img.shape[0] * k)))
        area = img.shape[0] * img.shape[1]
        if any(w * h / area >= min_area for x, y, w, h, _ in faces.detect(img)):
            return True
    return False


def fetch(ws, portrait=False):
    plan = load_json(ws.plan) or {"broll": []}
    if not plan.get("broll"):
        log("Aucune illustration prévue dans le plan (pas de transcription ou plan vide) : rien à chercher.")
    out_dir = ws.dir / "assets" / "broll"
    out_dir.mkdir(parents=True, exist_ok=True)
    pending = []
    for i, b in enumerate(plan.get("broll", [])):
        if b.get("file") and b.get("provider_used") in STOCK and not b.get("allow_people") \
                and not b.get("sans_personne") and Path(b["file"]).exists() and shows_person(b["file"]):
            log(f"  B-roll {i} « {b['query']} » retiré : une autre personne à l'image → nouveau visuel")
            Path(b["file"]).unlink(missing_ok=True)
            b["file"] = None
        if b.get("file"):
            b.setdefault("sans_personne", b.get("provider_used") in STOCK)
            continue
        prov = b.get("provider", "auto")
        if prov in GENERATIVE:
            pending.append((i, prov, b))
            continue
        order = ["pexels", "pixabay", "wikimedia"] if prov == "auto" else [prov]
        kinds = [b.get("kind", "video"), "image"]
        slug = re.sub(r"\W+", "_", b["query"].lower())[:40]
        hit, refused = None, 0
        for p in order:
            for k in dict.fromkeys(kinds):
                try:
                    cands = STOCK[p](b["query"], k, portrait)
                except Exception as e:  # réseau, quota…
                    log(f"  {p} échec : {e}")
                    cands = []
                for url, ext in cands[:6]:
                    dest = out_dir / f"{i:02d}_{slug}.{ext}"
                    try:
                        _download(url, dest)
                    except Exception as e:
                        log(f"  {p} téléchargement échoué : {e}")
                        continue
                    if not b.get("allow_people") and shows_person(dest):
                        refused += 1
                        dest.unlink(missing_ok=True)
                        continue
                    hit = (dest, ext, p)
                    break
                if hit:
                    break
            if hit:
                break
        if refused:
            log(f"  « {b['query']} » : {refused} visuel(s) écarté(s) — une autre personne à l'image")
        if not hit:
            log(f"  Aucun visuel pour « {b['query']} » — à générer (Higgsfield/Magnific/Flow) ou à remplacer.")
            continue
        dest, ext, b["provider_used"] = hit
        b["file"], b["kind"], b["sans_personne"] = str(dest), "video" if ext == "mp4" else "image", True
        log(f"  B-roll {i} « {b['query']} » → {dest.name} ({b['provider_used']})")
    save_json(ws.plan, plan)
    if pending:
        log(f"{len(pending)} illustration(s) à générer par IA :")
        for i, prov, b in pending:
            log(f"  #{i} [{prov}] « {b.get('prompt') or b['query']} » {b['start']}s→{b['end']}s")
    return plan, pending
