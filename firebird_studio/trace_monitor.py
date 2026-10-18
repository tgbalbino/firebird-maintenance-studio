from __future__ import annotations

from pathlib import Path

from .models import ConnectionProfile


def find_trace_manager(profile: ConnectionProfile) -> Path | None:
    """Locate fbtracemgr beside the configured client or common installs."""
    candidates: list[Path] = []
    if profile.isql_path:
        candidates.append(Path(profile.isql_path.strip().strip('"')).parent / "fbtracemgr.exe")
    candidates.extend(
        Path(root) / "bin" / "fbtracemgr.exe"
        for root in (
            r"C:\Program Files\Firebird\Firebird_2_5",
            r"C:\Program Files\Firebird\Firebird_3_0",
            r"C:\Program Files\Firebird\Firebird_4_0",
            r"C:\Program Files\Firebird\Firebird_5_0",
            r"C:\Program Files (x86)\Firebird\Firebird_2_5",
        )
    )
    return next((path for path in candidates if path.exists()), None)


def build_trace_config(profile: ConnectionProfile) -> str:
    """Return a trace configuration compatible with Firebird 2.5 and newer."""
    database = profile.database.strip().replace("\\", "/")
    if profile.version == "2.5":
        # Firebird 2.5 interprets a database selector as a regular expression
        # (the examples use %[\\\\/] to match either Windows separator).
        # Escape the configured path so dots and other filename characters do
        # not change the selector, while accepting both slash styles emitted
        # by the server.
        # The trace matcher receives the fully qualified path but the drive
        # prefix is not stable across client/server setups. Match the path
        # from its first separator, as recommended by Firebird's template.
        path = database[2:] if len(database) >= 2 and database[1] == ":" else database
        # The Firebird trace matcher uses SIMILAR TO syntax; filename dots
        # are accepted directly in its examples, while slashes need the
        # explicit separator class.
        pattern = "%" + path.replace("/", r"[\\/]")
        return (
            f"<database {pattern}>\n"
            "    enabled true\n"
            "    log_connections true\n"
            "    log_statement_start true\n"
            "    log_statement_finish true\n"
            "    print_perf true\n"
            "    time_threshold 0\n"
            "</database>\n"
        )
    return (
        f"database = {database}\n"
        "{\n"
        "    enabled true\n"
        "    log_statement_start true\n"
        "    log_statement_finish true\n"
        "    print_perf true\n"
        "    time_threshold 0\n"
        "}\n"
    )
