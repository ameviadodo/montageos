"""Monte le tuto MonteurOS Studio : intro carte → captation d'écran + bandeau d'explications → outro → écran « Pour commencer ».

Usage : python docs/tuto/compose.py <dossier_tuto>   (contient rec/screen.webm, rec/marks.json, tuto.monteur/assets/motion/{intro,outro}.mp4)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from monteur.common import ASSETS, ffmpeg, probe  # noqa: E402
from monteur.subtitles import ts  # noqa: E402

D = Path(sys.argv[1]).resolve()
W, H, FPS = 1920, 1080, 30
FONTS = str(ASSETS / "fonts").replace(":", "\\:")

# Bandeau : (repère, décalage s, chapitre, texte)
STEPS = [
    ("projets", 0, "01 · PROJETS", "Tous tes rushs au même endroit : projets, rendus, rendus périmés, espace disque."),
    ("projets", 6.5, "01 · PROJETS", "Cherche un projet, filtre par famille, format ou état, puis ouvre-le."),
    ("projet", 0, "02 · LE PROJET", "Chaque rendu est une version (v01, v02…). La vérification automatique s'affiche à droite."),
    ("actions", 0, "02 · LE PROJET", "« Préparer » transcrit et coupe le rush. « Rendu draft + vérif » fait un brouillon rapide puis le contrôle."),
    ("retours", 0, "03 · RETOURS FRAME PAR FRAME", "Lecture, puis −1 img / +1 img pour te placer sur la frame exacte."),
    ("retours", 13, "03 · RETOURS FRAME PAR FRAME", "Écris ton retour et appuie sur Entrée. Clique un retour pour revenir à sa frame."),
    ("retours", 23, "03 · RETOURS FRAME PAR FRAME", "« Envoyer au montage » : Claude applique tes retours au prochain rendu."),
    ("studio", 0, "04 · STUDIO", "Le texte transcrit défile avec la vidéo ; la timeline montre coupes, sous-titres, sons, B-roll, zooms, cartes."),
    ("studio", 10, "04 · STUDIO", "Choisis une carte animée, règle ses textes, puis « Aperçu »."),
    ("apercu", 0, "04 · STUDIO", "Si elle te plaît : « Poser à la tête de lecture » l'ajoute au montage."),
    ("biblio", 0, "05 · BIBLIOTHÈQUES", "Formats de reel, ta charte graphique et les styles de référence."),
    ("style", 0, "05 · BIBLIOTHÈQUES", "Chaque style regroupe ses cartes animées : « Voir en grand » pour les prévisualiser."),
    ("activite", 0, "06 · ACTIVITÉ", "L'historique de tout ce qui a été lancé : préparations, rendus, vérifications."),
]


def ass_header(styles):
    return "\n".join(["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 2",
                      "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
                      "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
                      "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
                      "MarginL, MarginR, MarginV, Encoding", *styles, "", "[Events]",
                      "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"])


def main():
    rec = D / "rec" / "screen.webm"
    marks = {m["id"]: m["t"] for m in json.loads((D / "rec" / "marks.json").read_text())}
    rdur = probe(rec)["duration"]
    end_t = marks.get("fin", rdur) + 1.5
    work = D / "build"
    work.mkdir(exist_ok=True)

    # 1) captation dans le cadre + bandeau
    times = [(marks[m] + off, chap, txt) for m, off, chap, txt in STEPS if m in marks]
    times.sort()
    ev = []
    for i, (t, chap, txt) in enumerate(times):
        e = times[i + 1][0] if i + 1 < len(times) else end_t
        ev.append(f"Dialogue: 0,{ts(t)},{ts(e)},Chap,,0,0,0,,{{\\an4\\pos(170,978)\\fad(150,0)}}{chap}")
        ev.append(f"Dialogue: 0,{ts(t)},{ts(e)},Txt,,0,0,0,,{{\\an4\\pos(170,1028)\\fad(250,150)}}{txt}")
    (work / "bandeau.ass").write_text(ass_header([
        "Style: Chap,Space Mono,28,&H0035D9FF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,3,0,1,0,0,4,0,0,0,1",
        "Style: Txt,Montserrat,36,&H00ECF1F2,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,0,0,4,0,0,0,1",
    ]) + "\n" + "\n".join(ev) + "\n", encoding="utf-8")
    ffmpeg(["-f", "lavfi", "-i", f"color=c=0x070A12:s={W}x{H}:r={FPS}:d={end_t:.2f}", "-i", rec, "-filter_complex",
            f"[1:v]fps={FPS},scale=1600:900,setsar=1[s];"
            f"[0:v]drawbox=x=156:y=24:w=1608:h=908:color=0x182033:t=fill,drawbox=x=156:y=948:w=6:h=96:color=0xFFD935:t=fill[bg];"
            f"[bg][s]overlay=160:28:eof_action=repeat,ass=bandeau.ass:fontsdir='{FONTS}',format=yuv420p[v]",
            "-map", "[v]", "-t", f"{end_t:.2f}", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "main.mp4"], cwd=work)

    # 2) écran « Pour commencer »
    fin = 7.0
    steps = ["bash setup.sh --all", "bin/monteur studio --root ~/Videos", "Dis à Claude : « Monte-moi cette vidéo »"]
    lines = [f"Dialogue: 0,{ts(0.2)},{ts(fin)},Big,,0,0,0,,{{\\an7\\pos(240,250)\\fad(300,0)}}Pour commencer"]
    for k, s in enumerate(steps):
        t0 = 0.8 + k * 0.6
        lines.append(f"Dialogue: 0,{ts(t0)},{ts(fin)},Num,,0,0,0,,{{\\an7\\pos(240,{430 + k * 130})\\fad(250,0)}}0{k + 1}")
        lines.append(f"Dialogue: 0,{ts(t0)},{ts(fin)},Step,,0,0,0,,{{\\an7\\pos(340,{420 + k * 130})\\fad(250,0)}}{s}")
    lines.append(f"Dialogue: 0,{ts(2.8)},{ts(fin)},Small,,0,0,0,,{{\\an7\\pos(240,860)\\fad(300,0)}}MonteurOS · github.com/ameviadodo/montageos")
    (work / "fin.ass").write_text(ass_header([
        "Style: Big,Instrument Serif,110,&H00ECF1F2,&H00FFFFFF,&H00000000,&H00000000,0,-1,0,0,100,100,0,0,1,0,0,7,0,0,0,1",
        "Style: Num,Space Mono,40,&H0035D9FF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,2,0,1,0,0,7,0,0,0,1",
        "Style: Step,Montserrat,52,&H00ECF1F2,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1",
        "Style: Small,Space Mono,26,&H009B877F,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,2,0,1,0,0,7,0,0,0,1",
    ]) + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
    ffmpeg(["-f", "lavfi", "-i", f"color=c=0x070A12:s={W}x{H}:r={FPS}:d={fin}", "-vf",
            f"drawbox=x=240:y=380:w=120:h=6:color=0xFFD935:t=fill,ass=fin.ass:fontsdir='{FONTS}',fade=t=out:st={fin - 0.6}:d=0.6,format=yuv420p",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "fin.mp4"], cwd=work)

    # 3) assemblage vidéo
    motion = D / "tuto.monteur" / "assets" / "motion"
    parts = [motion / "intro.mp4", work / "main.mp4", motion / "outro.mp4", work / "fin.mp4"]
    durs = [probe(p)["duration"] for p in parts]
    ins, fg = [], []
    for i, p in enumerate(parts):
        ins += ["-i", p]
        fg.append(f"[{i}:v]fps={FPS},scale={W}:{H},setsar=1,format=yuv420p[p{i}]")
    fg.append("".join(f"[p{i}]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=1:a=0[v]")
    total = sum(durs)

    # 4) audio : nappe douce synthétisée + whoosh à chaque chapitre + impact sur l'intro
    off = durs[0]
    hits = [(0.15, "riser"), (off - 0.35, "whoosh"), (off + durs[1] - 0.3, "whoosh"),
            (off + durs[1] + durs[2] - 0.3, "swoosh")]
    seen = set()
    for t, chap, _ in times:
        if chap not in seen:
            seen.add(chap)
            hits.append((off + t - 0.15, "swoosh"))
    pad = ("0.06*(sin(2*PI*110*t)+0.7*sin(2*PI*164.8*t)+0.5*sin(2*PI*220*t)+0.35*sin(2*PI*277.2*t))"
           "*(0.75+0.25*sin(2*PI*0.08*t))")
    k = len(parts)
    ins += ["-f", "lavfi", "-i", f"aevalsrc='{pad}':s=48000:d={total:.2f}"]
    fg.append(f"[{k}:a]lowpass=f=900,afade=t=in:d=2,afade=t=out:st={total - 3:.2f}:d=3,volume=0.55[pad]")
    mix = ["[pad]"]
    for j, (t, name) in enumerate(hits):
        f = ASSETS / "sfx" / f"{name}.wav"
        if not f.exists():
            continue
        ins += ["-i", f]
        ms = max(0, int(t * 1000))
        fg.append(f"[{k + len(mix)}:a]adelay={ms}|{ms},volume=0.35[h{j}]")
        mix.append(f"[h{j}]")
    fg.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=first,loudnorm=I=-18:TP=-2,aresample=48000[a]")
    out = D / "MonteurOS-tuto.mp4"
    ffmpeg([*ins, "-filter_complex", ";".join(fg), "-map", "[v]", "-map", "[a]", "-t", f"{total:.2f}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
            "-movflags", "+faststart", out])
    print(f"{out}  ({total:.1f} s)")


if __name__ == "__main__":
    main()
