"""MonteurOS — CLI.  python -m monteur <commande> …"""
import argparse
import sys
from pathlib import Path

from .common import Workspace, active_style, load_json, load_style, log, probe, save_json, which

ASPECT_CHOICES = ["source", "9:16", "16:9", "1:1", "4:5", "3:4", "2:3", "21:9"]
CUT_CHOICES = ["hard", "zoomcut", "flash", "dip", "whip", "glitch", "fondu", "mix"]
VOICE_ENGINES = ["auto", "elevenlabs", "inworld", "edge", "espeak"]


def get_ws(a, snap=None):
    """Projet + style. snap = libellé de l'action : instantané d'abord (annulable avec « monteur annuler »)."""
    ws = Workspace(a.video, getattr(a, "workdir", None))
    if snap and not getattr(a, "_snapped", False):
        from .history import snapshot
        snapshot(ws, snap + (f" · style {a.style}" if getattr(a, "style", None) else ""))
        a._snapped = True  # une seule photo par commande (prep → render dans « run »)
    style = load_style(a.style or load_json(ws.style, {}).get("name") or active_style())
    if a.style:
        save_json(ws.style, {"name": a.style})
    if getattr(a, "cuts", None):
        style["cut"]["transition"] = a.cuts
        plan = load_json(ws.plan)
        if plan is not None:  # le plan existant suit le nouveau type de cut
            from .transitions import auto_transitions
            plan["transitions"] = auto_transitions(ws, style, plan.get("duration"))
            save_json(ws.plan, plan)
    if getattr(a, "music", None):
        style["audio"]["music"] = str(Path(a.music).resolve())
    if getattr(a, "aspect", None):
        style["format"]["aspect"] = a.aspect
    return ws, style


def portrait(ws, style):
    asp = style["format"].get("aspect", "source")
    if asp == "source":
        i = probe(ws.source)
        return i["height"] > i["width"]
    return asp in ("9:16", "4:5")


def silent(video):
    import re
    from .common import run
    err = run(["ffmpeg", "-hide_banner", "-nostats", "-i", video, "-vn", "-af", "volumedetect", "-f", "null", "-"],
              capture=True).stderr
    m = re.search(r"max_volume: (-?[\d.]+|-inf) dB", err)
    return not m or m.group(1) == "-inf" or float(m.group(1)) < -60


def cmd_doctor(a):
    from . import sfx
    ok = True
    venv = sys.prefix != sys.base_prefix
    print(f"{'✅' if venv else '⚠️ '} Python {sys.version.split()[0]} — {sys.executable}"
          + ("" if venv else "  (hors venv : lance bash setup.sh)"))
    for b in ("ffmpeg", "ffprobe", "node", "npx"):
        print(f"{'✅' if which(b) else '❌'} {b}")
        ok &= which(b) or b in ("node", "npx")
    for mod in ("faster_whisper", "yt_dlp", "cv2", "google.genai"):
        try:
            __import__(mod)
            print(f"✅ {mod}")
        except ImportError:
            optional = mod in ("google.genai", "cv2")
            print(f"{'➖' if optional else '❌'} {mod}")
            ok &= optional
    try:
        import faster_whisper  # noqa: F401
        print("✅ transcription : Whisper local")
    except ImportError:
        print("⚠️  transcription : pas de Whisper local → bash setup.sh (Python 3.12 auto via uv) "
              "ou bin/monteur transcription RUSH fichier.srt (export WhisperAI)")
    import os
    for k in ("ELEVENLABS_API_KEY", "INWORLD_API_KEY", "PEXELS_API_KEY", "PIXABAY_API_KEY", "WIKIMEDIA_ACCESS_TOKEN",
              "FREESOUND_API_KEY", "MAGNIFIC_API_KEY", "GEMINI_API_KEY"):
        print(f"{'🔑' if os.environ.get(k) else '➖'} {k}")
    from .habillage import hyperframes_ok
    print(f"{'✅' if hyperframes_ok() else '➖'} Hyperframes (Node ≥ 22 + npx){'' if hyperframes_ok() else ' — bash setup.sh --motion'}")
    print("   bin/monteur cles --test : teste chaque clé configurée")
    from .facecam import status as fc_status
    fc = fc_status()
    if not fc["modele"]:
        print("➖ coupe-facecam non installé (facultatif, kit Agence Agentique) — voir docs/coupe-facecam.md")
    else:
        print(f"{'✅' if all(fc.values()) else '➖'} coupe-facecam (numpy, onnxruntime, requests, modèle Silero)"
              + ("" if all(fc.values()) else f" — manque : {', '.join(k for k, v in fc.items() if not v)} → bash setup.sh"))
    print("🔊 SFX :", ", ".join(sfx.ensure_library()))
    fonts = sorted(p.name for p in (Path(__file__).parent.parent / "assets" / "fonts").glob("*.[ot]tf"))
    print("🔤 Polices :", ", ".join(fonts) or "aucune (lance setup.sh)")
    sys.exit(0 if ok else 1)


