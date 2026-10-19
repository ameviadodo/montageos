"""Tests des fonctions issues d'EditingOS : cartes, retours, versions de rendu, vérification, bibliothèque."""
import json
import tempfile
import unittest
from pathlib import Path

from monteur import review
from monteur.cards import build, catalog
from monteur.common import Workspace
from monteur.render import next_render
from monteur.studio import front_matter, library, theme_css
from monteur.verify import cut_words


class Cartes(unittest.TestCase):
    def test_catalogue(self):
        ids = {c["id"] for c in catalog()}
        self.assertTrue({"ecran.rail", "stat.courbe", "medaillon.nom", "section.stage"} <= ids)
        for c in catalog():
            self.assertIn(c["mode"], ("overlay", "full"))

    def test_build_remplit_les_variables(self):
        html, card, dur = build("medaillon.nom", {"name": "ALEX <B>", "role": "Monteur"}, 1080, 1920, 3)
        self.assertIn("ALEX &lt;B>", html)
        self.assertIn('data-width="1080"', html)
        self.assertIn("--u:10.8px", html)
        self.assertEqual(dur, 3.0)
        self.assertNotIn("{{", html)
        self.assertIn('window.__timelines["main"]', html)


class Retours(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Workspace(Path(self.tmp.name) / "rush.mp4")

    def tearDown(self):
        self.tmp.cleanup()

    def test_cycle(self):
        review.add(self.ws, 1.5, "zoom trop tôt", 30)
        review.add(self.ws, 3.0, "faute « vidéo »", 30)
        items = review.load(self.ws)["items"]
        self.assertEqual([i["frame"] for i in items], [45, 90])
        review.send(self.ws)
        self.assertEqual({i["status"] for i in review.load(self.ws)["items"]}, {"envoyé"})
        review.mark(self.ws, [1])
        txt = review.as_text(self.ws)
        self.assertIn("#2 [00:03.00 · f0090]", txt)
        self.assertNotIn("#1 ", txt)

    def test_versions(self):
        a = next_render(self.ws, True)
        self.assertEqual(a.name, "rush-v01-draft.mp4")
        a.write_bytes(b"x")
        self.assertEqual(next_render(self.ws, False).name, "rush-v02-master.mp4")


class Verification(unittest.TestCase):
    def test_mots_coupes(self):
        t = {"words": [{"w": "bonjour", "start": 0.0, "end": 0.5}, {"w": "tout", "start": 0.6, "end": 1.0}]}
        self.assertEqual(cut_words(t, [[0.0, 0.8]])[0]["w"], "tout")
        self.assertEqual(cut_words(t, [[0.0, 0.55]]), [])


class Bibliotheque(unittest.TestCase):
    def test_formats_et_charte(self):
        lib = library()
        self.assertEqual([f["nom"] for f in lib["formats"]][:2], ["Split carte", "Avant/après"])
        self.assertTrue(any(t["name"] == "nocturne" for t in lib["charte"]))
        noct = next(s for s in lib["references"] if s["name"] == "nocturne")
        self.assertIn("#FFD935", noct["palette"])
        self.assertIn("--accent:#FFD935", theme_css("nocturne"))

    def test_front_matter(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write("---\nnom: Test\netat: Exemple\n---\n# Corps\n")
        meta, body = front_matter(Path(f.name))
        self.assertEqual(meta, {"nom": "Test", "etat": "Exemple"})
        self.assertTrue(body.startswith("# Corps"))


if __name__ == "__main__":
    unittest.main()
