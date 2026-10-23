"""Import d'une transcription faite ailleurs (connecteur WhisperAI de Claude, OpenAI, sous-titres…) → transcript.json.

Formats : SRT, VTT, JSON (liste de segments {start, end, text} en secondes ou millisecondes, avec ou sans
« words »), texte horodaté « [mm:ss] … ». Sans horodatage par mot, chaque mot reçoit une part du segment
proportionnelle à sa longueur — suffisant pour les sous-titres karaoké et la coupe.
"""
import json
import re
from pathlib import Path

from .common import log, save_json

TC = r"(?:(\d+):)?(\d{1,2}):(\d{2})(?:[.,](\d{1,3}))?"
SPEAKER = re.compile(r"^\s*(?:\[[^\]]{1,40}\]|[A-ZÀ-Ü][\w .'-]{0,30}:)\s+")


def _sec(h, m, s, ms):
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + (int((ms or "0").ljust(3, "0")) / 1000)


def _clean(text):
    text = re.sub(r"<[^>]+>", "", text)          # balises VTT / HTML
    text = SPEAKER.sub("", text)                 # « Speaker 1: », « [Nom] »
    return " ".join(text.split())


def parse_subtitles(src):
    segs = []
    for block in re.split(r"\n\s*\n", src.replace("\r", "")):
        m = re.search(TC + r"\s*-->\s*" + TC, block)
        if not m:
            continue
        g = m.groups()
        text = _clean(" ".join(block[m.end():].strip().splitlines()))
        if text:
            segs.append({"start": _sec(*g[:4]), "end": _sec(*g[4:]), "text": text})
    return segs


def parse_timed_text(src):
    """Lignes « [00:12] texte » ou « 00:12 texte » : la fin d'un segment = début du suivant."""
    rows = []
    for line in src.replace("\r", "").splitlines():
        m = re.match(r"^\s*\[?" + TC + r"\]?\s+(.*)$", line)
        if m and _clean(m.group(5)):
            rows.append((_sec(*m.groups()[:4]), _clean(m.group(5))))
    return [{"start": t, "end": rows[i + 1][0] if i + 1 < len(rows) else t + max(1.5, len(x) / 14), "text": x}
            for i, (t, x) in enumerate(rows)]


def _num(seg, *keys):
    for k in keys:
        if seg.get(k) is not None:
            v = seg[k]
            if isinstance(v, str):
                m = re.fullmatch(TC, v.strip())
                return _sec(*m.groups()) if m else float(v)
            return float(v)
    return None


def parse_json(src, duration=None):
    data = json.loads(src)
    if isinstance(data, dict):
        data = data.get("segments") or data.get("utterances") or data.get("results") or data.get("words") or []
    segs, ms = [], False
    for s in data:
        a = _num(s, "start", "startTime", "start_time", "from", "offset")
        b = _num(s, "end", "endTime", "end_time", "to")
        seg = {"start": a, "end": b, "text": _clean(str(s.get("text") or s.get("content") or s.get("word") or ""))}
        if s.get("words"):
            seg["words"] = [{"w": _clean(str(w.get("word") or w.get("text") or w.get("w") or "")),
                             "start": _num(w, "start", "startTime", "start_time"),
                             "end": _num(w, "end", "endTime", "end_time")} for w in s["words"]]
        if seg["start"] is not None and (seg["text"] or seg.get("words")):
            segs.append(seg)
    # millisecondes ? > 10 h en « secondes », ou (durée du rush connue) bien au-delà du rush alors qu'en ms ça tombe juste
    top = max([s["end"] or s["start"] for s in segs] or [0])
    ms = top > 36000 or bool(duration and top > duration * 1.5 + 5 and top / 1000 <= duration * 1.5 + 5)
    if ms:
        for s in segs:
            s["start"], s["end"] = s["start"] / 1000, (s["end"] or s["start"]) / 1000
            for w in s.get("words", []):
                w["start"], w["end"] = (w["start"] or 0) / 1000, (w["end"] or 0) / 1000
    return segs


