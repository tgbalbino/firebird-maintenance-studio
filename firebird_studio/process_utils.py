"""Small helpers shared by Firebird command line integrations."""

from pathlib import Path
from dataclasses import dataclass
import os
import subprocess
from typing import Any, Callable


@dataclass(slots=True)
class CommandResult:
    completed: Any | None = None
    error: Exception | None = None
    timed_out: bool = False


def resolve_tool_path(value: Path | str, executable_name: str) -> Path:
    """Normalize a configured executable or installation directory."""
    path = Path(str(value).strip().strip('"')).expanduser()
    return path / executable_name if path.is_dir() else path


def run_command(runner: Callable[..., Any], args: list[str], **kwargs: Any) -> CommandResult:
    """Run a command while keeping timeout and startup handling consistent."""
    if os.name == "nt" and "creationflags" not in kwargs:
        # Keep console tools (isql, gbak, gfix and helper scripts) behind the
        # Qt window instead of briefly opening a black CMD window.
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        return CommandResult(completed=runner(args, **kwargs))
    except subprocess.TimeoutExpired as exc:
        return CommandResult(error=exc, timed_out=True)
    except OSError as exc:
        return CommandResult(error=exc)