def cmd_whisper(a):
    """Installe / précharge le modèle Whisper et le teste sur 1 s de silence."""
    import tempfile
    from .transcribe import load_model
    try:
        import faster_whisper
    except ImportError:
        if sys.prefix == sys.base_prefix:  # pas dans un venv : on n'installe rien dans le Python système
            raise SystemExit(f"faster-whisper introuvable, et ce Python n'est pas celui de MonteurOS ({sys.executable}).\n"
                             "Lance d'abord : bash setup.sh   (il crée .venv et installe Whisper)")
        log(f"faster-whisper absent du venv ({sys.executable}) : installation…")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "faster-whisper"], check=False)
        try:
            import faster_whisper
        except ImportError:
            raise SystemExit("Installation de faster-whisper impossible avec ce Python "
                             f"({sys.version.split()[0]}). Windows : installe Python 3.12, supprime .venv, relance bash setup.sh")
    log(f"faster-whisper {faster_whisper.__version__} — chargement du modèle « {a.model} »…")
    m = load_model(a.model)
    with tempfile.TemporaryDirectory() as d:
        wav = Path(d) / "s.wav"
        from .common import ffmpeg
        ffmpeg(["-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono", "-t", "1", "-c:a", "pcm_s16le", wav])
        from .transcribe import read_wav
        list(m.transcribe(read_wav(wav))[0])
    print(f"✅ Whisper prêt (modèle {a.model}, {m.model.device if hasattr(m.model, 'device') else 'cpu'})")


def cmd_voix(a):
    """Voix off française : un texte, ou un fichier (une réplique par ligne)."""
    from .voiceover import engines, script, synth
    if a.liste:
        print("moteurs disponibles :", ", ".join(engines()) or "aucun (pip install edge-tts, ou espeak-ng)")
        return
    if a.liste_voix:
        return list_voices(a.moteur)
    if a.fichier:
        lines = [l.strip() for l in Path(a.fichier).read_text(encoding="utf-8").splitlines() if l.strip()]
        script(lines, Path(a.out), a.moteur, a.voix, a.vitesse)
    else:
        wav, d, eng = synth(a.texte, a.out, a.moteur, a.voix, a.vitesse)
        print(f"✅ {wav} ({d:.1f} s, moteur {eng})")


def list_voices(engine):
    """Voix des API configurées (ElevenLabs, Inworld) ; Edge : quelques voix françaises."""
    import json
    import os
    import urllib.request
    shown = False
    if engine in ("auto", "elevenlabs") and os.environ.get("ELEVENLABS_API_KEY"):
        req = urllib.request.Request("https://api.elevenlabs.io/v1/voices",
                                     headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]})
        with urllib.request.urlopen(req, timeout=30) as r:
            for v in json.load(r).get("voices", []):
                lab = v.get("labels") or {}
                print(f"elevenlabs  {v['voice_id']}  {v.get('name', ''):<22} {lab.get('gender', '')} {lab.get('accent', '')}")
        shown = True
    if engine in ("auto", "inworld") and os.environ.get("INWORLD_API_KEY"):
        from .voiceover import inworld_voices
        for v in inworld_voices(None):
            print(f"inworld     {v.get('voiceId') or v.get('name'):<22} {v.get('displayName', '')} "
                  f"{','.join(v.get('languages') or [])}")
        shown = True
    if engine in ("auto", "edge"):
        print("edge        fr-FR-DeniseNeural  fr-FR-HenriNeural  fr-FR-VivienneMultilingualNeural  "
              "fr-FR-RemyMultilingualNeural  fr-CA-SylvieNeural  fr-BE-CharlineNeural")
        shown = True
    if not shown:
        print("Aucune clé pour ce moteur : bin/monteur cles --set ELEVENLABS_API_KEY=… (ou INWORLD_API_KEY=…)")


def cmd_cles(a):
    """Clés API dans .env : état (masqué), --set CLE=valeur, --retire CLE, --test."""
    from . import keys
    for kv in a.set or []:
        if "=" not in kv:
            raise SystemExit(f"Format attendu : CLE=valeur (reçu « {kv} »)")
        keys.set_key(*kv.split("=", 1))
    for k in a.retire or []:
        keys.set_key(k, "")
    if a.test:
        for k, (ok, detail) in keys.test().items():
            print(f"{'✅' if ok else '➖' if ok is None else '❌'} {k:<24} {detail}")
        return
    for s in keys.status():
        print(f"{'🔑' if s['set'] else '➖'} {s['key']:<24} {s['value'] or '':<10} {s['service']} — {s['usage']}  ({s['url']})")


def cmd_voixoff(a):
    """Voix off du projet : fichier fourni, ou script synthétisé ; --retire pour revenir au son du rush."""
    from . import voixoff
    ws, _ = get_ws(a, "Voix off")
    if a.retire:
        return voixoff.remove(ws)
    if a.fichier:
        vo = voixoff.from_file(ws, a.fichier, a.script, a.language or "fr")
    elif a.script:
        vo = voixoff.from_script(ws, a.script, a.moteur, a.voix, a.vitesse, language=a.language or "fr")
    else:
        raise SystemExit("Donne --fichier voix.mp3 (voix enregistrée) ou --script script.txt (ou \"texte\") à synthétiser.")
    if a.original is not None:
        voixoff.install(ws, ws.dir / vo["file"], load_json(ws.transcript)["words"], vo["how"],
                        a.language or "fr", vo.get("engine"), original=a.original)
    if a.prep:
        set_prep_defaults(a)
        cmd_prep(a)


