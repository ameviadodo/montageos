"""Pont Hyperframes (HeyGen) : animations HTML/GSAP rendues en vidéo, insérées dans le montage."""
import json
import re
import shutil

from .common import load_json, log, run, save_json

HF = ["npx", "-y", "hyperframes@latest"]


def new(ws, name, resolution="landscape", example="blank"):
    import os
    # init vérifie et installe ses skills depuis GitHub à chaque projet : inutile (et bloquant hors-ligne) ici
    os.environ.setdefault("HYPERFRAMES_SKIP_SKILLS", "1")
    root = ws.dir / "hyperframes"
    root.mkdir(exist_ok=True)
    proj = root / name
    if proj.exists():
        log(f"Projet existant : {proj}")
        return proj
    run([*HF, "init", name, "--example", example, "--resolution", resolution, "--non-interactive",
         "--skip-transcribe"], cwd=root)
    vendor_cdn(proj)
    log(f"Composition créée : {proj}/index.html — édite-la (skill hyperframes) puis `monteur motion-render`.")
    return proj


def vendor_cdn(proj):
    """Copie GSAP en local : le rendu ne dépend plus du CDN (hors-ligne / proxy d'entreprise)."""
    html = proj / "index.html"
    m = re.search(r"https://cdn\.jsdelivr\.net/npm/gsap@([\d.]+)/dist/gsap\.min\.js", html.read_text(encoding="utf-8"))
    if not m:
        return
    res = run(["npm", "install", "--silent", "--no-audit", "--no-fund", f"gsap@{m.group(1)}"], cwd=proj, check=False)
    src = proj / "node_modules" / "gsap" / "dist" / "gsap.min.js"
    if res.returncode == 0 and src.exists():
        (proj / "vendor").mkdir(exist_ok=True)
        shutil.copy(src, proj / "vendor" / "gsap.min.js")
        html.write_text(html.read_text(encoding="utf-8").replace(m.group(0), "vendor/gsap.min.js"), encoding="utf-8")


def render(ws, name, start, end=None, alpha=True, layout=None, variables=None):
    proj = ws.dir / "hyperframes" / name
    if not proj.exists():
        raise SystemExit(f"Projet Hyperframes introuvable : {proj}")
    out_dir = ws.dir / "assets" / "motion"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{name}.{'mov' if alpha else 'mp4'}"
    cmd = [*HF, "render", str(proj), "--output", str(out), "--quality", "delivery",
           "--format", "mov" if alpha else "mp4", "--quiet"]
    if variables:
        cmd += ["--variables", json.dumps(variables)]
    run([*HF, "lint", str(proj)], check=False)
    run(cmd)
    from .common import probe
    d = probe(out)["duration"]
    plan = load_json(ws.plan, {"motion": []})
    plan.setdefault("motion", [])
    plan["motion"] = [m for m in plan["motion"] if m.get("name") != name]
    plan["motion"].append({"type": "hyperframes", "name": name, "file": str(out), "start": start,
                           "end": end if end else round(start + d, 3),
                           "layout": layout or ("overlay" if alpha else "full")})
    save_json(ws.plan, plan)
    log(f"Animation {name} ({d:.1f}s) → {out}, ajoutée au plan à {start}s")
    return out


def available():
    return shutil.which("npx") is not None
