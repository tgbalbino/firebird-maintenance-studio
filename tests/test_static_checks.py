"""Static guard for refactors: undefined names only surface at runtime in Qt code."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _pyflakes_available() -> bool:
    return subprocess.run([sys.executable, "-m", "pyflakes", "--version"], capture_output=True).returncode == 0


@unittest.skipUnless(_pyflakes_available(), "pyflakes não instalado")
class StaticChecksTests(unittest.TestCase):
    def test_no_undefined_names_or_syntax_errors(self):
        result = subprocess.run(
            [sys.executable, "-m", "pyflakes", "firebird_studio", "tests"],
            cwd=ROOT, capture_output=True, text=True,
        )
        problems = [
            line for line in (result.stdout + result.stderr).splitlines()
            if "undefined name" in line or "invalid syntax" in line or "SyntaxError" in line or "may be undefined" in line
        ]
        self.assertEqual(problems, [], "\n".join(problems))
