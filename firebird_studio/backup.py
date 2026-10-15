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
    local_host = host.lower() in {"localhost", "127.0.0.1", "::1"} and source.exists()
    # For a local database gbak can open the file directly. The service
    # manager form is reserved for remote/server-side paths.
    if operation == "backup":
        args = [str(gbak_path), "-b", "-user", profile.user]
        if not local_host:
            args.extend(["-service", service_dsn])
        args.extend([str(source), str(target)])
        return args
    if operation == "restore":
        args = [str(gbak_path), "-c", "-user", profile.user]
        if not local_host:
            args.extend(["-service", service_dsn])
        args.extend([str(source), str(target)])
        return args
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
    gbak_path = Path(str(gbak_path).strip().strip('"')).expanduser()
    if gbak_path.is_dir():
        gbak_path = gbak_path / "gbak.exe"
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
            cwd=str(gbak_path.parent),
        )
    except subprocess.TimeoutExpired:
        return BackupResult(False, -1, "", f"{operation} excedeu o limite de {timeout_seconds} segundos.", operation)
    except OSError as exc:
        if getattr(exc, "winerror", None) == 5 or getattr(exc, "errno", None) == 13:
            return BackupResult(False, -1, "", f"Acesso negado ao gbak.exe: {gbak_path}. Verifique as permissões do arquivo e se o Windows não o bloqueou.", operation)
        return BackupResult(False, -1, "", f"Não foi possível iniciar o gbak: {exc}", operation)
    return BackupResult(completed.returncode == 0, completed.returncode, completed.stdout or "", completed.stderr or "", operation)
