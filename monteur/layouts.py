"""Formats de reel composés : « Avant / après » (deux vidéos empilées sous un titre)."""
from .common import ASSETS, ffmpeg, log, probe


def _text_filter(text, size, y, color="white", font="Montserrat-Black.ttf"):
    t = text.replace("\\", "").replace(":", "\\:").replace("'", "’").replace("%", "\\%")
    return (f"drawtext=fontfile='{ASSETS / 'fonts' / font}':text='{t}':fontsize={size}:fontcolor={color}:"
            f"x=(w-text_w)/2:y={y}:shadowcolor=black@0.6:shadowx=0:shadowy=3")


def avant_apres(after, before, out, title="", subtitle="", labels=("Transformé", "Originale"),
                audio="after", W=1080, H=1920):
    """Titre en haut ; vertical : transformée au milieu, originale en bas ; paysage / carré : côte à côte."""
    side = W >= H
    head = int(H * (0.2 if side else 0.29)) // 2 * 2
    if side:
        pw, ph = W // 2 // 2 * 2, (H - head) // 2 * 2
        pos = [(0, head), (pw, head)]
    else:
        pw, ph = W, (H - head) // 2 // 2 * 2
        pos = [(0, head), (0, head + ph)]
    dur = min(probe(after)["duration"], probe(before)["duration"])
    f = [f"color=c=black:s={W}x{H}:d={dur:.3f}[bg]"]
    for i, src in enumerate(("0:v", "1:v")):
        f.append(f"[{src}]scale={pw}:{ph}:force_original_aspect_ratio=increase,crop={pw}:{ph},setsar=1,"
                 + _text_filter(labels[i], int(min(W, H) * 0.045), int(ph * 0.04), font="Montserrat-ExtraBold.ttf")
                 + f"[p{i}]")
    f.append(f"[bg][p0]overlay={pos[0][0]}:{pos[0][1]}[a];[a][p1]overlay={pos[1][0]}:{pos[1][1]}[b]")
    W_txt = min(W, H * 0.75) if side else W
    txt = []
    if title:
        lines = title.split("\\n") if "\\n" in title else [title]
        for k, line in enumerate(lines[:2]):
            txt.append(_text_filter(line, int(W_txt * 0.068), int(head * 0.22 + k * W_txt * 0.08)))
    if subtitle:
        txt.append(_text_filter(subtitle, int(W_txt * 0.042), int(head * 0.72), font="Montserrat-Bold.ttf"))
    f.append("[b]" + (",".join(txt) if txt else "null") + "[v]")
    amap = ["-map", f"{0 if audio == 'after' else 1}:a?"]
    ffmpeg(["-i", after, "-i", before, "-filter_complex", ";".join(f), "-map", "[v]", *amap, "-t", f"{dur:.3f}",
            "-c:v", "libx264", "-crf", "17", "-preset", "fast", "-pix_fmt", "yuv420p", "-c:a", "aac", out])
    log(f"Avant/après → {out} ({dur:.1f}s)")
    return out
