"""Suivi du visage : recadrage 16:9 → 9:16 qui suit l'orateur et zooms centrés sur lui (OpenCV, facultatif)."""
import statistics

from .common import load_json, log, save_json


def detect(video, every=0.5):
    """Liste de (t, cx, cy) en fractions de l'image, visage le plus grand par échantillon."""
    try:
        import cv2
        cv2.CascadeClassifier  # retiré du paquet principal dans OpenCV 5 → on exige 4.x (setup.sh)
    except (ImportError, AttributeError):
        log("Suivi du visage indisponible (pip install 'opencv-python-headless<5') — cadrage fixe.")
        return None
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    step = max(1, int(round(fps * every)))
    front = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    prof = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")
    out, i = [], 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if i % step == 0:
            ok, frame = cap.retrieve()
            if ok:
                h, w = frame.shape[:2]
                scale = 480 / w
                gray = cv2.cvtColor(cv2.resize(frame, (480, int(h * scale))), cv2.COLOR_BGR2GRAY)
                faces = front.detectMultiScale(gray, 1.15, 5, minSize=(28, 28))
                if len(faces) == 0:
                    faces = prof.detectMultiScale(gray, 1.15, 5, minSize=(28, 28))
                if len(faces):
                    x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
                    gh = gray.shape[0]
                    out.append((round(i / fps, 2), round((x + fw / 2) / 480, 4), round((y + fh / 2) / gh, 4)))
        i += 1
    cap.release()
    return out


def track(ws, video):
    """Calcule (et met en cache) la position du visage pour la vidéo de base."""
    cache = ws.dir / "focus.json"
    data = load_json(cache)
    if data and data.get("video") == str(video):
        return data
    faces = detect(video)
    if faces is None:
        return None
    data = {"video": str(video), "faces": faces}
    if faces:
        data["median"] = [statistics.median(f[1] for f in faces), statistics.median(f[2] for f in faces)]
    save_json(cache, data)
    log(f"Visage détecté sur {len(faces)} échantillons" if faces else "Aucun visage détecté (cadrage centré)")
    return data


def keyframes(faces, window=2.0, min_move=0.03):
    """Lisse la trajectoire horizontale (médiane glissante) et ne garde que les vrais déplacements."""
    if not faces:
        return []
    end = faces[-1][0]
    keys, t = [], 0.0
    while t <= end + window:
        pts = [f[1] for f in faces if abs(f[0] - t) <= window]
        if pts:
            x = statistics.median(pts)
            if not keys or abs(x - keys[-1][1]) >= min_move:
                keys.append((round(t, 2), round(x, 4)))
        t += window
    return keys


def crop_x_expr(faces, src_w, crop_w):
    """Expression ffmpeg de la position x du recadrage (interpolation entre images clés, bornée)."""
    keys = keyframes(faces)
    if not keys:
        return None
    to_x = lambda cx: max(0.0, min(src_w - crop_w, cx * src_w - crop_w / 2))
    if len(keys) == 1:
        return f"{to_x(keys[0][1]):.1f}"
    terms = []
    for (t0, x0), (t1, x1) in zip(keys, keys[1:]):
        a, b = to_x(x0), to_x(x1)
        dur = max(0.01, min(0.8, t1 - t0))  # transition douce de 0,8 s max avant l'image clé suivante
        s = t1 - dur
        terms.append(f"between(t,{t0},{t1})*if(lt(t,{s:.2f}),{a:.1f},{a:.1f}+({b - a:.1f})*(t-{s:.2f})/{dur:.2f})")
    last = to_x(keys[-1][1])
    return "+".join(terms) + f"+gte(t,{keys[-1][0]})*{last:.1f}"