def set_prep_defaults(a):
    """« voixoff --prep » : la voix est déjà branchée, la préparation refait le plan dessus."""
    a.force, a.no_cut, a.voix_off, a.script = True, True, None, None
    a.no_broll, a.model = getattr(a, "no_broll", False), getattr(a, "model", "small")


def cmd_analyse(a):
    import json
    from .adapt import analyse
    ws = Workspace(a.video, getattr(a, "workdir", None))
    print(json.dumps(analyse(ws, a.brief or ""), ensure_ascii=False, indent=2))


def cmd_habiller(a):
    from .habillage import dress
    ws, style = get_ws(a, None if a.essai else "Habillage Hyperframes")
    dress(ws, style, a.nom, a.role, a.max, not a.sans_hyperframes, a.essai)


def cmd_notifier(a):
    from .notify import notify
    notify(" ".join(a.message), quiet=False)


def cmd_facecam(a):
    from .facecam import cli
    cli(a)


def cmd_transcription(a):
    """Importe une transcription faite ailleurs (WhisperAI via Claude, sous-titres…) puis, au choix, prépare."""
    from .transcript_import import import_transcript
    ws, _ = get_ws(a, "Import de transcription")
    import_transcript(ws, a.fichier, a.language or "fr")
    if a.prep:
        a.force, a.no_cut, a.no_broll, a.model = False, False, a.no_broll, "small"
        cmd_prep(a)


def cmd_transcribe(a):
    from .transcribe import transcribe
    ws, _ = get_ws(a)
    transcribe(ws.source, ws.transcript, a.model, a.language)


def cmd_cut(a):
    from .cut import cut
    ws, style = get_ws(a, "Coupe")
    edl = cut(ws, style, load_json(ws.transcript))
    print(edl["stats"])


def cmd_plan(a):
    from .plan import auto_plan
    ws, style = get_ws(a, "Plan automatique")
    auto_plan(ws, style, ws.base_transcript())


def cmd_broll(a):
    from .broll import fetch
    from .plan import auto_plan
    ws, style = get_ws(a, "Recherche B-roll")
    if not ws.plan.exists():
        log("Pas encore de plan de montage : création automatique (lance « Préparer » pour un plan complet).")
        auto_plan(ws, style, ws.base_transcript())
    fetch(ws, portrait(ws, style))


def cmd_render(a):
    from .render import render
    from .verify import verify
    ws, style = get_ws(a)
    if getattr(a, "style", None) and (load_json(ws.plan) or {}).get("style") not in (None, style.get("name")):
        log(f"⚠️  Le plan a été construit avec le style « {load_json(ws.plan).get('style')} » : zooms, B-roll et transitions "
            f"restent les siens. Pour tout passer en « {style.get('name')} » : monteur appliquer {a.video} --style {a.style}")
    out = render(ws, style, Path(a.out).resolve() if getattr(a, "out", None) else None, draft=getattr(a, "draft", False))
    from .history import record_render
    record_render(ws, out, f"Rendu {'draft' if getattr(a, 'draft', False) else 'master'} {out.name}")
    res = verify(ws, out) if getattr(a, "draft", False) or getattr(a, "verif", False) else None
    if not getattr(a, "draft", False):
        from .notify import notify
        notify(f"rendu master prêt : {out.name}" + ("" if res is None else " ✅" if res["ok"] else " — ⚠️ vérif à relire"))


def cmd_verif(a):
    from .project import renders
    from .verify import verify
    ws, _ = get_ws(a)
    rs = renders(ws)
    if not rs:
        raise SystemExit("Aucun rendu à vérifier.")
    verify(ws, Path(a.file).resolve() if a.file else Path(rs[-1]["path"]))


def cmd_retours(a):
    from . import review
    ws, _ = get_ws(a)
    if a.ajoute is not None:
        review.add(ws, a.ajoute, a.texte or "", probe(ws.base_video())["fps"])
    if a.applique:
        review.mark(ws, a.applique)
    print(review.as_text(ws, only_pending=not a.tous))


def cmd_projet(a):
    from .project import info, set_meta
    ws, _ = get_ws(a)
    if a.titre or a.etat or a.famille or a.type:
        set_meta(ws, title=a.titre, status=a.etat, family=a.famille, type=a.type)
    import json
    print(json.dumps(info(ws), ensure_ascii=False, indent=2))


def cmd_cartes(a):
    from .cards import search
    found = search(a.cherche, a.categorie)
    if not found:
        log(f"Aucune carte pour « {a.cherche} ».")
    for c in found:
        print(f"{c['id']:<26} [{c['category']}] {c['label']} — {c.get('usage', '')}")
        print(f"{'':<26} vars : " + ", ".join(f"{k}={v!r}" for k, v in c.get("vars", {}).items()))


