"""Force Windows to resolve Qt dependencies from the bundled application."""

import ctypes
import os
import sys
from pathlib import Path

if sys.platform.startswith("win") and getattr(sys, "frozen", False):
    bundle = Path(sys._MEIPASS)
    qt_dir = bundle / "PySide6"
    shiboken_dir = bundle / "shiboken6"
    paths = [p for p in (qt_dir, shiboken_dir, bundle) if p.is_dir()]
    os.environ["PATH"] = os.pathsep.join([str(p) for p in paths] + [os.environ.get("PATH", "")])
    # SetDllDirectoryW applies before the first extension module import and
    # prevents an unrelated Qt installation from satisfying QtWidgets.pyd.
    ctypes.windll.kernel32.SetDllDirectoryW(str(qt_dir))

