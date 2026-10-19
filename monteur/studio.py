"""MonteurOS Studio : interface web locale (http://127.0.0.1:8765) au-dessus de la CLI."""
import json
import mimetypes
import os
import subprocess
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .common import ROOT, STYLES, load_json, log, save_json

UI = ROOT / "ui"
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
ACTIONS = {"prep", "render", "broll", "cut", "plan", "style", "charte", "doctor", "transcribe"}
JOBS = {}


def theme_css(name):
    t = load_json(UI / "themes" / f"{name}.json") or load_json(UI / "themes" / "monteuros.json")
    c, f = t["colors"], t.get("fonts", {})
    vars_ = "".join(f"--{k}:{v};" for k, v in c.items())
    return (f":root{{{vars_}--radius:{t.get('radius', 14)}px;"
            f"--font-display:'{f.get('display', 'Montserrat')}',system-ui,sans-serif;"
            f"--font-body:'{f.get('body', 'Inter')}',system-ui,sans-serif}}")


def run_job(args):
    jid = uuid.uuid4().hex[:8]
    job = {"id": jid, "args": args, "log": [], "status": "running"}
    JOBS[jid] = job

    def worker():
        env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONUNBUFFERED": "1"}
        p = subprocess.Popen([sys.executable, "-m", "monteur", *args], stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, env=env)
        for line in p.stdout:
            job["log"].append(line.rstrip())
        job["status"] = "done" if p.wait() == 0 else "error"

    threading.Thread(target=worker, daemon=True).start()
    return job


class Handler(BaseHTTPRequestHandler):
    root: Path = Path(".")

    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else (json.dumps(body, ensure_ascii=False) if ctype ==
                                                     "application/json" else body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if "text" in ctype or "json" in ctype else ""))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def video_path(self, rel):
        p = (self.root / rel).resolve()
        if self.root not in p.parents and p != self.root:
            raise PermissionError(rel)
        return p

    def project(self, video):
        from .common import Workspace
        ws = Workspace(video)
        out = {"video": video.name, "dir": str(ws.dir), "plan": load_json(ws.plan),
               "edl": (load_json(ws.edl) or {}).get("stats"), "style": load_json(ws.style, {}).get("name"),
               "transcript": (ws.base_transcript() or {}).get("text", "") if ws.transcript.exists() else "",
               "files": {}}
        for key, p in (("source", ws.source), ("cut", ws.cut_video), ("final", ws.final)):
            if p.exists():
                out["files"][key] = "/file?path=" + str(p)
        return out

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path in ("/", "/index.html"):
                return self.send(200, (UI / "index.html").read_bytes(), "text/html")
            if u.path == "/theme.css":
                name = q.get("name") or load_json(UI / "settings.json", {}).get("theme", "monteuros")
                return self.send(200, theme_css(name), "text/css")
            if u.path == "/api/state":
                vids = sorted(p for p in self.root.iterdir() if p.suffix.lower() in VIDEO_EXT and p.is_file())
                return self.send(200, {
                    "root": str(self.root),
                    "videos": [{"name": v.name, "done": (v.with_name(v.stem + ".monteur") / "final.mp4").exists(),
                                "prepped": (v.with_name(v.stem + ".monteur") / "plan.json").exists()} for v in vids],
                    "styles": [{"name": p.stem, "description": load_json(p).get("description", "")}
                               for p in sorted(STYLES.glob("*.json"))],
                    "themes": sorted(p.stem for p in (UI / "themes").glob("*.json")),
                    "theme": load_json(UI / "settings.json", {}).get("theme", "monteuros")})
            if u.path == "/api/project":
                return self.send(200, self.project(self.video_path(q["video"])))
            if u.path == "/api/job":
                j = JOBS.get(q.get("id"))
                return self.send(200 if j else 404, j or {"error": "job inconnu"})
            if u.path == "/file":
                return self.send_file(Path(q["path"]).resolve())
            self.send(404, {"error": "introuvable"})
        except Exception as e:
            self.send(400, {"error": str(e)})

    def send_file(self, p):
        allowed = (self.root, ROOT)
        if not p.is_file() or not any(a in p.parents for a in allowed):
            return self.send(403, {"error": "accès refusé"})
        size = p.stat().st_size
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        if rng and rng.startswith("bytes="):
            a, _, b = rng[6:].partition("-")
            start = int(a or 0)
            end = int(b) if b else min(size - 1, start + (8 << 20))
        self.send_response(206 if rng else 200)
        self.send_header("Content-Type", mimetypes.guess_type(p.name)[0] or "application/octet-stream")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if rng:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with open(p, "rb") as f:
            f.seek(start)
            left = end - start + 1
            while left > 0 and (chunk := f.read(min(1 << 16, left))):
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return
                left -= len(chunk)

    def do_POST(self):
        u = urlparse(self.path)
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        try:
            if u.path == "/api/plan":
                from .common import Workspace
                ws = Workspace(self.video_path(body["video"]))
                save_json(ws.plan, body["plan"])
                return self.send(200, {"ok": True})
            if u.path == "/api/theme":
                save_json(UI / "settings.json", {"theme": body["theme"]})
                return self.send(200, {"ok": True})
            if u.path == "/api/run":
                act = body["action"]
                if act not in ACTIONS:
                    return self.send(400, {"error": f"action interdite : {act}"})
                args = [act]
                if act in ("style", "charte"):
                    args += [*body["sources"], "--name", body["name"]]
                elif act != "doctor":
                    args.append(str(self.video_path(body["video"])))
                    if body.get("style"):
                        args += ["--style", body["style"]]
                    if body.get("aspect") and body["aspect"] != "source":
                        args += ["--aspect", body["aspect"]]
                    if act == "prep" and body.get("force"):
                        args.append("--force")
                return self.send(200, run_job(args))
            self.send(404, {"error": "introuvable"})
        except Exception as e:
            self.send(400, {"error": str(e)})


def serve(port=8765, root="."):
    Handler.root = Path(root).resolve()
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    log(f"MonteurOS Studio → http://127.0.0.1:{port}  (rushs : {Handler.root})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
