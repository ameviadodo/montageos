"""Non-régression des correctifs : python -m unittest discover tests"""
import json
import tempfile
import unittest
from pathlib import Path

from monteur.cut import find_removals
from monteur.subtitles import build_subtitles, ts
from monteur.transcript_import import parse_json

CFG = {"remove_fillers": True, "fillers": ["euh"], "remove_retakes": True, "retake_similarity": 0.72}


def words(text, step=0.3):
    return [{"w": w, "start": round(i * step, 3), "end": round(i * step + step - 0.05, 3)}
            for i, w in enumerate(text.split())]


class Correctifs(unittest.TestCase):
    def test_horodatage_ass_arrondi(self):
        self.assertEqual(ts(59.996), "0:01:00.00")  # et non « 0:00:60.00 », illisible par libass
        self.assertEqual(ts(3599.999), "1:00:00.00")
        self.assertEqual(ts(1.234), "0:00:01.23")

    def test_doublons_legitimes_gardes(self):
        w = words("nous nous sommes trompés et vous vous en doutez")
        self.assertEqual(find_removals(w, CFG), {})

    def test_begaiement_toujours_coupe(self):
        self.assertEqual(sorted(find_removals(words("le le marketing"), CFG)), [0])

    def test_json_millisecondes_clip_court(self):
        seg = json.dumps([{"start": 1200, "end": 3400, "text": "bonjour"}])
        self.assertEqual(parse_json(seg, duration=20)[0]["start"], 1.2)  # 20 s de rush : ce sont des ms
        self.assertEqual(parse_json(json.dumps([{"start": 1.2, "end": 3.4, "text": "x"}]), duration=20)[0]["end"], 3.4)

    def test_sous_titres_masques_pendant_le_titre(self):
        style = json.loads(Path(__file__).resolve().parent.parent.joinpath("styles", "default.json").read_text("utf-8"))
        tr = {"words": words("bonjour à tous aujourd'hui on parle ventes et marketing digital", 0.4)}
        tr["words"][0]["start"] = 0.05  # la voix démarre avant le titre (0.15 s)
        plan = {"motion": [{"start": 0.15, "end": 2.3, "type": "title", "text": "BONJOUR"}]}
        with tempfile.TemporaryDirectory() as d:
            out = build_subtitles(tr, plan, style, 1080, 1920, Path(d) / "s.ass")
            starts = [l.split(",")[1] for l in out.read_text("utf-8").splitlines() if l.startswith("Dialogue")]
        self.assertTrue(starts)
        self.assertTrue(all(s >= "0:00:02" for s in starts), starts)


if __name__ == "__main__":
    unittest.main()
