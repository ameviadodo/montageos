"""Transcription mot à mot (faster-whisper > openai-whisper)."""
import os

from .common import log, save_json, ffmpeg

os.environ.setdefault("HF_HUB_VERBOSITY", "error")           # pas d'avertissement « HF_TOKEN » : inutile ici
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

TAILLES = {"tiny": "75 Mo", "base": "145 Mo", "small": "480 Mo", "medium": "1,5 Go",
           "large-v2": "3 Go", "large-v3": "3 Go", "large": "3 Go", "turbo": "1,6 Go", "large-v3-turbo": "1,6 Go"}


class NoWhisper(RuntimeError):
    """Aucun moteur de transcription installé dans ce Python."""


def load_model(model="small"):
    """Charge (et télécharge au besoin) le modèle faster-whisper ; repli CPU si CUDA/cuDNN est incomplet."""
    from faster_whisper import WhisperModel
    model = _download(model)
    try:
        return WhisperModel(model, device="auto", compute_type="auto")
    except Exception as e:
        if "cuda" in str(e).lower() or "cudnn" in str(e).lower() or "cublas" in str(e).lower():
            log("GPU indisponible pour Whisper (CUDA/cuDNN) → CPU.")
            return WhisperModel(model, device="cpu", compute_type="int8")
        raise SystemExit(f"Modèle Whisper « {model} » indisponible ({type(e).__name__}: {e}). Vérifie l'accès à "
                         "huggingface.co, essaie --model base, ou indique un dossier de modèle local avec --model.")


def _download(model):
    """Télécharge le modèle avec une barre de progression (faster-whisper la masque) ; renvoie son dossier."""
    if os.path.isdir(model):
        return model
    try:
        import huggingface_hub
        from faster_whisper.utils import _MODELS
    except ImportError:
        return model
    repo = _MODELS.get(model)
    if not repo:
        return model
    files = ["config.json", "preprocessor_config.json", "model.bin", "tokenizer.json", "vocabulary.*"]
    try:
        return huggingface_hub.snapshot_download(repo, allow_patterns=files, local_files_only=True)
    except Exception:
        pass  # pas encore en cache
    log(f"Téléchargement du modèle Whisper « {model} » ({TAILLES.get(model, '?')}, une seule fois) depuis huggingface.co…")
    try:
        path = huggingface_hub.snapshot_download(repo, allow_patterns=files)
    except Exception as e:
        raise SystemExit(f"Téléchargement du modèle Whisper « {model} » impossible ({type(e).__name__}: {e}).\n"
                         "Vérifie la connexion à huggingface.co (pare-feu, proxy, VPN), puis relance. "
                         "Modèle plus léger : --model base. Ou importe une transcription : "
                         "bin/monteur transcription <video> <fichier.srt> --prep")
    log(f"Modèle « {model} » téléchargé → {path}")
    return path


def read_wav(path):
    """WAV 16 kHz mono (déjà extrait par ffmpeg) → échantillons float32, sans passer par PyAV :
    faster-whisper ouvre les fichiers avec av.open(metadata_errors=…), option supprimée dans PyAV 19
    (« open() got an unexpected keyword argument 'metadata_errors' »)."""
    import wave
    import numpy as np
    with wave.open(str(path), "rb") as w:
        if w.getsampwidth() != 2 or w.getframerate() != 16000:
            raise RuntimeError(f"WAV inattendu ({w.getframerate()} Hz, {w.getsampwidth() * 8} bits) : {path}")
        data = np.frombuffer(w.readframes(w.getnframes()), np.int16)
        if w.getnchannels() > 1:
            data = data.reshape(-1, w.getnchannels()).mean(axis=1)
    return data.astype(np.float32) / 32768.0


def _segments(m, wav, language):
    audio = read_wav(wav)
    try:
        return m.transcribe(audio, language=language, word_timestamps=True,
                            vad_filter=False, condition_on_previous_text=False)
    except RuntimeError as e:  # DLL CUDA manquante découverte seulement à l'inférence (Windows)
        if "cud" not in str(e).lower() and "cublas" not in str(e).lower():
            raise
        log("GPU indisponible pour Whisper (CUDA/cuDNN) → CPU.")
        from faster_whisper import WhisperModel
        cpu = WhisperModel(m.model_size_or_path, device="cpu", compute_type="int8")
        return cpu.transcribe(audio, language=language, word_timestamps=True,
                              vad_filter=False, condition_on_previous_text=False)


def transcribe(video, out_json, model="small", language=None):
    wav = out_json.with_suffix(".wav")
    ffmpeg(["-i", video, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", wav])
    words, lang = [], language
    try:
        import faster_whisper  # noqa: F401 — déclenche le repli openai-whisper s'il manque
        log(f"faster-whisper ({model}) …")
        m = load_model(model)
        m.model_size_or_path = model
        segs, info = _segments(m, wav, language)
        lang = info.language
        for s in segs:
            for w in s.words or []:
                words.append({"w": w.word.strip(), "start": round(w.start, 3),
                              "end": round(w.end, 3), "p": round(w.probability, 3)})
    except ImportError:
        try:
            import whisper
        except ImportError:
            wav.unlink(missing_ok=True)
            raise NoWhisper("Aucun moteur Whisper installé dans ce Python")
        log(f"openai-whisper ({model}) …")
        res = whisper.load_model(model).transcribe(str(wav), language=language, word_timestamps=True)
        lang = res.get("language")
        for s in res["segments"]:
            for w in s.get("words", []):
                words.append({"w": w["word"].strip(), "start": round(w["start"], 3),
                              "end": round(w["end"], 3), "p": round(w.get("probability", 1), 3)})
    wav.unlink(missing_ok=True)
    words = [w for w in words if w["w"]]
    data = {"language": lang, "words": words, "text": " ".join(w["w"] for w in words)}
    save_json(out_json, data)
    log(f"{len(words)} mots transcrits → {out_json}")
    return data
