from __future__ import annotations

import os
import sys
from pathlib import Path

_QT_DLL_HANDLES = []


def _prepare_qt_runtime() -> None:
    """Prioritize the Qt DLLs bundled with the frozen application.

    Some Windows installations have another Qt application on PATH. If that
    application's Qt6 DLL is picked first, importing QtWidgets fails with an
    entry-point error even when the correct DLL is present beside the EXE.
    """
    if not getattr(sys, "frozen", False):
        return

    bundle = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    candidates = [bundle, bundle / "PySide6", bundle / "shiboken6"]
    existing = [str(path) for path in candidates if path.is_dir()]
    if existing:
        os.environ["PATH"] = os.pathsep.join(existing + [os.environ.get("PATH", "")])
        # Prefer the bundled Qt directory even when another Qt installation
        # is present in the Windows process search path.  Without this, the
        # correct QtWidgets extension can be paired with an unrelated QtCore
        # DLL and fail with an entry-point error before the UI is created.
        if sys.platform == "win32":
            try:
                import ctypes
                qt_dir = next((path for path in existing if Path(path).name.lower() == "pyside6"), existing[0])
                ctypes.windll.kernel32.SetDllDirectoryW(qt_dir)
            except (OSError, AttributeError):
                pass
        if hasattr(os, "add_dll_directory"):
            for path in existing:
                try:
                    # Keep the handle alive; closing it removes the directory
                    # from the DLL search path on Windows.
                    _QT_DLL_HANDLES.append(os.add_dll_directory(path))
                except OSError:
                    pass



_prepare_qt_runtime()

from firebird_studio.__main__ import main


if __name__ == "__main__":
    raise SystemExit(main())
