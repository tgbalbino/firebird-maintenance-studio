from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import re
import subprocess

from .connection import _dsn
from .models import ConnectionProfile


@dataclass(slots=True)
class PlanNode:
    label: str
    children: list["PlanNode"] = field(default_factory=list)


@dataclass(slots=True)
class PlanResult:
    ok: bool
    raw: str
    tree: PlanNode | None
    suggestions: list[str]
    error: str = ""


def build_plan_script(sql: str, version: str) -> str:
    explain = "SET EXPLAIN ON;\n" if version != "2.5" else ""
    return f"SET PLAN ON;\n{explain}SET PLANONLY ON;\n{sql.strip().rstrip(';')};\nSET PLANONLY OFF;\nQUIT;\n"


def parse_plan(raw: str) -> PlanNode:
    root = PlanNode("Plano de acesso")
    stack: list[tuple[int, PlanNode]] = [(-1, root)]
    for line in raw.splitlines():
        stripped = line.strip()
        upper = stripped.upper()
        if not stripped or upper.startswith(("SQL>", "CON>", "PLAN (")) or "STATEMENT" in upper:
            if upper.startswith("PLAN ("):
                stripped = stripped[6:].rstrip(")")
            else:
                continue
        if not any(token in upper for token in ("NATURAL", "INDEX", "JOIN", "SORT", "FILTER", "TABLE", "VIEW", "BITMAP", "HASH", "MERGE", "ACCESS BY ID", "RECORD SOURCE")):
            continue
        indent = len(line) - len(line.lstrip())
        node = PlanNode(stripped)
        while stack[-1][0] >= indent:
            stack.pop()
        stack[-1][1].children.append(node)
        stack.append((indent, node))
    return root


def suggest_improvements(raw: str, sql: str) -> list[str]:
    upper = raw.upper()
    suggestions: list[str] = []
    if "NATURAL" in upper:
        suggestions.append("Há uma varredura NATURAL. Verifique filtros, cardinalidade e índices nas colunas usadas no WHERE e JOIN.")
    if "SORT" in upper:
        suggestions.append("O plano inclui SORT. Confira ORDER BY, GROUP BY e índices que possam atender a ordenação.")
    if "JOIN" in upper and "INDEX" not in upper:
        suggestions.append("O JOIN não mostra uso de índice. Verifique as colunas de junção e índices compatíveis.")
    if re.search(r"\bSELECT\s+\*\b", sql, re.IGNORECASE):
        suggestions.append("Evite SELECT * em consultas de produção; selecione somente as colunas necessárias.")
    if not suggestions:
        suggestions.append("Nenhum sinal simples de melhoria foi encontrado. Compare o plano com tempo e estatísticas reais.")
    return suggestions


def explain_query(profile: ConnectionProfile, sql: str, password: str | None, isql_path: Path, timeout_seconds: int = 120) -> PlanResult:
    errors = profile.validate()
    if errors:
        return PlanResult(False, "", None, [], " ".join(errors))
    if not sql.strip():
        return PlanResult(False, "", None, [], "Informe uma consulta SQL.")
    isql_path = Path(str(isql_path).strip().strip('"')).expanduser()
    if isql_path.is_dir():
        isql_path = isql_path / "isql.exe"
    if not isql_path.exists() or not isql_path.is_file():
        return PlanResult(False, "", None, [], f"Executável isql não encontrado: {isql_path}")
    args = [str(isql_path), "-user", profile.user, "-ch", profile.charset, "-m2", _dsn(profile)]
    if profile.role:
        args.extend(["-role", profile.role])
    try:
        database = _dsn(profile).replace("'", "''")
        user = profile.user.replace("'", "''")
        secret = (password or "").replace("'", "''")
        connect_command = f"CONNECT '{database}' USER '{user}' PASSWORD '{secret}';\n"
        completed = subprocess.run(
            args,
            # Supplying CONNECT through stdin handles Firebird installations
            # that ignore ISC_PASSWORD while keeping credentials out of the
            # process command line and event log.
            input=connect_command + build_plan_script(sql, profile.version),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
            cwd=str(isql_path.parent),
            env={**os.environ, "ISC_USER": profile.user, "ISC_PASSWORD": password or ""},
        )
    except subprocess.TimeoutExpired:
        return PlanResult(False, "", None, [], "A análise do plano excedeu o limite de tempo.")
    except OSError as exc:
        if getattr(exc, "winerror", None) == 5 or getattr(exc, "errno", None) == 13:
            return PlanResult(False, "", None, [], f"Acesso negado ao isql.exe: {isql_path}. Verifique as permissões do arquivo e se o Windows não o bloqueou.")
        return PlanResult(False, "", None, [], f"Não foi possível iniciar o isql: {exc}")
    raw = (completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else "")
    if completed.returncode != 0:
        return PlanResult(False, raw, None, [], "Falha ao obter o plano.")
    return PlanResult(True, raw, parse_plan(raw), suggest_improvements(raw, sql))
