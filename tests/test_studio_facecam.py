"""Studio (port pris, autotest), relais Scribe, import coupe-facecam, niveaux mesurés, ouverture."""
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

FFMPEG = shutil.which("ffmpeg") is not None


class Studio(unittest.TestCase):
    def test_port_pris_prend_le_suivant(self):
        from monteur import studio
        a, pa = studio._bind(8840)
        try:
            b, pb = studio._bind(8840)
            self.assertEqual(pb, pa + 1)  # Windows : SO_EXCLUSIVEADDRUSE, plus de double écoute sur le même port
            b.server_close()
        finally:
            a.server_close()


class Scribe(unittest.TestCase):
    def test_reponse_scribe_vers_mots(self):
        from monteur import transcribe
        fake = {"language_code": "fra", "words": [
            {"text": "Bonjour", "start": 0.1, "end": 0.5, "type": "word", "logprob": -0.01},
            {"text": " ", "start": 0.5, "end": 0.6, "type": "spacing"},
            {"text": "(rires)", "start": 0.6, "end": 0.9, "type": "audio_event"},
            {"text": "euh", "start": 1.0, "end": 1.2, "type": "word", "logprob": -0.3}]}

        class R(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"ELEVENLABS_API_KEY": "k"}), \
                mock.patch("urllib.request.urlopen", return_value=R(json.dumps(fake).encode())) as op:
            f = Path(d) / "a.flac"
            f.write_bytes(b"x")
            words, lang = transcribe.scribe(f, "fr")
        req = op.call_args[0][0]
        self.assertIn(b'name="model_id"', req.data)
        self.assertEqual(req.headers["Xi-api-key"], "k")
        self.assertEqual([w["w"] for w in words], ["Bonjour", "euh"])  # euh gardés, bruits exclus
        self.assertEqual(lang, "fra")


@unittest.skipUnless(FFMPEG, "ffmpeg requis")
class Facecam(unittest.TestCase):
    def test_import_sans_recoupe(self):
        from monteur.facecam import import_cut
        with tempfile.TemporaryDirectory() as d:
            work = Path(d) / "rush-coupe"
            work.mkdir()
            v = work / "rush-v1.mp4"
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=160x120:d=1",
                            "-pix_fmt", "yuv420p", v], check=True)
            (work / "analyse.json").write_text(json.dumps({"langue": "fr", "versions": [{"video": str(v)}]}), "utf-8")
            (work / "mots-coupe-v1.json").write_text(json.dumps(
                [{"text": "Salut", "n": "salut", "kind": "mot", "s": 0.05, "e": 0.4}]), "utf-8")
            video = import_cut(work)
            tr = json.loads((work / "rush-v1.monteur" / "transcript.json").read_text("utf-8"))
        self.assertEqual(video, v)
        self.assertEqual(tr["words"][0], {"w": "Salut", "start": 0.05, "end": 0.4, "p": 1.0})
        self.assertTrue(tr["source"].startswith("coupe-facecam"))


@unittest.skipUnless(FFMPEG, "ffmpeg requis")
class Niveaux(unittest.TestCase):
    def test_musique_sous_la_voix(self):
        from monteur.niveaux import music_gains
        with tempfile.TemporaryDirectory() as d:
            voix, mus = Path(d) / "v.wav", Path(d) / "m.wav"
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=f=200:d=4", "-af",
                            "volume=0.5", voix], check=True)
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=f=500:d=4", "-af",
                            "volume=0.5", mus], check=True)
            gh, gb = music_gains(voix, mus, 21, 12)
        self.assertAlmostEqual(gb, 10 ** (-21 / 20), places=2)  # même niveau au départ → −21 dB
        self.assertAlmostEqual(gh, 10 ** (-12 / 20), places=2)


@unittest.skipUnless(FFMPEG, "ffmpeg requis")
class Ouverture(unittest.TestCase):
    def test_image_zero_noire(self):
        from monteur.verify import opening
        with tempfile.TemporaryDirectory() as d:
            v = Path(d) / "n.mp4"
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=black:s=160x120:d=1",
                            "-pix_fmt", "yuv420p", v], check=True)
            luma, db = opening(v)
        self.assertLess(luma, 18)
        self.assertIsNone(db)


if __name__ == "__main__":
    unittest.main()