def _speech(start, end, silences):
    """Intervalles parlés de [start, end] : le segment moins les blancs détectés dans l'audio."""
    out, t = [], start
    for a, b in silences:
        if b <= t or a >= end:
            continue
        if a > t + 0.05:
            out.append((t, a))
        t = max(t, b)
    if end > t + 0.05:
        out.append((t, end))
    return out or [(start, end)]


def _place(pos, spans):
    """Position « parlée » (secondes cumulées) → temps réel dans les intervalles."""
    for a, b in spans:
        if pos <= b - a:
            return a + pos
        pos -= b - a
    return spans[-1][1]


def segments_to_words(segs, silences=None):
    words = []
    for s in segs:
        if s.get("words") and all(w.get("start") is not None for w in s["words"]):
            words += [{"w": w["w"], "start": round(w["start"], 3), "end": round(w["end"] or w["start"] + .3, 3), "p": 1.0}
                      for w in s["words"] if w["w"]]
            continue
        toks = []
        for tok in s["text"].split():  # « vraiment ? » : la ponctuation isolée rejoint le mot précédent
            if toks and re.fullmatch(r"[?!:;»…%]+", tok):
                toks[-1] += "\u202f" + tok if tok[0] in "?!:;»%" else tok
            else:
                toks.append(tok)
        if not toks:
            continue
        start, end = s["start"], s["end"] if s.get("end") and s["end"] > s["start"] else s["start"] + .35 * len(toks)
        weights = [len(t) + 2 for t in toks]
        spans = _speech(start, end, silences or [])  # les mots ne tombent pas dans les pauses
        span, t = sum(b - a for a, b in spans), 0.0
        for tok, wgt in zip(toks, weights):
            d = span * wgt / sum(weights)
            a, b = _place(t + 1e-6, spans), _place(t + d * 0.92, spans)
            b = min(b, next((e for s0, e in spans if s0 - 1e-6 <= a <= e), b))  # un mot n'enjambe pas une pause
            words.append({"w": tok, "start": round(a, 3), "end": round(max(b, a + 0.05), 3), "p": 0.9})
            t += d
    words.sort(key=lambda w: w["start"])
    return words


def load(path, duration=None):
    path = Path(path)
    src = path.read_text(encoding="utf-8-sig", errors="replace")
    segs = None
    if path.suffix.lower() == ".json" or src.lstrip().startswith(("[", "{")):
        try:
            segs = parse_json(src, duration)
        except json.JSONDecodeError:  # « [00:05] texte » commence aussi par un crochet
            if path.suffix.lower() == ".json":
                raise SystemExit(f"{path.name} n'est pas un JSON valide.")
    if segs is not None:
        pass
    elif "-->" in src:
        segs = parse_subtitles(src)
    else:
        segs = parse_timed_text(src)
    if not segs:
        raise SystemExit(f"Aucun segment horodaté reconnu dans {path.name} (attendu : SRT, VTT, JSON ou « [mm:ss] texte »).")
    return segs


def import_transcript(ws, path, language="fr"):
    """Écrit <rush>.monteur/transcript.json ; les fichiers dérivés de l'ancienne transcription sont écartés."""
    silences, duration = [], None
    try:  # cale les mots sur la voix réelle (pauses en fin de phrase, virgules)
        from .common import probe
        src_info = probe(ws.source)
        duration = src_info["duration"]
        if src_info["has_audio"]:
            from .cut import detect_silences
            silences = detect_silences(ws.source, -35, 0.12)
    except Exception:
        pass
    words = segments_to_words(load(path, duration), silences)
    for derived in (ws.cut_video, ws.cut_transcript):
        Path(derived).unlink(missing_ok=True)
    if ws.plan.exists():  # le plan dépendait de l'ancienne transcription : on le garde de côté
        ws.plan.replace(ws.plan.with_name("plan.avant-import.json"))
    data = {"language": language, "words": words, "text": " ".join(w["w"] for w in words), "source": Path(path).name}
    save_json(ws.transcript, data)
    log(f"{len(words)} mots importés depuis {Path(path).name} → {ws.transcript}")
    return data
