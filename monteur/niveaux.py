"""Niveaux audio mesurés (« mesurés, jamais devinés ») : la musique est posée à N dB SOUS la voix,
d'après des fenêtres RMS de 0,5 s de la voix réelle et de la musique choisie — et non avec un gain fixe."""
import subprocess

from .common import log


def windows_db(path, win=0.5, seconds=None, start=0.0):
    """Niveau RMS (dBFS) de chaque fenêtre de `win` secondes ; [] si le fichier n'a pas de son."""
    import numpy as np
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{start:.3f}", *(["-t", f"{seconds:.3f}"] if seconds else []),
           "-i", str(path), "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    x = np.frombuffer(raw, "<i2").astype(np.float32) / 32768.0
    n = int(16000 * win)
    if len(x) < n:
        return []
    fr = x[: len(x) // n * n].reshape(-1, n)
    rms = np.sqrt((fr ** 2).mean(axis=1))
    return [float(v) for v in 20 * np.log10(np.maximum(rms, 1e-6))]


def voice_db(path):
    """Niveau médian de la PAROLE (fenêtres à moins de 25 dB du maximum, silences exclus)."""
    import statistics
    w = windows_db(path)
    if not w:
        return None
    top = max(w)
    speech = [v for v in w if v > max(top - 25, -55)]
    return statistics.median(speech) if speech else None


def music_db(path, seconds=90):
    import statistics
    w = [v for v in windows_db(path, seconds=seconds) if v > -60]
    return statistics.median(w) if w else None


def music_gains(voice_src, music, under_body=21.0, under_hook=12.0):
    """(gain accroche, gain corps) linéaires pour la musique, ou None si la mesure est impossible."""
    v, m = voice_db(voice_src), music_db(music)
    if v is None or m is None:
        return None
    gb = 10 ** ((v - under_body - m) / 20)
    gh = 10 ** ((v - under_hook - m) / 20)
    log(f"Musique mesurée : voix {v:.1f} dB, musique {m:.1f} dB → accroche −{under_hook:g} dB, corps −{under_body:g} dB "
        "sous la voix")
    return min(gh, 4.0), min(gb, 4.0)
