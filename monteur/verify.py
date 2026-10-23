"""Contrôle qualité automatique d'un rendu : durée, écrans noirs, blancs oubliés, saturation, mots coupés, visuels manquants."""
import re

from .common import load_json, log, probe, run, save_json


def _status(cond_err, cond_warn=False):
    return "error" if cond_err else ("warn" if cond_warn else "ok")


def black_segments(video, min_d=0.5):
    err = run(["ffmpeg", "-hide_banner", "-nostats", "-i", video, "-an", "-vf",
               f"blackdetect=d={min_d}:pix_th=0.08", "-f", "null", "-"], capture=True).stderr
    return [(float(a), float(b)) for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", err)]


def peak_db(video):
    err = run(["ffmpeg", "-hide_banner", "-nostats", "-i", video, "-vn", "-af", "volumedetect", "-f", "null", "-"],
              capture=True).stderr
    m = re.search(r"max_volume: (-?[\d.]+) dB", err)
    return float(m.group(1)) if m else None


def cut_words(transcript, keep, tol=0.03):
    """Mots tronqués par une coupe : la frontière d'un segment gardé tombe au milieu du mot.
    Horodatage approximatif (transcription importée, p < 1) : la frontière doit tomber franchement dans le mot."""
    out = []
    for w in (transcript or {}).get("words", []):
        t = tol if w.get("p", 1) >= 1 else max(tol, 0.3 * (w["end"] - w["start"]))
        hit = next((b for s, e in keep for b in (s, e) if w["start"] + t < b < w["end"] - t), None)
        if hit is not None:
            out.append({"w": w["w"], "t": w["start"], "frontiere": hit})
    return out


def opening(video):
    """Image 0 (luminance moyenne, 0-255) et niveau du son sur les 0,3 premières secondes (dB, None si muet)."""
    err = run(["ffmpeg", "-hide_banner", "-nostats", "-i", video, "-frames:v", "1", "-vf",
               "scale=160:-2,signalstats,metadata=print", "-f", "null", "-"], capture=True).stderr
    m = re.search(r"YAVG=([\d.]+)", err)
    luma = float(m.group(1)) if m else None
    err = run(["ffmpeg", "-hide_banner", "-nostats", "-t", "0.3", "-i", video, "-vn", "-af", "volumedetect",
               "-f", "null", "-"], capture=True, check=False).stderr
    m = re.search(r"max_volume: (-?[\d.]+) dB", err)
    return luma, float(m.group(1)) if m else None


def verify(ws, video):
    from .cut import detect_silences
    info = probe(video)
    plan = load_json(ws.plan, {})
    edl = load_json(ws.edl, {})
    checks = []

    expected = plan.get("duration")
    if expected:
        gap = abs(info["duration"] - expected)
        checks.append({"id": "duree", "label": "Durée conforme au plan", "status": _status(gap > 1, gap > 0.25),
                       "detail": f"{info['duration']:.2f}s (attendu {expected:.2f}s)"})

    # jamais d'ouverture noire — l'image 0 est finie, la voix arrive tout de suite
    luma, head_db = opening(video)
    try:
        from .common import active_style, load_style
        dark = bool(load_style(load_json(ws.style, {}).get("name") or active_style()).get("look", {}).get("dark_style"))
    except Exception:
        dark = False
    first = next(iter((ws.base_transcript() or {}).get("words", [])), None)
    late = first and first["start"] > 0.6
    checks.append({"id": "ouverture", "label": "Ouverture : ni noir ni silence",
                   "status": _status(luma is not None and luma < 18 and not dark,
                                     (luma is not None and luma < 18) or (info["has_audio"] and (head_db is None or head_db < -45)
                                                                          and bool(late))),
                   "detail": f"image 0 : luminance {luma:.0f}/255" + (" (style sombre)" if dark else "") +
                             (f", premier mot à {first['start']:.2f}s" if first else "") if luma is not None else "illisible"})

    blacks = [b for b in black_segments(video) if b[0] > 0.2]
    checks.append({"id": "noir", "label": "Aucun écran noir", "status": _status(bool(blacks)),
                   "detail": ", ".join(f"{a:.1f}–{b:.1f}s" for a, b in blacks) or "rien à signaler"})

    if info["has_audio"]:
        sil = [s for s in detect_silences(video, -40, 1.2) if s[0] > 0.3 and s[1] < info["duration"] - 0.3]
        checks.append({"id": "blancs", "label": "Pas de blanc oublié (> 1,2 s)", "status": _status(False, bool(sil)),
                       "detail": ", ".join(f"{a:.1f}–{b:.1f}s" for a, b in sil) or "rien à signaler"})
        pk = peak_db(video)
        checks.append({"id": "saturation", "label": "Pas de saturation audio",
                       "status": _status(pk is not None and pk > -0.1, pk is not None and pk > -1),
                       "detail": f"crête {pk} dB" if pk is not None else "inconnue"})

    if edl.get("keep") and ws.cut_video.exists():  # coupe désactivée : l'ancien edl.json ne décrit plus la vidéo
        cw = cut_words(load_json(ws.transcript), edl["keep"])
        checks.append({"id": "mots_coupes", "label": "Aucun mot coupé", "status": _status(False, bool(cw)),
                       "detail": ", ".join(f"« {c['w']} » à {c['t']:.1f}s" for c in cw[:8]) or "rien à signaler"})

    missing = [i for i, b in enumerate(plan.get("broll", [])) if not b.get("file")]
    checks.append({"id": "visuels", "label": "Toutes les illustrations sont placées", "status": _status(False, bool(missing)),
                   "detail": f"à trouver/générer : {missing}" if missing else "rien à signaler"})

    res = {"video": str(video), "ok": all(c["status"] != "error" for c in checks), "checks": checks}
    save_json(video.with_suffix(".verif.json"), res)
    for c in checks:
        icon = {"ok": "✅", "warn": "⚠️ ", "error": "❌"}[c["status"]]
        log(f"{icon} {c['label']} — {c['detail']}")
    return res
