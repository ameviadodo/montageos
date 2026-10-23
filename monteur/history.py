"""Historique d'un projet : instantané avant chaque action, « Annuler » pour revenir en arrière.

<rush>.monteur/historique/<NN>-<action>/ contient l'état d'avant (plan, coupe, transcriptions, style).
cut.mp4 est gardé par lien physique (aucune copie : la coupe écrit toujours un nouveau fichier).
Un rendu annulé part dans historique/corbeille/ (récupérable à la main).
"""
import os
import shutil
import time

from .common import load_json, log, save_json

FILES = ["plan.json", "edl.json", "transcript.json", "transcript_cut.json", "style.json", "cut.mp4", "voixoff.json",
         "transcript.rush.json"]
KEEP = 30


def _dir(ws):
    return ws.dir / "historique"


def entries(ws):
    return load_json(_dir(ws) / "index.json", [])


def _save(ws, items):
    save_json(_dir(ws) / "index.json", items[-KEEP:])


def snapshot(ws, label):
    """Photographie l'état du projet AVANT une action. Renvoie l'entrée créée."""
    items = entries(ws)
    n = (items[-1]["n"] + 1) if items else 1
    d = _dir(ws) / f"{n:03d}"
    d.mkdir(parents=True, exist_ok=True)
    present = []
    for f in FILES:
        src = ws.dir / f
        if not src.exists():
            continue
        dst = d / f
        if f == "cut.mp4":  # la coupe écrit toujours un nouveau fichier (os.replace) : un lien physique suffit
            _link_or_copy(src, dst)
        else:  # les JSON sont réécrits sur place : vraie copie
            shutil.copy2(src, dst)
        present.append(f)
    entry = {"n": n, "label": label, "t": int(time.time()), "files": present}
    items.append(entry)
    for old in items[:-KEEP]:  # ménage des plus anciens
        shutil.rmtree(_dir(ws) / f"{old['n']:03d}", ignore_errors=True)
    _save(ws, items)
    return entry


def record_render(ws, path, label):
    """Un rendu ajoute une version : l'annuler la retire (vers la corbeille)."""
    items = entries(ws)
    n = (items[-1]["n"] + 1) if items else 1
    items.append({"n": n, "label": label, "t": int(time.time()), "render": str(path)})
    _save(ws, items)


def undo(ws, n=None):
    """Annule la dernière action (ou revient juste avant l'action n°n, en annulant aussi les suivantes)."""
    items = entries(ws)
    if not items:
        raise SystemExit("Rien à annuler pour ce projet.")
    target = n if n is not None else items[-1]["n"]
    if target not in [e["n"] for e in items]:
        raise SystemExit(f"Action n°{target} introuvable dans l'historique.")
    undone = []
    while items and items[-1]["n"] >= target:
        e = items.pop()
        if "render" in e:
            from pathlib import Path
            p = Path(e["render"])
            trash = _dir(ws) / "corbeille"
            trash.mkdir(parents=True, exist_ok=True)
            for f in (p, p.with_suffix(".verif.json")):
                if f.exists():
                    shutil.move(str(f), str(trash / f.name))
        else:
            d = _dir(ws) / f"{e['n']:03d}"
            for f in FILES:  # état d'avant : ce qui existait revient, ce qui n'existait pas disparaît
                cur = ws.dir / f
                if f in e["files"]:
                    if cur.exists() and os.path.samefile(d / f, cur):
                        continue  # inchangé depuis l'instantané (même fichier par lien physique)
                    tmp = ws.dir / (f + ".restaure")
                    tmp.unlink(missing_ok=True)
                    shutil.copy2(d / f, tmp) if f != "cut.mp4" else _link_or_copy(d / f, tmp)
                    os.replace(tmp, cur)
                elif cur.exists():
                    cur.unlink()
            shutil.rmtree(d, ignore_errors=True)
        undone.append(e["label"])
    _save(ws, items)
    for lab in undone:
        log(f"↶ Annulé : {lab}")
    return undone


def _link_or_copy(src, dst):
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)
