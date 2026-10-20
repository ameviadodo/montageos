"""Assemblage final : recadrage, zooms, B-roll, animations, sous-titres, bruitages, mixage."""
import shutil

from .common import ASSETS, ffmpeg, ffmpeg_progress, load_json, log, probe
from .sfx import auto_events
from .subtitles import build_motion, build_subtitles

ASPECTS = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080), "4:5": (1080, 1350)}


def out_size(info, fmt):
    if fmt.get("width") and fmt.get("height"):
        return int(fmt["width"]), int(fmt["height"])
    if fmt.get("aspect", "source") in ASPECTS:
        return ASPECTS[fmt["aspect"]]
    w, h = info["width"], info["height"]
    k = min(1.0, fmt.get("max_side", 1920) / max(w, h))  # 4K → 1080p : 4× plus rapide, suffisant pour les réseaux
    return int(w * k) // 2 * 2, int(h * k) // 2 * 2


def zoom_expr(zooms, cfg):
    terms = []
    r = cfg.get("ease_s", 0.35)
    for z in zooms:
        s, e, a = z["start"], z["end"], z.get("scale", cfg["scale"]) - 1
        if z["kind"] == "punch":
            terms.append(f"{a:.4f}*between(it,{s:.3f},{e:.3f})")
        elif z["kind"] == "pulse":
            c, h = (s + e) / 2, max(0.05, (e - s) / 2)
            terms.append(f"{a:.4f}*max(0,1-abs(it-{c:.3f})/{h:.3f})")
        else:  # ease : poussée douce avec smoothstep
            env = f"min(clip((it-{s:.3f})/{r},0,1),clip(({e:.3f}-it)/{r},0,1))"
            terms.append(f"{a:.4f}*({env})*({env})*(3-2*({env}))")
    return "1+" + "+".join(terms) if terms else "1"


def next_render(ws, draft):
    """renders/<slug>-vNN-<draft|master>.mp4 — un compteur de versions commun aux deux qualités."""
    d = ws.dir / "renders"
    d.mkdir(exist_ok=True)
    n = 1 + max([int(p.stem.split("-v")[-1][:2]) for p in d.glob("*-v[0-9][0-9]-*.mp4")] or [0])
    return d / f"{ws.source.stem}-v{n:02d}-{'draft' if draft else 'master'}.mp4"


