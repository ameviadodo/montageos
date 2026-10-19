"""Visuels produits : photos → vidéo dynamique (Ken Burns alterné), base du mode « produit »."""
from .common import ffmpeg, log
from .render import ASPECTS


def slideshow(images, out, per=2.5, aspect="9:16", audio=None, fps=30):
    W, H = ASPECTS[aspect]
    inputs, graph = [], []
    frames = int(per * fps)
    for i, img in enumerate(images):
        inputs += ["-loop", "1", "-t", f"{per}", "-i", img]
        zin = i % 2 == 0  # alterne zoom avant / zoom arrière
        z = f"1+0.12*on/{frames}" if zin else f"1.12-0.12*on/{frames}"
        graph.append(f"[{i}:v]scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2},"
                     f"zoompan=z='{z}':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':d={frames}:s={W}x{H}:fps={fps},"
                     f"setsar=1,trim=0:{per},setpts=PTS-STARTPTS[s{i}]")
    graph.append("".join(f"[s{i}]" for i in range(len(images))) + f"concat=n={len(images)}:v=1:a=0[v]")
    total = per * len(images)
    if audio:
        inputs += ["-i", audio]
        amap = ["-map", f"{len(images)}:a", "-af", f"afade=t=out:st={max(0, total - 1.5)}:d=1.5"]
    else:
        inputs += ["-f", "lavfi", "-t", f"{total}", "-i", "anullsrc=r=48000:cl=stereo"]
        amap = ["-map", f"{len(images)}:a"]
    ffmpeg([*inputs, "-filter_complex", ";".join(graph), "-map", "[v]", *amap, "-t", f"{total}",
            "-c:v", "libx264", "-crf", "16", "-preset", "fast", "-pix_fmt", "yuv420p", "-c:a", "aac", out])
    log(f"Diaporama produit {len(images)} images, {total:.1f}s → {out}")
    return out
