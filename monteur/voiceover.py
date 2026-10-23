"""Voix off : ElevenLabs et Inworld (clés API, horodatage des mots), Edge TTS (en ligne, gratuit),
espeak-ng + MBROLA (hors-ligne). En mode « auto », chaque moteur indisponible est contourné par le suivant."""
import asyncio
import base64
import json
import os
import re
import shutil
import urllib.error
import urllib.request
from pathlib import Path

from .common import ffmpeg, log, probe, run

EDGE_VOICE = "fr-FR-DeniseNeural"   # autres : fr-FR-HenriNeural, fr-FR-VivienneMultilingualNeural, fr-FR-RemyMultilingualNeural
ESPEAK_VOICES = ("mb-fr1", "mb-fr4", "fr-fr")
ELEVEN_VOICE = "JBFqnCBsd6RMkjVDRZzb"  # « George », voix prédéfinie multilingue (lit le français)
ELEVEN_MODEL = "eleven_multilingual_v2"
INWORLD_MODEL = "inworld-tts-1.5-max"

# Prononciation : mots anglais / sigles que les moteurs français lisent mal
LEXIQUE = {r"\bMonteurOS\b": "Monteur O S", r"\bdraft\b": "drafte", r"\bframes?\b": "frème", r"\breels?\b": "rile",
           r"\bB-roll\b": "bi rôle", r"\bsetup\.sh\b": "setup point S H"}


def prononce(text, engine):
    if engine in ("elevenlabs", "inworld"):
        return text
    if engine == "edge":  # les voix neuronales lisent bien l'anglais courant
        return text.replace("MonteurOS", "Monteur O.S.")
    for pat, rep in LEXIQUE.items():
        text = re.sub(pat, rep, text, flags=re.I)
    return text


def _edge(text, out, voice, rate):
    import edge_tts
    mp3 = out.with_suffix(".mp3")
    try:  # hors-ligne, edge-tts laisse un .mp3 vide : on le retire même en cas d'échec
        asyncio.run(edge_tts.Communicate(text, voice or EDGE_VOICE, rate=f"{int(round((rate - 1) * 100)):+d}%").save(str(mp3)))
        ffmpeg(["-i", mp3, "-ar", "48000", "-ac", "1", out])
    finally:
        mp3.unlink(missing_ok=True)


def _post(url, payload, headers, timeout=180):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": "MonteurOS/1.0", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"HTTP {e.code} : {body}") from None


def glue(words):
    """« jour ! » : la ponctuation isolée (typographie française) rejoint le mot précédent."""
    out = []
    for w in words:
        if out and re.fullmatch(r"[?!:;»…%.,]+", w["w"]):
            out[-1] = {**out[-1], "w": out[-1]["w"] + "\u202f" + w["w"] if w["w"][0] in "?!:;»%" else out[-1]["w"] + w["w"],
                       "end": w["end"]}
        else:
            out.append(w)
    return out


def _words_from_chars(chars, starts, ends):
    """Alignement par caractère (ElevenLabs) → mots horodatés."""
    words, cur, t0, t1 = [], "", None, None
    for c, a, b in zip(chars, starts, ends):
        if c.isspace():
            if cur:
                words.append({"w": cur, "start": round(t0, 3), "end": round(t1, 3), "p": 1.0})
            cur, t0 = "", None
            continue
        cur += c
        t0 = a if t0 is None else t0
        t1 = b
    if cur:
        words.append({"w": cur, "start": round(t0, 3), "end": round(t1, 3), "p": 1.0})
    return glue(words)


