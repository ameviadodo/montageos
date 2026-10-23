"""Voix off d'un projet : fichier fourni par l'utilisateur, ou script synthétisé (ElevenLabs, Inworld, Edge, espeak).

La voix devient la piste principale du montage (la prise son du rush passe dessous, `original`), et sa transcription
horodatée remplace celle du rush : sous-titres, zooms, B-roll et habillage se calent sur la voix off.
La vidéo n'est pas coupée (pas de parole à nettoyer) ; si la voix est plus longue, la dernière image est prolongée.
Réglages : <rush>.monteur/voixoff.json (copié dans plan.json["voiceover"], modifiable ; null = voix off coupée).
"""
import re
import shutil
from pathlib import Path

from .common import ffmpeg, load_json, log, probe, save_json

AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac", ".opus", ".webm", ".mp4", ".mov"}


def _dir(ws):
    d = ws.dir / "voixoff"
    d.mkdir(parents=True, exist_ok=True)
    return d


def cfg_path(ws):
    return ws.dir / "voixoff.json"


def settings(ws, plan=None):
    """Voix off active du projet (plan.json prioritaire, null = désactivée), sinon None."""
    if plan is not None and "voiceover" in plan:
        return plan["voiceover"]
    return load_json(cfg_path(ws))


def end_time(vo):
    return float(vo.get("start", 0)) + float(vo.get("duration", 0)) + 0.4 if vo else 0.0


def read_script(src):
    """Texte ou fichier → répliques (une par ligne ; un long paragraphe est découpé en phrases)."""
    p = Path(src)
    text = p.read_text(encoding="utf-8-sig") if len(str(src)) < 400 and p.suffix and p.is_file() else str(src)
    lines = [l.strip() for l in text.replace("\r", "").splitlines() if l.strip() and not l.lstrip().startswith("#")]
    if len(lines) == 1 and len(lines[0]) > 160:
        lines = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", lines[0]) if s.strip()]
    if not lines:
        raise SystemExit("Script vide.")
    return lines


def align_text(text, wav, dur=None):
    """Sans horodatage du moteur : mots répartis sur la parole réelle (les pauses détectées sont sautées)."""
    from .cut import detect_silences
    from .transcript_import import segments_to_words
    dur = dur or probe(wav)["duration"]
    sil = detect_silences(wav, -40, 0.12)
    s0 = next((e for s, e in sil if s <= 0.05), 0.0)
    s1 = next((s for s, e in reversed(sil) if e >= dur - 0.05), dur)
    if s1 - s0 < 0.2:
        s0, s1 = 0.0, dur
    return segments_to_words([{"start": s0, "end": s1, "text": text}], sil)


def _concat(parts, out, gap):
    """WAV des répliques bout à bout, séparés de `gap` secondes."""
    lst = out.with_suffix(".txt")
    sil = out.with_name("silence.wav")
    ffmpeg(["-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", f"{gap:.3f}", "-c:a", "pcm_s16le", sil])
    items = []
    for k, p in enumerate(parts):
        items.append(p)
        if k + 1 < len(parts):
            items.append(sil)
    lst.write_text("".join(f"file '{Path(p).resolve().as_posix()}'\n" for p in items), encoding="utf-8")
    ffmpeg(["-f", "concat", "-safe", "0", "-i", lst, "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", out])
    lst.unlink(missing_ok=True)
    sil.unlink(missing_ok=True)
    return out


