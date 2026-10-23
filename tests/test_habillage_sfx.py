"""Élisions, nom / liste détectés, bruitages placés et mesurés, polices du style, cartes aux couleurs du style."""
import unittest
from unittest import mock

from monteur.common import load_style, merge_elisions


def words(text, step=0.4):
    return [{"w": w, "start": round(i * step, 2), "end": round(i * step + step - 0.05, 2)} for i, w in enumerate(text.split())]


class Elisions(unittest.TestCase):
    def test_recolle(self):
        out = [w["w"] for w in merge_elisions(words("moi c 'est Soprador l' homme peut -être"))]
        self.assertEqual(out, ["moi", "c'est", "Soprador", "l'homme", "peut-être"])

    def test_horodatage(self):
        w = merge_elisions(words("c 'est"))
        self.assertEqual((w[0]["start"], w[0]["end"]), (0.0, 0.75))


class Detection(unittest.TestCase):
    def test_nom(self):
        from monteur.habillage import detect_name
        self.assertEqual(detect_name(merge_elisions(words("Bienvenue, moi c 'est Soprador. Aujourd'hui")))[1], "Soprador")
        self.assertEqual(detect_name(words("Salut je m'appelle Léa Martin et"))[1], "Léa Martin")
        self.assertIsNone(detect_name(words("je suis content de vous voir")))

    def test_liste(self):
        from monteur.habillage import detect_list
        st, en, items, kicker = detect_list(words("Voici trois astuces. Premièrement, coupez les blancs. "
                                                  "Deuxièmement, ajoutez des sous-titres. Troisièmement, soignez le son."))
        self.assertEqual(items, ["coupez les blancs", "ajoutez des sous-titres", "soignez le son"])
        self.assertIn("astuces", kicker)
        self.assertIsNone(detect_list(words("Premièrement, rien d'autre.")))

    def test_cartes_du_style_et_place(self):
        from monteur.habillage import plan_cards
        w = merge_elisions(words("Bienvenue, moi c 'est Soprador. Je vais vous montrer deux astuces. Premièrement, "
                                 "coupez les blancs. Deuxièmement, ajoutez des sous-titres. Grâce à ça j'ai gagné "
                                 "12 000 abonnés.", 0.5))
        plan = {"duration": 20, "motion": [{"type": "title", "start": 0.15, "end": 2.3}], "broll": [], "emphasis": []}
        style = {"library": {"cards": ["ecran.rail", "stat.courbe"]}}
        cards = plan_cards(w, plan, style)
        ids = [c["card"] for c in cards]
        self.assertEqual(ids[0], "medaillon.nom")
        self.assertIn("ecran.rail", ids)  # la carte « liste » du style, pas celle par défaut
        self.assertIn("stat.courbe", ids)
        self.assertGreaterEqual(cards[0]["start"], 2.3)  # le nom arrive après le titre d'accroche
        for a, b in zip(cards, cards[1:]):
            self.assertLessEqual(a["end"], b["start"])  # jamais deux cartes en même temps


class Bruitages(unittest.TestCase):
    def setUp(self):
        self.style = load_style("default")

    def test_espacement_et_priorites(self):
        from monteur.sfx import auto_events
        plan = {"duration": 30, "transitions": [{"t": 5.0, "kind": "whip"}],
                "zooms": [{"start": 5.2, "end": 6, "kind": "punch"}, {"start": 12, "end": 13, "kind": "punch"}],
                "motion": [{"type": "title", "start": 0.15, "end": 2.3}], "sfx": [{"t": 9.0, "name": "ding"}, {"t": 9.4, "name": "pop"}]}
        ev = auto_events(plan, self.style, -30.0, words("un deux trois", 4.0))
        names = [(e["name"], e["why"]) for e in ev]
        self.assertIn(("ding", "posé à la main"), names)          # le choix de l'utilisateur passe toujours
        self.assertIn(("whoosh", "raccord whip"), names)
        self.assertEqual(sum(w == "posé à la main" for _, w in names), 2)  # même rapprochés, les deux restent
        self.assertTrue(all(e["t"] >= 0 for e in ev))
        title = next(e for e in ev if e["why"] == "apparition title")
        self.assertEqual(title["name"], "pop")  # pas de riser coupé à 0 s : pas la place avant le titre

    def test_volume_sous_la_voix(self):
        from monteur.sfx import auto_events, level_db
        plan = {"duration": 10, "motion": [{"type": "cta", "start": 6, "end": 9, "sfx": "ding"}]}
        e = auto_events(plan, self.style, -30.0, [])[0]
        import math
        self.assertAlmostEqual(20 * math.log10(e["gain"]) + level_db(e["file"]), -30.0 - 17, delta=0.5)

    def test_densite(self):
        from monteur.sfx import auto_events
        plan = {"duration": 10, "zooms": [{"start": t, "end": t + 0.5, "kind": "punch", "sfx": "pop"} for t in range(0, 10)]}
        self.assertLessEqual(len(auto_events(plan, self.style, -20.0, [])), 3)  # 14/min → 2-3 sur 10 s


class Polices(unittest.TestCase):
    def test_installee_et_graisse(self):
        from monteur import fonts
        self.assertEqual(fonts.resolve("Montserrat ExtraBold"), "Montserrat ExtraBold")
        self.assertTrue(fonts.is_bold_face("Montserrat Black"))

    def test_repli_sans_reseau(self):
        from monteur import fonts
        with mock.patch.object(fonts, "download", return_value=None):
            self.assertEqual(fonts.resolve("Police Inconnue Black"), "Montserrat Black")
            self.assertEqual(fonts.resolve("Mystery Serif Display"), "Instrument Serif")

    def test_titres_dans_la_police_display_du_style(self):
        s = load_style("explainer-editorial")
        self.assertEqual(s["motion"]["font"], "Fraunces")

    def test_carte_aux_couleurs_du_style(self):
        from monteur.cards import build
        style = load_style("default")
        style["motion"]["accent"] = "#12AB34"
        html, _, _ = build("stat.courbe", {"value": "5"}, 1080, 1920, None, style)
        self.assertIn("--accent:#12AB34", html)
        self.assertIn("--font-body:", html)


if __name__ == "__main__":
    unittest.main()
