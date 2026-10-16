from __future__ import annotations

import os
import time
from pathlib import Path


def log_event(path: Path, message: str, **details) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        suffix = " ".join(f"{key}={value!s}" for key, value in details.items() if value not in (None, ""))
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{timestamp}] {message}{(' ' + suffix) if suffix else ''}\n")
    except OSError:
        return


def open_log(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)
    os.startfile(str(path))
