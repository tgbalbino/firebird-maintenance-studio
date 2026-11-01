"""Make errors that escape a Qt slot visible instead of vanishing.

The packaged app has no console, so PySide6 prints an uncaught slot exception
to a stderr nobody sees and the action just seems to do nothing.
"""

from __future__ import annotations

import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Callable


def install(log_path: Path, show: Callable[[str, str], None]) -> None:
    """Route uncaught exceptions to `log_path` and, once per distinct error, to `show`."""
    reported: set[str] = set()

    def record(exc_type, exc, tb) -> str:
        detail = "".join(traceback.format_exception(exc_type, exc, tb))
        try:
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            with Path(log_path).open("a", encoding="utf-8") as handle:
                handle.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Erro não tratado\n{detail}\n")
        except OSError:
            pass
        return detail

    def hook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        detail = record(exc_type, exc, tb)
        signature = f"{exc_type.__name__}:{exc}"
        if signature in reported:
            return
        reported.add(signature)
        try:
            show("Erro inesperado", f"{exc_type.__name__}: {exc}\n\nOs detalhes foram gravados em:\n{log_path}")
        except Exception:
            pass

    def thread_hook(args):
        if args.exc_type is not SystemExit:
            record(args.exc_type, args.exc_value, args.exc_traceback)

    sys.excepthook = hook
    threading.excepthook = thread_hook
