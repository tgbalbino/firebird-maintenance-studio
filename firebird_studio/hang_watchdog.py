"""Record where the UI thread is stuck when the window stops responding."""

import faulthandler
import time
from pathlib import Path

from PySide6.QtCore import QObject, QTimer


class HangWatchdog(QObject):
    """Rearm a faulthandler countdown from the UI thread's own event loop.

    While the loop turns, the countdown never expires.  If the UI thread blocks
    longer than `timeout` seconds, faulthandler writes every thread's stack to
    `dump_path` from its own watcher thread, so the cause survives a hang that
    would otherwise leave nothing in the event log.
    """

    def __init__(self, dump_path: Path, timeout: float = 8.0, parent=None):
        super().__init__(parent)
        self.dump_path = Path(dump_path)
        self.timeout = timeout
        self._file = None
        self._last_beat = time.monotonic()
        self.longest_stall = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self.beat)

    def start(self) -> bool:
        try:
            self.dump_path.parent.mkdir(parents=True, exist_ok=True)
            self._file = self.dump_path.open("a", encoding="utf-8")
        except OSError:
            return False
        self._file.write(f"--- vigia iniciado {time.strftime('%Y-%m-%d %H:%M:%S')} (limite {self.timeout:g}s) ---\n")
        self._file.flush()
        self._last_beat = time.monotonic()
        self._arm()
        self._timer.start()
        return True

    def stop(self) -> None:
        self._timer.stop()
        faulthandler.cancel_dump_traceback_later()
        if self._file is not None:
            self._file.close()
            self._file = None

    def beat(self) -> None:
        now = time.monotonic()
        stalled = now - self._last_beat - self._timer.interval() / 1000
        self._last_beat = now
        if stalled > self.longest_stall:
            self.longest_stall = stalled
        if stalled >= self.timeout and self._file is not None:
            self._file.write(f"--- a interface voltou após ~{stalled:.0f}s parada ({time.strftime('%H:%M:%S')}) ---\n")
            self._file.flush()
        self._arm()

    def _arm(self) -> None:
        if self._file is not None:
            faulthandler.dump_traceback_later(self.timeout, repeat=False, file=self._file)
