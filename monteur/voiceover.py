"""Voix off française : Edge TTS (voix neuronales, en ligne) sinon espeak-ng + MBROLA (hors-ligne)."""
import asyncio
import re
import shutil
from pathlib import Path

from .common import ffmpeg, log, probe, run

EDGE_VOICE = "fr-FR-DeniseNeural"   # autres : fr-FR-HenriNeural, fr-FR-VivienneMultilingualNeural, fr-FR-RemyMultilingualNeural
ESPEAK_VOICES = ("mb-fr1", "mb-fr4", "fr-fr")

# Prononciation : mots anglais / sigles que les moteurs français lisent mal
LEXIQUE = {r"\bMonteurOS\b": "Monteur O S", r"\bdraft\b": "drafte", r"\bframes?\b": "frème", r"\breels?\b": "rile",
           r"\bB-roll\b": "bi rôle", r"\bsetup\.sh\b": "setup point S H"}


def prononce(text, engine):
    if engine == "edge":  # les voix neuronales lisent bien l'anglais courant
        return text.replace("MonteurOS", "Monteur O.S.")
    for pat, rep in LEXIQUE.items():
        text = re.sub(pat, rep, text, flags=re.I)
    return text


def _edge(text, out, voice, rate):
    import edge_tts
    mp3 = out.with_suffix(".mp3")
    asyncio.run(edge_tts.Communicate(text, voice or EDGE_VOICE, rate=f"{int(round((rate - 1) * 100)):+d}%").save(str(mp3)))
    ffmpeg(["-i", mp3, "-ar", "48000", "-ac", "1", out])
    mp3.unlink(missing_ok=True)


def _espeak_voice(voice=None):
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if not exe:
        raise RuntimeError("espeak-ng absent (Linux : apt install espeak-ng mbrola-fr1 ; Windows : installeur espeak-ng)")
    if voice:
        return exe, voice
    listed = run([exe, "--voices=mb"], capture=True, check=False).stdout
    mbrola = Path("/usr/share/mbrola")
    for v in ESPEAK_VOICES:
        if not v.startswith("mb-") or (v in listed and (mbrola / v[3:]).exists()):
            return exe, v
    return exe, "fr-fr"


def _espeak(text, out, voice, rate):
    exe, v = _espeak_voice(voice)
    raw = out.with_suffix(".raw.wav")
    run([exe, "-v", v, "-a", "80", "-s", str(int(150 * rate)), "-p", "42", "-g", "3", "-w", raw, text])
    # adoucit le timbre synthétique : passe-haut, léger grave, compression, petite pièce
    ffmpeg(["-i", raw, "-af", "highpass=f=70,lowpass=f=9000,equalizer=f=180:t=q:w=1:g=3,"
            "acompressor=threshold=-20dB:ratio=3:attack=5:release=120,aecho=0.8:0.5:28:0.12", "-ar", "48000", "-ac", "1", out])
    raw.unlink(missing_ok=True)


def engines():
    out = []
    try:
        import edge_tts  # noqa: F401
        out.append("edge")
    except ImportError:
        pass
    if shutil.which("espeak-ng") or shutil.which("espeak"):
        out.append("espeak")
    return out


def synth(text, out, engine="auto", voice=None, rate=1.0):
    """Synthétise `text` en WAV 48 kHz mono. Renvoie (chemin, durée, moteur utilisé)."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    order = ["edge", "espeak"] if engine == "auto" else [engine]
    errors = []
    for eng in order:
        try:
            (_edge if eng == "edge" else _espeak)(prononce(text, eng), out, voice if eng == engine else None, rate)
            return out, probe(out)["duration"], eng
        except Exception as e:  # réseau coupé, module absent… on tente le moteur suivant
            errors.append(f"{eng}: {type(e).__name__}: {str(e)[:120]}")
    raise SystemExit("Voix off impossible — " + " | ".join(errors))


def script(lines, out_dir, engine="auto", voice=None, rate=1.0):
    """Synthétise une liste de répliques ; renvoie [(texte, wav, durée, moteur)]."""
    res = []
    for k, text in enumerate(lines):
        wav, d, eng = synth(text, Path(out_dir) / f"vo_{k:02d}.wav", engine, voice, rate)
        res.append((text, wav, d, eng))
        log(f"  voix {k:02d} [{eng}] {d:4.1f}s — {text[:60]}")
    return res

