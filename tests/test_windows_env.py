"""Simule Git Bash sous Windows (uname MINGW, venv .venv/Scripts/python.exe, chemin avec espaces, ffmpeg via winget)."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@unittest.skipIf(os.name == "nt" or not shutil.which("bash"), "simulation prévue pour un hôte Unix")
class GitBashWindows(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.root = base / "Mes Documents" / "montageos"
        (self.root / "bin").mkdir(parents=True)
        shutil.copy(ROOT / "bin" / "_env.sh", self.root / "bin")
        shutil.copy(ROOT / "bin" / "monteur", self.root / "bin")
        os.symlink(ROOT / "monteur", self.root / "monteur")
        scripts = self.root / ".venv" / "Scripts"
        scripts.mkdir(parents=True)
        self._exe(scripts / "python.exe", f'exec "{sys.executable}" "$@"')
        self.fake = base / "fakebin"
        self.fake.mkdir()
        self._exe(self.fake / "uname", 'echo MINGW64_NT-10.0-26100')
        self._exe(self.fake / "cygpath", 'shift; echo "$1"')
        self.links = base / "AppData" / "Local" / "Microsoft" / "WinGet" / "Links"
        self.links.mkdir(parents=True)
        for n in ("ffmpeg.exe", "ffmpeg"):
            self._exe(self.links / n, "echo ffmpeg-winget")

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def _exe(path, body):
        path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
        path.chmod(0o755)

    def bash(self, script, path=None, **env):
        e = {**os.environ, "PATH": path or f"{self.fake}:{os.environ['PATH']}", **env}
        return subprocess.run([shutil.which("bash"), "-c", script], cwd=self.root, env=e, capture_output=True, text=True)

    def test_venv_scripts_et_espaces(self):
        r = self.bash('ROOT="$PWD"; . bin/_env.sh; echo "$MONTEUR_WIN"; printf "%s\\n" "${MONTEUR_PY[@]}"')
        win, py = r.stdout.split("\n")[:2]
        self.assertEqual(win, "1")
        self.assertTrue(py.endswith("Mes Documents/montageos/.venv/Scripts/python.exe"), py)

    def test_lanceur(self):
        r = self.bash("bin/monteur cartes")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("stat.courbe", r.stdout)

    def test_ffmpeg_winget_hors_path(self):
        r = self.bash('ROOT="$PWD"; . bin/_env.sh; ffmpeg', path=str(self.fake),
                      LOCALAPPDATA=str(self.links.parents[2]))
        self.assertEqual(r.stdout.strip(), "ffmpeg-winget", r.stderr)


if __name__ == "__main__":
    unittest.main()
