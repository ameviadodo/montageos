"""Passerelle vers le skill coupe-facecam (skills/coupe-facecam) : coupe fine d'un rush facecam par ElevenLabs Scribe
+ écoute Silero VAD (la dernière prise gagne), regard caméra Descript, relecture dans l'Agentique Editor.

  monteur facecam analyse RUSH.mov [--script s.txt]   → <rush>-coupe/ (revue.md, transcription.md)
  monteur facecam rendu <rush>-coupe [--sans-eyecontact]
  monteur facecam retouches <rush>-coupe
  monteur facecam importer <rush>-coupe [--prep --style hormozi]   → projet MonteurOS sur la coupe, mots déjà calés

Le script tourne avec le Python de MonteurOS (numpy, onnxruntime, requests installés par setup.sh) et lit la même
clé ElevenLabs que la voix off (.env de MonteurOS ou skills/coupe-facecam/config/cles.env).
"""
import json
import subprocess
import sys
from pathlib import Path

from .common import ROOT, Workspace, load_json, log, save_json

SKILL = ROOT / "skills" / "coupe-facecam"
SCRIPT = SKILL / "scripts" / "coupe.py"


def run(args):
    if not SCRIPT.exists():
        raise SystemExit(f"Skill coupe-facecam absent ({SKILL}). Il n'est pas publié avec MonteurOS (licence Agence "
                         "Agentique) : copie ton dossier coupe-facecam dans skills/ — voir docs/coupe-facecam.md. "
                         "Sans lui, la coupe intégrée de « bin/monteur prep » fonctionne.")
    return subprocess.call([sys.executable, str(SCRIPT), *args])


def latest_version(work):
    st = load_json(Path(work) / "analyse.json") or {}
    vs = st.get("versions") or []
    if not vs:
        raise SystemExit(f"Aucune coupe rendue dans {work} : lance d'abord « monteur facecam rendu {work} ».")
    return st, len(vs)


def import_cut(work, version=None):
    """Projet MonteurOS sur la vidéo coupée : transcription = mots-coupe-vN.json (aucune retranscription)."""
    work = Path(work).expanduser().resolve()
    st, n = latest_version(work)
    n = version or n
    if n > len(st["versions"]):
        raise SystemExit(f"Version v{n} inconnue (dernière : v{len(st['versions'])}).")
    video = Path(st["versions"][n - 1]["video"])
    words_file = work / f"mots-coupe-v{n}.json"
    items = load_json(words_file)
    if not video.exists() or items is None:
        raise SystemExit(f"Coupe v{n} incomplète : {video.name} ou {words_file.name} manquant.")
    ws = Workspace(video)
    words = [{"w": it["text"], "start": it["s"], "end": it["e"], "p": 1.0} for it in items if it.get("kind", "mot") == "mot"]
    save_json(ws.transcript, {"language": st.get("langue", "fr"), "words": words,
                              "text": " ".join(w["w"] for w in words), "source": f"coupe-facecam v{n}"})
    ws.cut_video.unlink(missing_ok=True)       # déjà coupée : MonteurOS ne recoupe pas
    ws.cut_transcript.unlink(missing_ok=True)
    save_json(ws.dir / "facecam.json", {"work": str(work), "version": n, "video": str(video)})
    log(f"Coupe facecam v{n} importée : {video.name}, {len(words)} mots calés → {ws.dir}")
    return video


def cli(a):
    if a.action == "importer":
        import argparse
        ip = argparse.ArgumentParser(prog="monteur facecam importer")
        ip.add_argument("work")
        ip.add_argument("--version", type=int)
        ip.add_argument("--prep", action="store_true", help="enchaîne la préparation MonteurOS (sans recouper)")
        ip.add_argument("--style")
        ip.add_argument("--no-broll", action="store_true")
        ip.add_argument("--hyperframes", action="store_true")
        o = ip.parse_args(a.args)
        video = import_cut(o.work, o.version)
        if o.prep:
            from .cli import main
            main(["prep", str(video), "--no-cut", *(["--style", o.style] if o.style else []),
                  *(["--no-broll"] if o.no_broll else []), *(["--hyperframes"] if o.hyperframes else [])])
        else:
            print(f"\nSuite : bin/monteur prep \"{video}\" --no-cut [--style …] [--hyperframes]")
        return
    sys.exit(run([a.action, *a.args]))


def status():
    """Pour doctor : dépendances du skill."""
    out = {}
    for mod in ("numpy", "onnxruntime", "requests"):
        try:
            __import__(mod)
            out[mod] = True
        except ImportError:
            out[mod] = False
    out["modele"] = (SKILL / "models" / "silero_vad.onnx").exists()
    return out


if __name__ == "__main__":  # pragma: no cover
    print(json.dumps(status()))
