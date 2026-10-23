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

from .common import ASSETS, ROOT, STYLES, Workspace, active_style, load_json, log, save_json, set_setting

UI = ROOT / "ui"
LIB = ROOT / "library"
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
ACTIONS = {"affiner", "appliquer", "retouche", "prep", "render", "broll", "cut", "plan", "style", "charte", "doctor", "transcribe",
           "verif", "carte", "projet", "voixoff", "habiller", "analyse"}
JOBS = {}
API = 5  # à incrémenter quand ui/index.html attend de nouveaux champs : la page détecte un Studio pas redémarré


def code_stamp():
    return max(p.stat().st_mtime for p in (ROOT / "monteur").glob("*.py"))


STARTED_CODE = code_stamp()
BOOT = uuid.uuid4().hex[:8]  # change à chaque (re)démarrage : la page sait quand le nouveau Studio répond
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
    asp = s.get("format", {}).get("aspect", "source")
    return {"name": p.stem, "description": s.get("description", ""), "etat": lib.get("etat", "Prêt"),
            "palette": list(dict.fromkeys(pal)), "fonts": fonts, "cards": lib.get("cards", []),
            "format": asp, "layout": s.get("format", {}).get("layout"),
            "ratios": lib.get("ratios") or ([asp] if asp != "source" else []), "sources": lib.get("sources", []),
            "cut": s.get("cut", {}).get("transition", "hard"), "active": p.stem == (active_style() or "default")}


