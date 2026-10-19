"""MonteurOS — CLI.  python -m monteur <commande> …"""
import argparse
import sys
from pathlib import Path

from .common import Workspace, load_json, load_style, log, probe, save_json, which


def get_ws(a):
    ws = Workspace(a.video, getattr(a, "workdir", None))
    style = load_style(a.style or load_json(ws.style, {}).get("name"))
    if a.style:
        save_json(ws.style, {"name": a.style})
    if getattr(a, "music", None):
        style["audio"]["music"] = str(Path(a.music).resolve())
    if getattr(a, "aspect", None):
        style["format"]["aspect"] = a.aspect
    return ws, style


def portrait(ws, style):
    asp = style["format"].get("aspect", "source")
    if asp == "source":
        i = probe(ws.source)
        return i["height"] > i["width"]
    return asp in ("9:16", "4:5")


def silent(video):
    import re
    from .common import run
    err = run(["ffmpeg", "-hide_banner", "-nostats", "-i", video, "-vn", "-af", "volumedetect", "-f", "null", "-"],
              capture=True).stderr
    m = re.search(r"max_volume: (-?[\d.]+|-inf) dB", err)
    return not m or m.group(1) == "-inf" or float(m.group(1)) < -60


def cmd_doctor(a):
    from . import sfx
    ok = True
    for b in ("ffmpeg", "ffprobe", "node", "npx"):
        print(f"{'✅' if which(b) else '❌'} {b}")
        ok &= which(b) or b in ("node", "npx")
    for mod in ("faster_whisper", "yt_dlp", "cv2", "google.genai"):
        try:
            __import__(mod)
            print(f"✅ {mod}")
        except ImportError:
            optional = mod in ("google.genai", "cv2")
            print(f"{'➖' if optional else '❌'} {mod}")
            ok &= optional
    import os
    for k in ("PEXELS_API_KEY", "PIXABAY_API_KEY", "FREESOUND_API_KEY", "MAGNIFIC_API_KEY", "GEMINI_API_KEY"):
        print(f"{'🔑' if os.environ.get(k) else '➖'} {k}")
    print("🔊 SFX :", ", ".join(sfx.ensure_library()))
    fonts = sorted(p.name for p in (Path(__file__).parent.parent / "assets" / "fonts").glob("*.[ot]tf"))
    print("🔤 Polices :", ", ".join(fonts) or "aucune (lance setup.sh)")
    sys.exit(0 if ok else 1)


def cmd_transcribe(a):
    from .transcribe import transcribe
    ws, _ = get_ws(a)
    transcribe(ws.source, ws.transcript, a.model, a.language)


def cmd_cut(a):
    from .cut import cut
    ws, style = get_ws(a)
    edl = cut(ws, style, load_json(ws.transcript))
    print(edl["stats"])


def cmd_plan(a):
    from .plan import auto_plan
    ws, style = get_ws(a)
    auto_plan(ws, style, ws.base_transcript())


def cmd_broll(a):
    from .broll import fetch
    ws, style = get_ws(a)
    fetch(ws, portrait(ws, style))


def cmd_render(a):
    from .render import render
    ws, style = get_ws(a)
    render(ws, style, Path(a.out).resolve() if a.out else None)


def cmd_prep(a):
    """Transcription → coupe → plan → B-roll : tout sauf le rendu (pour relecture par Claude)."""
    from .broll import fetch
    from .cut import cut
    from .plan import auto_plan
    from .transcribe import transcribe
    ws, style = get_ws(a)
    has_audio = probe(ws.source)["has_audio"] and not silent(ws.source)
    t = load_json(ws.transcript) if ws.transcript.exists() and not a.force else \
        (transcribe(ws.source, ws.transcript, a.model, a.language) if has_audio else {"words": []})
    if style["cut"].get("enabled", True) and not a.no_cut and t.get("words"):
        edl = cut(ws, style, t)
    else:
        ws.cut_video.unlink(missing_ok=True)
        save_json(ws.transcript, t)
        edl = {"stats": "coupe désactivée"}
    if not ws.plan.exists() or a.force:
        auto_plan(ws, style, ws.base_transcript())
    if not a.no_broll:
        fetch(ws, portrait(ws, style))
    print(f"\nDossier : {ws.dir}\nCoupe : {edl['stats']}\nÉdite {ws.plan} puis : monteur render {a.video}")


def cmd_run(a):
    cmd_prep(a)
    cmd_render(a)


def cmd_slideshow(a):
    from .slideshow import slideshow
    slideshow(a.images, a.out, a.per, a.aspect or "9:16", a.audio)


def cmd_charte(a):
    from .charte import extract
    extract(a.sources, a.name)


def cmd_studio(a):
    from .studio import serve
    serve(a.port, a.root)


def cmd_style(a):
    from .style_clone import clone
    clone(a.sources, a.name, a.transcribe)


def cmd_sfx(a):
    from . import sfx
    if a.search:
        sfx.freesound(a.search, a.name)
    print("\n".join(sfx.ensure_library()))


def cmd_motion_new(a):
    from .hyperframes import new
    ws, style = get_ws(a)
    res = "portrait" if portrait(ws, style) else "landscape"
    new(ws, a.name, a.resolution or res, a.example)


def cmd_motion_render(a):
    from .hyperframes import render
    ws, _ = get_ws(a)
    render(ws, a.name, a.start, a.end, not a.opaque, a.layout)


