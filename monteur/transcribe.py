"""Transcription mot à mot (faster-whisper > openai-whisper)."""
from .common import log, save_json, ffmpeg


def transcribe(video, out_json, model="small", language=None):
    wav = out_json.with_suffix(".wav")
    ffmpeg(["-i", video, "-vn", "-ac", "1", "-ar", "16000", wav])
    words, lang = [], language
    try:
        from faster_whisper import WhisperModel
        log(f"faster-whisper ({model}) …")
        try:
            m = WhisperModel(model, device="auto", compute_type="auto")
        except Exception as e:
            raise SystemExit(f"Modèle Whisper « {model} » indisponible ({type(e).__name__}). Vérifie l'accès à "
                             "huggingface.co, essaie --model base, ou place le modèle en cache puis HF_HUB_OFFLINE=1.")
        segs, info = m.transcribe(str(wav), language=language, word_timestamps=True,
                                  vad_filter=False, condition_on_previous_text=False)
        lang = info.language
        for s in segs:
            for w in s.words or []:
                words.append({"w": w.word.strip(), "start": round(w.start, 3),
                              "end": round(w.end, 3), "p": round(w.probability, 3)})
    except ImportError:
        try:
            import whisper
        except ImportError:
            raise SystemExit("Aucun moteur Whisper installé. Lance : bash setup.sh")
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
