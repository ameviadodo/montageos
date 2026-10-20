"""Métadonnées projet pour le tableau de bord : état, versions de rendu, rendus périmés, miniature."""
import time

from .common import ffmpeg, load_json, probe, save_json
from . import review

STATES = ["brut", "préparé", "rendu", "prêt à relire", "livré"]


def meta_path(ws):
    return ws.dir / "project.json"


def renders(ws):
    d = ws.dir / "renders"
    out = []
    for p in sorted(d.glob("*.mp4")) if d.exists() else []:
        ver = load_json(p.with_suffix(".verif.json"))
        out.append({"name": p.name, "path": str(p), "mtime": int(p.stat().st_mtime), "size": p.stat().st_size,
                    "quality": "draft" if p.stem.endswith("-draft") else "master",
                    "verif": ver and {"ok": ver["ok"], "warn": sum(c["status"] == "warn" for c in ver["checks"]),
                                      "error": sum(c["status"] == "error" for c in ver["checks"])}})
    return out


def info(ws):
    meta = load_json(meta_path(ws), {})
    from .common import active_style
    style = load_json(ws.style, {}).get("name") or active_style() or "default"
    rs = renders(ws)
    last = rs[-1] if rs else None
    edits = [p.stat().st_mtime for p in (ws.plan, ws.source, ws.dir / "style.json") if p.exists()]
    stale = bool(last) and max(edits or [0]) > last["mtime"] + 1
    fb = review.load(ws)["items"]
    if meta.get("status") == "livré":
        status = "livré"
    elif rs:
        status = "prêt à relire" if last["quality"] == "master" else "rendu"
    elif ws.plan.exists():
        status = "préparé"
    else:
        status = "brut"
    try:
        from .common import load_style
        fmt = load_style(style)["format"].get("aspect", "source")
        if fmt == "source":
            src = probe(last["path"] if last else ws.source)
            fmt = "9:16" if src["height"] > src["width"] else ("1:1" if src["height"] == src["width"] else "16:9")
    except Exception:
        fmt = "?"
    return {
        "title": meta.get("title") or ws.source.stem.replace("_", " ").replace("-", " "),
        "slug": ws.source.stem, "video": ws.source.name, "style": style,
        "family": meta.get("family") or style, "type": meta.get("type") or "talking-head",
        "format": load_json(ws.plan, {}).get("format") or fmt,
        "status": status, "stale": stale, "renders": rs, "last": last,
        "deliverables": sum(r["quality"] == "master" for r in rs),
        "feedback": {"total": len(fb), "open": sum(i["status"] != "appliqué" for i in fb)},
        "modified": int(max(edits or [time.time()])),
        "disk": sum(r["size"] for r in rs),
    }


def set_meta(ws, **kw):
    meta = load_json(meta_path(ws), {})
    meta.update({k: v for k, v in kw.items() if v is not None})
    return save_json(meta_path(ws), meta)


def thumbnail(ws):
    """Miniature du dernier rendu (sinon du rush), régénérée quand la source change."""
    rs = renders(ws)
    src = rs[-1]["path"] if rs else str(ws.source)
    out = ws.dir / "thumb.jpg"
    if not out.exists() or out.stat().st_mtime < (rs[-1]["mtime"] if rs else ws.source.stat().st_mtime):
        try:
            t = min(1.0, probe(src)["duration"] / 3)
            ffmpeg(["-ss", f"{t:.2f}", "-i", src, "-frames:v", "1", "-vf", "scale=480:-2", out])
        except Exception:
            return None
    return out