def cmd_carte(a):
    from .cards import render as card_render
    from .render import out_size
    ws, style = get_ws(a, f"Carte {a.card}")
    values = dict(kv.split("=", 1) for kv in (a.set or []))
    W, H = out_size(probe(ws.base_video()), style["format"])
    layout = None
    if style["format"].get("layout") == "split":
        H, layout = int(H * style["format"].get("split", 0.42)) // 2 * 2, "panel"
    card_render(ws, a.card, a.start, values, W, H, a.duree, layout=layout, style=style)


def cmd_avant_apres(a):
    from .layouts import avant_apres
    from .render import ASPECTS
    W, H = ASPECTS[a.aspect]
    avant_apres(a.apres, a.avant, a.out, a.title or "", a.subtitle or "", tuple(a.labels.split(",")),
                "after" if a.audio == "apres" else "before", W, H)


def cmd_prep(a):
    """Transcription → coupe → plan → B-roll : tout sauf le rendu (pour relecture par Claude)."""
    from .broll import fetch
    from .cut import cut
    from .plan import auto_plan
    from .transcribe import transcribe
    from .transcribe import NoWhisper
    from . import voixoff
    if getattr(a, "brief", None) is not None and not a.style and not load_json(Workspace(a.video, getattr(a, "workdir", None)).style):
        from .adapt import analyse  # pas de style choisi : celui qui convient à la vidéo source
        a.style = analyse(Workspace(a.video, getattr(a, "workdir", None)), a.brief)["style_conseille"]
        log(f"Style adapté à la vidéo : « {a.style} »")
    ws, style = get_ws(a, "Préparation")
    if getattr(a, "voix_off", None):
        voixoff.from_file(ws, a.voix_off, getattr(a, "script", None), a.language or "fr")
    elif getattr(a, "script", None):
        voixoff.from_script(ws, a.script, getattr(a, "moteur", "auto"), getattr(a, "voix", None),
                            language=a.language or "fr")
    vo = voixoff.settings(ws)
    has_audio = probe(ws.source)["has_audio"] and not silent(ws.source)
    if not has_audio and not vo:
        log("🎙️  Cette vidéo n'a pas de voix. Pour des sous-titres et un montage calé sur une voix :")
        log("   • voix off enregistrée : bin/monteur voixoff RUSH --fichier voix.mp3 [--script script.txt] --prep")
        log("   • ou un script à faire lire : bin/monteur voixoff RUSH --script script.txt "
            "[--moteur elevenlabs|inworld|edge] --prep")
        log("   Préparation sans voix pour l'instant (zooms, musique, habillage).")
    no_whisper = False
    try:
        t = load_json(ws.transcript) if (ws.transcript.exists() and (not a.force or vo)) else \
            (transcribe(ws.source, ws.transcript, a.model, a.language) if has_audio else {"words": []})
    except NoWhisper:
        no_whisper, t = True, {"words": []}
        log("⚠️  Whisper n'est pas installé : préparation sans transcription (coupe des silences, zooms, "
            "pas de sous-titres ni de coupe des répétitions).")
        log("   Pour l'activer : installe Python 3.12 (Windows : winget install Python.Python.3.12) puis bash setup.sh")
    except SystemExit:
        raise
    except Exception as e:  # modèle illisible, bibliothèque cassée… : la préparation va quand même au bout
        no_whisper, t = True, {"words": []}
        log(f"⚠️  Transcription impossible ({type(e).__name__}: {e}) : préparation sans transcription "
            "(coupe des silences, zooms). Relance « Préparer » après « bin/monteur doctor », ou importe une transcription.")
    if vo:  # voix off : la vidéo garde sa durée, rien à couper dans la prise son du rush
        ws.cut_video.unlink(missing_ok=True)
        ws.cut_transcript.unlink(missing_ok=True)
        edl = {"stats": f"pas de coupe (voix off : {vo.get('how')})"}
    elif style["cut"].get("enabled", True) and not a.no_cut and (t.get("words") or (no_whisper and has_audio)):
        edl = cut(ws, style, t if t.get("words") else None)
    else:
        ws.cut_video.unlink(missing_ok=True)
        save_json(ws.transcript, t)
        edl = {"stats": "déjà coupée par coupe-facecam" if str(t.get("source", "")).startswith("coupe-facecam")
               else "coupe désactivée"}
    old_style = (load_json(ws.plan) or {}).get("style")
    if not ws.plan.exists() or a.force:
        auto_plan(ws, style, ws.base_transcript())
    elif old_style and old_style != style.get("name"):  # style changé depuis la bibliothèque : le plan le suit
        from .plan import apply_style
        apply_style(ws, style)
    if not a.no_broll:
        fetch(ws, portrait(ws, style))
    auto = (style.get("habillage") or {}).get("auto", True) and (style.get("library") or {}).get("cards")
    if getattr(a, "hyperframes", False) or getattr(a, "nom", None) or auto:  # cartes du style posées sur la vidéo
        from .habillage import dress
        dress(ws, style, getattr(a, "nom", None), getattr(a, "role", None),
              use_hyperframes=(style.get("habillage") or {}).get("hyperframes", True))
    print(f"\nDossier : {ws.dir}\nCoupe : {edl['stats']}\nÉdite {ws.plan} puis : monteur render {a.video}")


