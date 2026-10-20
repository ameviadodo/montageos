"""Tests : types de cut, ratios, recherche de cartes, styles clonés et bibliothèque multi-formats."""
import json
import tempfile
import unittest
from pathlib import Path

from monteur import transitions as tr
from monteur.cards import catalog, search
from monteur.common import STYLES, Workspace, load_style, save_json
from monteur.render import ASPECTS, aspect_of
from monteur.studio import library
from monteur.style_clone import pick_cards, profile_to_style, slug


class Transitions(unittest.TestCase):
    def ws(self, d, keep):
        rush = Path(d) / "rush.mp4"
        rush.write_bytes(b"")
        ws = Workspace(rush)
        save_json(ws.edl, {"keep": keep})
        ws.cut_video.write_bytes(b"")
        return ws

    def test_points_et_mix(self):
        with tempfile.TemporaryDirectory() as d:
            ws = self.ws(d, [[0, 2], [3, 5], [6, 6.5], [7, 10], [11, 14]])
            self.assertEqual(tr.cut_points(ws), [2.0, 4.0, 4.5, 7.5])
            style = load_style()
            style["cut"]["transition"] = "mix"
            out = tr.auto_transitions(ws, style, 10)
            self.assertEqual([x["t"] for x in out], [2.0, 4.0, 7.5])  # 4.5 trop proche (écart < 1,2 s)
            self.assertEqual([x["kind"] for x in out], ["zoomcut", "whip", "zoomcut"])
            style["cut"]["transition"] = "hard"
            self.assertEqual(tr.auto_transitions(ws, style, 10), [])

    def test_sans_coupe_pas_de_transition(self):
        with tempfile.TemporaryDirectory() as d:
            ws = self.ws(d, [[0, 2], [3, 5]])
            ws.cut_video.unlink()
            self.assertEqual(tr.cut_points(ws), [])

    def test_filtres_et_zooms(self):
        trans = [{"t": 2, "kind": "flash"}, {"t": 4, "kind": "dip"}, {"t": 6, "kind": "glitch"},
                 {"t": 8, "kind": "whip"}, {"t": 9, "kind": "zoomcut"}, {"t": 11, "kind": "zoomcut"}]
        f = ";".join(tr.filters(trans))
        self.assertIn("eq=brightness='0.550*max(0,1-abs(t-2.000)/0.070)+-0.950*", f)
        self.assertIn("eval=frame", f)
        self.assertIn("rgbashift", f)
        self.assertIn("tmix=frames=4", f)
        z = tr.zooms(trans, 14)
        self.assertEqual([(x["kind"], x["start"]) for x in z], [("pulse", 7.88), ("punch", 9)])  # 1 zoom cut sur 2
        self.assertEqual(z[1]["end"], 11)
        names = [e["name"] for e in tr.sfx_events(trans)]
        self.assertEqual(names, ["camera", "glitch", "whoosh"])


class Ratios(unittest.TestCase):
    def test_aspect_of(self):
        self.assertEqual(aspect_of(1080, 1350), "4:5")
        self.assertEqual(aspect_of(720, 1280), "9:16")
        self.assertEqual(aspect_of(3840, 1600), "21:9")
        self.assertEqual(aspect_of(1000, 1000), "1:1")
        for w, h in ASPECTS.values():
            self.assertEqual((w % 2, h % 2), (0, 0))

    def test_formats_de_la_bibliotheque(self):
        lib = library()
        ratios = {r for f in lib["formats"] for r in f["ratios"]}
        self.assertTrue({"9:16", "16:9", "1:1", "4:5", "21:9"} <= ratios)
        self.assertGreaterEqual(len(lib["formats"]), 7)
        self.assertIn("mix", lib["cuts"])


