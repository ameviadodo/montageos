"""Bibliothèque de bruitages : synthèse locale (aucune dépendance) + fichiers perso / Freesound."""
import os
from pathlib import Path

import json
import urllib.parse
import urllib.request

from .common import ASSETS, ffmpeg, log

SFX_DIR = ASSETS / "sfx"

# Expressions aevalsrc : (durée, expression, filtre post)
SYNTH = {
    "whoosh": (0.55, "(random(0)*2-1)*pow(sin(PI*t/0.55),2)", "bandpass=f=1800:w=1.6,highpass=f=300,volume=2.2"),
    "swoosh": (0.35, "(random(0)*2-1)*pow(sin(PI*t/0.35),3)", "bandpass=f=3200:w=1.2,volume=2.5"),
    "pop": (0.12, "sin(2*PI*(380+1600*exp(-45*t))*t)*exp(-28*t)", "volume=0.9"),
    "click": (0.04, "(random(0)*2-1)*exp(-160*t)", "highpass=f=1500,volume=1.4"),
    "ding": (0.9, "(0.6*sin(2*PI*1318*t)+0.3*sin(2*PI*2637*t))*exp(-5*t)", "volume=0.8"),
    "impact": (0.9, "(sin(2*PI*(48+90*exp(-9*t))*t)*0.9+(random(0)*2-1)*0.35*exp(-25*t))*exp(-4.5*t)", "lowpass=f=4000,volume=1.6"),
    "riser": (1.2, "(random(0)*2-1)*0.5*t/1.2+0.4*sin(2*PI*(200+900*t*t)*t)*t/1.2", "highpass=f=200,afade=t=out:st=1.1:d=0.1"),
    "glitch": (0.25, "if(lt(mod(t,0.05),0.025),1,-1)*(random(0)*2-1)*exp(-6*t)", "bandpass=f=2500:w=2,volume=0.9"),
    "camera": (0.3, "(random(0)*2-1)*(exp(-90*t)+0.6*exp(-90*abs(t-0.12))*gte(t,0.12))", "bandpass=f=2200:w=1.5,volume=1.5"),
}


def ensure_library():
    SFX_DIR.mkdir(parents=True, exist_ok=True)
    for name, (d, expr, post) in SYNTH.items():
        out = SFX_DIR / f"{name}.wav"
        if out.exists():
            continue
        ffmpeg(["-f", "lavfi", "-i", f"aevalsrc='{expr}':s=48000:d={d}", "-af",
                f"{post},alimiter=limit=0.9", "-ac", "2", out])
    return sorted(p.stem for p in SFX_DIR.iterdir() if p.suffix in (".wav", ".mp3", ".ogg"))


def resolve(name):
    """Fichier perso (assets/sfx/<name>.*) prioritaire sur la synthèse."""
    if not name:
        return None
    p = Path(name)
    if p.exists():
        return p
    for ext in (".wav", ".mp3", ".ogg", ".m4a"):
        f = SFX_DIR / f"{name}{ext}"
        if f.exists():
            return f
    ensure_library()
    f = SFX_DIR / f"{name}.wav"
    return f if f.exists() else None


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


def auto_events(plan, style):
    """Bruitages déduits du plan (zooms, B-roll, animations) + entrées manuelles plan['sfx']."""
    c = style["sfx"]
    if not c.get("enabled"):
        return []
    ev = []
    for z in plan.get("zooms", []):
        name = z.get("sfx", c["on_zoom"].get(z["kind"]))
        if name:
            ev.append({"t": z["start"] - (0.12 if name in ("whoosh", "swoosh") else 0), "name": name})
    for b in plan.get("broll", []):
        name = b.get("sfx", c.get("on_broll"))
        if name and b.get("file"):
            ev.append({"t": b["start"] - 0.1, "name": name})
    for m in plan.get("motion", []):
        name = m.get("sfx", c.get("on_motion") if m.get("type") == "title" else None)
        if name:
            ev.append({"t": m["start"] - (0.9 if name == "riser" else 0), "name": name})
    if plan.get("transitions"):
        from .transitions import sfx_events
        ev += sfx_events(plan["transitions"], c)
    ev += plan.get("sfx", [])
    out = []
    for e in sorted(ev, key=lambda e: e["t"]):
        f = resolve(e["name"])
        if f:
            out.append({"t": max(0, e["t"]), "file": f, "gain": e.get("gain", c["volume"])})
    return out