def cmd_run(a):
    cmd_prep(a)
    cmd_render(a)


def cmd_slideshow(a):
    from .slideshow import slideshow
    slideshow(a.images, a.out, a.per, a.aspect or "9:16", a.audio)


def cmd_charte(a):
    from .charte import extract
    extract(a.sources, a.name, with_style=not a.sans_style)


def cmd_appliquer(a):
    """Applique le style choisi à un projet existant : zooms, B-roll, transitions, titre et CTA recalculés."""
    from .plan import apply_style
    if not a.style:
        raise SystemExit("Précise le style : monteur appliquer RUSH.mp4 --style hormozi")
    ws, style = get_ws(a, "Application du style")
    apply_style(ws, style)
    if not a.no_broll:
        from .broll import fetch
        fetch(ws, portrait(ws, style))
    if (style.get("habillage") or {}).get("auto", True) and (style.get("library") or {}).get("cards"):
        from .habillage import dress  # le style s'applique aussi par ses cartes (polices et couleurs du style)
        dress(ws, style, use_hyperframes=(style.get("habillage") or {}).get("hyperframes", True))


def cmd_retouche(a):
    """Retouche directe à un instant de la vidéo montée, puis (option) rendu draft pour la voir."""
    from . import retouche as R
    what = (f"Coupe de {a.coupe[1]:.1f}s à {a.coupe[0]:.1f}s" if a.coupe else f"Zoom à {a.zoom:.1f}s" if a.zoom is not None
            else f"Retrait à {a.retire:.1f}s" if a.retire is not None else f"Bruitage à {float(a.bruitage[0]):.1f}s"
            if a.bruitage else None)
    if not what:
        raise SystemExit("Précise une retouche : --coupe T D, --zoom T, --retire T ou --bruitage T NOM")
    ws, style = get_ws(a, what)
    if a.coupe:
        R.cut_range(ws, *a.coupe)
    elif a.zoom is not None:
        R.zoom(ws, a.zoom, a.type)
    elif a.retire is not None:
        R.remove(ws, a.retire)
    else:
        R.sfx(ws, float(a.bruitage[0]), a.bruitage[1])
    if a.rendu:
        a.draft = True
        cmd_render(a)


def cmd_annuler(a):
    from .history import entries, undo
    ws = Workspace(a.video, getattr(a, "workdir", None))
    if a.liste:
        for e in reversed(entries(ws)):
            print(f"{e['n']:>3}  {time_ago(e['t']):<14} {e['label']}")
        return
    undo(ws, a.jusqua)


def time_ago(t):
    import time
    d = int(time.time() - t)
    return "à l'instant" if d < 60 else f"il y a {d // 60} min" if d < 3600 else f"il y a {d // 3600} h" if d < 86400 \
        else f"il y a {d // 86400} j"


def cmd_activer(a):
    from .common import STYLES, set_setting
    if not (STYLES / f"{a.name}.json").exists():
        raise SystemExit(f"Style inconnu : {a.name} (voir `monteur styles`)")
    set_setting(style=a.name)
    log(f"Style « {a.name} » activé : utilisé par défaut pour les nouveaux projets (sauf --style).")


def cmd_styles(a):
    from .common import STYLES
    act = active_style()
    for p in sorted(STYLES.glob("*.json")):
        s = load_json(p)
        lib = s.get("library", {})
        print(f"{'●' if p.stem == act else ' '} {p.stem:<22} {s.get('format', {}).get('aspect', 'source'):<7} "
              f"{lib.get('etat', ''):<9} {s.get('description', '')[:70]}")


def cmd_cuts(a):
    from .transitions import KINDS
    for k, v in KINDS.items():
        print(f"{k:<9} {v}")
    print("\nbin/monteur render RUSH.mp4 --cuts mix   (ou « cut.transition » dans le style, « transitions » dans plan.json)")


def cmd_studio(a):
    from .studio import serve
    serve(a.port, a.root, open_browser=not a.no_browser)


def cmd_style(a):
    from .style_clone import clone
    clone(a.sources, a.name, a.transcribe, a.activer, refine=not a.sans_affinage)


def cmd_affiner(a):
    from .style_refine import refine
    refine(a.name)


def cmd_sfx(a):
    from . import sfx
    if a.search:
        sfx.freesound(a.search, a.name)
    print("\n".join(sfx.ensure_library()))


def cmd_motion_new(a):
    from .hyperframes import new
    ws, style = get_ws(a)
    res = "portrait" if portrait(ws, style) else "landscape"
    new(ws, a.name, a.resolution or res, a.example)


def cmd_motion_render(a):
    from .hyperframes import render
    ws, _ = get_ws(a)
    render(ws, a.name, a.start, a.end, not a.opaque, a.layout)


def cmd_attach(a):
    from .generate import attach
    ws, _ = get_ws(a, "Fichier branché sur le plan")
    attach(ws, a.index, a.file, a.kind, a.section)


def cmd_upscale(a):
    from .generate import magnific_upscale
    magnific_upscale(a.image, a.out, a.scale, a.mode, a.prompt)


def cmd_veo(a):
    from .generate import veo_generate
    veo_generate(a.prompt, a.out, a.aspect, a.model, a.image)


