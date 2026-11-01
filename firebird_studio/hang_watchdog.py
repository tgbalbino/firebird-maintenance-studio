"""Record where the UI thread is stuck when the window stops responding."""

import faulthandler
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, QTimer


class HangWatchdog(QObject):
    """Rearm a faulthandler countdown from the UI thread's own event loop.

    While the loop turns, the countdown never expires.  If the UI thread blocks
    longer than `timeout` seconds, faulthandler writes every thread's stack to
    `dump_path` from its own watcher thread, so the cause survives a hang that
    would otherwise leave nothing in the event log.  A second, plain Python
    thread adds the timestamp and a few samples of the UI thread's native
    stack, which is where a block inside Qt actually shows up.
    """

    def __init__(self, dump_path: Path, timeout: float = 8.0, parent=None):
        super().__init__(parent)
        self.dump_path = Path(dump_path)
        self.timeout = timeout
        self._file = None
        self._last_beat = time.monotonic()
        self.longest_stall = 0.0
        self._ui_thread_id = None
        self._stop = threading.Event()
        self._monitor = None
        self._reported = False
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
        self._ui_thread_id = threading.get_native_id()
        self._arm()
        self._timer.start()
        self._stop.clear()
        self._monitor = threading.Thread(target=self._watch, name="hang-watchdog", daemon=True)
        self._monitor.start()
        return True

    def stop(self) -> None:
        self._stop.set()
        if self._monitor is not None:
            self._monitor.join(timeout=2)
            self._monitor = None
        self._timer.stop()
        faulthandler.cancel_dump_traceback_later()
        if self._file is not None:
            self._file.close()
            self._file = None

    def beat(self) -> None:
        now = time.monotonic()
        stalled = now - self._last_beat - self._timer.interval() / 1000
        self._last_beat = now
        self._reported = False
        if stalled > self.longest_stall:
            self.longest_stall = stalled
        if stalled >= self.timeout and self._file is not None:
            self._file.write(f"--- a interface voltou após ~{stalled:.0f}s parada ({time.strftime('%H:%M:%S')}) ---\n")
            self._file.flush()
        self._arm()

    def _arm(self) -> None:
        if self._file is not None:
            faulthandler.dump_traceback_later(self.timeout, repeat=False, file=self._file)

    def _watch(self) -> None:
        """Runs off the UI thread: report once per stall, with native stack samples."""
        from .native_stack import capture_thread_stack

        while not self._stop.wait(1.0):
            file = self._file
            if file is None or self._reported or self._ui_thread_id is None:
                continue
            silent = time.monotonic() - self._last_beat
            if silent < self.timeout:
                continue
            self._reported = True
            try:
                file.write(f"--- interface sem resposta há {silent:.0f}s ({time.strftime('%H:%M:%S')}) ---\n")
                for sample in range(1, 4):
                    stack = capture_thread_stack(self._ui_thread_id)
                    file.write(f"pilha nativa da interface, amostra {sample}/3:\n")
                    file.writelines(f"  {line}\n" for line in stack)
                    file.flush()
                    if self._stop.wait(0.7):
                        return
            except (OSError, ValueError):
                return
