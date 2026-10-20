"""Copie de style : analyse de vidéos de référence (YouTube ou MP4) → profil + style.json."""
import re
import statistics
from pathlib import Path

from .common import STYLES, ffmpeg, load_json, log, probe, run, save_json, deep_merge
from .render import aspect_of


def download(url, dest_dir):
    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        import yt_dlp
    except ImportError:
        raise SystemExit("yt-dlp absent. Lance : bash setup.sh")
    opts = {"format": "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080]/b",
            "merge_output_format": "mp4", "outtmpl": str(dest_dir / "%(id)s.%(ext)s"),
            "quiet": True, "noplaylist": True}
    with yt_dlp.YoutubeDL(opts) as y:
        meta = y.extract_info(url, download=True)
    path = dest_dir / f"{meta['id']}.mp4"
    save_json(dest_dir / f"{meta['id']}.meta.json",
              {k: meta.get(k) for k in ("id", "title", "uploader", "duration", "webpage_url", "chapters")})
    return path


def scene_cuts(video, thr=0.3):
    res = run(["ffmpeg", "-hide_banner", "-nostats", "-i", video, "-an", "-vf",
               f"scale=320:-2,select='gt(scene,{thr})',showinfo", "-f", "null", "-"], capture=True)
    return [float(m.group(1)) for m in re.finditer(r"pts_time:([\d.]+)", res.stderr)]


def loudness(video):
    res = run(["ffmpeg", "-hide_banner", "-nostats", "-i", video, "-vn", "-af", "ebur128", "-f", "null", "-"],
              capture=True)
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", res.stderr)
    return float(m[-1]) if m else None


def silence_ratio(video, dur):
    from .cut import detect_silences
    sil = detect_silences(video, -35, 0.3)
    return round(sum(e - s for s, e in sil) / max(dur, 1), 3)


def color_stats(video):
    res = run(["ffmpeg", "-hide_banner", "-nostats", "-i", video, "-an", "-vf",
               "fps=1,scale=160:-2,signalstats,metadata=print", "-f", "null", "-"], capture=True)
    y = [float(v) for v in re.findall(r"YAVG=([\d.]+)", res.stderr)]
    sat = [float(v) for v in re.findall(r"SATAVG=([\d.]+)", res.stderr)]
    return {"luma_avg": round(statistics.mean(y), 1) if y else None,
            "saturation_avg": round(statistics.mean(sat), 1) if sat else None}


