"""Sous-titres animés (ASS) : karaoké mot par mot, pop, emphases colorées + titres animés."""
import re

from .common import log


def ass_color(hex_color, alpha=0):
    h = hex_color.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def ts(t):
    t = max(0, t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def esc(text):
    return text.replace("\\", "").replace("{", "(").replace("}", ")")


def wrap(text, max_chars):
    lines, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > max_chars:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        lines.append(cur)
    return "\\N".join(lines)


def header(w, h, styles):
    lines = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {w}", f"PlayResY: {h}",
             "WrapStyle: 2", "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
             "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
             "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
             "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding"]
    lines += styles
    lines += ["", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    return lines


def group_words(words, max_words, max_chars, gap=0.45):
    groups, cur = [], []
    for w in words:
        txt = " ".join(x["w"] for x in cur + [w])
        if cur and (len(cur) >= max_words or len(txt) > max_chars or w["start"] - cur[-1]["end"] > gap):
            groups.append(cur)
            cur = []
        cur.append(w)
        if re.search(r"[.!?…]$", w["w"]) and len(cur) >= 1:
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    return groups


def build_subtitles(transcript, plan, style, w, h, out):
    c = style["subtitles"]
    base = min(w, h)
    size = int(c["size"] * base * 1.15)
    align = {"lower": 2, "center": 2, "upper": 8}.get(c["position"], 2)
    mv = int(c["margin_v"] * h)
    if c.get("box"):  # style « TikTok natif » : texte sombre sur cartouche claire
        bt, bc = c.get("box_text", "#000000"), c.get("box_color", "#FFFFFF")
        c = {**c, "primary": bt, "outline": bc,
             **{k: bt for k in ("highlight", "emphasis") if c[k].upper() == bc.upper()}}
        border, ow = 3, max(4, int(size * 0.18))
    else:
        border, ow = 1, max(1, round(c["outline_w"] * base))
    st = (f"Style: Sub,{c['font']},{size},{ass_color(c['primary'])},{ass_color(c['highlight'])},"
          f"{ass_color(c['outline'])},{ass_color('#000000', 0x80)},-1,0,0,0,100,100,0,0,{border},"
          f"{ow},{c['shadow']},{align},{int(w * .06)},{int(w * .06)},{mv},1")
    lines = header(w, h, [st])
    words = [dict(x, idx=i) for i, x in enumerate(transcript["words"])]
    emph = set(plan.get("emphasis", []))
    emph_words = {x.lower() for x in plan.get("emphasis_words", [])}
    hidden = [(b["start"], b["end"]) for b in plan.get("broll", []) if b.get("hide_subs")]
    if c.get("hide_during_title", True):
        hidden += [(m["start"], m["end"]) for m in plan.get("motion", []) if m.get("type") in ("title", "cta")]
    hi, em, pr = ass_color(c["highlight"]), ass_color(c["emphasis"]), ass_color(c["primary"])

    def label(word):
        t = esc(word["w"])
        return t.upper() if c["uppercase"] else t

    groups = group_words(words, c["max_words"], c["max_chars"])
    for gi, g in enumerate(groups):
        g_end = g[-1]["end"] + 0.12
        if gi + 1 < len(groups):
            g_end = min(g_end + 0.3, groups[gi + 1][0]["start"])
        if any(s <= g[0]["start"] < e for s, e in hidden):
            continue
        steps = g if c.get("karaoke", True) else [g[0]]
        for k, cur in enumerate(steps):
            s = cur["start"]
            e = steps[k + 1]["start"] if k + 1 < len(steps) else g_end
            if e <= s:
                continue
            parts = []
            for x in g:
                is_em = x["idx"] in emph or x["w"].lower().strip(".,!?") in emph_words
                col = em if is_em else (hi if (c.get("karaoke", True) and x is cur) else pr)
                parts.append(f"{{\\c{col}}}{label(x)}")
            pop = ""
            if c.get("pop", True) and k == 0:
                pop = "\\fscx80\\fscy80\\t(0,90,\\fscx108\\fscy108)\\t(90,160,\\fscx100\\fscy100)"
            lines.append(f"Dialogue: 0,{ts(s)},{ts(e)},Sub,,0,0,0,,{{{pop}}}" + " ".join(parts))
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"Sous-titres : {len(groups)} blocs → {out}")
    return out


