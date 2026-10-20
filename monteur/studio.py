"""MonteurOS Studio : interface web locale (http://127.0.0.1:8765) — Projets, Studio, Retours, Bibliothèques, Activité."""
import json
import mimetypes
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .common import ASSETS, ROOT, STYLES, Workspace, load_json, log, save_json

UI = ROOT / "ui"
LIB = ROOT / "library"
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
ACTIONS = {"prep", "render", "broll", "cut", "plan", "style", "charte", "doctor", "transcribe", "verif", "carte", "projet"}
JOBS = {}
ACTIVITY = UI / "activity.json"
_lock = threading.Lock()


# ---------- thème / bibliothèque ----------

def theme_name():
    return load_json(UI / "settings.json", {}).get("theme", "nocturne")


def theme_css(name):
    t = load_json(UI / "themes" / f"{name}.json") or load_json(UI / "themes" / "nocturne.json")
    c, f = t["colors"], t.get("fonts", {})
    defaults = {"danger": "#FF5A6E", "ink": "#0B0F1A"}
    vars_ = "".join(f"--{k}:{v};" for k, v in {**defaults, **c}.items())
    faces = "".join(f"@font-face{{font-family:'{fam}';{extra}src:url(/fonts/{file})}}" for fam, extra, file in (
        ("Instrument Serif", "font-style:italic;", "InstrumentSerif-Italic.ttf"),
        ("Instrument Serif", "", "InstrumentSerif-Regular.ttf"),
        ("Montserrat", "font-weight:500;", "Montserrat-SemiBold.ttf"),
        ("Montserrat", "font-weight:700;", "Montserrat-Bold.ttf"),
        ("Montserrat", "font-weight:800;", "Montserrat-ExtraBold.ttf"),
        ("Space Mono", "", "SpaceMono-Regular.ttf"),
        ("Space Mono", "font-weight:700;", "SpaceMono-Bold.ttf")))
    return (faces + f":root{{{vars_}--radius:{t.get('radius', 14)}px;"
            f"--font-display:'{f.get('display', 'Instrument Serif')}',Georgia,serif;"
            f"--font-body:'{f.get('body', 'Montserrat')}',system-ui,sans-serif;"
            f"--font-mono:'{f.get('mono', 'Space Mono')}',ui-monospace,monospace}}")


def front_matter(path):
    txt = path.read_text(encoding="utf-8")
    meta, body = {}, txt
    m = re.match(r"---\n(.*?)\n---\n(.*)", txt, re.S)
    if m:
        body = m.group(2)
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
    return meta, body


def style_entry(p):
    s = load_json(p) or {}
    lib = s.get("library", {})
    sub = s.get("subtitles", {})
    pal = lib.get("palette") or [c for c in (sub.get("primary"), sub.get("highlight"), sub.get("emphasis"),
                                             s.get("motion", {}).get("accent")) if c]
    fonts = lib.get("fonts") or {"display": s.get("motion", {}).get("font") or sub.get("font"), "body": sub.get("font")}
    return {"name": p.stem, "description": s.get("description", ""), "etat": lib.get("etat", "Prêt"),
            "palette": list(dict.fromkeys(pal)), "fonts": fonts, "cards": lib.get("cards", []),
            "format": s.get("format", {}).get("aspect", "source"), "layout": s.get("format", {}).get("layout")}


def library():
    from .cards import catalog
    formats = []
    for p in sorted((LIB / "formats").glob("*.md")):
        meta, _ = front_matter(p)
        ex = next(iter((LIB / "formats" / "exemples").glob(p.stem + ".*")), None) if (LIB / "formats" / "exemples").exists() else None
        formats.append({**meta, "id": p.stem, "exemple": f"/file?path={ex}" if ex else None})
    charte = []
    for p in sorted((UI / "themes").glob("*.json")):
        t = load_json(p)
        charte.append({"name": p.stem, "colors": t.get("colors", {}), "fonts": t.get("fonts", {}),
                       "active": p.stem == theme_name(), "notes": t.get("layout_notes", "")})
    return {"formats": formats, "charte": charte, "references": [style_entry(p) for p in sorted(STYLES.glob("*.json"))],
            "cards": catalog()}


# ---------- activité / tâches ----------

def log_activity(entry):
    with _lock:
        items = load_json(ACTIVITY, [])
        items = [i for i in items if i["id"] != entry["id"]] + [entry]
        save_json(ACTIVITY, items[-200:])