def sheets(video, out_dir, dur):
    """Planches-contact pour l'analyse visuelle par Claude (sous-titres, typographie, zooms, B-roll)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    every = max(1.0, dur / 30)
    ffmpeg(["-i", video, "-vf", f"fps=1/{every:.2f},scale=360:-2,tile=6x5:padding=4:color=black",
            "-frames:v", "1", out_dir / "contact_sheet.png"])
    # rafale 4 i/s sur 6 s au premier tiers : révèle zooms, pops de texte, transitions
    ffmpeg(["-ss", f"{min(dur * 0.3, max(0, dur - 7)):.2f}", "-t", "6", "-i", video, "-vf",
            "fps=4,scale=320:-2,tile=6x4:padding=4:color=black", "-frames:v", "1", out_dir / "burst.png"])
    # zoom pleine résolution sur 3 images pour lire la typo des sous-titres
    for k, frac in enumerate((0.2, 0.5, 0.8)):
        ffmpeg(["-ss", f"{dur * frac:.2f}", "-i", video, "-frames:v", "1", "-vf", "scale=1080:-2",
                out_dir / f"frame_{k + 1}.png"])
    return sorted(str(p) for p in out_dir.glob("*.png"))


def colors(video):
    """Couleurs vives dominantes (accents des titres / sous-titres), via la palette de charte.py."""
    from .charte import dedupe, lum, palette, sat, to_hex
    try:
        cols = dedupe(palette(video, 16))
    except Exception:
        return []
    vivid = sorted((c for c in cols if sat(c) > 0.35), key=sat, reverse=True)
    # lisibles en sous-titres sur l'image (jaune, vert, cyan, rose…) d'abord ; bleu nuit / rouge sombre ensuite
    return [to_hex(c) for c in sorted(vivid, key=lambda c: lum(c) < 110)[:4]]


def pick_cards(cpm, aspect):
    """Cartes de la bibliothèque adaptées au rythme mesuré (à affiner par Claude après lecture des planches)."""
    if cpm >= 30:
        return ["mot.punch", "titre.barre", "surlignage.liste", "stat.courbe"]
    if cpm >= 12:
        return ["titre.barre", "ecran.rail", "medaillon.nom", "stat.courbe"]
    return ["section.marqueurs", "citation.surligne", "medaillon.nom", "doc.lieu-date"] if aspect in ("16:9", "21:9") \
        else ["section.stage", "citation.surligne", "medaillon.nom"]


def analyze(video, out_dir, transcribe_words=False):
    info = probe(video)
    dur = info["duration"]
    cuts = scene_cuts(video)
    shots = [b - a for a, b in zip([0] + cuts, cuts + [dur]) if b - a > 0.05]
    prof = {
        "source": str(video), "duration": round(dur, 2),
        "width": info.get("width"), "height": info.get("height"), "fps": info.get("fps"),
        "aspect": aspect_of(info["width"], info["height"]),
        "cuts_per_minute": round(len(cuts) / dur * 60, 1) if dur else 0,
        "avg_shot_s": round(statistics.mean(shots), 2) if shots else dur,
        "median_shot_s": round(statistics.median(shots), 2) if shots else dur,
        "silence_ratio": silence_ratio(video, dur) if info["has_audio"] else None,
        "lufs": loudness(video) if info["has_audio"] else None,
        **color_stats(video),
    }
    if transcribe_words and info["has_audio"]:
        from .transcribe import transcribe
        t = transcribe(video, out_dir / "transcript.json")
        prof["words_per_minute"] = round(len(t["words"]) / dur * 60) if dur else None
    prof["sheets"] = sheets(video, out_dir, dur)
    prof["colors"] = colors(video)
    meta = load_json(Path(video).with_suffix(".meta.json"), {})
    prof["title"], prof["url"] = meta.get("title") or Path(video).stem, meta.get("webpage_url")
    save_json(out_dir / "profile.json", prof)
    return prof


def profile_to_style(profiles, name):
    """Transforme les mesures en réglages ; Claude complète ensuite le visuel (police, couleurs…)."""
    avg = lambda k: statistics.mean([p[k] for p in profiles if p.get(k) is not None] or [0])
    shot, cpm, sil = avg("avg_shot_s"), avg("cuts_per_minute"), avg("silence_ratio")
    aspects = [p["aspect"] for p in profiles]
    aspect = max(set(aspects), key=aspects.count)
    accents = [c for p in profiles for c in p.get("colors", [])]
    accent = accents[0] if accents else "#FFD400"
    second = accents[1] if len(accents) > 1 else "#00E676"
    titles = ", ".join(f"« {p.get('title')} »" for p in profiles[:3])
    style = {
        "name": name,
        "description": f"Style copié de {titles} : {cpm:.0f} coupes/min, plans de {shot:.1f} s en moyenne.",
        "library": {"etat": "Copié", "palette": list(dict.fromkeys(["#000000", "#FFFFFF", *accents[:4]])),
                    "fonts": {"display": "Montserrat Black", "body": "Montserrat ExtraBold"},
                    "cards": pick_cards(cpm, aspect), "ratios": sorted(set(aspects)),
                    "sources": [p.get("url") or p["source"] for p in profiles]},
        "reference": {"profiles": [p["source"] for p in profiles], "cuts_per_minute": round(cpm, 1),
                      "avg_shot_s": round(shot, 2), "silence_ratio": round(sil, 3)},
        "format": {"aspect": aspect},
        "cut": {"min_silence": 0.25 if sil < 0.05 else 0.4 if sil < 0.12 else 0.7,
                "padding": 0.05 if sil < 0.05 else 0.1,
                "transition": "mix" if cpm >= 30 else "zoomcut" if cpm >= 15 else "hard"},
        "subtitles": {"highlight": accent, "emphasis": second, "uppercase": cpm >= 15,
                      "max_words": 2 if cpm >= 30 else 3 if cpm >= 12 else 5},
        "motion": {"accent": accent},
        "zoom": {"every_s": round(min(12, max(2, shot * 1.1)), 1),
                 "pattern": ["punch", "pulse"] if shot < 3 else ["punch", "pulse", "ease"] if shot < 6 else ["ease"]},
        "broll": {"per_minute": round(min(10, max(1, cpm / 3)), 1),
                  "duration": round(min(4, max(1.2, shot * 0.8)), 1)},
        "audio": {"lufs": round(avg("lufs"), 1) if avg("lufs") else -14},
        "_todo_claude": "Regarde contact_sheet.png / burst.png / frame_*.png et affine subtitles "
                        "(font, size, couleurs, uppercase, max_words, position), cut.transition (flash, whip, glitch…), "
                        "motion, sfx et library.cards.",
    }
    return style


def slug(name):
    import unicodedata
    s = unicodedata.normalize("NFD", name.lower())
    s = re.sub(r"[^a-z0-9]+", "-", "".join(c for c in s if unicodedata.category(c) != "Mn")).strip("-")
    return s or "style-copie"


def clone(sources, name, transcribe_words=False, activate=False, refine=True):
    """Télécharge/analyse les références → styles/<nom>.json, rangé dans la bibliothèque (état « Copié »)."""
    name = slug(name)
    base = STYLES / "refs" / name
    profiles = []
    for src in sources:
        if re.match(r"https?://", src):
            log(f"Téléchargement {src} …")
            src = download(src, base / "downloads")
        src = Path(src).resolve()
        log(f"Analyse {src.name} …")
        profiles.append(analyze(src, base / src.stem, transcribe_words))
    style = profile_to_style(profiles, name)
    existing = load_json(STYLES / f"{name}.json")
    if existing:  # ne pas écraser ce que Claude a déjà affiné
        style = deep_merge(style, {k: v for k, v in existing.items() if k in ("subtitles", "motion", "sfx")})
        old = existing.get("library", {})
        style["library"].update({k: old[k] for k in ("cards", "fonts", "etat") if k in old})
    save_json(STYLES / f"{name}.json", style)
    if refine:
        try:
            from .style_refine import refine as do_refine
            style, _ = do_refine(name)
        except ImportError:
            log("Affinage automatique indisponible (OpenCV absent : bash setup.sh) — fais-le avec Claude.")
    if activate:
        from .common import set_setting
        set_setting(style=name)
        log(f"Style « {name} » activé pour les nouveaux projets.")
    log(f"Style « {name} » → styles/{name}.json ; planches à analyser :")
    for p in profiles:
        for s in p["sheets"]:
            log(f"  {s}")
    return style, profiles
