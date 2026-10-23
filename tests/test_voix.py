"""Voix off ElevenLabs / Inworld (réponses d'API simulées), script → voix de projet, clés .env, habillage."""
import base64
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from monteur import keys, voiceover, voixoff
from monteur.common import Workspace

FFMPEG = shutil.which("ffmpeg") is not None


def fake_mp3(seconds=1.2):
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "a.mp3"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"sine=f=200:d={seconds}", out],
                       check=True)
        return base64.b64encode(out.read_bytes()).decode()


def eleven_response(text, seconds=1.2):
    n = len(text)
    starts = [round(i * seconds / n, 3) for i in range(n)]
    return {"audio_base64": fake_mp3(seconds), "alignment": {
        "characters": list(text), "character_start_times_seconds": starts,
        "character_end_times_seconds": [s + seconds / n for s in starts]}}


@unittest.skipUnless(FFMPEG, "ffmpeg requis")
class Moteurs(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.env = mock.patch.dict(os.environ, {"ELEVENLABS_API_KEY": "sk_test", "INWORLD_API_KEY": "abc:def"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.d, ignore_errors=True)

    def test_elevenlabs_mots_horodates(self):
        calls = []

        def post(url, payload, headers, timeout=180):
            calls.append((url, payload, headers))
            return eleven_response(payload["text"])
        with mock.patch.object(voiceover, "_post", post):
            wav, d, eng, words = voiceover.synth_timed("Bonjour à tous !", self.d / "v.wav", "elevenlabs")
        url, payload, headers = calls[0]
        self.assertIn("/v1/text-to-speech/JBFqnCBsd6RMkjVDRZzb/with-timestamps", url)
        self.assertEqual(headers, {"xi-api-key": "sk_test"})
        self.assertEqual(payload["model_id"], "eleven_multilingual_v2")
        self.assertEqual(eng, "elevenlabs")
        self.assertAlmostEqual(d, 1.2, delta=0.1)
        self.assertEqual([w["w"] for w in words], ["Bonjour", "à", "tous !"])

    def test_inworld_et_repli_sans_horodatage(self):
        bodies = []

        def post(url, payload, headers, timeout=180):
            bodies.append(dict(payload))
            if "timestampType" in payload:  # compte qui refuse l'horodatage : on doit réessayer sans
                raise RuntimeError("HTTP 400 : timestamps unsupported")
            self.assertEqual(headers["Authorization"], "Basic " + base64.b64encode(b"abc:def").decode())
            return {"audioContent": fake_mp3(0.8)}
        with mock.patch.object(voiceover, "_post", post):
            wav, d, eng, words = voiceover.synth_timed("Salut", self.d / "i.wav", "inworld", voice="Alain")
        self.assertEqual(bodies[0]["voiceId"], "Alain")
        self.assertEqual(bodies[0]["timestampType"], "WORD")
        self.assertNotIn("timestampType", bodies[1])
        self.assertIsNone(words)
        self.assertTrue(wav.exists())

    def test_auto_contourne_un_moteur_en_panne(self):
        def post(url, payload, headers, timeout=180):
            if "elevenlabs" in url:
                raise RuntimeError("HTTP 401 : invalid key")
            return {"audioContent": fake_mp3(0.5),
                    "timestampInfo": {"wordAlignment": {"words": ["Go"], "wordStartTimeSeconds": [0.05],
                                                        "wordEndTimeSeconds": [0.4]}}}
        with mock.patch.object(voiceover, "_post", post), \
                mock.patch.object(voiceover, "inworld_voices", lambda lang="fr": [{"voiceId": "Hélène"}]):
            _, _, eng, words = voiceover.synth_timed("Go", self.d / "a.wav", "auto")
        self.assertEqual(eng, "inworld")
        self.assertEqual(words[0]["w"], "Go")

    def test_script_vers_voix_de_projet(self):
        rush = self.d / "r.mp4"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=320x240:d=1",
                        "-pix_fmt", "yuv420p", rush], check=True)
        ws = Workspace(rush)
        with mock.patch.object(voiceover, "_post", lambda u, p, h, timeout=180: eleven_response(p["text"], 1.0)):
            vo = voixoff.from_script(ws, "Première phrase.\nDeuxième phrase.", "elevenlabs", gap=0.5)
        tr = json.loads(ws.transcript.read_text("utf-8"))
        self.assertEqual(tr["source"], "voixoff")
        self.assertAlmostEqual(vo["duration"], 2.5, delta=0.15)  # 1 s + 0,5 s de pause + 1 s
        second = next(w for w in tr["words"] if w["w"] == "Deuxième")
        self.assertAlmostEqual(second["start"], 1.5, delta=0.1)  # décalé de la 1re réplique + pause
        self.assertEqual(voixoff.settings(ws)["file"], "voixoff/voix.wav")
        voixoff.remove(ws)
        self.assertIsNone(voixoff.settings(ws))


class Cles(unittest.TestCase):
    def test_set_et_retire_dans_env(self):
        with tempfile.TemporaryDirectory() as d:
            env = Path(d) / ".env"
            env.write_text("# commentaire\nPEXELS_API_KEY=old\nAUTRE=1\n", encoding="utf-8")
            with mock.patch.object(keys, "ENV", env), mock.patch.dict(os.environ, {}, clear=False):
                keys.set_key("PEXELS_API_KEY", "nouvelle-cle-123456")
                keys.set_key("ELEVENLABS_API_KEY", "sk_abcdef123456")
                txt = env.read_text("utf-8")
                self.assertIn("PEXELS_API_KEY=nouvelle-cle-123456", txt)
                self.assertIn("# commentaire", txt)
                self.assertIn("AUTRE=1", txt)
                st = {s["key"]: s for s in keys.status()}
                self.assertEqual(st["ELEVENLABS_API_KEY"]["value"], "sk_…456")  # jamais en clair
                keys.set_key("PEXELS_API_KEY", "")
                self.assertNotIn("PEXELS_API_KEY", env.read_text("utf-8"))
                with self.assertRaises(SystemExit):
                    keys.set_key("INCONNUE", "x")


class Habillage(unittest.TestCase):
    def test_prix_promo_et_chiffres(self):
        from monteur.habillage import plan_cards
        text = "Voici la crème. Seulement 29 euros au lieu de 49, soit 40 pour cent. Déjà 125 000 clientes conquises."
        words = [{"w": w, "start": round(i * 0.5, 2), "end": round(i * 0.5 + 0.4, 2)} for i, w in enumerate(text.split())]
        style = {"library": {"cards": ["prix.promo", "stat.courbe"]}}
        plan = {"duration": 20, "motion": [{"start": 0.15, "end": 1.0, "type": "title"}],
                "broll": [{"start": 2, "end": 4, "file": None}]}  # B-roll pas encore trouvé : ne bloque rien
        cards = plan_cards(words, plan, style, gap=3)
        ids = [c["card"] for c in cards]
        self.assertEqual(ids[0], "prix.promo")
        self.assertEqual(cards[0]["vars"]["badge"], "-40 %")
        self.assertIn("stat.courbe", ids)
        stat = next(c for c in cards if c["card"] == "stat.courbe")
        self.assertEqual((stat["vars"]["value"], stat["vars"]["unit"]), ("125000", "clientes"))


if __name__ == "__main__":
    unittest.main()