class Bibliotheque(unittest.TestCase):
    def test_chaque_style_a_des_cartes_existantes(self):
        ids = {c["id"] for c in catalog()}
        for p in STYLES.glob("*.json"):
            cards = json.loads(p.read_text(encoding="utf-8")).get("library", {}).get("cards", [])
            self.assertTrue(cards, f"{p.stem} sans cartes")
            self.assertTrue(set(cards) <= ids, f"{p.stem} : cartes inconnues {set(cards) - ids}")
            load_style(p.stem)

    def test_recherche_sans_accents(self):
        self.assertEqual({c["id"] for c in search("temoignage")}, {"avis.etoiles", "citation.surligne"})
        self.assertIn("stat.courbe", [c["id"] for c in search("CHIFFRE")])
        self.assertEqual([c["id"] for c in search("prix promo")], ["prix.promo"])
        self.assertTrue(all(c["category"] == "Titres" for c in search(None, "titres")))
        self.assertEqual(search("zzz-introuvable"), [])

    def test_style_clone(self):
        prof = {"source": "/x/ref.mp4", "title": "Viral", "url": "https://youtu.be/abc", "aspect": "9:16",
                "avg_shot_s": 1.4, "cuts_per_minute": 42, "silence_ratio": 0.02, "lufs": -12.5,
                "colors": ["#FFE600", "#00E5FF"]}
        s = profile_to_style([prof], "viral")
        self.assertEqual(s["cut"]["transition"], "mix")
        self.assertEqual(s["subtitles"]["highlight"], "#FFE600")
        self.assertEqual(s["library"]["etat"], "Copié")
        self.assertEqual(s["library"]["sources"], ["https://youtu.be/abc"])
        self.assertEqual(s["library"]["cards"], pick_cards(42, "9:16"))
        self.assertEqual(slug("Mon Style ÉTÉ !"), "mon-style-ete")


if __name__ == "__main__":
    unittest.main()


class Affinage(unittest.TestCase):
    def test_decide(self):
        from monteur.style_refine import decide
        zone = {"found": True, "y": 0.62, "band": [0.6, 0.65], "size": 0.075, "max_words": 2,
                "primary": "#FFFFFF", "accent": "#FFE600"}
        out, rep = decide(["flash", "flash", "hard"], [{"kind": "punch", "scale": 1.15}] * 6, 30, zone)
        self.assertEqual(out["cut"]["transition"], "flash")
        self.assertEqual(out["zoom"]["every_s"], 5.0)
        self.assertEqual(out["subtitles"]["position"], "center")
        self.assertAlmostEqual(out["subtitles"]["margin_v"], 0.35)
        self.assertEqual((out["subtitles"]["highlight"], out["subtitles"]["max_words"]), ("#FFE600", 2))
        out, _ = decide(["whip", "glitch", "hard", "whip", "glitch"], [], 30, {"found": False})
        self.assertEqual(out["cut"]["transition"], "mix")
        self.assertNotIn("subtitles", out)  # sans sous-titres dans la référence, on garde ceux du style
        out, _ = decide(["hard"] * 9 + ["dip"], [], 30, None)
        self.assertEqual(out["cut"]["transition"], "hard")


class TranscriptionImportee(unittest.TestCase):
    def test_mots_hors_des_pauses(self):
        from monteur.transcript_import import segments_to_words
        w = segments_to_words([{"start": 0, "end": 4, "text": "un deux trois quatre"}], [(1.5, 2.5), (3.6, 5)])
        for x in w:
            self.assertFalse(1.5 < x["start"] < 2.5 or 1.5 < x["end"] < 2.5, x)  # rien dans la pause
            self.assertLessEqual(x["end"], 3.6)
        self.assertTrue(w[-1]["start"] >= 2.5)
        self.assertEqual(segments_to_words([{"start": 0, "end": 2, "text": "vraiment ?"}])[0]["w"], "vraiment ?")

    def test_remap_garde_le_mot_qui_deborde(self):
        from monteur.cut import remap_transcript
        tr = {"words": [{"w": "euh", "start": 0.1, "end": 0.3}, {"w": "bien.", "start": 1.0, "end": 1.6},
                        {"w": "Alors", "start": 2.0, "end": 2.4}]}
        out = remap_transcript(tr, [[0.0, 1.4], [2.0, 3.0]], removed=[0])
        self.assertEqual([w["w"] for w in out["words"]], ["bien.", "Alors"])
        self.assertAlmostEqual(out["words"][1]["start"], 1.4)

    def test_verif_tolere_les_horodatages_approximatifs(self):
        from monteur.verify import cut_words
        keep = [[0, 1.05]]
        self.assertEqual(cut_words({"words": [{"w": "x", "start": 0.6, "end": 1.1, "p": 0.9}]}, keep), [])
        self.assertEqual(len(cut_words({"words": [{"w": "x", "start": 0.6, "end": 1.4, "p": 1.0}]}, keep)), 1)


class Studio(unittest.TestCase):
    def test_version_api_partagee_avec_la_page(self):
        import re
        from monteur.studio import API
        html = (Path(__file__).resolve().parent.parent / "ui" / "index.html").read_text(encoding="utf-8")
        self.assertEqual(int(re.search(r"const API_VERSION = (\d+)", html).group(1)), API)
