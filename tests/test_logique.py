"""Tests de la logique pure (sans ffmpeg) : python -m unittest discover tests"""
import unittest

from monteur.cut import find_removals, merge, remap_transcript, subtract
from monteur.focus import crop_x_expr, keyframes
from monteur.plan import keywords
from monteur.render import zoom_expr
from monteur.subtitles import group_words, wrap

CFG = {"remove_fillers": True, "fillers": ["euh", "hum"], "remove_retakes": True, "retake_similarity": 0.72}


def words(text, t0=0.0, step=0.3, gaps=None):
    out, t = [], t0
    for i, w in enumerate(text.split()):
        t += (gaps or {}).get(i, 0)
        out.append({"w": w, "start": round(t, 3), "end": round(t + step - 0.05, 3)})
        t += step
    return out


class Coupe(unittest.TestCase):
    def test_filler(self):
        w = words("bonjour euh tout le monde")
        self.assertEqual(find_removals(w, CFG), {1: "filler"})

    def test_begaiement(self):
        w = words("je pense que je pense que c'est bien")
        self.assertEqual(sorted(find_removals(w, CFG)), [0, 1, 2])

    def test_prise_ratee_garde_la_derniere(self):
        w = words("la première étape c'est le", 0) + words("la première étape c'est le marketing digital.", 3)
        drop = find_removals(w, CFG)
        self.assertTrue(all(i < 5 for i in drop))
        self.assertTrue(drop)

    def test_pas_de_faux_positif(self):
        w = words("le marketing digital fonctionne. ensuite on automatise les emails.")
        self.assertEqual(find_removals(w, CFG), {})

    def test_intervalles(self):
        self.assertEqual(merge([[0, 1], [1.2, 2], [5, 6]], gap=0.3), [[0, 2], [5, 6]])
        self.assertEqual(subtract([[0, 10]], [(2, 3), (5, 6)]), [[0, 2], [3, 5], [6, 10]])

    def test_remap(self):
        t = {"words": [{"w": "a", "start": 1.0, "end": 1.4}, {"w": "b", "start": 5.0, "end": 5.4}]}
        r = remap_transcript(t, [[0.9, 1.5], [4.9, 5.5]])
        self.assertAlmostEqual(r["words"][1]["start"], 0.6 + 0.1, places=3)


class Rendu(unittest.TestCase):
    def test_zoom_expr(self):
        z = zoom_expr([{"start": 1, "end": 2, "kind": "punch", "scale": 1.2},
                       {"start": 3, "end": 3.5, "kind": "pulse", "scale": 1.1},
                       {"start": 4, "end": 6, "kind": "ease", "scale": 1.05}], {"scale": 1.1, "ease_s": 0.3})
        self.assertTrue(z.startswith("1+0.2000*between(it,1.000,2.000)"))
        self.assertIn("max(0,1-abs(it-3.250)/0.250)", z)
        self.assertIn("clip((it-4.000)/0.3,0,1)", z)
        self.assertEqual(zoom_expr([], {"scale": 1.1}), "1")

    def test_suivi_visage(self):
        faces = [(t / 2, 0.25 if t < 10 else 0.75, 0.4) for t in range(24)]
        self.assertEqual(len(keyframes(faces)), 2)
        expr = crop_x_expr(faces, 1920, 607.5)
        self.assertIn("between(t", expr)
        self.assertIsNone(crop_x_expr([], 1920, 607.5))


class Texte(unittest.TestCase):
    def test_groupes(self):
        g = group_words(words("un deux trois quatre cinq. six"), 3, 30)
        self.assertEqual([len(x) for x in g], [3, 2, 1])

    def test_wrap(self):
        self.assertEqual(wrap("DOUBLE TES VENTES MAINTENANT", 12), "DOUBLE TES\\NVENTES\\NMAINTENANT")

    def test_mots_cles(self):
        self.assertEqual(keywords("Ensuite il faut automatiser vos emails".split())[0], "automatiser")


if __name__ == "__main__":
    unittest.main()


class Corrections(unittest.TestCase):
    def test_sortie_plafonnee_1080p(self):
        from monteur.render import out_size
        self.assertEqual(out_size({"width": 2160, "height": 3840}, {"aspect": "source"}), (1080, 1920))
        self.assertEqual(out_size({"width": 1280, "height": 720}, {"aspect": "source"}), (1280, 720))
        self.assertEqual(out_size({"width": 3840, "height": 2160}, {"aspect": "9:16"}), (1080, 1920))

    def test_zooms_sans_transcription(self):
        import tempfile
        from pathlib import Path
        from unittest import mock
        from monteur.common import Workspace, load_json, load_style, save_json
        from monteur.plan import auto_plan
        with tempfile.TemporaryDirectory() as d:
            ws = Workspace(Path(d) / "rush.mp4")
            save_json(ws.edl, {"keep": [[0, 4.1], [6, 12], [14, 20]]})
            with mock.patch("monteur.plan.probe", return_value={"duration": 16.1}):
                auto_plan(ws, load_style("default"), None)
            z = load_json(ws.plan)["zooms"]
            self.assertTrue(z)
            self.assertIn(4.1, [x["start"] for x in z])   # zoom calé sur le point de coupe
