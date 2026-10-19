"""Retours frame par frame : notes horodatées à l'image près, envoyées au montage puis appliquées par Claude."""
import time

from .common import load_json, save_json


def path(ws):
    return ws.dir / "review" / "feedback.json"


def load(ws):
    return load_json(path(ws), {"items": []})


def save(ws, data):
    save_json(path(ws), data)
    return data


def add(ws, t, text, fps=30, render=None):
    data = load(ws)
    n = 1 + max([i["id"] for i in data["items"]] or [0])
    data["items"].append({"id": n, "t": round(t, 3), "frame": int(round(t * fps)), "text": text.strip(),
                          "render": render, "status": "ouvert", "created": int(time.time())})
    return save(ws, data)


def send(ws):
    """« Envoyer au montage » : les retours ouverts passent à envoyé (Claude les traite au prochain tour)."""
    data = load(ws)
    for i in data["items"]:
        if i["status"] == "ouvert":
            i["status"] = "envoyé"
    return save(ws, data)


def mark(ws, ids, status="appliqué"):
    data = load(ws)
    for i in data["items"]:
        if i["id"] in ids:
            i["status"] = status
    return save(ws, data)


def tc(t):
    m, s = divmod(t, 60)
    return f"{int(m):02d}:{s:05.2f}"


def as_text(ws, only_pending=True):
    data = load(ws)
    items = [i for i in data["items"] if not only_pending or i["status"] != "appliqué"]
    if not items:
        return "Aucun retour en attente."
    lines = [f"Retours frame par frame — {ws.source.name} ({len(items)})"]
    for i in items:
        lines.append(f"#{i['id']} [{tc(i['t'])} · f{i['frame']:04d}] {i['text']}"
                     + (f"  (rendu {i['render']})" if i.get("render") else ""))
    lines.append("→ Applique chaque retour dans plan.json / style, re-rends un draft, puis "
                 "`monteur retours RUSH --applique <ids>`.")
    return "\n".join(lines)