def _elevenlabs(text, out, voice, rate):
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError("ELEVENLABS_API_KEY absente (bin/monteur cles --set ELEVENLABS_API_KEY=…)")
    vid = voice or os.environ.get("ELEVENLABS_VOICE_ID") or ELEVEN_VOICE
    settings = {"stability": 0.5, "similarity_boost": 0.75}
    if abs(rate - 1) > 0.01:
        settings["speed"] = max(0.7, min(1.2, rate))
    res = _post(f"https://api.elevenlabs.io/v1/text-to-speech/{vid}/with-timestamps?output_format=mp3_44100_128",
                {"text": text, "model_id": os.environ.get("ELEVENLABS_MODEL", ELEVEN_MODEL), "voice_settings": settings},
                {"xi-api-key": key})
    mp3 = out.with_suffix(".src.mp3")
    try:
        mp3.write_bytes(base64.b64decode(res["audio_base64"]))
        ffmpeg(["-i", mp3, "-ar", "48000", "-ac", "1", out])
    finally:
        mp3.unlink(missing_ok=True)
    al = res.get("alignment") or res.get("normalized_alignment") or {}
    if al.get("characters"):
        return _words_from_chars(al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"])
    return None


def inworld_voices(lang="fr"):
    from .keys import inworld_auth
    req = urllib.request.Request("https://api.inworld.ai/tts/v1/voices", headers={"Authorization": inworld_auth()})
    with urllib.request.urlopen(req, timeout=30) as r:
        voices = json.load(r).get("voices", [])
    langs = lambda v: [str(x).lower() for x in (v.get("languages") or [v.get("langCode", "")])]
    return [v for v in voices if not lang or any(x.startswith(lang) for x in langs(v))] or voices


def _inworld(text, out, voice, rate):
    if not os.environ.get("INWORLD_API_KEY"):
        raise RuntimeError("INWORLD_API_KEY absente (bin/monteur cles --set INWORLD_API_KEY=…)")
    from .keys import inworld_auth
    vid = voice or os.environ.get("INWORLD_VOICE")
    if not vid:  # première voix française du compte
        vs = inworld_voices("fr")
        if not vs:
            raise RuntimeError("aucune voix Inworld disponible : précise INWORLD_VOICE")
        vid = vs[0].get("voiceId") or vs[0].get("name")
    body = {"text": text[:2000], "voiceId": vid, "modelId": os.environ.get("INWORLD_MODEL", INWORLD_MODEL),
            "audioConfig": {"audioEncoding": "MP3", "speakingRate": max(0.5, min(1.5, rate))},
            "timestampType": "WORD"}
    try:
        res = _post("https://api.inworld.ai/tts/v1/voice", body, {"Authorization": inworld_auth()})
    except RuntimeError as e:  # modèle ou horodatage refusés par ce compte : requête minimale
        if not str(e).startswith("HTTP 400"):
            raise
        body.pop("timestampType")
        body["modelId"] = "inworld-tts-1"
        res = _post("https://api.inworld.ai/tts/v1/voice", body, {"Authorization": inworld_auth()})
    mp3 = out.with_suffix(".src.mp3")
    try:
        mp3.write_bytes(base64.b64decode(res["audioContent"]))
        ffmpeg(["-i", mp3, "-ar", "48000", "-ac", "1", out])
    finally:
        mp3.unlink(missing_ok=True)
    wa = (res.get("timestampInfo") or {}).get("wordAlignment") or {}
    if wa.get("words"):
        return glue([{"w": w.strip(), "start": round(a, 3), "end": round(b, 3), "p": 1.0}
                     for w, a, b in zip(wa["words"], wa["wordStartTimeSeconds"], wa["wordEndTimeSeconds"]) if w.strip()])
    return None  # horodatage absent (français expérimental chez Inworld) : calé sur les silences par voixoff.py


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
    out = [e for e, k in (("elevenlabs", "ELEVENLABS_API_KEY"), ("inworld", "INWORLD_API_KEY")) if os.environ.get(k)]
    try:
        import edge_tts  # noqa: F401
        out.append("edge")
    except ImportError:
        pass
    if shutil.which("espeak-ng") or shutil.which("espeak"):
        out.append("espeak")
    return out


def synth_timed(text, out, engine="auto", voice=None, rate=1.0):
    """Synthétise `text` en WAV 48 kHz mono. Renvoie (chemin, durée, moteur, mots horodatés ou None)."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if engine == "auto":
        # API avec clé d'abord, puis Edge et espeak toujours tentés en secours
        order = [e for e in ("elevenlabs", "inworld") if e in engines()] + ["edge", "espeak"]
    else:
        order = [engine]
    errors = []
    fns = {"elevenlabs": _elevenlabs, "inworld": _inworld, "edge": _edge, "espeak": _espeak}
    for eng in order:
        try:
            v = voice if eng == engine or (voice and _voice_engine(voice) == eng) else None
            words = fns[eng](prononce(text, eng), out, v, rate)
            return out, probe(out)["duration"], eng, words
        except Exception as e:  # réseau coupé, clé refusée, module absent… on contourne avec le moteur suivant
            errors.append(f"{eng}: {type(e).__name__}: {str(e)[:160]}")
            if eng != order[-1]:
                log(f"  voix {eng} indisponible → moteur suivant ({str(e)[:90]})")
    raise SystemExit("Voix off impossible — " + " | ".join(errors))


def _voice_engine(voice):
    """Moteur auquel appartient un nom de voix (mode auto) : « fr-FR-…Neural » → Edge, « mb-fr1 » → espeak,
    identifiant ElevenLabs (20 caractères) → elevenlabs, sinon nom Inworld."""
    if voice.endswith("Neural"):
        return "edge"
    if voice.startswith(("mb-", "fr-")):
        return "espeak"
    return "elevenlabs" if re.fullmatch(r"[A-Za-z0-9]{20}", voice) else "inworld"


def synth(text, out, engine="auto", voice=None, rate=1.0):
    """Synthétise `text` en WAV 48 kHz mono. Renvoie (chemin, durée, moteur utilisé)."""
    wav, d, eng, _ = synth_timed(text, out, engine, voice, rate)
    return wav, d, eng


def script(lines, out_dir, engine="auto", voice=None, rate=1.0):
    """Synthétise une liste de répliques ; renvoie [(texte, wav, durée, moteur)]."""
    res = []
    for k, text in enumerate(lines):
        wav, d, eng = synth(text, Path(out_dir) / f"vo_{k:02d}.wav", engine, voice, rate)
        res.append((text, wav, d, eng))
        log(f"  voix {k:02d} [{eng}] {d:4.1f}s — {text[:60]}")
    return res

