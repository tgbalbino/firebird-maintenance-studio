"""Capture reference screenshots of the main window for before/after comparison.

Usage (from the repository root, with a real display so fonts render):

    python tools/capture_screens.py OUTPUT_DIR [--scale 1.5]

Writes ``<theme>_<state>_<width>x<height>.png`` for the light and dark themes
with the welcome page and with an SQL window open. Uses a throw-away settings
folder and profile store, so it never touches the user's real data.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SIZES = ((1280, 720), (1920, 1080))
THEMES = ("light", "dark")
SAMPLE_PROFILES = (("Producao", "srv-erp", True), ("Homologacao", "localhost", False), ("Financeiro", "10.0.0.5", False))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output", type=Path)
    parser.add_argument("--scale", type=float, default=1.0, help="QT_SCALE_FACTOR, e.g. 1.5 for 150%%")
    args = parser.parse_args()
    if args.scale != 1.0:
        os.environ["QT_SCALE_FACTOR"] = str(args.scale)
    args.output.mkdir(parents=True, exist_ok=True)

    from PySide6.QtCore import QSettings

    temp = tempfile.mkdtemp(prefix="fms-shots-")
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, temp)
    QSettings("TGBalbino", "FirebirdMaintenanceStudio").setValue("auto_update_check", False)

    from firebird_studio.models import ConnectionProfile, ProfileStore
    from firebird_studio.ui import MainWindow, create_application

    app = create_application()
    store = ProfileStore(Path(temp) / "profiles.json")
    store.save([ConnectionProfile(n, host=h, database=f"C:/dados/{n}.fdb", favorite=f) for n, h, f in SAMPLE_PROFILES])
    window = MainWindow(store)
    win = window._window
    window._new_sql_tab()
    window._new_sql_tab()  # keep an SQL window available for the "sql" state
    states = {"sql": True}
    for theme in THEMES:
        window._apply_theme(theme)
        for width, height in SIZES:
            win.resize(width, height)
            win.show()
            app.processEvents()
            win.grab().save(str(args.output / f"{theme}_sql_{width}x{height}.png"))
    while window.sql_tabs.count():
        window.close_sql_tab(0)
        app.processEvents()
    for theme in THEMES:
        window._apply_theme(theme)
        for width, height in SIZES:
            win.resize(width, height)
            app.processEvents()
            win.grab().save(str(args.output / f"{theme}_welcome_{width}x{height}.png"))
    print(f"{len(THEMES) * len(SIZES) * len(states) * 2} imagens em {args.output}")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    raise SystemExit(main())