def fesc(path):
    return str(path).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def render(ws, style, out=None, draft=False):
    """Rendu master (ou draft rapide, demi-résolution) versionné dans renders/ ; master copié en final.mp4."""
    plan = load_json(ws.plan, {})
    video = ws.base_video()
    info = probe(video)
    W, H = out_size(info, style["format"])
    if draft:
        W, H = W // 4 * 2, H // 4 * 2
    fps = info["fps"]
    dur = info["duration"]
    zc = style["zoom"]
    inputs, graph = ["-i", video], []
    n_in = 1

    # « Split carte » : panneau d'animations en haut, orateur en bas
    fmt = style["format"]
    split = fmt.get("layout") == "split"
    y0 = int(H * fmt.get("split", 0.42)) // 2 * 2 if split else 0
    CW, CH = W, H          # toile finale
    H = H - y0             # zone orateur (= toile entière hors split)
    if split:
        plan = {**plan, "motion": [dict(m, y=m.get("y", y0 / 2 / CH)) if m.get("type") in ("title", "callout", "cta")
                                   else m for m in plan.get("motion", [])]}

    # 1) recadrage au format cible — suit le visage si focus « auto » (OpenCV), sinon focus fixe
    sw, sh = info["width"], info["height"]
    fx, fy = zc.get("focus_x", 0.5), zc.get("focus_y", 0.4)
    face = None
    if zc.get("focus", "auto") == "auto":
        from .focus import track
        face = track(ws, video)
    if face and face.get("median"):
        fy = min(0.6, max(0.25, face["median"][1]))
    if abs(sw / sh - W / H) > 0.01:
        if sw / sh > W / H:
            cw, ch = f"ih*{W}/{H}", "ih"
            xexpr = None
            if face and face.get("faces"):
                from .focus import crop_x_expr
                xexpr = crop_x_expr(face["faces"], sw, sh * W / H)
            crop = f"crop={cw}:{ch}:'{xexpr}':0" if xexpr else f"crop={cw}:{ch}:(iw-ow)*{fx}:0"
        else:
            crop = f"crop=iw:iw*{H}/{W}:0:(ih-oh)*{fy}"
        graph.append(f"[0:v]{crop},scale={W}:{H}:flags=lanczos,setsar=1[v0]")
    else:
        graph.append(f"[0:v]scale={W}:{H}:flags=lanczos,setsar=1[v0]")
    cur = "v0"
    cropped_on_face = abs(sw / sh - W / H) > 0.01 and sw / sh > W / H and bool(face and face.get("faces"))
    zx = 0.5 if cropped_on_face else (face["median"][0] if face and face.get("median") else fx)

    # 2) zooms rapides avant/arrière
    zooms = plan.get("zooms", []) if zc.get("enabled") else []
    if zooms:
        z = zoom_expr(zooms, zc)
        graph.append(f"[{cur}]scale={W * 2}:{H * 2}:flags=bicubic,"
                     f"zoompan=z='{z}':x='(iw-iw/zoom)*{zx:.3f}':"
                     f"y='(ih-ih/zoom)*{fy}':d=1:s={W}x{H}:fps={fps}[vz]")
        cur = "vz"

    # 2b) étalonnage / look (documentaire, pub…)
    look = style.get("look", {})
    fx = []
    if look.get("eq"):
        fx.append(f"eq={look['eq']}")
    if look.get("curves"):
        fx.append(f"curves=preset={look['curves']}")
    if look.get("vignette"):
        fx.append("vignette=PI/5")
    if look.get("grain"):
        fx.append(f"noise=alls={int(look['grain'])}:allf=t")
    if look.get("letterbox"):
        bar = int(max(0, H - W / look["letterbox"]) / 2) if W > H else int(H * 0.06)
        fx.append(f"drawbox=x=0:y=0:w=iw:h={bar}:color=black:t=fill,drawbox=x=0:y=ih-{bar}:w=iw:h={bar}:color=black:t=fill")
    if fx:
        graph.append(f"[{cur}]{','.join(fx)}[vl]")
        cur = "vl"
    if split:
        graph.append(f"[{cur}]pad={CW}:{CH}:0:{y0}:color={fmt.get('panel_color', '#0B0F1A')}[vp]")
        cur = "vp"
    W, H = CW, CH

    # 3) B-roll / illustrations / inserts Hyperframes
    bc = style["broll"]
    overlays = [b for b in plan.get("broll", []) if b.get("file")]
    overlays += [dict(m, layout=m.get("layout", "overlay")) for m in plan.get("motion", [])
                 if m.get("type") == "hyperframes" and m.get("file")]
    for k, b in enumerate(overlays):
        s, e = b["start"], min(b["end"], dur)
        d = max(0.1, e - s)
        f = b.get("fade", bc.get("fade", 0.15))
        lay = b.get("layout", "full")
        is_img = b.get("kind") == "image" or str(b["file"]).lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
        if is_img:
            inputs += ["-loop", "1", "-framerate", str(fps), "-t", f"{d:.3f}", "-i", b["file"]]
        else:
            inputs += ["-stream_loop", "-1", "-t", f"{d + 0.5:.3f}", "-i", b["file"]]
        idx = n_in
        n_in += 1
        if split and lay == "full":
            lay = "panel"
        tw, th = {"full": (W, H), "overlay": (W, H), "fullscreen": (W, H), "panel": (W, y0)}.get(
            lay, (int(W * 0.46) // 2 * 2, int(W * 0.46 * 9 / 16) // 2 * 2))
        alpha = b.get("type") == "hyperframes" and str(b["file"]).lower().endswith((".mov", ".webm"))
        if alpha:  # alpha conservé (MOV/WebM Hyperframes), dans la toile ou le panneau
            chain = (f"[{idx}:v]trim=0:{d:.3f},setpts=PTS-STARTPTS,"
                     f"scale={tw}:{th}:force_original_aspect_ratio=decrease,format=yuva420p")
        elif is_img:
            chain = (f"[{idx}:v]scale={int(tw * 1.15)}:{int(th * 1.15)}:force_original_aspect_ratio=increase,"
                     f"crop={tw}:{th}:x='(iw-ow)*t/{d:.3f}':y='(ih-oh)/2',setsar=1,format=yuva420p")
        else:
            chain = (f"[{idx}:v]trim=0:{d:.3f},setpts=PTS-STARTPTS,fps={fps},"
                     f"scale={tw}:{th}:force_original_aspect_ratio=increase,crop={tw}:{th},setsar=1,format=yuva420p")
        chain += (f",fade=t=in:st=0:d={f}:alpha=1,fade=t=out:st={max(0, d - f):.3f}:d={f}:alpha=1,"
                  f"setpts=PTS+{s:.3f}/TB[b{k}]")
        graph.append(chain)
        x, y = {"full": ("0", "0"), "fullscreen": ("0", "0"), "panel": ("(main_w-overlay_w)/2", "0"),
                "overlay": ("(main_w-overlay_w)/2", "(main_h-overlay_h)/2")}.get(
            lay, (f"{int(W * 0.5)}", f"{int(H * 0.08)}"))
        graph.append(f"[{cur}][b{k}]overlay={x}:{y}:enable='between(t,{s:.3f},{e:.3f})':eof_action=pass[o{k}]")
        cur = f"o{k}"

    # 4) sous-titres + animations texte (ASS)
    transcript = ws.base_transcript()
    fonts = fesc(ASSETS / "fonts")
    if style["subtitles"].get("enabled") and transcript and transcript.get("words"):
        build_subtitles(transcript, plan, style, W, H, ws.subs)
        graph.append(f"[{cur}]ass={ws.subs.name}:fontsdir='{fonts}'[vs]")
        cur = "vs"
    if style["motion"].get("enabled") and build_motion(plan, style, W, H, ws.motion_ass):
        graph.append(f"[{cur}]ass={ws.motion_ass.name}:fontsdir='{fonts}'[vm]")
        cur = "vm"
    graph.append(f"[{cur}]format=yuv420p[vout]")

    # 5) audio : voix + bruitages + musique (ducking) → loudnorm
    mix = []
    if info["has_audio"]:
        graph.append("[0:a]aresample=48000,asplit=2[voice][sc]")
    else:
        graph.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{dur:.3f},asplit=2[voice][sc]")
    mix.append("[voice]")
    for k, ev in enumerate(auto_events(plan, style)):
        inputs += ["-i", ev["file"]]
        ms = int(ev["t"] * 1000)
        graph.append(f"[{n_in}:a]aresample=48000,aformat=channel_layouts=stereo,"
                     f"adelay={ms}|{ms},volume={ev['gain']}[s{k}]")
        mix.append(f"[s{k}]")
        n_in += 1
    ac = style["audio"]
    music = plan.get("music") or ac.get("music")
    if music:
        inputs += ["-stream_loop", "-1", "-i", music]
        graph.append(f"[{n_in}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{dur:.3f},"
                     f"volume={ac['music_volume']},afade=t=out:st={max(0, dur - 2):.3f}:d=2[mus]")
        n_in += 1
        if ac.get("duck", True):
            graph.append("[mus][sc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[musd]")
            mix.append("[musd]")
        else:
            mix.append("[mus]")
            graph.append("[sc]anullsink")
    else:
        graph.append("[sc]anullsink")
    graph.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=first,"
                 f"loudnorm=I={ac['lufs']}:TP=-1.5:LRA=11,aresample=48000[aout]")

    script = ws.dir / "render_filter.txt"
    script.write_text(";\n".join(graph), encoding="utf-8")
    target = next_render(ws, draft)
    ex = style["export"]
    preset, crf = ("ultrafast", 30) if draft else (ex["preset"], ex["crf"])
    log(f"Rendu {'draft' if draft else 'master'} {W}x{H} @ {fps}fps — {len(zooms)} zooms, "
        f"{len(overlays)} visuels, {len(mix) - 1} pistes son…")
    ffmpeg_progress([*inputs, "-filter_complex_script", script.name, "-map", "[vout]", "-map", "[aout]",
                     "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
                     "-r", str(fps), "-c:a", "aac", "-b:a", ex["audio_bitrate"], "-movflags", "+faststart",
                     str(target)], dur, f"Rendu {'draft' if draft else 'master'}", cwd=ws.dir)
    if not draft:
        shutil.copyfile(target, ws.final)
    if out:
        shutil.copyfile(target, out)
    log(f"✅ {'Draft' if draft else 'Master'} → {target}")
    return target
