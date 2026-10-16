"""Small helpers shared by Firebird command line integrations."""

from pathlib import Path


def resolve_tool_path(value: Path | str, executable_name: str) -> Path:
    """Normalize a configured executable or installation directory."""
    path = Path(str(value).strip().strip('"')).expanduser()
    return path / executable_name if path.is_dir() else path
