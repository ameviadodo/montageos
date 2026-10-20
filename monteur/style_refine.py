"""Affinage automatique d'un style copié : ce que les mesures globales ne voient pas.

- types de cut réels aux coupes : flash blanc, passage au noir, whip (image floue), zoom cut (même plan recadré) ;
- zooms à l'intérieur des plans (punch-in instantané ou poussée lente) → fréquence, amplitude, motif ;
- sous-titres incrustés : bande de l'image, taille des lettres, mots par bloc, couleurs (blanc + accent).
Résultat fusionné dans styles/<nom>.json (état « Affiné ») + planche annotée affinage.png pour vérification.
"""
import statistics
import subprocess
from pathlib import Path

from .common import STYLES, load_json, log, probe, save_json


CAPS = 0.45  # hauteur des capitales / taille ASS, étalonnée sur un rendu MonteurOS de taille connue


def _frames(video, fps, width, gray):
    import numpy as np
    info = probe(video)
    h = max(2, int(round(width * info["height"] / info["width"] / 2)) * 2)
    ch = 1 if gray else 3
    p = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(video), "-an", "-vf",
                          f"fps={fps},scale={width}:{h},format={'gray' if gray else 'rgb24'}", "-f", "rawvideo", "-"],
                         stdout=subprocess.PIPE)
    size, k = width * h * ch, 0
    while True:
        buf = p.stdout.read(size)
        if len(buf) < size:
            break
        a = np.frombuffer(buf, np.uint8).reshape((h, width) if gray else (h, width, 3))
        yield k / fps, a
        k += 1
    p.wait()


def _scale(a, b):
    """Facteur d'échelle entre deux images (ORB + similitude) ; None si le contenu n'est pas le même plan."""
    import cv2
    import numpy as np
    orb = cv2.ORB_create(500)
    ka, da = orb.detectAndCompute(a, None)
    kb, db = orb.detectAndCompute(b, None)
    if da is None or db is None or len(ka) < 20 or len(kb) < 20:
        return None
    m = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(da, db)
    if len(m) < 20:
        return None
    pa = np.float32([ka[x.queryIdx].pt for x in m])
    pb = np.float32([kb[x.trainIdx].pt for x in m])
    M, inl = cv2.estimateAffinePartial2D(pa, pb, method=cv2.RANSAC, ransacReprojThreshold=3)
    if M is None or inl is None or inl.sum() < 18 or inl.mean() < 0.35:
        return None
    return float((M[0, 0] ** 2 + M[1, 0] ** 2) ** 0.5)


def cuts_and_zooms(video, cuts):
    """Classe chaque coupe et repère les zooms dans les plans (image 320 px, 12 i/s)."""
    import cv2
    import numpy as np
    fps = 12
    Y, S, F = [], [], []
    for _, g in _frames(video, fps, 320, gray=True):
        Y.append(float(g.mean()))
        S.append(float(cv2.Laplacian(g, cv2.CV_32F).var()))
        F.append(g)
    n = len(F)
    kinds = []
    for t in cuts:
        c = int(round(t * fps))
        if c < 4 or c > n - 5:
            continue
        before, after = statistics.median(Y[max(0, c - 5):c - 2]), statistics.median(Y[c + 2:c + 5])
        win, sharp = Y[c - 1:c + 2], S[c - 1:c + 2]
        ref_sharp = statistics.median(S[max(0, c - 6):c - 2] + S[c + 2:c + 6]) or 1
        if max(win) > max(before, after) + 35:
            kinds.append("flash")
        elif min(win) < min(before, after) - 35 and min(win) < 45:
            kinds.append("dip")
        elif min(sharp) < 0.3 * ref_sharp:
            kinds.append("whip")
        else:
            s = _scale(F[c - 2], F[c + 2])
            kinds.append("zoomcut" if s and (s > 1.05 or s < 0.95) and 0.6 < s < 1.7 else "hard")
    # zooms dans les plans : pas de 1/4 s, hors voisinage des coupes
    near = {int(round(t * fps)) + d for t in cuts for d in range(-3, 4)}
    zooms, step = [], 3
    for i in range(0, n - step, step):
        if any(j in near for j in range(i, i + step + 1)):
            continue
        s = _scale(F[i], F[i + step])
        if s and 1.04 < max(s, 1 / s) < 1.6:
            zooms.append({"t": round(i / fps, 2), "scale": round(max(s, 1 / s), 3)})
    merged = []  # une poussée lente = plusieurs pas successifs dans le même sens
    for z in zooms:
        if merged and z["t"] - merged[-1]["t_end"] <= step / fps + 0.01:
            merged[-1]["t_end"], merged[-1]["steps"] = z["t"], merged[-1]["steps"] + 1
            merged[-1]["scale"] = round(merged[-1]["scale"] * z["scale"], 3)
        else:
            merged.append({**z, "t_end": z["t"], "steps": 1})
    for z in merged:
        z["kind"] = "punch" if z["steps"] == 1 else "ease"
    return kinds, merged, n / fps


