"""Charte graphique : extrait palette + captures d'images, vidéos ou URL YouTube → thème Studio + style vidéo."""
import colorsys
import re
import subprocess
from pathlib import Path

from .common import ROOT, ffmpeg, load_json, log, probe, save_json

THEMES = ROOT / "ui" / "themes"


def palette(src, n=10):
    """Palette dominante via palettegen (aucune dépendance Python)."""
    tmp = THEMES / f".pal_{Path(src).stem}.png"
    ffmpeg(["-i", src, "-vf", f"fps=1/2,scale=320:-2,palettegen=max_colors={n}:reserve_transparent=0:stats_mode=full",
            "-frames:v", "1", tmp])
    data = subprocess.run(["ffmpeg", "-v", "error", "-i", str(tmp), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                          capture_output=True, check=True).stdout
    tmp.unlink(missing_ok=True)
    cols = {tuple(data[i:i + 3]) for i in range(0, len(data) - 2, 3)}
    return sorted(cols)


def to_hex(c):
    return "#{:02X}{:02X}{:02X}".format(*c)


def lum(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def sat(c):
    return colorsys.rgb_to_hsv(*(x / 255 for x in c))[1] * (max(c) / 255)


def dedupe(cols, dist=28):
    out = []
    for c in cols:
        if all(sum((a - b) ** 2 for a, b in zip(c, o)) ** 0.5 > dist for o in out):
            out.append(c)
    return out


def build_theme(cols, name, shots):
    cols = dedupe(cols)
    by_l = sorted(cols, key=lum)
    vivid = sorted((c for c in cols if sat(c) > 0.35), key=sat, reverse=True) or [by_l[-1]]
    bg, surface, text = by_l[0], by_l[1] if len(by_l) > 1 else by_l[0], by_l[-1]
    return {
        "name": name,
        "colors": {"bg": to_hex(bg), "surface": to_hex(surface), "surface2": to_hex(by_l[min(2, len(by_l) - 1)]),
                   "text": to_hex(text), "muted": to_hex(by_l[len(by_l) // 2]),
                   "accent": to_hex(vivid[0]), "accent2": to_hex(vivid[1] if len(vivid) > 1 else vivid[0])},
        "fonts": {"display": "Montserrat", "body": "Inter"},
        "radius": 14,
        "palette": [to_hex(c) for c in cols],
        "screenshots": shots,
        "_todo_claude": "Regarde les captures : corrige couleurs/rôles, nomme les polices (display/body), "
                        "le rayon des coins, et décris la mise en page dans 'layout_notes'.",
    }


def extract(sources, name):
    THEMES.mkdir(parents=True, exist_ok=True)
    shots_dir = THEMES / name
    shots_dir.mkdir(exist_ok=True)
    cols, shots = set(), []
    for src in sources:
        if re.match(r"https?://", src):
            from .style_clone import download
            src = str(download(src, shots_dir / "downloads"))
        p = Path(src)
        if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            shots.append(str(p.resolve()))
        else:
            d = probe(p)["duration"]
            for k in range(8):
                out = shots_dir / f"{p.stem}_{k}.png"
                ffmpeg(["-ss", f"{d * (k + 0.5) / 8:.2f}", "-i", p, "-frames:v", "1", "-vf", "scale=1280:-2", out])
                shots.append(str(out))
        cols |= set(palette(src))
    theme = build_theme(sorted(cols), name, shots)
    old = load_json(THEMES / f"{name}.json")
    if old:  # garder les corrections déjà faites par Claude
        theme = {**theme, **{k: old[k] for k in ("colors", "fonts", "radius", "layout_notes") if k in old}}
    save_json(THEMES / f"{name}.json", theme)
    log(f"Charte « {name} » → ui/themes/{name}.json ({len(shots)} captures à vérifier)")
    return theme
