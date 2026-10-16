import tempfile
import unittest
from pathlib import Path

from firebird_studio.process_utils import resolve_tool_path


class ProcessUtilsTests(unittest.TestCase):
    def test_keeps_explicit_executable_path(self):
        self.assertEqual(resolve_tool_path('"C:/Firebird/isql.exe"', "isql.exe"), Path("C:/Firebird/isql.exe"))

    def test_expands_installation_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(resolve_tool_path(directory, "gbak.exe"), Path(directory) / "gbak.exe")


if __name__ == "__main__":
    unittest.main()