def subtitles_zone(video, every=0.5):
    """Bande des sous-titres incrustés : texte clair ou vif bordé de sombre, stable d'une image à l'autre."""
    import cv2
    import numpy as np
    heat, samples, text_px, letters, words = None, 0, [], [], []
    for _, rgb in _frames(video, 1 / every, 360, gray=False):
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        Hh, Ss, Vv = hsv[..., 0], hsv[..., 1], hsv[..., 2]
        light = ((Vv > 215) & (Ss < 60)) | ((Ss > 140) & (Vv > 190))
        dark = cv2.dilate(((Vv < 70).astype(np.uint8)), np.ones((5, 5), np.uint8)) > 0
        mask = (light & dark).astype(np.uint8)
        h, w = mask.shape
        mask[:, :int(w * 0.04)] = 0
        mask[:, int(w * 0.96):] = 0
        heat = mask.astype(np.float32) if heat is None else heat + mask
        samples += 1
        text_px.append((rgb, mask))
    if not samples:
        return None
    h, w = heat.shape
    prof = np.convolve(heat.sum(axis=1), np.ones(9) / 9, mode="same")
    prof[:int(h * 0.04)] = 0
    prof[int(h * 0.96):] = 0
    peak = int(prof.argmax())
    if prof[peak] < samples * w * 0.004:
        return {"found": False}
    rows = np.where(prof > prof[peak] * 0.35)[0]
    rows = rows[(rows > peak - h * 0.12) & (rows < peak + h * 0.12)]
    top, bot = int(rows.min()), int(rows.max())
    # des sous-titres : texte concentré dans une bande, et qui change (un menu ou un logo reste identique)
    concentration = float(heat[top:bot + 1].sum() / max(1.0, heat.sum()))
    bands = [m[top:bot + 1].astype(bool) for _, m in text_px]
    changes = [np.logical_xor(a_, b_).sum() / max(1, a_.sum() + b_.sum()) for a_, b_ in zip(bands, bands[1:])
               if a_.sum() + b_.sum() > w * 0.02]
    change = float(statistics.median(changes)) if changes else 0.0
    if concentration < 0.3 or change < 0.25:
        return {"found": False, "concentration": round(concentration, 2), "change": round(change, 2)}
    present, white, vivid = 0, 0, []
    bh = bot - top + 1
    pad = int(bh * 0.6)
    y0, y1 = max(0, top - pad), min(h, bot + pad + 1)
    for rgb, mask in text_px:
        if mask[top:bot + 1].sum() < w * 0.01:
            continue
        present += 1
        hsv = cv2.cvtColor(rgb[y0:y1], cv2.COLOR_RGB2HSV)
        light = (((hsv[..., 2] > 215) & (hsv[..., 1] < 60)) | ((hsv[..., 1] > 140) & (hsv[..., 2] > 190))).astype(np.uint8)
        dark = (hsv[..., 2] < 70).astype(np.uint8)
        ring = cv2.dilate(light, np.ones((5, 5), np.uint8)) - light
        n, lab, st, _ = cv2.connectedComponentsWithStats(light, 8)
        boxes = []
        for i in range(1, n):
            x, y, bw, bhh, area = st[i]
            if area < 6 or bhh < 4 or bhh > bh * 2.5 or bw > w * 0.25:
                continue  # grands aplats (fond, décor) exclus
            r = ring[y:y + bhh + 4, x:x + bw + 4]
            if r.sum() and (dark[y:y + bhh + 4, x:x + bw + 4][r > 0]).mean() > 0.35:
                boxes.append(st[i])
                comp = lab[y:y + bhh, x:x + bw] == i
                px = rgb[y0:y1][y:y + bhh, x:x + bw][comp]
                ph = hsv[y:y + bhh, x:x + bw][comp]
                white += int((ph[:, 1] < 60).sum())
                vivid.append(px[ph[:, 1] > 140])
        if not boxes:
            continue
        letters += [b[3] for b in boxes]
        xs = sorted((b[0], b[0] + b[2]) for b in boxes)
        hl = statistics.median([b[3] for b in boxes])
        gaps = [xs[i + 1][0] - max(e for _, e in xs[:i + 1]) for i in range(len(xs) - 1)]
        words.append(1 + sum(g > hl * 0.45 for g in gaps))
    if present < max(2, samples * 0.25):
        return {"found": False}
    viv = np.concatenate(vivid) if vivid else np.zeros((0, 3))
    total = white + len(viv)
    accent = None
    if len(viv) > total * 0.06:
        hsv = cv2.cvtColor(viv.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_RGB2HSV).reshape(-1, 3)
        hist = np.bincount(hsv[:, 0] // 10, minlength=18)
        sel = viv[(hsv[:, 0] // 10) == hist.argmax()]
        accent = "#{:02X}{:02X}{:02X}".format(*[int(x) for x in np.median(sel, axis=0)])
    lh = sorted(letters)[int(len(letters) * 0.8)] if letters else (bot - top) * 0.6  # capitales ≈ 80e centile
    yc = (top + bot) / 2 / h
    return {"found": True, "presence": round(present / samples, 2), "concentration": round(concentration, 2),
            "change": round(change, 2), "band": [round(top / h, 3), round(bot / h, 3)],
            "y": round(yc, 3), "letter_px": int(lh), "frame": [w, h],
            "size": round(float(lh) / CAPS / min(w, h) / 1.15, 3),
            "max_words": int(min(6, max(1, round(statistics.median(words))))) if words else None,
            "primary": "#FFFFFF" if white >= 0.3 * total else accent, "accent": accent}


def annotate(video, zone, out):
    """Planche affinage.png : 3 images avec la bande des sous-titres détectée."""
    from .common import ffmpeg
    d = probe(video)["duration"]
    vf = "scale=360:-2"
    if zone and zone.get("found"):
        y0, y1 = zone["band"]
        vf += f",drawbox=x=0:y=ih*{y0}:w=iw:h=ih*{y1 - y0:.3f}:color=0xFFD935@0.9:t=3"
    ffmpeg(["-i", video, "-vf", f"fps={3 / max(d, 1):.4f},{vf},tile=3x1:padding=6:color=black", "-frames:v", "1", out])
    return out


def decide(kinds, zooms, dur, zone):
    """Mesures → réglages du style."""
    out, rep = {}, {}
    if kinds:
        counts = {k: kinds.count(k) for k in set(kinds)}
        rep["coupes"] = counts
        fancy = {k: v for k, v in counts.items() if k != "hard"}
        n_f = sum(fancy.values())
        if n_f < 0.25 * len(kinds):
            kind = "hard"
        elif len([v for v in fancy.values() if v >= 0.2 * n_f]) > 1:
            kind = "mix"
        else:
            kind = max(fancy, key=fancy.get)
        out["cut"] = {"transition": kind}
        if kind != "hard":
            out["cut"]["transition_every"] = int(min(3, max(1, round(len(kinds) / max(1, n_f)))))
    if dur:
        rate = len(zooms) / dur * 60
        rep["zooms_par_minute"] = round(rate, 1)
        if zooms:
            pat = [z["kind"] for z in zooms]
            sc = [z["scale"] for z in zooms if z["kind"] == "punch"] or [z["scale"] for z in zooms]
            out["zoom"] = {"enabled": True, "every_s": round(min(12, max(1.5, 60 / max(rate, 0.1))), 1),
                           "scale": round(min(1.3, max(1.05, statistics.median(sc))), 2),
                           "pattern": ["punch", "pulse"] if pat.count("punch") > 2 * pat.count("ease")
                           else ["ease"] if pat.count("ease") > 2 * pat.count("punch") else ["punch", "pulse", "ease"]}
        elif dur > 10:
            out["zoom"] = {"every_s": 10.0, "pattern": ["ease"]}
    if zone is not None:
        rep["sous_titres"] = zone
        if zone.get("found"):
            y = zone["y"]
            pos = "upper" if y < 0.4 else "center" if y < 0.68 else "lower"
            sub = {"enabled": True, "position": pos, "size": round(min(0.11, max(0.035, zone["size"])), 3),
                   "margin_v": round(zone["band"][0] if pos == "upper" else 1 - zone["band"][1], 3)}
            if zone.get("max_words"):
                sub["max_words"] = zone["max_words"]
            if zone.get("primary"):
                sub["primary"] = zone["primary"]
            if zone.get("accent"):
                sub["highlight"] = zone["accent"]
            out["subtitles"] = sub
        # pas de sous-titres incrustés dans la référence : on garde ceux du style (le rush en aura quand même)
    return out, rep


def refine(name):
    from .common import deep_merge
    from .style_clone import scene_cuts
    path = STYLES / f"{name}.json"
    style = load_json(path)
    if not style:
        raise SystemExit(f"Style inconnu : {name}")
    base = STYLES / "refs" / name
    profiles = sorted(base.glob("*/profile.json"))
    videos = [Path(load_json(p)["source"]) for p in profiles if Path(load_json(p)["source"]).exists()]
    if not videos:
        raise SystemExit(f"Aucune vidéo de référence pour « {name} » : clone d'abord le style (monteur style … --name {name}).")
    allk, allz, total, zones = [], [], 0.0, []
    for v in videos:
        log(f"Affinage — coupes et zooms : {v.name}…")
        kinds, zooms, dur = cuts_and_zooms(v, scene_cuts(v))
        allk += kinds
        allz += zooms
        total += dur
        log(f"Affinage — sous-titres : {v.name}…")
        zones.append(subtitles_zone(v))
        annotate(v, zones[-1], base / v.stem / "affinage.png")
    zone = next((z for z in zones if z and z.get("found")), zones[0] if zones else None)
    over, rep = decide(allk, allz, total, zone)
    style = deep_merge(style, over)
    style.setdefault("reference", {})["affinage"] = rep
    style.setdefault("library", {})["etat"] = "Affiné"
    style["_todo_claude"] = ("Affinage auto fait (cuts, zooms, bande/taille/couleurs des sous-titres). Reste à vérifier "
                             "sur affinage.png / frame_*.png : police exacte, majuscules, cartouche, cartes.")
    save_json(path, style)
    log(f"Style « {name} » affiné → styles/{name}.json")
    for k, v in over.items():
        log(f"  {k} : {v}")
    return style, rep
