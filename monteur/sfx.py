"""Bruitages : synthèse locale (numpy) + fichiers perso / Freesound, placés AVEC DISCERNEMENT.

Placement (auto_events) : chaque événement visuel du plan (raccord, B-roll, carte, titre, CTA, zoom) propose un son
avec une priorité ; on garde les plus utiles en respectant un écart minimal (`sfx.min_gap`) et une densité maximale
(`sfx.max_per_minute`). Les bruitages posés à la main (plan.sfx) passent toujours.
Volume : MESURÉ par rapport à la voix (`sfx.under_db` dB sous le niveau médian de la parole, −3 dB de plus s'il tombe
sur un mot) — avec un gain fixe, sur une prise de téléphone calme, les bruitages sortaient 7 à 10 dB AU-DESSUS de la voix.
"""
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

from .common import ASSETS, log

SFX_DIR = ASSETS / "sfx"
SYNTH_VERSION = 3          # à incrémenter quand la synthèse change : les .wav générés sont refaits
SR = 48000
NAMES = ["whoosh", "swoosh", "pop", "click", "ding", "impact", "riser", "glitch", "camera"]


# ------------------------------------------------------------------ synthèse ---

def _noise_sweep(np, dur, f0, f1, width, shape=2.0, seed=1, rise=False):
    """Souffle filtré dont la bande passe de f0 à f1 (et revient) : un vrai « whoosh », pas un chuintement plat."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    noise = rng.standard_normal(n + 2048)
    hop, win = 256, 1024
    w = np.hanning(win)
    out = np.zeros(n + 2048)
    freqs = np.fft.rfftfreq(win, 1 / SR)
    for i, start in enumerate(range(0, n, hop)):
        x = (start / max(1, n))
        if rise:                                           # montée continue jusqu'au bout (riser)
            bell, fc = x ** shape, f0 * (f1 / f0) ** x
        else:
            bell = np.sin(np.pi * x) ** shape              # montée puis retombée
            fc = f0 + (f1 - f0) * np.sin(np.pi * x)        # le filtre « passe » devant l'auditeur
        mask = np.exp(-0.5 * ((freqs - fc) / (width * fc)) ** 2) * bell
        seg = np.fft.irfft(np.fft.rfft(noise[start:start + win] * w) * mask, win)
        out[start:start + win] += seg * w
    return out[:n]


def _synth(name):
    import numpy as np
    t = lambda d: np.arange(int(d * SR)) / SR
    if name == "whoosh":
        y = _noise_sweep(np, 0.6, 500, 2600, 0.35)
    elif name == "swoosh":
        y = _noise_sweep(np, 0.32, 1200, 4800, 0.3, 1.5, seed=2)
    elif name == "pop":
        x = t(0.11)
        y = np.sin(2 * np.pi * (300 * x + 2600 * (1 - np.exp(-40 * x)) / 40)) * np.exp(-38 * x)
        y *= np.minimum(1, x / 0.003)                         # pas de clic à l'attaque
    elif name == "click":
        x = t(0.035)
        y = np.sin(2 * np.pi * 2200 * x) * np.exp(-170 * x)
    elif name == "ding":
        x = t(1.1)
        y = (0.6 * np.sin(2 * np.pi * 1318.5 * x) + 0.25 * np.sin(2 * np.pi * 2637 * x)
             + 0.12 * np.sin(2 * np.pi * 3955.5 * x)) * np.exp(-4.2 * x) * np.minimum(1, x / 0.004)
    elif name == "impact":
        x = t(1.0)
        boom = np.sin(2 * np.pi * (45 * x + 70 * (1 - np.exp(-9 * x)) / 9)) * np.exp(-4 * x)
        y = boom + 0.25 * _noise_sweep(np, 1.0, 300, 900, 0.6, 4, seed=3) * np.exp(-12 * x)
    elif name == "riser":
        x = t(1.2)
        y = (0.6 * _noise_sweep(np, 1.2, 300, 6000, 0.25, 1.4, seed=4, rise=True)
             + 0.3 * np.sin(2 * np.pi * (180 * x + 380 * x ** 2)) * (x / 1.2) ** 2)
        y *= np.minimum(1, (1.2 - x) / 0.05)
    elif name == "glitch":
        x = t(0.24)
        rng = np.random.default_rng(5)
        steps = np.repeat(rng.uniform(-1, 1, int(0.24 / 0.012) + 1), int(0.012 * SR))[:len(x)]
        y = steps * np.sign(np.sin(2 * np.pi * 90 * x)) * np.exp(-7 * x) * 0.7
    elif name == "camera":
        x = t(0.28)
        rng = np.random.default_rng(6)
        n = rng.standard_normal(len(x))
        y = n * (np.exp(-120 * x) + 0.7 * np.exp(-120 * np.abs(x - 0.11)) * (x >= 0.11))
        y = np.convolve(y, np.ones(6) / 6, "same")           # plus mat qu'un bruit blanc
    else:
        return None
    y = y / (np.max(np.abs(y)) or 1) * 0.89
    return np.stack([y, y], 1)


def _write_wav(path, y):
    import wave
    import numpy as np
    data = (np.clip(y, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


def ensure_library():
    """Synthétise les bruitages manquants ou d'une ancienne version (les fichiers perso ne sont jamais touchés)."""
    SFX_DIR.mkdir(parents=True, exist_ok=True)
    manifest = SFX_DIR / ".synth.json"
    made = {}
    try:
        made = json.loads(manifest.read_text(encoding="utf-8"))
    except Exception:
        pass
    changed = False
    for name in NAMES:
        out = SFX_DIR / f"{name}.wav"
        old_synth = out.exists() and (name in made or not manifest.exists())  # v1 n'avait pas de manifeste
        if out.exists() and not (old_synth and made.get(name) != SYNTH_VERSION):
            continue
        try:
            y = _synth(name)
        except ImportError:  # numpy absent : on garde l'existant
            continue
        if y is None:
            continue
        _write_wav(out, y)
        made[name] = SYNTH_VERSION
        changed = True
    if changed:
        manifest.write_text(json.dumps(made), encoding="utf-8")
    return sorted(p.stem for p in SFX_DIR.iterdir() if p.suffix in (".wav", ".mp3", ".ogg", ".m4a"))


