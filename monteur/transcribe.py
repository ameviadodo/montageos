"""Transcription mot à mot (faster-whisper > openai-whisper)."""
from .common import log, save_json, ffmpeg


class NoWhisper(RuntimeError):
    """Aucun moteur de transcription installé dans ce Python."""


def load_model(model="small"):
    """Charge (et télécharge au besoin) le modèle faster-whisper ; repli CPU si CUDA/cuDNN est incomplet."""
    from faster_whisper import WhisperModel
    try:
        return WhisperModel(model, device="auto", compute_type="auto")
    except Exception as e:
        if "cuda" in str(e).lower() or "cudnn" in str(e).lower() or "cublas" in str(e).lower():
            log("GPU indisponible pour Whisper (CUDA/cuDNN) → CPU.")
            return WhisperModel(model, device="cpu", compute_type="int8")
        raise SystemExit(f"Modèle Whisper « {model} » indisponible ({type(e).__name__}: {e}). Vérifie l'accès à "
                         "huggingface.co, essaie --model base, ou indique un dossier de modèle local avec --model.")


def _segments(m, wav, language):
    try:
        return m.transcribe(str(wav), language=language, word_timestamps=True,
                            vad_filter=False, condition_on_previous_text=False)
    except RuntimeError as e:  # DLL CUDA manquante découverte seulement à l'inférence (Windows)
        if "cud" not in str(e).lower() and "cublas" not in str(e).lower():
            raise
        log("GPU indisponible pour Whisper (CUDA/cuDNN) → CPU.")
        from faster_whisper import WhisperModel
        cpu = WhisperModel(m.model_size_or_path, device="cpu", compute_type="int8")
        return cpu.transcribe(str(wav), language=language, word_timestamps=True,
                              vad_filter=False, condition_on_previous_text=False)


def transcribe(video, out_json, model="small", language=None):
    wav = out_json.with_suffix(".wav")
    ffmpeg(["-i", video, "-vn", "-ac", "1", "-ar", "16000", wav])
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
