from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class SchemaObject:
    kind: str
    name: str
    ddl: str
    dependencies: tuple[str, ...] = ()
    # TABLE objects carry catalog column metadata for the object inspector.
    # Other object types leave this tuple empty.
    columns: tuple[tuple[str, str, str, str, str], ...] = ()
    # TABLE objects may expose their primary-key fields for safe row edits.
    primary_key: tuple[str, ...] = ()

    @property
    def key(self) -> tuple[str, str]:
        return (self.kind.upper(), self.name.upper())

    @property
    def normalized_ddl(self) -> str:
        text = self.ddl.strip().replace("\r\n", "\n").rstrip(";").strip()
        return re.sub(r"\s+", " ", text).upper()


@dataclass(frozen=True, slots=True)
class SchemaChange:
    action: str
    object: SchemaObject
    previous: SchemaObject | None = None
    destructive: bool = False


_MIGRATION_ORDER = {
    "DOMAIN": 10,
    "SEQUENCE": 20,
    "GENERATOR": 20,
    "EXCEPTION": 30,
    "TABLE": 40,
    "CONSTRAINT": 50,
    "INDEX": 60,
    "VIEW": 70,
    "PACKAGE": 80,
    "PROCEDURE": 90,
    "FUNCTION": 100,
    "TRIGGER": 110,
}


def compare_schema(source: list[SchemaObject], target: list[SchemaObject]) -> list[SchemaChange]:
    source_map = {obj.key: obj for obj in source}
    target_map = {obj.key: obj for obj in target}
    changes: list[SchemaChange] = []
    for key in sorted(source_map.keys() - target_map.keys()):
        changes.append(SchemaChange("ADD", source_map[key]))
    for key in sorted(target_map.keys() - source_map.keys()):
        changes.append(SchemaChange("REMOVE", target_map[key], destructive=True))
    for key in sorted(source_map.keys() & target_map.keys()):
        source_obj, target_obj = source_map[key], target_map[key]
        if source_obj.normalized_ddl != target_obj.normalized_ddl:
            changes.append(SchemaChange("ALTER", source_obj, target_obj, destructive=_is_destructive(source_obj, target_obj)))
    return changes


def _is_destructive(source: SchemaObject, target: SchemaObject) -> bool:
    source_ddl, target_ddl = source.normalized_ddl, target.normalized_ddl
    return any(token in source_ddl or token in target_ddl for token in ("DROP ", "NOT NULL", "PRIMARY KEY")) or len(source_ddl) < len(target_ddl)


def generate_migration(changes: list[SchemaChange]) -> str:
    lines = ["-- Firebird Maintenance Studio: migration preview", "-- Review every statement before applying it.", ""]
    ordered_changes = sorted(
        changes,
        key=lambda change: (
            _MIGRATION_ORDER.get(change.object.kind.upper(), 999),
            change.action == "REMOVE",
            change.object.name.upper(),
        ),
    )
    for change in ordered_changes:
        label = f"{change.action} {change.object.kind} {change.object.name}"
        if change.action == "ADD":
            lines.extend([f"-- {label}", change.object.ddl.rstrip().rstrip(";") + ";", ""])
        elif change.action == "ALTER":
            review = " [REVIEW: potentially destructive]" if change.destructive else ""
            ddl = change.object.ddl.rstrip().rstrip(";") + ";"
            if re.match(r"\s*(CREATE|RECREATE)\b", ddl, re.IGNORECASE):
                lines.append(f"-- {label}{review} [MANUAL ALTER REQUIRED]")
                lines.append("-- The source DDL is shown for review and is not executable as an ALTER:")
                lines.extend(f"-- {line}" for line in ddl.splitlines())
                lines.append("")
            else:
                lines.extend([f"-- {label}{review}", ddl, ""])
        elif change.action == "REMOVE":
            lines.extend([f"-- {label} [NOT GENERATED: destructive change]", ""])
    if not changes:
        lines.append("-- No structural differences found.")
    return "\n".join(lines).rstrip() + "\n"