def build_motion(plan, style, w, h, out):
    """Animations texte natives (titre d'accroche, lower-third, callout)."""
    m = style["motion"]
    base = min(w, h)
    col, acc = ass_color(m["color"]), ass_color(m["accent"])
    styles = [
        f"Style: Title,{m['font']},{int(base * .11)},{col},{acc},{ass_color('#000000')},&H80000000,-1,0,0,0,100,100,0,0,1,{max(2, base // 140)},3,5,40,40,0,1",
        f"Style: Lower,{m['font']},{int(base * .05)},{ass_color('#111111')},{acc},{acc},&H00000000,-1,0,0,0,100,100,0,0,3,{base // 70},0,1,0,0,0,1",
        f"Style: CTA,{m['font']},{int(base * .085)},{ass_color('#111111')},{col},{acc},&H00000000,-1,0,0,0,100,100,0,0,3,{base // 45},0,5,40,40,0,1",
        f"Style: Chapter,{m['font']},{int(base * .09)},{col},{acc},{ass_color('#000000')},&HA0000000,-1,0,0,0,100,100,2,0,1,{max(2, base // 160)},4,5,60,60,0,1",
        f"Style: Callout,{m['font']},{int(base * .075)},{acc},{col},{ass_color('#000000')},&H80000000,-1,0,0,0,100,100,0,0,1,{max(2, base // 160)},2,8,40,40,{int(h * .1)},1",
    ]
    lines = header(w, h, styles)
    n = 0
    for it in plan.get("motion", []):
        s, e, typ, txt = it["start"], it["end"], it.get("type"), esc(it.get("text", ""))
        dms = int((e - s) * 1000)
        if typ == "title":
            txt = wrap(txt, max(8, int(w / (base * .11) * 1.6)))
            y = int(h * it.get("y", 0.42))
            fx = ("\\fscx0\\fscy0\\t(0,160,\\fscx115\\fscy115)\\t(160,260,\\fscx100\\fscy100)"
                  f"\\t({dms - 200},{dms},\\fscx60\\fscy60\\alpha&HFF&)")
            lines.append(f"Dialogue: 2,{ts(s)},{ts(e)},Title,,0,0,0,,{{\\an5\\pos({w // 2},{y}){fx}}}{txt}")
        elif typ == "lower_third":
            y, x = int(h * .8), int(w * .06)
            lines.append(f"Dialogue: 2,{ts(s)},{ts(e)},Lower,,0,0,0,,"
                         f"{{\\an1\\move({-w // 2},{y},{x},{y},0,280)\\fad(0,250)}} {txt} ")
        elif typ == "callout":
            fx = "\\fscx50\\fscy50\\t(0,120,\\fscx112\\fscy112)\\t(120,200,\\fscx100\\fscy100)\\fad(0,150)"
            lines.append(f"Dialogue: 2,{ts(s)},{ts(e)},Callout,,0,0,0,,{{{fx}}}{txt}")
        elif typ == "cta":
            y = int(h * it.get("y", 0.5))
            sub = esc(it.get("subtext", ""))
            fx = "\\fscx0\\fscy0\\t(0,180,\\fscx108\\fscy108)\\t(180,260,\\fscx100\\fscy100)"
            lines.append(f"Dialogue: 3,{ts(s)},{ts(e)},CTA,,0,0,0,,{{\\an5\\pos({w // 2},{y}){fx}}} {wrap(txt, 16)} ")
            if sub:
                lines.append(f"Dialogue: 3,{ts(s + .25)},{ts(e)},Title,,0,0,0,,"
                             f"{{\\an5\\pos({w // 2},{int(y + base * .16)})\\fs{int(base * .05)}\\fad(200,0)}}{sub}")
        elif typ == "chapter":
            num = esc(str(it.get("number", "")))
            head = f"{{\\fs{int(base * .05)}\\c{acc}}}{num}\\N{{\\r}}" if num else ""
            lines.append(f"Dialogue: 3,{ts(s)},{ts(e)},Chapter,,0,0,0,,"
                         f"{{\\an5\\pos({w // 2},{h // 2})\\fad(250,250)\\blur0.6}}{head}{wrap(txt, 18)}")
        else:
            continue
        n += 1
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out if n else None
