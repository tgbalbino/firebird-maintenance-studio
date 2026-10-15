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
    if profile.port == 3050:
        return f"{host}:{profile.database}"
    return f"{host}/{profile.port}:{profile.database}"


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
            looks_like_path = bool(Path(profile.database).drive or "\\" in profile.database or "/" in profile.database)
            if host in {"", "localhost", "127.0.0.1"} and looks_like_path:
                if not Path(profile.database).exists():
                    details.append("O arquivo informado não existe neste computador.")
        if not password:
            details.append("Informe a senha do usuário SYSDBA (a senha não é salva no perfil).")
        if profile.isql_path and not Path(profile.isql_path).exists():
            details.append(f"isql.exe não encontrado: {profile.isql_path}")
        if profile.gbak_path and not Path(profile.gbak_path).exists():
            details.append(f"gbak.exe não encontrado: {profile.gbak_path}")
        if details:
            message += " " + " ".join(details)
        return ConnectionResult(False, message)