def load_env():
    import os
    env = Path(__file__).resolve().parent.parent / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main(argv=None):
    from .common import utf8_console
    utf8_console()
    load_env()
    p = argparse.ArgumentParser(prog="monteur", description="MonteurOS — monteur vidéo automatique")
    sub = p.add_subparsers(dest="cmd", required=True)

    def vid(name, fn, help_):
        s = sub.add_parser(name, help=help_)
        s.add_argument("video")
        s.add_argument("--style", "-s")
        s.add_argument("--workdir")
        s.add_argument("--aspect", choices=ASPECT_CHOICES)
        s.add_argument("--cuts", choices=CUT_CHOICES, help="type de cut entre les plans (voir `monteur cuts`)")
        s.set_defaults(fn=fn)
        return s

    sub.add_parser("doctor", help="Vérifie l'installation").set_defaults(fn=cmd_doctor)
    s = sub.add_parser("whisper", help="Précharge et teste le modèle Whisper")
    s.add_argument("--model", default="small", help="tiny, base, small, medium, large-v3 ou dossier local")
    s.set_defaults(fn=cmd_whisper)
    for name, fn, h in (("prep", cmd_prep, "Transcrit, coupe, planifie, cherche les B-roll"),
                        ("run", cmd_run, "Chaîne complète rush → vidéo finale")):
        s = vid(name, fn, h)
        s.add_argument("--model", default="small")
        s.add_argument("--language")
        s.add_argument("--music")
        s.add_argument("--out")
        s.add_argument("--force", action="store_true")
        s.add_argument("--no-broll", action="store_true")
        s.add_argument("--no-cut", action="store_true")
        s.add_argument("--voix-off", metavar="FICHIER", help="voix off enregistrée (WAV/MP3…) à la place du son du rush")
        s.add_argument("--script", help="script (fichier ou texte) : lu par --moteur, ou calé sur --voix-off")
        s.add_argument("--moteur", default="auto", choices=VOICE_ENGINES)
        s.add_argument("--voix", help="voix du moteur (ID ElevenLabs, nom Inworld, fr-FR-DeniseNeural…)")
        s.add_argument("--hyperframes", action="store_true", help="habillage automatique en cartes animées")
        s.add_argument("--nom", help="nom de l'orateur (médaillon animé au début)")
        s.add_argument("--role", help="titre de l'orateur (avec --nom)")
        s.add_argument("--brief", nargs="?", const="", help="sans --style : style adapté à la vidéo (et au brief : pub, ugc…)")
    s = vid("transcription", cmd_transcription,
            "Importe une transcription (SRT/VTT/JSON, ex. export WhisperAI) à la place de Whisper local")
    s.add_argument("fichier")
    s.add_argument("--prep", action="store_true", help="enchaîne la préparation (coupe, plan, B-roll)")
    s.add_argument("--language")
    s.add_argument("--no-broll", action="store_true")
    s = vid("transcribe", cmd_transcribe, "Transcription mot à mot")
    s.add_argument("--model", default="small")
    s.add_argument("--language")
    vid("cut", cmd_cut, "Supprime blancs, hésitations, répétitions")
    s = vid("appliquer", cmd_appliquer, "Applique un style à un projet (zooms, B-roll, transitions, titre recalculés)")
    s.add_argument("--no-broll", action="store_true")
    s = vid("retouche", cmd_retouche, "Retouche à un instant : --coupe T D, --zoom T, --retire T, --bruitage T NOM")
    s.add_argument("--coupe", nargs=2, type=float, metavar=("T", "DUREE"))
    s.add_argument("--zoom", type=float, metavar="T")
    s.add_argument("--type", default="punch", choices=["punch", "pulse", "ease"])
    s.add_argument("--retire", type=float, metavar="T", help="retire zoom / B-roll / carte / raccord / bruitage à T")
    s.add_argument("--bruitage", nargs=2, metavar=("T", "NOM"))
    s.add_argument("--rendu", action="store_true", help="enchaîne un rendu draft pour voir le résultat")
    s = vid("annuler", cmd_annuler, "Annule la dernière action sur un projet (--liste : historique)")
    s.add_argument("--liste", action="store_true")
    s.add_argument("--jusqua", type=int, metavar="N", help="revient juste avant l'action n°N")
    vid("plan", cmd_plan, "Génère le plan auto (zooms, B-roll, animations)")
    s = vid("voixoff", cmd_voixoff, "Voix off : --fichier voix.mp3 (enregistrée) ou --script (synthèse ElevenLabs/Inworld/Edge)")
    s.add_argument("--fichier", help="voix off enregistrée (WAV, MP3, M4A…)")
    s.add_argument("--script", help="script : fichier .txt (une réplique par ligne) ou texte entre guillemets")
    s.add_argument("--moteur", default="auto", choices=VOICE_ENGINES)
    s.add_argument("--voix")
    s.add_argument("--vitesse", type=float, default=1.0)
    s.add_argument("--original", type=float, metavar="GAIN", help="volume du son du rush sous la voix (0 = muet, défaut 0.15)")
    s.add_argument("--language")
    s.add_argument("--retire", action="store_true", help="retire la voix off (retour au son du rush)")
    s.add_argument("--prep", action="store_true", help="enchaîne la préparation (plan, B-roll) sur la voix off")
    s.add_argument("--no-broll", action="store_true")
    s.add_argument("--hyperframes", action="store_true")
    s = vid("analyse", cmd_analyse, "Analyse la vidéo source : voix ?, format, style conseillé, ce qu'il faut demander")
    s.add_argument("--brief", help="ce que veut l'utilisateur (pub, ugc, tuto…) pour affiner le style conseillé")
    s = vid("habiller", cmd_habiller, "Habillage automatique : cartes animées Hyperframes sur les chiffres, mots forts, nom")
    s.add_argument("--nom")
    s.add_argument("--role")
    s.add_argument("--max", type=int, default=4)
    s.add_argument("--sans-hyperframes", action="store_true", help="animations texte natives seulement")
    s.add_argument("--essai", action="store_true", help="affiche les cartes prévues sans rien rendre")
    vid("broll", cmd_broll, "Télécharge les illustrations du plan")
    s = vid("render", cmd_render, "Rendu versionné (master, ou --draft rapide + vérification)")
    s.add_argument("--out")
    s.add_argument("--music")
    s.add_argument("--draft", action="store_true", help="demi-résolution, ~4× plus rapide, puis vérification")
    s.add_argument("--verif", action="store_true", help="vérifier aussi le master")
    s = vid("verif", cmd_verif, "Contrôle qualité du dernier rendu (noirs, blancs, saturation, mots coupés…)")
    s.add_argument("--file")
    s = vid("retours", cmd_retours, "Retours frame par frame : liste / ajoute / marque appliqués")
    s.add_argument("--ajoute", type=float, metavar="SECONDES")
    s.add_argument("--texte")
    s.add_argument("--applique", type=int, nargs="+", metavar="ID")
    s.add_argument("--tous", action="store_true")
    s = vid("projet", cmd_projet, "Infos projet (état, versions, retours) ; --etat livré pour livrer")
    s.add_argument("--titre")
    s.add_argument("--etat", choices=["livré", "en cours"])
    s.add_argument("--famille")
    s.add_argument("--type")
    s = vid("carte", cmd_carte, "Pose une carte animée de la bibliothèque (rendue via Hyperframes)")
    s.add_argument("card")
    s.add_argument("--start", type=float, required=True)
    s.add_argument("--duree", type=float)
    s.add_argument("--set", action="append", metavar="clé=valeur")
    s = vid("motion-new", cmd_motion_new, "Crée une composition Hyperframes")
    s.add_argument("name")
    s.add_argument("--example", default="blank")
    s.add_argument("--resolution")
    s = vid("motion-render", cmd_motion_render, "Rend une composition Hyperframes et l'ajoute au plan")
    s.add_argument("name")
    s.add_argument("--start", type=float, required=True)
    s.add_argument("--end", type=float)
    s.add_argument("--opaque", action="store_true", help="MP4 plein écran au lieu d'un overlay transparent")
    s.add_argument("--layout", choices=["overlay", "full", "pip"])
    s = vid("attach", cmd_attach, "Branche un fichier sur une entrée du plan")
    s.add_argument("index", type=int)
    s.add_argument("file")
    s.add_argument("--kind", choices=["video", "image"])
    s.add_argument("--section", default="broll", choices=["broll", "motion"])

    s = sub.add_parser("style", help="Copie le style de vidéos (URLs YouTube ou MP4)")
    s.add_argument("sources", nargs="+")
    s.add_argument("--name", required=True)
    s.add_argument("--transcribe", action="store_true", help="mesure aussi le débit de parole")
    s.add_argument("--activer", action="store_true", help="active le style pour les nouveaux projets")
    s.add_argument("--sans-affinage", action="store_true", help="saute l'analyse fine (cuts, zooms, sous-titres)")
    s.set_defaults(fn=cmd_style)
    s = sub.add_parser("affiner", help="Affine un style copié : vrais types de cut, zooms, place/taille/couleurs des sous-titres")
    s.add_argument("name")
    s.set_defaults(fn=cmd_affiner)
    s = sub.add_parser("activer", help="Active un style : utilisé par défaut pour les nouveaux projets")
    s.add_argument("name")
    s.set_defaults(fn=cmd_activer)
    sub.add_parser("styles", help="Liste les styles (bibliothèque) et le style actif").set_defaults(fn=cmd_styles)
    sub.add_parser("cuts", help="Types de cut / transitions entre les plans").set_defaults(fn=cmd_cuts)
    s = sub.add_parser("cartes", help="Catalogue des cartes animées (--cherche pour filtrer)")
    s.add_argument("--cherche", "-q", help="mot-clé : chiffre, nom, liste, prix, avis…")
    s.add_argument("--categorie")
    s.set_defaults(fn=cmd_cartes)
    s = sub.add_parser("voix", help="Voix off française (Edge TTS en ligne, sinon espeak-ng + MBROLA)")
    s.add_argument("texte", nargs="?", default="")
    s.add_argument("--out", default="voix.wav", help="fichier WAV (ou dossier avec --fichier)")
    s.add_argument("--fichier", help="script texte : une réplique par ligne")
    s.add_argument("--moteur", default="auto", choices=VOICE_ENGINES)
    s.add_argument("--voix", help="ID ElevenLabs, nom Inworld, fr-FR-DeniseNeural, mb-fr1…")
    s.add_argument("--vitesse", type=float, default=1.0)
    s.add_argument("--liste", action="store_true", help="moteurs disponibles")
    s.add_argument("--liste-voix", action="store_true", help="voix disponibles (ElevenLabs, Inworld, Edge)")
    s.set_defaults(fn=cmd_voix)
    s = sub.add_parser("cles", help="Clés API (.env) : état, --set CLE=valeur, --retire CLE, --test")
    s.add_argument("--set", action="append", metavar="CLE=valeur")
    s.add_argument("--retire", action="append", metavar="CLE")
    s.add_argument("--test", action="store_true", help="teste la connexion à chaque service configuré")
    s.set_defaults(fn=cmd_cles)
    s = sub.add_parser("avant-apres", help="Format reel Avant/après (2 vidéos empilées + titre)")
    s.add_argument("apres", help="version transformée")
    s.add_argument("avant", help="version originale")
    s.add_argument("--out", required=True)
    s.add_argument("--title")
    s.add_argument("--subtitle")
    s.add_argument("--labels", default="Transformé,Originale")
    s.add_argument("--audio", choices=["apres", "avant"], default="apres")
    s.add_argument("--aspect", choices=ASPECT_CHOICES[1:], default="9:16", help="16:9 / 1:1 : côte à côte")
    s.set_defaults(fn=cmd_avant_apres)
    s = sub.add_parser("slideshow", help="Vidéo produit à partir de photos (Ken Burns)")
    s.add_argument("images", nargs="+")
    s.add_argument("--out", required=True)
    s.add_argument("--per", type=float, default=2.5, help="secondes par image")
    s.add_argument("--aspect", choices=ASPECT_CHOICES[1:])
    s.add_argument("--audio", help="voix off ou musique")
    s.set_defaults(fn=cmd_slideshow)
    s = sub.add_parser("charte", help="Extrait une charte graphique (couleurs, typo) d'images/vidéos/URL → thème Studio")
    s.add_argument("sources", nargs="+")
    s.add_argument("--name", required=True)
    s.add_argument("--sans-style", action="store_true", help="ne crée pas le style vidéo styles/<nom>.json")
    s.set_defaults(fn=cmd_charte)
    s = sub.add_parser("facecam", help="Coupe fine d'un rush facecam (skill coupe-facecam : Scribe + VAD, Descript, éditeur)",
                       description="analyse RUSH [--script s.txt] | rendu DOSSIER [--sans-eyecontact] | retouches DOSSIER | "
                                   "eyecontact DOSSIER | importer DOSSIER [--prep]")
    s.add_argument("action", choices=["analyse", "rendu", "retouches", "eyecontact", "importer"])
    s.add_argument("args", nargs=argparse.REMAINDER, help="arguments de coupe.py (voir skills/coupe-facecam/SKILL.md)")
    s.set_defaults(fn=cmd_facecam)
    s = sub.add_parser("notifier", help="Envoie un message Telegram (étape à valider, question bloquante…)")
    s.add_argument("message", nargs="+")
    s.set_defaults(fn=cmd_notifier)
    s = sub.add_parser("studio", help="Interface web MonteurOS Studio")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--root", default=".", help="dossier des rushs")
    s.add_argument("--no-browser", action="store_true", help="n'ouvre pas le navigateur automatiquement")
    s.set_defaults(fn=cmd_studio)
    s = sub.add_parser("sfx", help="Liste / télécharge des bruitages")
    s.add_argument("--search")
    s.add_argument("--name")
    s.set_defaults(fn=cmd_sfx)
    s = sub.add_parser("upscale", help="Upscale Magnific d'une image")
    s.add_argument("image")
    s.add_argument("--out")
    s.add_argument("--scale", default="2x")
    s.add_argument("--mode", default="precision", choices=["precision", "creative"])
    s.add_argument("--prompt")
    s.set_defaults(fn=cmd_upscale)
    s = sub.add_parser("veo", help="Génère un clip IA (Veo — moteur de Google Flow)")
    s.add_argument("prompt")
    s.add_argument("--out", required=True)
    s.add_argument("--aspect", default="16:9")
    s.add_argument("--model")
    s.add_argument("--image")
    s.set_defaults(fn=cmd_veo)

    a = p.parse_args(argv)
    try:
        a.fn(a)
    except RuntimeError as e:  # détail d'abord, cause en dernière ligne (c'est elle que l'Activité du Studio affiche)
        lines = str(e).splitlines() or ["erreur"]
        if a.cmd in ("render", "run", "prep"):
            from .notify import notify
            notify(f"échec de « {a.cmd} » : {lines[0][:200]}")
        if len(lines) > 1:
            log("\n".join(lines[1:][-20:]))
        log("❌ " + lines[0])
        sys.exit(1)


if __name__ == "__main__":
    main()