def cmd_attach(a):
    from .generate import attach
    ws, _ = get_ws(a)
    attach(ws, a.index, a.file, a.kind, a.section)


def cmd_upscale(a):
    from .generate import magnific_upscale
    magnific_upscale(a.image, a.out, a.scale, a.mode, a.prompt)


def cmd_veo(a):
    from .generate import veo_generate
    veo_generate(a.prompt, a.out, a.aspect, a.model, a.image)


def load_env():
    import os
    env = Path(__file__).resolve().parent.parent / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main(argv=None):
    load_env()
    p = argparse.ArgumentParser(prog="monteur", description="MonteurOS — monteur vidéo automatique")
    sub = p.add_subparsers(dest="cmd", required=True)

    def vid(name, fn, help_):
        s = sub.add_parser(name, help=help_)
        s.add_argument("video")
        s.add_argument("--style", "-s")
        s.add_argument("--workdir")
        s.add_argument("--aspect", choices=["source", "9:16", "16:9", "1:1", "4:5"])
        s.set_defaults(fn=fn)
        return s

    sub.add_parser("doctor", help="Vérifie l'installation").set_defaults(fn=cmd_doctor)
    for name, fn, h in (("prep", cmd_prep, "Transcrit, coupe, planifie, cherche les B-roll"),
                        ("run", cmd_run, "Chaîne complète rush → vidéo finale")):
        s = vid(name, fn, h)
        s.add_argument("--model", default="small")
        s.add_argument("--language")
        s.add_argument("--music")
        s.add_argument("--out")
        s.add_argument("--force", action="store_true")
        s.add_argument("--no-broll", action="store_true")
        s.add_argument("--no-cut", action="store_true")
    s = vid("transcribe", cmd_transcribe, "Transcription mot à mot")
    s.add_argument("--model", default="small")
    s.add_argument("--language")
    vid("cut", cmd_cut, "Supprime blancs, hésitations, répétitions")
    vid("plan", cmd_plan, "Génère le plan auto (zooms, B-roll, animations)")
    vid("broll", cmd_broll, "Télécharge les illustrations du plan")
    s = vid("render", cmd_render, "Rendu final")
    s.add_argument("--out")
    s.add_argument("--music")
    s = vid("motion-new", cmd_motion_new, "Crée une composition Hyperframes")
    s.add_argument("name")
    s.add_argument("--example", default="blank")
    s.add_argument("--resolution")
    s = vid("motion-render", cmd_motion_render, "Rend une composition Hyperframes et l'ajoute au plan")
    s.add_argument("name")
    s.add_argument("--start", type=float, required=True)
    s.add_argument("--end", type=float)
    s.add_argument("--opaque", action="store_true", help="MP4 plein écran au lieu d'un overlay transparent")
    s.add_argument("--layout", choices=["overlay", "full", "pip"])
    s = vid("attach", cmd_attach, "Branche un fichier sur une entrée du plan")
    s.add_argument("index", type=int)
    s.add_argument("file")
    s.add_argument("--kind", choices=["video", "image"])
    s.add_argument("--section", default="broll", choices=["broll", "motion"])

    s = sub.add_parser("style", help="Copie le style de vidéos (URLs YouTube ou MP4)")
    s.add_argument("sources", nargs="+")
    s.add_argument("--name", required=True)
    s.add_argument("--transcribe", action="store_true", help="mesure aussi le débit de parole")
    s.set_defaults(fn=cmd_style)
    s = sub.add_parser("slideshow", help="Vidéo produit à partir de photos (Ken Burns)")
    s.add_argument("images", nargs="+")
    s.add_argument("--out", required=True)
    s.add_argument("--per", type=float, default=2.5, help="secondes par image")
    s.add_argument("--aspect", choices=["9:16", "16:9", "1:1", "4:5"])
    s.add_argument("--audio", help="voix off ou musique")
    s.set_defaults(fn=cmd_slideshow)
    s = sub.add_parser("charte", help="Extrait une charte graphique (couleurs, typo) d'images/vidéos/URL → thème Studio")
    s.add_argument("sources", nargs="+")
    s.add_argument("--name", required=True)
    s.set_defaults(fn=cmd_charte)
    s = sub.add_parser("studio", help="Interface web MonteurOS Studio")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--root", default=".", help="dossier des rushs")
    s.set_defaults(fn=cmd_studio)
    s = sub.add_parser("sfx", help="Liste / télécharge des bruitages")
    s.add_argument("--search")
    s.add_argument("--name")
    s.set_defaults(fn=cmd_sfx)
    s = sub.add_parser("upscale", help="Upscale Magnific d'une image")
    s.add_argument("image")
    s.add_argument("--out")
    s.add_argument("--scale", default="2x")
    s.add_argument("--mode", default="precision", choices=["precision", "creative"])
    s.add_argument("--prompt")
    s.set_defaults(fn=cmd_upscale)
    s = sub.add_parser("veo", help="Génère un clip IA (Veo — moteur de Google Flow)")
    s.add_argument("prompt")
    s.add_argument("--out", required=True)
    s.add_argument("--aspect", default="16:9")
    s.add_argument("--model")
    s.add_argument("--image")
    s.set_defaults(fn=cmd_veo)

    a = p.parse_args(argv)
    try:
        a.fn(a)
    except RuntimeError as e:
        log(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
