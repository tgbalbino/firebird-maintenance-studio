from __future__ import annotations

from dataclasses import dataclass

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
        return ConnectionResult(False, f"Falha ao conectar: {exc}")
