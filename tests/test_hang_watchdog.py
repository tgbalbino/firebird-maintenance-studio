import os
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QCoreApplication
except ImportError:  # pragma: no cover - UI extras are optional
    QCoreApplication = None


@unittest.skipIf(QCoreApplication is None, "PySide6 não instalado")
class HangWatchdogTests(unittest.TestCase):
    def setUp(self):
        from firebird_studio.ui import create_application

        self.app = create_application()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "hang.txt"

    def watchdog(self, timeout):
        from firebird_studio.hang_watchdog import HangWatchdog

        dog = HangWatchdog(self.path, timeout=timeout)
        self.assertTrue(dog.start())
        self.addCleanup(dog.stop)
        return dog

    def test_blocked_ui_thread_leaves_a_stack_dump(self):
        dog = self.watchdog(0.4)
        time.sleep(1.2)  # the UI thread is stuck here, like a blocking call
        dog.stop()
        text = self.path.read_text(encoding="utf-8")
        self.assertIn("most recent call first", text)
        self.assertIn("test_blocked_ui_thread_leaves_a_stack_dump", text)

    def test_responsive_loop_writes_no_dump(self):
        dog = self.watchdog(0.6)
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            self.app.processEvents()
            dog.beat()
            time.sleep(0.05)
        dog.stop()
        self.assertNotIn("most recent call first", self.path.read_text(encoding="utf-8"))

    def test_unwritable_location_is_not_fatal(self):
        from firebird_studio.hang_watchdog import HangWatchdog

        blocker = Path(self._tmp.name) / "arquivo"
        blocker.write_text("x")
        self.assertFalse(HangWatchdog(blocker / "hang.txt").start())


if __name__ == "__main__":
    unittest.main()