def run_job(args, label, video=None):
    jid = uuid.uuid4().hex[:8]
    job = {"id": jid, "args": args, "label": label, "video": video, "log": [], "status": "running",
           "started": int(time.time())}
    JOBS[jid] = job
    log_activity({k: v for k, v in job.items() if k != "log"})

    def worker():
        env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONUNBUFFERED": "1", "PYTHONUTF8": "1",
               "PYTHONIOENCODING": "utf-8"}
        p = subprocess.Popen([sys.executable, "-m", "monteur", *args], stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", env=env)
        for line in p.stdout:
            job["log"].append(line.rstrip())
        job["status"] = "done" if p.wait() == 0 else "error"
        job["ended"] = int(time.time())
        log_activity({**{k: v for k, v in job.items() if k != "log"}, "tail": job["log"][-6:]})

    threading.Thread(target=worker, daemon=True).start()
    return job


# ---------- HTTP ----------

class Handler(BaseHTTPRequestHandler):
    root: Path = Path(".")

    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json"):
        if isinstance(body, bytes):
            data = body
        else:
            data = (json.dumps(body, ensure_ascii=False) if ctype == "application/json" else body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if "text" in ctype or "json" in ctype else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def video_path(self, rel):
        p = (self.root / rel).resolve()
        if self.root not in p.parents:
            raise PermissionError(rel)
        return p

    def videos(self):
        return sorted(p for p in self.root.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXT)

    def projects(self):
        from .project import info
        out = []
        for v in self.videos():
            ws = Workspace(v)
            i = info(ws)
            i["thumb"] = f"/api/thumb?video={v.name}&t={i['last']['mtime'] if i['last'] else 0}"
            out.append(i)
        return out

    def project(self, video):
        from . import review
        from .project import info
        ws = Workspace(video)
        i = info(ws)
        tr = ws.base_transcript() if ws.transcript.exists() else None
        files = {"source": "/file?path=" + str(ws.source)}
        if ws.cut_video.exists():
            files["cut"] = "/file?path=" + str(ws.cut_video)
        for r in i["renders"]:
            r["url"] = "/file?path=" + r["path"]
        last_verif = load_json(Path(i["last"]["path"]).with_suffix(".verif.json")) if i["last"] else None
        subs, sfx = [], []
        try:
            from .common import load_style
            from .sfx import auto_events
            from .subtitles import group_words
            style = load_style(i["style"])
            if tr and tr.get("words"):
                c = style["subtitles"]
                subs = [{"start": g[0]["start"], "end": g[-1]["end"], "text": " ".join(w["w"] for w in g)}
                        for g in group_words(tr["words"], c["max_words"], c["max_chars"])]
            sfx = [{"t": e["t"], "name": Path(e["file"]).stem} for e in auto_events(load_json(ws.plan, {}), style)]
        except Exception:
            pass
        return {**i, "dir": str(ws.dir), "plan": load_json(ws.plan), "edl": (load_json(ws.edl) or {}).get("stats"),
                "keep": (load_json(ws.edl) or {}).get("keep"), "transcript": tr, "files": files,
                "review": review.load(ws), "verif": last_verif, "subs": subs, "sfx_events": sfx,
                "styles": [p.stem for p in sorted(STYLES.glob("*.json"))]}

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path in ("/", "/index.html"):
                return self.send(200, (UI / "index.html").read_bytes(), "text/html")
            if u.path == "/theme.css":
                return self.send(200, theme_css(q.get("name") or theme_name()), "text/css")
            if u.path.startswith("/fonts/") or u.path.startswith("/card/fonts/"):
                return self.send_file((ASSETS / "fonts" / Path(unquote(u.path)).name).resolve())
            if u.path == "/api/state":
                vids = self.videos()
                return self.send(200, {"root": str(self.root), "theme": theme_name(), "count": len(vids),
                                       "themes": sorted(p.stem for p in (UI / "themes").glob("*.json"))})
            if u.path == "/api/projects":
                ps = self.projects()
                stats = {"projets": len(ps), "avec_rendu": sum(bool(p["renders"]) for p in ps),
                         "perimes": sum(p["stale"] for p in ps), "disque": sum(p["disk"] for p in ps),
                         "retours": sum(p["feedback"]["open"] for p in ps)}
                return self.send(200, {"stats": stats, "projects": ps})
            if u.path == "/api/project":
                return self.send(200, self.project(self.video_path(q["video"])))
            if u.path == "/api/thumb":
                from .project import thumbnail
                t = thumbnail(Workspace(self.video_path(q["video"])))
                return self.send_file(t) if t else self.send(404, {"error": "pas de miniature"})
            if u.path == "/api/library":
                return self.send(200, library())
            if u.path == "/api/format":
                p = (LIB / "formats" / f"{Path(q['id']).name}.md")
                meta, body = front_matter(p)
                return self.send(200, {"meta": meta, "body": body})
            if u.path == "/api/style":
                p = STYLES / f"{Path(q['name']).name}.json"
                from .cards import catalog
                cards = {c["id"]: c for c in catalog()}
                e = style_entry(p)
                return self.send(200, {**e, "json": load_json(p), "cards": [cards[c] for c in e["cards"] if c in cards]})
            if u.path == "/card":
                from .cards import build
                vals = json.loads(q.get("vars") or "{}")
                html, _, _ = build(q["id"], vals, int(q.get("W", 1920)), int(q.get("H", 1080)))
                if (ASSETS / "vendor" / "gsap.min.js").exists():  # aperçu hors-ligne
                    html = re.sub(r"https://cdn\.jsdelivr\.net/npm/gsap@[\d.]+/dist/gsap\.min\.js", "/vendor/gsap.min.js", html)
                return self.send(200, html, "text/html")
            if u.path == "/vendor/gsap.min.js":
                return self.send_file((ASSETS / "vendor" / "gsap.min.js").resolve())
            if u.path == "/api/activity":
                live = [{k: v for k, v in j.items() if k != "log"} for j in JOBS.values() if j["status"] == "running"]
                return self.send(200, {"items": list(reversed(load_json(ACTIVITY, []))), "running": live})
            if u.path == "/api/job":
                j = JOBS.get(q.get("id"))
                return self.send(200 if j else 404, j or {"error": "tâche inconnue"})
            if u.path == "/file":
                return self.send_file(Path(q["path"]).resolve())
            self.send(404, {"error": "introuvable"})
        except Exception as e:
            self.send(400, {"error": f"{type(e).__name__}: {e}"})

    def send_file(self, p):
        if not p or not p.is_file() or not any(a in p.parents for a in (self.root, ROOT)):
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
                save_json(Workspace(self.video_path(body["video"])).plan, body["plan"])
                return self.send(200, {"ok": True})
            if u.path == "/api/theme":
                save_json(UI / "settings.json", {"theme": body["theme"]})
                return self.send(200, {"ok": True})
            if u.path == "/api/review":
                from . import review
                ws = Workspace(self.video_path(body["video"]))
                act = body["action"]
                if act == "add":
                    data = review.add(ws, float(body["t"]), body["text"], float(body.get("fps", 30)), body.get("render"))
                elif act == "delete":
                    data = review.load(ws)
                    data["items"] = [i for i in data["items"] if i["id"] != body["id"]]
                    review.save(ws, data)
                elif act == "send":
                    data = review.send(ws)
                    log_activity({"id": uuid.uuid4().hex[:8], "label": "Retours envoyés au montage",
                                  "video": body["video"], "status": "done", "started": int(time.time())})
                elif act == "mark":
                    data = review.mark(ws, [body["id"]], body.get("status", "appliqué"))
                else:
                    return self.send(400, {"error": "action inconnue"})
                return self.send(200, {**data, "text": review.as_text(ws)})
            if u.path == "/api/run":
                return self.run_action(body)
            self.send(404, {"error": "introuvable"})
        except Exception as e:
            self.send(400, {"error": f"{type(e).__name__}: {e}"})

    def run_action(self, body):
        act = body["action"]
        if act not in ACTIONS:
            return self.send(400, {"error": f"action interdite : {act}"})
        labels = {"prep": "Préparation", "render": "Rendu master", "broll": "Recherche B-roll", "verif": "Vérification",
                  "style": "Copie de style", "charte": "Extraction de charte", "carte": "Carte animée",
                  "projet": "Mise à jour projet", "doctor": "Diagnostic"}
        label = labels.get(act, act)
        busy = [j for j in JOBS.values() if j["status"] == "running" and j.get("video") and j["video"] == body.get("video")]
        if busy and act not in ("verif",):
            return self.send(409, {"error": f"« {busy[0]['label']} » est déjà en cours sur ce projet : attends la fin "
                                            "(suivi dans Activité) avant de lancer autre chose."})
        args = [act]
        if act in ("style", "charte"):
            args += [*body["sources"], "--name", body["name"]]
        elif act != "doctor":
            args.append(str(self.video_path(body["video"])))
            if body.get("style") and act not in ("verif", "projet"):
                args += ["--style", body["style"]]
            if body.get("aspect") and body["aspect"] != "source" and act not in ("verif", "projet", "carte"):
                args += ["--aspect", body["aspect"]]
            if act == "prep" and body.get("force"):
                args.append("--force")
            if act == "render" and body.get("draft"):
                args.append("--draft")
                label = "Rendu draft + vérif"
            if act == "carte":
                args += [body["card"], "--start", str(float(body["start"]))]
                for k, v in (body.get("vars") or {}).items():
                    args += ["--set", f"{k}={v}"]
            if act == "projet" and body.get("etat"):
                args += ["--etat", body["etat"]]
        return self.send(200, run_job(args, label, body.get("video")))


def close_stale_jobs():
    """Tâches « en cours » d'un Studio précédent (fermé ou planté) → « interrompu »."""
    with _lock:
        items = load_json(ACTIVITY, [])
        for i in items:
            if i.get("status") == "running":
                i["status"] = "interrupted"
        save_json(ACTIVITY, items)


def serve(port=8765, root="."):
    close_stale_jobs()
    Handler.root = Path(root).resolve()
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    log(f"MonteurOS Studio → http://127.0.0.1:{port}  (rushs : {Handler.root})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
