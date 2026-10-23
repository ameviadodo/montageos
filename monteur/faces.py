"""Détection de visages : YuNet (réseau OpenCV, fiable sur toutes les carnations, visages partiellement masqués)
avec repli Haar. Les cascades de Haar seules ratent beaucoup de visages à peau foncée : le recadrage ne suivait pas
l'orateur et le filtre des B-roll laissait passer d'autres personnes.
Modèle : assets/models/face_detection_yunet_2023mar.onnx (MIT, opencv_zoo), téléchargé au premier usage."""
from .common import ASSETS, log

MODEL = ASSETS / "models" / "face_detection_yunet_2023mar.onnx"
URL = ("https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/"
       "face_detection_yunet_2023mar.onnx")
_state = {}


def _yunet_model():
    if MODEL.exists() and MODEL.stat().st_size > 100_000:
        return MODEL
    if _state.get("dl_failed"):
        return None
    try:
        import urllib.request
        MODEL.parent.mkdir(parents=True, exist_ok=True)
        tmp = MODEL.with_suffix(".part")
        urllib.request.urlretrieve(URL, tmp)
        if tmp.stat().st_size < 100_000:  # pointeur Git LFS, page d'erreur…
            raise OSError("fichier incomplet")
        tmp.replace(MODEL)
        log("Détecteur de visages YuNet installé → assets/models/")
        return MODEL
    except Exception:
        _state["dl_failed"] = True
        return None


def available():
    try:
        import cv2  # noqa: F401
        return True
    except ImportError:
        return False


def detect(img_bgr, min_score=0.6):
    """[(x, y, w, h, score)] des visages d'une image BGR (numpy)."""
    import cv2
    h, w = img_bgr.shape[:2]
    model = _yunet_model() if hasattr(cv2, "FaceDetectorYN") else None
    if model:
        try:
            key = ("yunet", w, h)
            if key not in _state:
                _state[key] = cv2.FaceDetectorYN.create(str(model), "", (w, h), min_score, 0.3, 50)
            _, faces = _state[key].detect(img_bgr)
            return [(int(f[0]), int(f[1]), int(f[2]), int(f[3]), float(f[-1])) for f in (faces if faces is not None else [])]
        except cv2.error:
            pass
    if "haar" not in _state:
        _state["haar"] = [cv2.CascadeClassifier(cv2.data.haarcascades + n) for n in
                          ("haarcascade_frontalface_default.xml", "haarcascade_profileface.xml")]
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY) if img_bgr.ndim == 3 else img_bgr
    for cas in _state["haar"]:
        found = cas.detectMultiScale(gray, 1.1, 5, minSize=(24, 24))
        if len(found):
            return [(int(x), int(y), int(fw), int(fh), 0.5) for x, y, fw, fh in found]
    return []
