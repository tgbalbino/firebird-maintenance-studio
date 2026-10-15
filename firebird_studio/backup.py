from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import subprocess

from .models import ConnectionProfile


@dataclass(slots=True)
class BackupResult:
    ok: bool
    return_code: int
    output: str
    error: str
    operation: str


def build_gbak_args(profile: ConnectionProfile, operation: str, source: Path, target: Path, gbak_path: Path) -> list[str]:
    host = profile.host.strip() or "localhost"
    service_dsn = f"{host}:service_mgr" if profile.port == 3050 else f"{host}/{profile.port}:service_mgr"
    if operation == "backup":
        return [str(gbak_path), "-b", "-user", profile.user, "-service", service_dsn, str(source), str(target)]
    if operation == "restore":
        return [str(gbak_path), "-c", "-user", profile.user, "-service", service_dsn, str(source), str(target)]
    raise ValueError(f"Operação desconhecida: {operation}")


def run_gbak(
    profile: ConnectionProfile,
    operation: str,
    source: Path,
    target: Path,
    password: str | None,
    gbak_path: Path,
    timeout_seconds: int = 3600,
) -> BackupResult:
    errors = profile.validate()
    if errors:
        return BackupResult(False, -1, "", " ".join(errors), operation)
    if operation == "restore" and target.exists():
        return BackupResult(False, -1, "", "O destino já existe; escolha um novo arquivo para evitar substituição acidental.", operation)
    if not gbak_path.exists() or not gbak_path.is_file():
        return BackupResult(False, -1, "", f"Executável gbak não encontrado: {gbak_path}", operation)
    if operation == "backup" and not source.exists():
        return BackupResult(False, -1, "", f"Banco de origem não encontrado: {source}", operation)
    if operation == "restore" and not source.exists():
        return BackupResult(False, -1, "", f"Arquivo de backup não encontrado: {source}", operation)
    args = build_gbak_args(profile, operation, source, target, gbak_path)
    try:
        completed = subprocess.run(
            args,
            input=(password or "") + os.linesep,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return BackupResult(False, -1, "", f"{operation} excedeu o limite de {timeout_seconds} segundos.", operation)
    except OSError as exc:
        return BackupResult(False, -1, "", f"Não foi possível iniciar o gbak: {exc}", operation)
    return BackupResult(completed.returncode == 0, completed.returncode, completed.stdout or "", completed.stderr or "", operation)
