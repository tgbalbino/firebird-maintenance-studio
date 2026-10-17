from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .models import ConnectionProfile, ProfileStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Firebird Maintenance Studio")
    parser.add_argument("--check", action="store_true", help="valida dependências e encerra")
    parser.add_argument("--profiles", type=Path, help="arquivo de perfis sem senhas")
    parser.add_argument("backup", nargs="?", type=Path, help="arquivo .fbk/.gbk para abrir na tela de restauração")
    return parser


def register_backup_association() -> None:
    """Register .fbk/.gbk for the current Windows user without elevation."""
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return
    try:
        import winreg
        command = f'"{Path(sys.executable).resolve()}" "%1"'
        for extension, class_name, description in ((".fbk", "FirebirdMaintenanceStudio.Backup", "Backup Firebird"), (".gbk", "FirebirdMaintenanceStudio.Backup", "Backup Firebird")):
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{extension}") as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, class_name)
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{class_name}") as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, description)
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{class_name}\shell\open\command") as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, command)
    except (OSError, ImportError):
        # Association is a convenience; startup must never fail if Windows
        # policy blocks writing the per-user registry.
        return


def check_dependencies() -> int:
    modules = {
        "PySide6": "interface Windows",
        "firebird.driver": "Firebird 3/4/5",
        "firebird.lib": "metadados e monitoramento",
        "fdb": "Firebird 2.5",
        "keyring": "cofre de credenciais",
    }
    missing = []
    for module, purpose in modules.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(f"{module} ({purpose})")
    if missing:
        print("Dependências ausentes: " + ", ".join(missing))
        return 1
    print("Dependências principais disponíveis.")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.check:
        return check_dependencies()

    from .ui import MainWindow, create_application

    app = create_application()
    register_backup_association()
    profile_path = args.profiles or Path.home() / ".firebird-maintenance-studio" / "profiles.json"
    window = MainWindow(ProfileStore(profile_path))
    window.show()
    if args.backup and args.backup.suffix.lower() in {".fbk", ".gbk"}:
        from PySide6.QtCore import QTimer
        QTimer.singleShot(250, lambda: window.restore_backup_file(args.backup))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
