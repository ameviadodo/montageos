"""Utilitaires partagés : exécution ffmpeg, sondes, JSON, chemins."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
STYLES = ROOT / "styles"


def log(msg):
    print(f"[monteur] {msg}", file=sys.stderr, flush=True)


WINDOWS = os.name == "nt"


def run(cmd, capture=False, check=True, cwd=None):
    cmd = [str(c) for c in cmd]
    if WINDOWS:  # npx, npm… sont des .cmd : CreateProcess exige le chemin complet
        cmd[0] = shutil.which(cmd[0]) or cmd[0]
    if os.environ.get("MONTEUR_DEBUG"):
        log("$ " + " ".join(cmd))
    res = subprocess.run(cmd, capture_output=capture, text=True, encoding="utf-8", errors="replace", cwd=cwd)
    if check and res.returncode != 0:
        err = (res.stderr or "")[-3000:] if capture else ""
        raise RuntimeError(f"Commande échouée ({res.returncode}): {cmd[0]}\n{err}")
    return res


def ffmpeg_progress(args, duration, label, cwd=None, step=5):
    """ffmpeg long (rendu, coupe) : affiche « label 35 % » toutes les `step` % pour le Studio et le terminal."""
    cmd = ["ffmpeg", "-hide_banner", "-y", "-loglevel", "error", "-nostats", "-progress", "pipe:1", *[str(a) for a in args]]
    if WINDOWS:
        cmd[0] = shutil.which("ffmpeg") or "ffmpeg"
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                         errors="replace", cwd=cwd)
    last = -step
    for line in p.stdout:
        if line.startswith("out_time_us=") and duration:
            try:
                pct = min(99, int(int(line.split("=")[1]) / 1e6 / duration * 100))
            except ValueError:
                continue
            if pct >= last + step:
                last = pct
                log(f"{label} {pct} %")
    err = p.stderr.read()
    if p.wait() != 0:
        raise RuntimeError(f"Commande échouée ({p.returncode}): ffmpeg\n{err[-3000:]}")
    log(f"{label} 100 %")


def ffmpeg(args, capture=False, cwd=None):
    return run(["ffmpeg", "-hide_banner", "-y", "-loglevel", "error", *args], capture=capture, cwd=cwd)


def probe(path):
    out = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format",
               "-show_streams", path], capture=True).stdout
    data = json.loads(out)
    v = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in data["streams"] if s["codec_type"] == "audio"), None)
    info = {"duration": float(data["format"].get("duration", 0)), "has_audio": a is not None}
    if v:
        num, den = (v.get("avg_frame_rate") or "30/1").split("/")
        fps = float(num) / float(den) if float(den) else 30.0
        rot = 0
        for sd in v.get("side_data_list", []) or []:
            rot = int(sd.get("rotation", 0) or 0)
        w, h = int(v["width"]), int(v["height"])
        if abs(rot) in (90, 270):
            w, h = h, w
        info.update(width=w, height=h, fps=round(fps, 3) if fps < 121 else 30.0)
    return info


def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def save_json(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def deep_merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_style(name_or_path=None):
    """Charge styles/default.json puis fusionne le style demandé (nom ou chemin)."""
    style = load_json(STYLES / "default.json", {})
    if not name_or_path:
        return style
    p = Path(name_or_path)
    if not p.exists():
        p = STYLES / f"{name_or_path}.json"
    if not p.exists():
        raise FileNotFoundError(f"Style introuvable : {name_or_path}")
    return deep_merge(style, load_json(p))


class Workspace:
    """Dossier de travail d'un projet : <video>.monteur/"""

    def __init__(self, source, workdir=None):
        self.source = Path(source).resolve()
        self.dir = Path(workdir) if workdir else self.source.with_suffix("").with_name(self.source.stem + ".monteur")
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "assets").mkdir(exist_ok=True)

    def __getattr__(self, name):
        files = {
            "transcript": "transcript.json", "edl": "edl.json", "cut_video": "cut.mp4",
            "cut_transcript": "transcript_cut.json", "plan": "plan.json",
            "subs": "subtitles.ass", "motion_ass": "motion.ass", "final": "final.mp4",
            "style": "style.json",
        }
        if name in files:
            return self.dir / files[name]
        raise AttributeError(name)

    def base_video(self):
        return self.cut_video if self.cut_video.exists() else self.source

    def base_transcript(self):
        return load_json(self.cut_transcript) if self.cut_video.exists() else load_json(self.transcript)


def which(binary):
    return shutil.which(binary) is not None


def utf8_console():
    """Console Windows (cp1252) : évite UnicodeEncodeError sur les ✅ / « » des messages."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
