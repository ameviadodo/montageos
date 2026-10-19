"""Suppression des blancs, des hésitations et des répétitions / prises ratées."""
import re
import unicodedata
from difflib import SequenceMatcher

from .common import ffmpeg, log, probe, run, save_json


def norm(word):
    w = unicodedata.normalize("NFKD", word.lower())
    w = "".join(c for c in w if not unicodedata.combining(c))
    return re.sub(r"[^\w']", "", w)


def detect_silences(video, db=-35, min_d=0.45):
    res = run(["ffmpeg", "-hide_banner", "-nostats", "-i", video, "-af",
               f"silencedetect=noise={db}dB:d={min_d}", "-f", "null", "-"], capture=True)
    sil, start = [], None
    for line in res.stderr.splitlines():
        m = re.search(r"silence_start: (-?[\d.]+)", line)
        if m:
            start = max(0.0, float(m.group(1)))
        m = re.search(r"silence_end: ([\d.]+)", line)
        if m and start is not None:
            sil.append((start, float(m.group(1))))
            start = None
    if start is not None:
        sil.append((start, probe(video)["duration"]))
    return sil


def phrases(words, gap=0.3):
    out, cur = [], []
    for i, w in enumerate(words):
        if cur and (w["start"] - words[cur[-1]]["end"] > gap):
            out.append(cur)
            cur = []
        cur.append(i)
        if re.search(r"[.!?…]$", w["w"]):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def find_removals(words, cfg):
    """Renvoie {index_mot: raison} pour les mots à supprimer."""
    drop = {}
    toks = [norm(w["w"]) for w in words]
    if cfg.get("remove_fillers", True):
        fillers = {norm(f) for f in cfg.get("fillers", [])}
        for i, t in enumerate(toks):
            if t in fillers:
                drop[i] = "filler"
    # bégaiements / n-grammes répétés à la suite : « je pense que je pense que »
    for n in (5, 4, 3, 2, 1):
        i = 0
        while i + 2 * n <= len(toks):
            a, b = toks[i:i + n], toks[i + n:i + 2 * n]
            if all(a) and a == b and not any(k in drop for k in range(i, i + n)):
                for k in range(i, i + n):
                    drop[k] = "repeat"
                i += n
            else:
                i += 1
    # prises ratées : une phrase reprise juste après (on garde la dernière prise)
    if cfg.get("remove_retakes", True):
        thr = cfg.get("retake_similarity", 0.72)
        ph = phrases(words)
        for pi, p in enumerate(ph):
            ta = " ".join(toks[k] for k in p if k not in drop)
            if len(ta) < 6:
                continue
            for q in ph[pi + 1:pi + 4]:
                tb = " ".join(toks[k] for k in q if k not in drop)
                head = tb[:len(ta) + 4]
                ratio = SequenceMatcher(None, ta, head).ratio()
                if ratio >= thr and len(tb) >= len(ta) * 0.8:
                    for k in p:
                        drop.setdefault(k, "retake")
                    break
    return drop


def merge(iv, gap=0.0):
    iv = sorted(iv)
    out = []
    for s, e in iv:
        if out and s <= out[-1][1] + gap:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out


def subtract(keep, holes):
    out = []
    for s, e in keep:
        cur = [[s, e]]
        for hs, he in holes:
            nxt = []
            for a, b in cur:
                if he <= a or hs >= b:
                    nxt.append([a, b])
                else:
                    if hs > a:
                        nxt.append([a, hs])
                    if he < b:
                        nxt.append([he, b])
            cur = nxt
        out.extend(cur)
    return out


