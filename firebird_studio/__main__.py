from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .models import ConnectionProfile, ProfileStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Firebird Maintenance Studio")
    parser.add_argument("--check", action="store_true", help="valida dependências e encerra")
    parser.add_argument("--profiles", type=Path, help="arquivo de perfis sem senhas")
    return parser


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
    profile_path = args.profiles or Path.home() / ".firebird-maintenance-studio" / "profiles.json"
    window = MainWindow(ProfileStore(profile_path))
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
