import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from firebird_studio import error_reporting


def raised():
    try:
        raise PermissionError(13, "Acesso negado", "profiles.json")
    except PermissionError:
        return sys.exc_info()


class ErrorReportingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = Path(self.tmp.name) / "erros.txt"
        self.shown = []
        self.addCleanup(setattr, sys, "excepthook", sys.excepthook)
        self.addCleanup(setattr, threading, "excepthook", threading.excepthook)

    def install(self):
        error_reporting.install(self.log, lambda title, text: self.shown.append((title, text)))

    def test_uncaught_error_is_logged_with_traceback_and_shown(self):
        self.install()
        sys.excepthook(*raised())
        text = self.log.read_text(encoding="utf-8")
        self.assertIn("PermissionError", text)
        self.assertIn("Traceback", text)
        self.assertEqual(len(self.shown), 1)
        self.assertIn("Acesso negado", self.shown[0][1])

    def test_a_failing_dialog_never_hides_the_log(self):
        error_reporting.install(self.log, lambda title, text: 1 / 0)
        sys.excepthook(*raised())
        self.assertIn("PermissionError", self.log.read_text(encoding="utf-8"))

    def test_repeated_identical_errors_open_one_dialog(self):
        self.install()
        for _ in range(3):
            sys.excepthook(*raised())
        self.assertEqual(len(self.shown), 1)
        self.assertEqual(self.log.read_text(encoding="utf-8").count("Traceback"), 3)

    def test_keyboard_interrupt_keeps_default_behaviour(self):
        self.install()
        try:
            raise KeyboardInterrupt
        except KeyboardInterrupt:
            info = sys.exc_info()
        original = sys.__excepthook__
        sys.__excepthook__ = lambda *args: self.shown.append("default")
        self.addCleanup(setattr, sys, "__excepthook__", original)
        sys.excepthook(*info)
        self.assertEqual(self.shown, ["default"])


if __name__ == "__main__":
    unittest.main()