def from_script(ws, script, engine="auto", voice=None, rate=1.0, gap=0.35, language="fr"):
    """Script → voix off synthétisée (une réplique après l'autre) + transcription horodatée."""
    from .voiceover import synth_timed
    lines = read_script(script)
    d = _dir(ws)
    for old in d.glob("ligne_*.wav"):
        old.unlink()
    words, t, parts, used = [], 0.0, [], []
    for k, line in enumerate(lines):
        wav, dur, eng, w = synth_timed(line, d / f"ligne_{k:02d}.wav", engine, voice, rate)
        used.append(eng)
        if not w:
            w = align_text(line, wav, dur)
        words += [{**x, "start": round(x["start"] + t, 3), "end": round(x["end"] + t, 3)} for x in w]
        parts.append(wav)
        log(f"  réplique {k + 1}/{len(lines)} [{eng}] {dur:4.1f}s — {line[:60]}")
        t += dur + gap
    (d / "script.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    out = _concat(parts, d / "voix.wav", gap)
    engines = ", ".join(dict.fromkeys(used))
    return install(ws, out, words, f"script synthétisé ({engines})", language, engine=engines)


def from_file(ws, file, script=None, language="fr", model="small"):
    """Voix off fournie (WAV, MP3, M4A… ou vidéo dont on garde le son) ; script facultatif pour des sous-titres exacts."""
    src = Path(file).resolve()
    if not src.is_file():
        raise SystemExit(f"Voix off introuvable : {file}")
    if src.suffix.lower() not in AUDIO_EXT:
        raise SystemExit(f"Format de voix off non pris en charge : {src.suffix} (WAV, MP3, M4A, OGG, FLAC…)")
    d = _dir(ws)
    out = d / "voix.wav"
    ffmpeg(["-i", src, "-vn", "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", out])
    shutil.copy2(src, d / f"original{src.suffix.lower()}")
    words = []
    if script:
        lines = read_script(script)
        (d / "script.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        words = align_text(" ".join(lines), out)
        how = "fichier + script"
    else:
        try:  # Whisper local s'il est là ; sinon on contourne : voix sans sous-titres, script conseillé
            from .transcribe import transcribe
            words = transcribe(out, d / "transcription.json", model, language)["words"]
            how = "fichier transcrit par Whisper"
        except (Exception, SystemExit) as e:
            how = "fichier sans transcription"
            log(f"⚠️  Voix off non transcrite ({type(e).__name__}) : pas de sous-titres. Donne le texte avec "
                "--script (fichier ou texte) pour des sous-titres calés sur la voix.")
    return install(ws, out, words, how, language, engine="fichier")


def install(ws, wav, words, how, language="fr", engine=None, start=0.0, original=0.15):
    """Branche la voix sur le projet : transcription remplacée (celle du rush gardée de côté), vidéo non coupée."""
    vo_dur = probe(wav)["duration"]
    tr = load_json(ws.transcript)
    if tr and tr.get("source") != "voixoff" and not (ws.dir / "transcript.rush.json").exists():
        shutil.copy2(ws.transcript, ws.dir / "transcript.rush.json")
    save_json(ws.transcript, {"language": language, "words": words, "text": " ".join(w["w"] for w in words),
                              "source": "voixoff"})
    ws.cut_video.unlink(missing_ok=True)       # la timeline est celle du rush entier
    ws.cut_transcript.unlink(missing_ok=True)
    vo = {"file": str(Path(wav).relative_to(ws.dir)), "start": start, "duration": round(vo_dur, 3),
          "gain": 1.0, "original": original, "engine": engine, "how": how}
    save_json(cfg_path(ws), vo)
    plan = load_json(ws.plan)
    if plan is not None:
        plan["voiceover"] = vo
        plan["duration"] = round(max(probe(ws.source)["duration"], end_time(vo)), 3)
        save_json(ws.plan, plan)
    log(f"🎙️  Voix off branchée ({how}) : {vo_dur:.1f}s, {len(words)} mots horodatés → {wav}")
    return vo


def remove(ws):
    """Retire la voix off : la transcription du rush revient."""
    cfg_path(ws).unlink(missing_ok=True)
    back = ws.dir / "transcript.rush.json"
    tr = load_json(ws.transcript)
    if back.exists():
        back.replace(ws.transcript)
    elif tr and tr.get("source") == "voixoff":
        ws.transcript.unlink()
    plan = load_json(ws.plan)
    if plan is not None:
        plan.pop("voiceover", None)
        plan["duration"] = round(probe(ws.base_video())["duration"], 3)
        save_json(ws.plan, plan)
    log("Voix off retirée : relance « prep » pour recaler sous-titres et plan sur le rush.")