def resolve(name):
    """Fichier perso (assets/sfx/<name>.mp3/ogg/m4a, ou chemin) prioritaire sur la synthèse."""
    if not name:
        return None
    p = Path(name)
    if p.suffix and p.exists():
        return p
    ensure_library()
    for ext in (".mp3", ".ogg", ".m4a", ".wav"):
        f = SFX_DIR / f"{name}{ext}"
        if f.exists():
            return f
    return None


def freesound(query, name=None):
    """Télécharge un preview HQ depuis Freesound (FREESOUND_API_KEY requis)."""
    key = os.environ.get("FREESOUND_API_KEY")
    if not key:
        raise SystemExit("FREESOUND_API_KEY manquant (gratuit sur https://freesound.org/apiv2/apply)")
    q = urllib.parse.urlencode({"query": query, "filter": "duration:[0 TO 4]", "sort": "rating_desc",
                                "fields": "id,name,previews", "token": key, "page_size": 1})
    with urllib.request.urlopen(f"https://freesound.org/apiv2/search/text/?{q}") as r:
        res = json.load(r)["results"]
    if not res:
        raise SystemExit(f"Aucun son pour « {query} »")
    out = SFX_DIR / f"{name or query.replace(' ', '_')}.mp3"
    urllib.request.urlretrieve(res[0]["previews"]["preview-hq-mp3"], out)
    log(f"SFX « {res[0]['name']} » → {out}")
    return out


# ------------------------------------------------------------- niveaux ---

_LEVELS = {}


