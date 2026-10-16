import tempfile
import unittest
from pathlib import Path
import subprocess

from firebird_studio.process_utils import resolve_tool_path, run_command


class ProcessUtilsTests(unittest.TestCase):
    def test_keeps_explicit_executable_path(self):
        self.assertEqual(resolve_tool_path('"C:/Firebird/isql.exe"', "isql.exe"), Path("C:/Firebird/isql.exe"))

    def test_expands_installation_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(resolve_tool_path(directory, "gbak.exe"), Path(directory) / "gbak.exe")

    def test_run_command_captures_timeout(self):
        def runner(_args, **_kwargs):
            raise subprocess.TimeoutExpired("tool", 1)

        result = run_command(runner, ["tool"])

        self.assertTrue(result.timed_out)
        self.assertIsNotNone(result.error)

    def test_run_command_keeps_completed_process(self):
        completed = subprocess.CompletedProcess(["tool"], 0, stdout="ok", stderr="")
        result = run_command(lambda _args, **_kwargs: completed, ["tool"])

        self.assertIs(result.completed, completed)
        self.assertIsNone(result.error)


if __name__ == "__main__":
    unittest.main()