def build_edl(video, transcript, cfg):
    dur = probe(video)["duration"]
    pad, min_sil = cfg.get("padding", 0.08), cfg.get("min_silence", 0.45)
    sil = detect_silences(video, cfg.get("silence_db", -35), min_sil)
    removed = {}
    if transcript and transcript.get("words"):
        words = transcript["words"]
        removed = find_removals(words, cfg)
        keep = [[max(0, w["start"] - pad), min(dur, w["end"] + pad)]
                for i, w in enumerate(words) if i not in removed]
        keep = merge(keep, gap=min_sil)
        # la fusion peut enjamber un mot retiré : on le ré-excise explicitement
        for i in removed:
            prev_end = words[i - 1]["end"] if i > 0 and (i - 1) not in removed else words[i]["start"]
            nxt = words[i + 1]["start"] if i + 1 < len(words) and (i + 1) not in removed else words[i]["end"]
            keep = subtract(keep, [(max(prev_end, words[i]["start"] - 0.02), min(nxt, words[i]["end"] + 0.02))])
        holes = [(s + pad, e - pad) for s, e in sil if e - s > min_sil + 2 * pad]
        keep = subtract(keep, holes)
    else:
        keep = subtract([[0, dur]], [(s + pad, e - pad) for s, e in sil])
    keep = [[round(s, 3), round(e, 3)] for s, e in merge(keep) if e - s >= cfg.get("min_keep", 0.25)]
    kept = sum(e - s for s, e in keep)
    stats = {"source_duration": round(dur, 2), "kept_duration": round(kept, 2),
             "removed_s": round(dur - kept, 2), "segments": len(keep),
             "removed_words": {r: list(removed.values()).count(r) for r in set(removed.values())}}
    removed_txt = [{"i": i, "w": transcript["words"][i]["w"], "t": transcript["words"][i]["start"], "why": r}
                   for i, r in sorted(removed.items())] if removed else []
    return {"keep": keep, "stats": stats, "removed": removed_txt}


def render_cut(video, edl, out, workdir):
    info = probe(video)
    lines, n = [], len(edl["keep"])
    for i, (s, e) in enumerate(edl["keep"]):
        d = e - s
        f = min(0.012, d / 4)
        lines.append(f"[0:v]trim=start={s}:end={e},setpts=PTS-STARTPTS[v{i}];")
        if info["has_audio"]:
            lines.append(f"[0:a]atrim=start={s}:end={e},asetpts=PTS-STARTPTS,"
                         f"afade=t=in:d={f},afade=t=out:st={d - f:.3f}:d={f}[a{i}];")
    if info["has_audio"]:
        lines.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[vo][ao]")
        maps = ["-map", "[vo]", "-map", "[ao]"]
    else:
        lines.append("".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vo]")
        maps = ["-map", "[vo]"]
    script = workdir / "cut_filter.txt"
    script.write_text("\n".join(lines))
    ffmpeg(["-i", video, "-filter_complex_script", script, *maps, "-c:v", "libx264",
            "-preset", "fast", "-crf", "16", "-r", str(info["fps"]), "-c:a", "aac", "-b:a", "256k", out])
    log(f"Coupe : {edl['stats']['source_duration']}s → {edl['stats']['kept_duration']}s "
        f"({edl['stats']['segments']} segments) → {out}")


def remap_transcript(transcript, keep):
    words, offset, out = transcript["words"], 0.0, []
    bounds = []
    for s, e in keep:
        bounds.append((s, e, offset))
        offset += e - s
    for w in words:
        for s, e, off in bounds:
            if w["start"] >= s - 0.02 and w["end"] <= e + 0.02:
                out.append({**w, "start": round(max(0, w["start"] - s) + off, 3),
                            "end": round(min(e, w["end"]) - s + off, 3)})
                break
    return {**transcript, "words": out, "text": " ".join(w["w"] for w in out)}


def cut(ws, style, transcript=None):
    cfg = style.get("cut", {})
    edl = build_edl(ws.source, transcript, cfg)
    save_json(ws.edl, edl)
    render_cut(ws.source, edl, ws.cut_video, ws.dir)
    if transcript:
        save_json(ws.cut_transcript, remap_transcript(transcript, edl["keep"]))
    return edl