def level_db(f):
    """Niveau RMS (dBFS) de la partie active du son (cache par fichier + date)."""
    import statistics
    from .niveaux import windows_db
    key = (str(f), Path(f).stat().st_mtime)
    if key not in _LEVELS:
        w = [v for v in windows_db(f, win=0.05) if v > -60]
        _LEVELS[key] = statistics.median(sorted(w)[len(w) // 3:]) if w else -20.0
    return _LEVELS[key]


# ------------------------------------------------------------- placement ---

PRE = {"whoosh": 0.18, "swoosh": 0.1, "riser": 1.1}   # le son « arrive » sur l'image : départ un peu avant


def _speaking(words, t):
    return any(w["start"] - 0.03 <= t <= w["end"] + 0.03 for w in words)


def auto_events(plan, style, voice_db=None, words=None):
    """Bruitages retenus [{t, file, gain, name, why}] : candidats du plan triés par utilité, espacés, au bon niveau."""
    c = style["sfx"]
    manual = [dict(e, prio=9, why="posé à la main") for e in plan.get("sfx", []) if e.get("name")]
    if not c.get("enabled"):
        cands = manual
    else:
        cands = list(manual)
        words = words or []
        anchors = sorted({round(w["start"], 2) for i, w in enumerate(words)
                          if i == 0 or w["start"] - words[i - 1]["end"] > 0.25}
                         | {round(words[i]["start"], 2) for i in plan.get("emphasis", []) if i < len(words)})
        near_anchor = lambda t: any(abs(t - a) <= 0.3 for a in anchors) if anchors else True
        for x in plan.get("transitions") or []:
            from .transitions import SFX as TSFX
            name = x.get("sfx", {**TSFX, **(c.get("on_transition") or {})}.get(x["kind"]))
            if name:
                cands.append({"t": x["t"], "name": name, "prio": 5, "why": f"raccord {x['kind']}"})
        for b in plan.get("broll", []):
            name = b.get("sfx", c.get("on_broll"))
            if name and b.get("file"):
                cands.append({"t": b["start"], "name": name, "prio": 4, "why": "entrée B-roll"})
        for m in plan.get("motion", []):
            typ = m.get("type")
            if "sfx" in m:
                name = m["sfx"]
            elif typ == "title":
                name = c.get("on_motion")
                if name == "riser" and m["start"] < PRE["riser"]:  # pas la place d'une montée avant : un pop net
                    name = "pop"
            elif typ in ("hyperframes", "callout", "lower_third", "chapter"):
                name = c.get("on_card", "swoosh")
            else:
                name = None
            if name:
                cands.append({"t": m["start"], "name": name, "prio": 6 if typ in ("cta", "title") else 4,
                              "why": f"apparition {typ}"})
        for z in plan.get("zooms", []):  # un zoom ne sonne que s'il tombe sur une attaque de phrase ou un mot fort
            name = z.get("sfx", c["on_zoom"].get(z["kind"]))
            if name and ("sfx" in z or near_anchor(z["start"])):
                cands.append({"t": z["start"], "name": name, "prio": 2, "why": f"zoom {z['kind']}"})
    gap = float(c.get("min_gap", 1.1))
    per_min = float(c.get("max_per_minute", 14))
    dur = float(plan.get("duration") or 60)
    budget = max(1, int(per_min * dur / 60))
    kept = []
    for e in sorted(cands, key=lambda e: (-e["prio"], e["t"])):
        if e["prio"] < 9 and (len([k for k in kept if k["prio"] < 9]) >= budget
                              or any(abs(e["t"] - k["t"]) < gap for k in kept)):
            continue
        kept.append(e)
    out = []
    under = float(c.get("under_db", 17))
    for e in sorted(kept, key=lambda e: e["t"]):
        f = resolve(e["name"])
        if not f:
            continue
        t = max(0.0, e["t"] - PRE.get(e["name"], 0.0)) if e["prio"] < 9 else max(0.0, e["t"])
        if "gain" in e:
            gain = float(e["gain"])
        elif voice_db is not None:  # niveau mesuré : N dB sous la voix, un peu moins fort s'il tombe sur un mot
            db = voice_db - under - level_db(f) - (3 if words and _speaking(words, e["t"]) else 0)
            gain = round(min(2.0, 10 ** (db / 20)), 4)
        else:
            gain = c["volume"]
        out.append({"t": round(t, 3), "file": f, "gain": gain, "name": e["name"], "why": e["why"]})
    return out
