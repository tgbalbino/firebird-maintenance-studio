from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json


SUPPORTED_VERSIONS = ("2.5", "3", "4", "5")


@dataclass(slots=True)
class ConnectionProfile:
    name: str
    host: str = "localhost"
    port: int = 3050
    database: str = ""
    version: str = "5"
    user: str = "SYSDBA"
    role: str = ""
    charset: str = "UTF8"
    trusted: bool = False
    isql_path: str = ""

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.name.strip():
            errors.append("O nome do perfil é obrigatório.")
        if self.version not in SUPPORTED_VERSIONS:
            errors.append(f"Versão não suportada: {self.version}.")
        if not 1 <= self.port <= 65535:
            errors.append("A porta deve estar entre 1 e 65535.")
        if not self.database.strip():
            errors.append("Informe o caminho ou alias do banco.")
        if not self.trusted and not self.user.strip():
            errors.append("Informe o usuário ou use autenticação confiável.")
        return errors


class ProfileStore:
    """Stores connection metadata only; passwords are intentionally excluded."""

    def __init__(self, path: Path):
        self.path = path

    def load(self) -> list[ConnectionProfile]:
        if not self.path.exists():
            return []
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return [ConnectionProfile(**{**item, "isql_path": item.get("isql_path", "")}) for item in raw]

    def save(self, profiles: list[ConnectionProfile]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(profile) for profile in profiles]
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
