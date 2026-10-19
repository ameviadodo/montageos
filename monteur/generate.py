"""Génération / amélioration IA des visuels : Magnific (upscale), Google Veo (moteur de Flow).
Higgsfield passe par son connecteur MCP (outils mcp__higgsfield__*) : Claude génère, puis `monteur attach`."""
import base64
import json
import os
import time
import urllib.request
from pathlib import Path

from .common import load_json, log, save_json


def _req(url, payload=None, headers=None, method=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method or ("POST" if data else "GET"),
                                 headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def magnific_upscale(image, out=None, scale="2x", mode="precision", prompt=None):
    """Upscale Magnific. MAGNIFIC_API_KEY requis. Base/entête configurables si l'API évolue."""
    key = os.environ.get("MAGNIFIC_API_KEY") or os.environ.get("FREEPIK_API_KEY")
    if not key:
        raise SystemExit("MAGNIFIC_API_KEY manquant (clé API sur magnific.com / freepik.com/api).")
    base = os.environ.get("MAGNIFIC_API_BASE", "https://api.freepik.com")
    header = os.environ.get("MAGNIFIC_API_HEADER", "x-freepik-api-key")
    path = "/v1/ai/image-upscaler-precision" if mode == "precision" else "/v1/ai/image-upscaler"
    body = {"image": base64.b64encode(Path(image).read_bytes()).decode()}
    if mode == "precision":
        body["scale_factor"] = int(scale.rstrip("x"))
    else:
        body.update(scale_factor=scale, optimized_for="standard", creativity=0, hdr=0, resemblance=0)
        if prompt:
            body["prompt"] = prompt
    res = _req(base + path, body, {header: key})["data"]
    task = res["task_id"]
    log(f"Magnific tâche {task} …")
    while res.get("status") not in ("COMPLETED", "FAILED"):
        time.sleep(4)
        res = _req(f"{base}{path}/{task}", headers={header: key})["data"]
    if res["status"] == "FAILED":
        raise SystemExit("Magnific : échec de la tâche")
    out = Path(out or Path(image).with_name(Path(image).stem + "_magnific.png"))
    urllib.request.urlretrieve(res["generated"][0], out)
    log(f"Upscale Magnific → {out}")
    return out


def veo_generate(prompt, out, aspect="16:9", model=None, image=None):
    """Clip IA via l'API Gemini / Veo (même moteur que Google Flow). GEMINI_API_KEY requis."""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise SystemExit("google-genai absent : bash setup.sh --ai")
    client = genai.Client()
    kw = {"model": model or os.environ.get("VEO_MODEL", "veo-3.1-generate-preview"), "prompt": prompt,
          "config": types.GenerateVideosConfig(aspect_ratio=aspect)}
    if image:
        kw["image"] = types.Image.from_file(location=str(image))
    op = client.models.generate_videos(**kw)
    log("Veo : génération en cours …")
    while not op.done:
        time.sleep(10)
        op = client.operations.get(op)
    vid = op.response.generated_videos[0]
    client.files.download(file=vid.video)
    vid.video.save(str(out))
    log(f"Clip Veo → {out}")
    return Path(out)


def attach(ws, index, file, kind=None, section="broll"):
    """Branche un fichier (généré par Higgsfield, Flow, Magnific, ou fourni) sur une entrée du plan."""
    plan = load_json(ws.plan)
    item = plan[section][index]
    item["file"] = str(Path(file).resolve())
    item["kind"] = kind or ("image" if str(file).lower().endswith((".png", ".jpg", ".jpeg", ".webp")) else "video")
    save_json(ws.plan, plan)
    log(f"{section}[{index}] ← {file}")
