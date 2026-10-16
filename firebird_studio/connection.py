from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import ConnectionProfile


@dataclass(slots=True)
class ConnectionResult:
    ok: bool
    message: str
    server_version: str | None = None


def _dsn(profile: ConnectionProfile) -> str:
    host = profile.host.strip() or "localhost"
    database = profile.database.strip().strip('"')
    if profile.port == 3050:
        return f"{host}:{database}"
    return f"{host}/{profile.port}:{database}"


def _client_library(profile: ConnectionProfile) -> str | None:
    """Prefer the client DLL shipped with the selected Firebird install."""
    if profile.version != "2.5":
        return None
    candidates: list[Path] = []
    if profile.isql_path:
        candidates.append(Path(profile.isql_path.strip().strip('"')).parent / "fbclient.dll")
    candidates.extend(
        Path(root) / "bin" / "fbclient.dll"
        for root in (
            r"C:\Program Files\Firebird\Firebird_2_5",
            r"C:\Program Files (x86)\Firebird\Firebird_2_5",
        )
    )
    return next((str(path) for path in candidates if path.exists()), None)


def test_connection(profile: ConnectionProfile, password: str | None = None) -> ConnectionResult:
    errors = profile.validate()
    if errors:
        return ConnectionResult(False, " ".join(errors))
    if profile.version == "2.5":
        import fdb

        connect = fdb.connect
    else:
        from firebird.driver import connect

    try:
        kwargs = {
            "dsn": _dsn(profile),
            "user": profile.user,
            "password": password or "",
            "charset": profile.charset,
        }
        client_library = _client_library(profile)
        if client_library:
            kwargs["fb_library_name"] = client_library
        if profile.role:
            kwargs["role"] = profile.role
        with connect(**kwargs) as con:
            server_version = getattr(con, "server_version", None)
        return ConnectionResult(True, "Conexão realizada com sucesso.", server_version)
    except Exception as exc:  # driver-specific exceptions differ by version
        message = f"Falha ao conectar: {exc}"
        details: list[str] = []
        error_text = str(exc).lower()
        host = profile.host.strip().lower()
        if "unavailable database" in error_text or "335544375" in error_text:
            details.append("Verifique se o serviço Firebird está ativo e se o caminho do banco é o caminho visto pelo servidor.")
            database_path = profile.database.strip().strip('"')
            looks_like_path = bool(Path(database_path).drive or "\\" in database_path or "/" in database_path)
            if host in {"", "localhost", "127.0.0.1"} and looks_like_path:
                if not Path(database_path).exists():
                    details.append("O arquivo informado não existe neste computador.")
        if not password:
            details.append("Informe a senha do usuário SYSDBA (a senha não é salva no cadastro).")
        if profile.isql_path and not Path(profile.isql_path).exists():
            details.append(f"isql.exe não encontrado: {profile.isql_path}")
        if profile.gbak_path and not Path(profile.gbak_path).exists():
            details.append(f"gbak.exe não encontrado: {profile.gbak_path}")
        if details:
            message += " " + " ".join(details)
        return ConnectionResult(False, message)