def library():
    from .cards import catalog
    formats = []
    for p in sorted((LIB / "formats").glob("*.md")):
        meta, _ = front_matter(p)
        ex = next(iter((LIB / "formats" / "exemples").glob(p.stem + ".*")), None) if (LIB / "formats" / "exemples").exists() else None
        ratios = [r.strip() for r in meta.get("ratios", "9:16").split(",") if r.strip()]
        formats.append({**meta, "id": p.stem, "ratios": ratios, "exemple": f"/file?path={ex}" if ex else None})
    charte = []
    for p in sorted((UI / "themes").glob("*.json")):
        t = load_json(p)
        charte.append({"name": p.stem, "colors": t.get("colors", {}), "fonts": t.get("fonts", {}),
                       "active": p.stem == theme_name(), "notes": t.get("layout_notes", "")})
    from .render import ASPECTS
    from .transitions import KINDS
    return {"formats": formats, "charte": charte, "references": [style_entry(p) for p in sorted(STYLES.glob("*.json"))],
            "cards": catalog(), "aspects": list(ASPECTS), "cuts": KINDS, "active_style": active_style() or "default"}


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

    def trusted(self):
        """Requête venue du Studio lui-même : hôte local (pas de DNS rebinding) et, si présente, origine locale
        (un site ouvert dans le navigateur ne peut pas lancer d'action ni lire .env via /file)."""
        local = ("127.0.0.1", "localhost", "[::1]")
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        if host and host not in local:
            return False
        origin = self.headers.get("Origin")
        if origin and urlparse(origin).hostname not in ("127.0.0.1", "localhost", "::1"):
            return False
        return True

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
            try:
                i = info(ws)
            except Exception as e:  # un projet abîmé ne doit pas vider toute la liste
                log(f"⚠️  Projet {v.name} illisible : {type(e).__name__}: {e}")
                i = {"title": v.stem, "slug": v.stem, "video": v.name, "style": "?", "family": "?", "type": "?",
                     "format": "?", "status": "brut", "stale": False, "renders": [], "last": None, "deliverables": 0,
                     "feedback": {"total": 0, "open": 0}, "modified": int(v.stat().st_mtime), "disk": 0,
                     "error": f"{type(e).__name__}: {e}"}
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
            sfx = [{"t": e["t"], "name": e["name"], "why": e["why"]}
                   for e in auto_events(load_json(ws.plan, {}), style, None, (tr or {}).get("words"))]
        except Exception:
            pass
        from .transitions import auto_transitions, cut_points
        plan = load_json(ws.plan) or {}
        try:
            from .common import load_style
            trans = plan.get("transitions")
            if trans is None:
                trans = auto_transitions(ws, load_style(i["style"]), plan.get("duration"))
        except Exception:
            trans = []
        from .history import entries
        from .voixoff import settings as vo_settings
        vs = ws.dir / "voixoff" / "script.txt"
        return {**i, "dir": str(ws.dir), "plan": load_json(ws.plan),
                "plan_mtime": ws.plan.stat().st_mtime if ws.plan.exists() else 0,
                "voiceover": vo_settings(ws, plan or None), "vo_script": vs.read_text(encoding="utf-8") if vs.exists() else "", "transitions": trans, "cut_points": cut_points(ws),
                "history": list(reversed(entries(ws)))[:15],
                "plan_style": plan.get("style") or (i["style"] if plan else None),  # plans d'avant : style du projet
                "edl": (load_json(ws.edl) or {}).get("stats"),
                "keep": (load_json(ws.edl) or {}).get("keep"), "transcript": tr, "files": files,
                "review": review.load(ws), "verif": last_verif, "subs": subs, "sfx_events": sfx,
                "styles": [p.stem for p in sorted(STYLES.glob("*.json"))]}

    def do_GET(self):
        if not self.trusted():
            return self.send(403, {"error": "origine refusée"})
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
                return self.send(200, {"root": str(self.root), "theme": theme_name(), "count": len(vids), "api": API, "boot": BOOT,
                                       "outdated": code_stamp() > STARTED_CODE + 1,
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
                refs = STYLES / "refs" / p.stem
                order = {"affinage": 0, "contact_sheet": 1, "burst": 2}
                sheets = sorted(refs.glob("*/*.png"), key=lambda x: (x.parent.name, order.get(x.stem, 3), x.name)) if refs.exists() else []
                js = load_json(p) or {}
                return self.send(200, {**e, "json": js, "cards": [cards[c] for c in e["cards"] if c in cards],
                                       "sheets": [{"name": f"{x.parent.name}/{x.name}", "url": f"/file?path={x}"} for x in sheets],
                                       "affinage": js.get("reference", {}).get("affinage"),
                                       "refinable": bool(refs.exists() and any(refs.glob("*/profile.json")))})
            if u.path == "/card":
                from .cards import build
                vals = json.loads(q.get("vars") or "{}")
                html, _, _ = build(q["id"], vals, int(q.get("W", 1920)), int(q.get("H", 1080)))
                if (ASSETS / "vendor" / "gsap.min.js").exists():  # aperçu hors-ligne
                    html = re.sub(r"https://cdn\.jsdelivr\.net/npm/gsap@[\d.]+/dist/gsap\.min\.js", "/vendor/gsap.min.js", html)
                return self.send(200, html, "text/html")
            if u.path == "/vendor/gsap.min.js":
                return self.send_file((ASSETS / "vendor" / "gsap.min.js").resolve())
            if u.path == "/api/keys":
                from .keys import status
                return self.send(200, {"keys": status()})
            if u.path == "/api/activity":
                live = [{k: v for k, v in j.items() if k != "log"} for j in JOBS.values() if j["status"] == "running"]
                return self.send(200, {"items": list(reversed(load_json(ACTIVITY, []))), "running": live})
            if u.path == "/api/job":
                j = JOBS.get(q.get("id"))
                return self.send(200 if j else 404, j or {"error": "tâche inconnue"})
            if u.path == "/file":
                return self.send_file(Path(q["path"]).resolve())
            self.send(404, {"error": "introuvable"})
        except ConnectionError:
            return
        except Exception as e:
            try:
                self.send(400, {"error": f"{type(e).__name__}: {e}"})
            except ConnectionError:
                pass

    def do_HEAD(self):  # certains navigateurs / antivirus sondent la page avant de l'ouvrir
        self.send_response(200 if urlparse(self.path).path in ("/", "/index.html") else 404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def send_file(self, p):
        if not p or not p.is_file() or not any(a in p.parents for a in (self.root, ROOT)) \
                or p.name.startswith(".env") or ".venv" in p.parts or ".git" in p.parts:
            return self.send(403, {"error": "accès refusé"})
        size = p.stat().st_size
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        if rng and rng.startswith("bytes="):
            a, _, b = rng[6:].split(",")[0].partition("-")
            if a:
                start = int(a)
                end = min(size - 1, int(b)) if b else min(size - 1, start + (8 << 20))
            else:  # « bytes=-500 » : les 500 derniers octets
                start, end = max(0, size - int(b or 0)), size - 1
            if start >= size or start > end:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
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
                except ConnectionError:  # BrokenPipe, Reset, Aborted (WinError 10053 : le lecteur saute ailleurs)
                    return
                left -= len(chunk)

    def upload(self, q):
        """Échantillon vidéo/image envoyé tel quel (corps binaire) → styles/refs/<nom>/uploads ou ui/themes/<nom>/uploads."""
        from .style_clone import slug
        name = slug(q.get("name") or "import")
        base = (STYLES / "refs" / name) if q.get("kind") == "style" else (UI / "themes" / name)
        fname = Path(unquote(q.get("filename") or "echantillon.mp4")).name
        if q.get("kind") == "voixoff":  # voix off enregistrée → <rush>.monteur/voixoff/upload/
            from .voixoff import AUDIO_EXT
            if Path(fname).suffix.lower() not in AUDIO_EXT:
                return self.send(400, {"error": f"pas un fichier audio : {fname}"})
            dest = Workspace(self.video_path(q["video"])).dir / "voixoff" / "upload" / fname
            self._receive(dest, 2 << 30)
            return self.send(200, {"path": str(dest), "size": dest.stat().st_size})
        if q.get("kind") == "rush":  # nouveau rush choisi sur l'ordinateur → dossier des projets
            if Path(fname).suffix.lower() not in VIDEO_EXT:
                return self.send(400, {"error": f"pas une vidéo : {fname}"})
            dest, k = self.root / fname, 1
            while dest.exists():
                dest, k = self.root / f"{Path(fname).stem}-{k}{Path(fname).suffix}", k + 1
            self._receive(dest, 100 << 30)
            log_activity({"id": uuid.uuid4().hex[:8], "label": "Vidéo ajoutée", "video": dest.name, "status": "done",
                          "started": int(time.time()), "tail": [f"{dest.stat().st_size >> 20} Mo"]})
            return self.send(200, {"path": str(dest), "video": dest.name, "size": dest.stat().st_size})
        if Path(fname).suffix.lower() not in VIDEO_EXT | {".png", ".jpg", ".jpeg", ".webp"}:
            return self.send(400, {"error": f"format non pris en charge : {fname}"})
        dest = base / "uploads" / fname
        if int(self.headers.get("Content-Length", 0)) > 2 << 30:
            return self.send(413, {"error": "fichier > 2 Go : coupe un extrait de 10 à 60 s"})
        self._receive(dest, 2 << 30)
        return self.send(200, {"path": str(dest), "name": name, "size": dest.stat().st_size})

    def _receive(self, dest, limit):
        dest.parent.mkdir(parents=True, exist_ok=True)
        left = min(int(self.headers.get("Content-Length", 0)), limit)
        tmp = dest.with_name(dest.name + ".part")
        with open(tmp, "wb") as f:
            while left > 0 and (chunk := self.rfile.read(min(1 << 20, left))):
                f.write(chunk)
                left -= len(chunk)
        if left > 0:
            tmp.unlink(missing_ok=True)
            raise RuntimeError("envoi interrompu")
        os.replace(tmp, dest)

    def do_POST(self):
        if not self.trusted():
            return self.send(403, {"error": "origine refusée"})
        u = urlparse(self.path)
        if u.path == "/api/upload":
            try:
                return self.upload({k: v[0] for k, v in parse_qs(u.query).items()})
            except Exception as e:
                return self.send(400, {"error": f"{type(e).__name__}: {e}"})
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        try:
            if u.path == "/api/plan":
                from .history import snapshot
                ws = Workspace(self.video_path(body["video"]))
                # le plan a été réécrit côté moteur (carte posée, style appliqué, retouche…) depuis que la page l'a lu :
                # on refuse d'écraser ces changements avec l'ancienne copie de la page
                if body.get("mtime") is not None and ws.plan.exists() and ws.plan.stat().st_mtime > float(body["mtime"]) + 0.5:
                    return self.send(409, {"error": "plan modifié entre-temps (carte, style, retouche) : rechargé",
                                           "plan": load_json(ws.plan), "plan_mtime": ws.plan.stat().st_mtime})
                if load_json(ws.plan) != body["plan"]:  # un instantané seulement si quelque chose change
                    snapshot(ws, body.get("label") or "Plan modifié dans le Studio")
                save_json(ws.plan, body["plan"])
                return self.send(200, {"ok": True, "plan_mtime": ws.plan.stat().st_mtime})
            if u.path == "/api/theme":
                set_setting(theme=body["theme"])
                return self.send(200, {"ok": True})
            if u.path == "/api/style/activate":
                if not (STYLES / f"{Path(body['name']).name}.json").exists():
                    return self.send(404, {"error": "style inconnu"})
                set_setting(style=Path(body["name"]).name)
                return self.send(200, {"ok": True, "active": body["name"]})
            if u.path == "/api/transitions":
                from .common import load_style
                from .transitions import KINDS, auto_transitions
                ws = Workspace(self.video_path(body["video"]))
                if body["kind"] not in KINDS:
                    return self.send(400, {"error": "type de cut inconnu"})
                from .history import snapshot
                snapshot(ws, f"Cuts : {body['kind']}")
                style = load_style(load_json(ws.style, {}).get("name") or active_style())
                style["cut"].update(transition=body["kind"], transition_every=int(body.get("every", 1)))
                plan = load_json(ws.plan) or {}
                plan["transitions"] = auto_transitions(ws, style, plan.get("duration"))
                save_json(ws.plan, plan)
                return self.send(200, {"transitions": plan["transitions"]})
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
            if u.path == "/api/transcript":
                from .history import snapshot
                from .transcript_import import import_transcript
                ws = Workspace(self.video_path(body["video"]))
                snapshot(ws, "Import de transcription")
                dest = ws.dir / "import" / Path(body["name"]).name
                dest.parent.mkdir(exist_ok=True)
                dest.write_text(body["content"], encoding="utf-8")
                data = import_transcript(ws, dest)
                log_activity({"id": uuid.uuid4().hex[:8], "label": "Transcription importée", "video": body["video"],
                              "status": "done", "started": int(time.time()), "tail": [f"{len(data['words'])} mots"]})
                return self.send(200, {"words": len(data["words"])})
            if u.path == "/api/run":
                return self.run_action(body)
            if u.path == "/api/keys":
                from .keys import set_key, status
                for k, v in (body.get("set") or {}).items():
                    if v is not None and not str(v).startswith(("•", "…")) and "…" not in str(v):  # valeur masquée renvoyée telle quelle
                        set_key(k, v)
                return self.send(200, {"keys": status()})
            if u.path == "/api/keys/test":
                from .keys import test
                return self.send(200, {"results": {k: {"ok": ok, "detail": d} for k, (ok, d) in test().items()}})
            if u.path == "/api/undo":
                from .history import entries, undo
                if any(j["status"] == "running" and j.get("video") == body["video"] for j in JOBS.values()):
                    return self.send(409, {"error": "une action est en cours sur ce projet : attends la fin pour annuler"})
                ws = Workspace(self.video_path(body["video"]))
                done = undo(ws, body.get("n"))
                log_activity({"id": uuid.uuid4().hex[:8], "label": "Annulation", "video": body["video"], "status": "done",
                              "started": int(time.time()), "tail": [f"↶ {x}" for x in done]})
                return self.send(200, {"undone": done, "history": list(reversed(entries(ws)))[:15]})
            if u.path == "/api/restart":
                if any(j["status"] == "running" for j in JOBS.values()):
                    return self.send(409, {"error": "une tâche est en cours : attends la fin avant de redémarrer"})
                self.send(200, {"ok": True})
                threading.Thread(target=restart, args=(self.server,), daemon=True).start()
                return
            self.send(404, {"error": "introuvable"})
        except Exception as e:
            self.send(400, {"error": f"{type(e).__name__}: {e}"})

    def run_action(self, body):
        act = body["action"]
        if act not in ACTIONS:
            return self.send(400, {"error": f"action interdite : {act}"})
        labels = {"retouche": "Retouche", "affiner": "Affinage du style", "appliquer": "Application du style", "prep": "Préparation", "render": "Rendu master", "broll": "Recherche B-roll", "verif": "Vérification",
                  "style": "Copie de style", "charte": "Extraction de charte", "carte": "Carte animée",
                  "projet": "Mise à jour projet", "doctor": "Diagnostic", "analyse": "Analyse de la vidéo",
                  "voixoff": "Voix off", "habiller": "Habillage Hyperframes"}
        label = labels.get(act, act)
        busy = [j for j in JOBS.values() if j["status"] == "running" and j.get("video") and j["video"] == body.get("video")]
        if busy and act not in ("verif",):
            return self.send(409, {"error": f"« {busy[0]['label']} » est déjà en cours sur ce projet : attends la fin "
                                            "(suivi dans Activité) avant de lancer autre chose."})
        args = [act]
        if act == "affiner":
            args.append(Path(body["name"]).name)
        elif act in ("style", "charte"):
            sources = [x.strip() for x in body.get("sources", []) if x.strip()]
            if not sources or not body.get("name"):
                return self.send(400, {"error": "donne un nom et au moins un lien ou un fichier MP4"})
            args += [*sources, "--name", body["name"]]
            if act == "style" and body.get("activer"):
                args.append("--activer")
        elif act != "doctor":
            args.append(str(self.video_path(body["video"])))
            if body.get("style") and act not in ("verif", "projet", "analyse", "voixoff" if body.get("retire") else ""):  # appliquer : le style choisi devient celui du projet
                args += ["--style", body["style"]]
            if body.get("aspect") and body["aspect"] != "source" and act not in ("verif", "projet", "carte", "analyse"):
                args += ["--aspect", body["aspect"]]
            if body.get("cuts") and act in ("prep", "render", "plan"):
                args += ["--cuts", body["cuts"]]
            if act == "prep" and body.get("force"):
                args.append("--force")
            if act == "render" and body.get("draft"):
                args.append("--draft")
                label = "Rendu draft + vérif"
            if act == "carte":
                args += [body["card"], "--start", str(float(body["start"]))]
                if body.get("duree"):
                    args += ["--duree", str(float(body["duree"]))]
                for k, v in (body.get("vars") or {}).items():
                    args += ["--set", f"{k}={v}"]
            if act == "retouche":
                op, t = body["op"], f"{float(body['t']):.3f}"
                args += {"coupe": ["--coupe", t, str(float(body.get("d", 0.5)))], "zoom": ["--zoom", t, "--type", body.get("kind", "punch")],
                         "retire": ["--retire", t], "bruitage": ["--bruitage", t, body.get("name", "whoosh")]}[op]
                if body.get("rendu", True):
                    args.append("--rendu")
                label = {"coupe": "Coupe ici", "zoom": "Zoom ici", "retire": "Retrait ici", "bruitage": "Bruitage ici"}[op] + " + draft"
            if act == "projet" and body.get("etat"):
                args += ["--etat", body["etat"]]
            if act == "voixoff":
                ws = Workspace(self.video_path(body["video"]))
                if body.get("retire"):
                    args.append("--retire")
                else:
                    if body.get("fichier"):
                        fp = Path(body["fichier"]).resolve()
                        if ws.dir not in fp.parents or not fp.is_file():
                            return self.send(400, {"error": "fichier de voix off introuvable (envoie-le d'abord)"})
                        args += ["--fichier", str(fp)]
                    if (body.get("script") or "").strip():
                        sp = ws.dir / "voixoff" / "script_studio.txt"
                        sp.parent.mkdir(parents=True, exist_ok=True)
                        sp.write_text(body["script"].strip() + "\n", encoding="utf-8")
                        args += ["--script", str(sp)]
                    if not body.get("fichier") and not (body.get("script") or "").strip():
                        return self.send(400, {"error": "envoie un fichier de voix off ou écris un script"})
                    args += ["--moteur", body.get("moteur") or "auto"]
                    if body.get("voix"):
                        args += ["--voix", str(body["voix"])]
                    if body.get("prep", True):
                        args.append("--prep")
                    label = "Voix off + préparation"
            if act == "habiller":
                for k in ("nom", "role"):
                    if body.get(k):
                        args += [f"--{k}", str(body[k])]
                label = "Habillage Hyperframes"
            if act == "analyse" and body.get("brief"):
                args += ["--brief", str(body["brief"])]
        return self.send(200, run_job(args, label, body.get("video")))


def close_stale_jobs():
    """Tâches « en cours » d'un Studio précédent (fermé ou planté) → « interrompu »."""
    with _lock:
        items = load_json(ACTIVITY, [])
        for i in items:
            if i.get("status") == "running":
                i["status"] = "interrupted"
        save_json(ACTIVITY, items)


def restart(srv):
    """Arrête la boucle HTTP ; serve() recharge ensuite le code à jour dans le même processus."""
    time.sleep(0.3)
    srv.restart = True
    srv.shutdown()


def reload_code():
    """Recharge tous les modules monteur.* (après un git pull) : même processus, même console, même port.
    Pas de nouveau processus à lancer — sous Windows / Git Bash, le relancer échouait (« le Studio ne répond pas »)."""
    import importlib
    mods = [m for n, m in list(sys.modules.items()) if m and (n == "monteur" or n.startswith("monteur."))]
    mods.sort(key=lambda m: (m.__name__ != "monteur.common", m.__name__ == "monteur.studio", m.__name__))
    for m in mods:
        try:
            importlib.reload(m)
        except Exception as e:  # un module cassé ne doit pas empêcher le Studio de revenir
            log(f"⚠️  Rechargement de {m.__name__} impossible : {type(e).__name__}: {e}")
    return sys.modules["monteur.studio"]


class Server(ThreadingHTTPServer):
    """Serveur du Studio. Sous Windows, SO_REUSEADDR laisse DEUX programmes écouter le même port : le navigateur
    tombait alors sur un ancien Studio (ou une autre application) et « la page ne s'ouvrait pas ». On exige le port
    en exclusivité, et les déconnexions du lecteur vidéo (WinError 10053) ne remplissent plus la console."""
    daemon_threads = True
    allow_reuse_address = os.name != "nt"

    def server_bind(self):
        import socket
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def handle_error(self, request, client_address):
        if isinstance(sys.exc_info()[1], (ConnectionError, TimeoutError)):
            return  # onglet fermé, vidéo qui saute : normal
        super().handle_error(request, client_address)


class Server6(Server):
    address_family = __import__("socket").AF_INET6


def _probe(port, timeout=1.5):
    """Ce qui répond déjà sur ce port : {"monteur": True, …} pour un Studio, {} pour autre chose, None si rien."""
    import urllib.request
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # jamais via le proxy système
    try:
        with opener.open(f"http://127.0.0.1:{port}/api/state", timeout=timeout) as r:
            st = json.loads(r.read().decode("utf-8", "replace"))
            return {"monteur": True, **st} if "boot" in st else {}
    except Exception as e:
        return {} if getattr(e, "code", None) else None


def _bind(port, tries=20):
    """Port demandé, sinon le suivant libre (8766, 8767…). Un ancien Studio sur le port est signalé."""
    for p in range(port, port + tries):
        for k in range(3):  # le port peut rester occupé un instant après la fermeture
            try:
                srv = Server(("127.0.0.1", p), Handler)
                break
            except OSError:
                srv = None
                time.sleep(0.2)
        if srv:
            if p != port:
                other = _probe(port)
                what = ("un autre MonteurOS Studio (ancienne fenêtre encore ouverte ?)" if other and other.get("monteur")
                        else "une autre application")
                log(f"⚠️  Le port {port} est pris par {what} : ce Studio utilise le port {p}.")
            try:  # « localhost » peut viser ::1 (IPv6) sous Windows : on écoute aussi là, sans bloquer si impossible
                srv6 = Server6(("::1", p), Handler)
                threading.Thread(target=srv6.serve_forever, daemon=True).start()
                srv.v6 = srv6
            except OSError:
                srv.v6 = None
            return srv, p
    raise SystemExit(f"Aucun port libre entre {port} et {port + tries - 1} : ferme les anciens Studios "
                     f"(ou lance : bin/monteur studio --port 9000)")


def _self_test(url, open_browser):
    """Vérifie que la page répond vraiment, puis ouvre le navigateur ; sinon explique quoi faire."""
    import urllib.request
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(20):
        try:
            with opener.open(url + "api/state", timeout=2) as r:
                if r.status == 200:
                    break
        except Exception as e:
            err = e
            time.sleep(0.25)
    else:
        log(f"❌ Le Studio ne répond pas à sa propre adresse ({type(err).__name__}: {err}).")
        log("   Pare-feu / antivirus qui filtre 127.0.0.1 ? Essaie : bin/monteur studio --port 9000")
        return
    log("✅ Studio prêt. Laisse CETTE fenêtre ouverte pendant que tu travailles (Ctrl+C pour arrêter).")
    if open_browser:
        import webbrowser
        try:
            if os.name == "nt":
                os.startfile(url)  # navigateur par défaut, fiable depuis Git Bash / cmd
            elif not webbrowser.open(url):
                raise OSError("aucun navigateur")
            log(f"   Navigateur ouvert sur {url} — sinon copie l'adresse dans Chrome, Edge ou Firefox.")
        except Exception:
            log(f"   Ouvre {url} dans ton navigateur.")


def serve(port=8765, root=".", open_browser=True):
    close_stale_jobs()
    Handler.root = Path(root).resolve()
    if not Handler.root.is_dir():
        raise SystemExit(f"Dossier des rushs introuvable : {Handler.root}")
    srv, port = _bind(port)
    url = f"http://127.0.0.1:{port}/"
    log(f"MonteurOS Studio → {url}  (rushs : {Handler.root})")
    srv.restart = False
    threading.Thread(target=_self_test, args=(url, open_browser and not os.environ.get("MONTEUR_NO_BROWSER")),
                     daemon=True).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        log("Studio arrêté (Ctrl+C). Relance : bin/monteur studio --root \"<dossier des rushs>\"")
    srv.server_close()
    if getattr(srv, "v6", None):
        srv.v6.shutdown()
        srv.v6.server_close()
    if srv.restart:
        log("Code mis à jour : rechargement du Studio…")
        new = reload_code()
        new.JOBS.update(JOBS)  # les tâches en cours restent suivies
        return new.serve(port, root, open_browser=False)
