from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .catalog import open_database
from .models import ConnectionProfile


@dataclass(slots=True)
class HealthFinding:
    severity: str
    title: str
    evidence: str
    recommendation: str


@dataclass(slots=True)
class HealthReport:
    metrics: dict[str, Any]
    findings: list[HealthFinding]


def _fetch_one(connection: Any, query: str) -> tuple:
    cursor = connection.cursor()
    cursor.execute(query)
    return tuple(cursor.fetchone() or ())


def _rows(connection: Any, query: str) -> list[tuple]:
    cursor = connection.cursor()
    cursor.execute(query)
    return list(cursor.fetchall())


def build_findings(metrics: dict[str, Any]) -> list[HealthFinding]:
    findings: list[HealthFinding] = []
    oldest_active = metrics.get("oldest_active")
    next_transaction = metrics.get("next_transaction")
    if isinstance(oldest_active, int) and isinstance(next_transaction, int) and next_transaction - oldest_active > 100_000:
        findings.append(HealthFinding("warning", "Transação antiga", f"Diferença entre OAT e NEXT_TRANSACTION: {next_transaction - oldest_active}", "Investigue transações longas e conexões abandonadas antes de executar sweep."))
    attachments = metrics.get("attachments")
    if isinstance(attachments, int) and attachments > 100:
        findings.append(HealthFinding("info", "Muitas conexões", f"{attachments} conexões ativas na fotografia", "Confirme o pool de conexões e encerre somente sessões identificadas como abandonadas."))
    if metrics.get("backup_state") not in (None, 0, "NORMAL"):
        findings.append(HealthFinding("warning", "Backup em andamento", f"Estado reportado: {metrics.get('backup_state')}", "Aguarde o backup terminar antes de iniciar manutenção concorrente."))
    if not findings:
        findings.append(HealthFinding("ok", "Sem alertas simples", "Os indicadores coletados não cruzaram os limites básicos.", "Continue acompanhando tendência, tempo de consulta e testes de restore."))
    return findings


def inspect_health(profile: ConnectionProfile, password: str | None = None) -> HealthReport:
    with open_database(profile, password) as connection:
        try:
            database = _fetch_one(connection, "SELECT MON$OLDEST_TRANSACTION, MON$OLDEST_ACTIVE, MON$OLDEST_SNAPSHOT, MON$NEXT_TRANSACTION, MON$BACKUP_STATE FROM MON$DATABASE")
        except Exception:
            # Firebird 2.5 exposes a smaller MON$DATABASE surface.
            database = _fetch_one(connection, "SELECT MON$OLDEST_TRANSACTION, MON$OLDEST_ACTIVE, MON$OLDEST_SNAPSHOT, MON$NEXT_TRANSACTION FROM MON$DATABASE")
        try:
            attachment = _fetch_one(connection, "SELECT COUNT(*) FROM MON$ATTACHMENTS")
        except Exception:
            attachment = (0,)
    metrics = {
        "oldest_transaction": database[0] if len(database) > 0 else None,
        "oldest_active": database[1] if len(database) > 1 else None,
        "oldest_snapshot": database[2] if len(database) > 2 else None,
        "next_transaction": database[3] if len(database) > 3 else None,
        "backup_state": database[4] if len(database) > 4 else None,
        "attachments": attachment[0] if attachment else 0,
    }
    return HealthReport(metrics, build_findings(metrics))


def list_sessions(profile: ConnectionProfile, password: str | None = None) -> list[dict[str, Any]]:
    """Return a read-only snapshot of active attachments."""
    with open_database(profile, password) as connection:
        try:
            rows = _rows(connection, "SELECT MON$ATTACHMENT_ID, MON$USER, MON$REMOTE_ADDRESS, MON$REMOTE_PROCESS, MON$STATE FROM MON$ATTACHMENTS ORDER BY MON$ATTACHMENT_ID")
        except Exception:
            rows = _rows(connection, "SELECT MON$ATTACHMENT_ID, MON$USER, MON$REMOTE_ADDRESS, MON$REMOTE_PROCESS FROM MON$ATTACHMENTS ORDER BY MON$ATTACHMENT_ID")
    sessions = []
    for row in rows:
        sessions.append({"id": row[0] if len(row) > 0 else None, "user": row[1] if len(row) > 1 else "", "address": row[2] if len(row) > 2 else "", "process": row[3] if len(row) > 3 else "", "state": row[4] if len(row) > 4 else None})
    return sessions
