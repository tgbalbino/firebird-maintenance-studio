from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import subprocess

from .connection import _dsn
from .models import ConnectionProfile


@dataclass(slots=True)
class ScriptResult:
    ok: bool
    return_code: int
    output: str
    error: str
    command_label: str


def build_isql_args(profile: ConnectionProfile, script: Path, isql_path: Path) -> list[str]:
    """Build arguments without including the password, which is supplied through stdin."""
    args = [str(isql_path), "-user", profile.user, "-ch", profile.charset, "-input", str(script)]
    if profile.role:
        args.extend(["-role", profile.role])
    args.append(_dsn(profile))
    return args


def run_script(
    profile: ConnectionProfile,
    script: Path,
    password: str | None,
    isql_path: Path,
    timeout_seconds: int = 600,
) -> ScriptResult:
    errors = profile.validate()
    if errors:
        return ScriptResult(False, -1, "", " ".join(errors), "isql")
    if not script.exists() or not script.is_file():
        return ScriptResult(False, -1, "", f"Arquivo SQL não encontrado: {script}", "isql")
    if not isql_path.exists() or not isql_path.is_file():
        return ScriptResult(False, -1, "", f"Executável isql não encontrado: {isql_path}", "isql")
    args = build_isql_args(profile, script, isql_path)
    # Password is sent on stdin so it is not present in the process command line.
    input_text = (password or "") + os.linesep
    try:
        completed = subprocess.run(
            args,
            input=input_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return ScriptResult(False, -1, "", f"Script excedeu o limite de {timeout_seconds} segundos.", "isql")
    except OSError as exc:
        return ScriptResult(False, -1, "", f"Não foi possível iniciar o isql: {exc}", "isql")
    output = completed.stdout or ""
    error = completed.stderr or ""
    return ScriptResult(completed.returncode == 0, completed.returncode, output, error, "isql")
