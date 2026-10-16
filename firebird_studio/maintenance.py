from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import subprocess

from .connection import _dsn
from .models import ConnectionProfile


@dataclass(slots=True)
class ValidationResult:
    ok: bool
    output: str
    error: str


def validate_database(profile: ConnectionProfile, password: str | None, gfix_path: Path, timeout_seconds: int = 300) -> ValidationResult:
    errors = profile.validate()
    if errors:
        return ValidationResult(False, "", " ".join(errors))
    tool = Path(str(gfix_path).strip().strip('"')).expanduser()
    if tool.is_dir():
        tool = tool / "gfix.exe"
    if not tool.exists() or not tool.is_file():
        return ValidationResult(False, "", f"Executável gfix não encontrado: {tool}")
    database = _dsn(profile)
    args = [str(tool), "-v", "-full", "-user", profile.user, database]
    try:
        completed = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout_seconds, cwd=str(tool.parent), env={**os.environ, "ISC_USER": profile.user, "ISC_PASSWORD": password or ""}, check=False)
    except subprocess.TimeoutExpired:
        return ValidationResult(False, "", "A validação excedeu o limite de tempo.")
    except OSError as exc:
        return ValidationResult(False, "", f"Não foi possível iniciar o gfix: {exc}")
    return ValidationResult(completed.returncode == 0, completed.stdout or "", completed.stderr or "")
