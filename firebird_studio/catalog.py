from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from .connection import _client_library, _dsn
from .models import ConnectionProfile
from .schema import SchemaObject


@contextmanager
def open_database(profile: ConnectionProfile, password: str | None = None) -> Iterator[Any]:
    errors = profile.validate()
    if errors:
        raise ValueError(" ".join(errors))
    kwargs = {"dsn": _dsn(profile), "user": profile.user, "password": password or "", "charset": profile.charset}
    client_library = _client_library(profile)
    if client_library:
        kwargs["fb_library_name"] = client_library
    if profile.role:
        kwargs["role"] = profile.role
    if profile.version == "2.5":
        import fdb
        connect = fdb.connect
    else:
        from firebird.driver import connect
    with connect(**kwargs) as connection:
        yield connection


def _rows(connection: Any, query: str) -> list[tuple]:
    cursor = connection.cursor()
    cursor.execute(query)
    return list(cursor.fetchall())


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _field_type(field_type: int, length: int, scale: int, precision: int | None) -> str:
    names = {7: "SMALLINT", 8: "INTEGER", 10: "FLOAT", 12: "DATE", 13: "TIME", 14: "CHAR", 16: "BIGINT", 23: "BOOLEAN", 24: "DECFLOAT(16)", 25: "DECFLOAT(34)", 26: "INT128", 27: "DOUBLE PRECISION", 28: "TIME WITH TIME ZONE", 29: "TIMESTAMP WITH TIME ZONE", 35: "TIMESTAMP", 37: "VARCHAR", 261: "BLOB"}
    name = names.get(field_type, "BLOB")
    if name in {"CHAR", "VARCHAR"}:
        return f"{name}({length})"
    if precision and field_type in {7, 8, 16} and scale:
        return f"DECIMAL({precision},{abs(scale)})"
    return name


def load_schema(profile: ConnectionProfile, password: str | None = None, detailed: bool = True) -> list[SchemaObject]:
    """Extract a conservative schema snapshot using common Firebird catalog tables."""
    objects: list[SchemaObject] = []
    with open_database(profile, password) as connection:
        if not detailed:
            queries = (
                ("TABLE", "SELECT TRIM(RDB$RELATION_NAME) FROM RDB$RELATIONS WHERE COALESCE(RDB$SYSTEM_FLAG,0)=0 AND RDB$VIEW_BLR IS NULL ORDER BY RDB$RELATION_NAME"),
                ("VIEW", "SELECT TRIM(RDB$RELATION_NAME) FROM RDB$RELATIONS WHERE RDB$VIEW_BLR IS NOT NULL AND COALESCE(RDB$SYSTEM_FLAG,0)=0 ORDER BY RDB$RELATION_NAME"),
                ("PROCEDURE", "SELECT TRIM(RDB$PROCEDURE_NAME) FROM RDB$PROCEDURES WHERE COALESCE(RDB$SYSTEM_FLAG,0)=0 ORDER BY RDB$PROCEDURE_NAME"),
                ("TRIGGER", "SELECT TRIM(RDB$TRIGGER_NAME) FROM RDB$TRIGGERS WHERE COALESCE(RDB$SYSTEM_FLAG,0)=0 ORDER BY RDB$TRIGGER_NAME"),
                ("DOMAIN", "SELECT TRIM(RDB$FIELD_NAME) FROM RDB$FIELDS WHERE COALESCE(RDB$SYSTEM_FLAG,0)=0 AND RDB$FIELD_NAME NOT LIKE 'RDB$%' ORDER BY RDB$FIELD_NAME"),
                ("INDEX", "SELECT TRIM(RDB$INDEX_NAME) FROM RDB$INDICES WHERE COALESCE(RDB$SYSTEM_FLAG,0)=0 ORDER BY RDB$INDEX_NAME"),
                ("CONSTRAINT", "SELECT TRIM(RDB$CONSTRAINT_NAME) FROM RDB$RELATION_CONSTRAINTS ORDER BY RDB$CONSTRAINT_NAME"),
                ("SEQUENCE", "SELECT TRIM(RDB$GENERATOR_NAME) FROM RDB$GENERATORS WHERE COALESCE(RDB$SYSTEM_FLAG,0)=0 ORDER BY RDB$GENERATOR_NAME"),
                ("EXCEPTION", "SELECT TRIM(RDB$EXCEPTION_NAME) FROM RDB$EXCEPTIONS WHERE COALESCE(RDB$SYSTEM_FLAG,0)=0 ORDER BY RDB$EXCEPTION_NAME"),
            )
            for kind, query in queries:
                try:
                    for (name,) in _rows(connection, query):
                        clean_name = _text(name)
                        objects.append(SchemaObject(kind, clean_name, f"-- {kind} {clean_name}\n-- Use 'Ler estrutura' para carregar o DDL completo."))
                except Exception:
                    continue
            if profile.version != "2.5":
                try:
                    for (name,) in _rows(connection, "SELECT TRIM(RDB$FUNCTION_NAME) FROM RDB$FUNCTIONS WHERE COALESCE(RDB$SYSTEM_FLAG,0)=0 ORDER BY RDB$FUNCTION_NAME"):
                        clean_name = _text(name)
                        objects.append(SchemaObject("FUNCTION", clean_name, f"-- FUNCTION {clean_name}\n-- Use 'Ler estrutura' para carregar o DDL completo."))
                except Exception:
                    pass
                try:
                    for (name,) in _rows(connection, "SELECT TRIM(RDB$PACKAGE_NAME) FROM RDB$PACKAGES ORDER BY RDB$PACKAGE_NAME"):
                        clean_name = _text(name)
                        objects.append(SchemaObject("PACKAGE", clean_name, f"-- PACKAGE {clean_name}\n-- Use 'Ler estrutura' para carregar o DDL completo."))
                except Exception:
                    pass
            return objects
        table_rows = _rows(connection, """
            SELECT TRIM(RDB$RELATION_NAME) FROM RDB$RELATIONS
            WHERE COALESCE(RDB$SYSTEM_FLAG, 0) = 0 AND RDB$VIEW_BLR IS NULL
            ORDER BY RDB$RELATION_NAME
        """)
        for (table_name,) in table_rows:
            columns = _rows(connection, f"""
                SELECT TRIM(rf.RDB$FIELD_NAME), f.RDB$FIELD_TYPE, f.RDB$FIELD_LENGTH,
                       f.RDB$FIELD_SCALE, f.RDB$FIELD_PRECISION, rf.RDB$NULL_FLAG
                FROM RDB$RELATION_FIELDS rf JOIN RDB$FIELDS f ON f.RDB$FIELD_NAME = rf.RDB$FIELD_SOURCE
                WHERE rf.RDB$RELATION_NAME = '{_text(table_name).replace("'", "''")}'
                ORDER BY rf.RDB$FIELD_POSITION
            """)
            definitions = []
            column_details = []
            for name, field_type, length, scale, precision, null_flag in columns:
                type_name = _field_type(int(field_type), int(length), int(scale), int(precision) if precision is not None else None)
                column_details.append((_text(name), type_name, str(length or ""), str(abs(scale or 0)), "NÃO" if null_flag else "SIM"))
                definitions.append(f'  "{_text(name)}" {type_name}')
            ddl = f'CREATE TABLE "{_text(table_name)}" (\n' + ",\n".join(definitions) + "\n)"
            objects.append(SchemaObject("TABLE", _text(table_name), ddl, columns=tuple(column_details)))

        for name, source in _rows(connection, "SELECT TRIM(RDB$RELATION_NAME), RDB$VIEW_SOURCE FROM RDB$RELATIONS WHERE RDB$VIEW_BLR IS NOT NULL AND COALESCE(RDB$SYSTEM_FLAG,0)=0"):
            objects.append(SchemaObject("VIEW", _text(name), f'CREATE VIEW "{_text(name)}" AS\n{_text(source)}'))
        for name, source in _rows(connection, "SELECT TRIM(RDB$PROCEDURE_NAME), RDB$PROCEDURE_SOURCE FROM RDB$PROCEDURES WHERE COALESCE(RDB$SYSTEM_FLAG,0)=0"):
            objects.append(SchemaObject("PROCEDURE", _text(name), f'CREATE PROCEDURE "{_text(name)}"\n{_text(source)}'))
        # Firebird 2.5 does not expose RDB$FUNCTION_SOURCE. Keep the
        # connection usable and list functions only when their source column
        # exists (Firebird 3+). External/UDF functions on 2.5 remain usable
        # through SQL, but their source cannot be reconstructed from the
        # system tables.
        if profile.version != "2.5":
            try:
                function_rows = _rows(connection, "SELECT TRIM(RDB$FUNCTION_NAME), RDB$FUNCTION_SOURCE FROM RDB$FUNCTIONS WHERE COALESCE(RDB$SYSTEM_FLAG,0)=0")
            except Exception:
                function_rows = []
            for name, source in function_rows:
                objects.append(SchemaObject("FUNCTION", _text(name), f'CREATE FUNCTION "{_text(name)}"\n{_text(source)}'))
        for name, source in _rows(connection, "SELECT TRIM(RDB$TRIGGER_NAME), RDB$TRIGGER_SOURCE FROM RDB$TRIGGERS WHERE COALESCE(RDB$SYSTEM_FLAG,0)=0"):
            objects.append(SchemaObject("TRIGGER", _text(name), f'CREATE TRIGGER "{_text(name)}"\n{_text(source)}'))
        # Domains are included in the full snapshot so schema comparison does
        # not silently ignore reusable field definitions.
        try:
            domain_rows = _rows(connection, """
                SELECT TRIM(RDB$FIELD_NAME), RDB$FIELD_TYPE, RDB$FIELD_LENGTH,
                       RDB$FIELD_SCALE, RDB$FIELD_PRECISION, RDB$NULL_FLAG
                FROM RDB$FIELDS
                WHERE COALESCE(RDB$SYSTEM_FLAG, 0)=0 AND RDB$FIELD_NAME NOT LIKE 'RDB$%'
                ORDER BY RDB$FIELD_NAME
            """)
        except Exception:
            domain_rows = []
        for name, field_type, length, scale, precision, null_flag in domain_rows:
            domain_name = _text(name)
            type_name = _field_type(int(field_type), int(length), int(scale), int(precision) if precision is not None else None)
            suffix = " NOT NULL" if null_flag else ""
            objects.append(SchemaObject("DOMAIN", domain_name, f'CREATE DOMAIN "{domain_name}" AS {type_name}{suffix}'))

        # Indexes need their segments grouped before generating a reviewable
        # CREATE INDEX statement. Expression indexes without segments remain
        # visible with a catalog note instead of being dropped silently.
        try:
            index_rows = _rows(connection, """
                SELECT TRIM(i.RDB$INDEX_NAME), TRIM(i.RDB$RELATION_NAME),
                       COALESCE(i.RDB$UNIQUE_FLAG, 0), TRIM(s.RDB$FIELD_NAME),
                       s.RDB$FIELD_POSITION
                FROM RDB$INDICES i
                LEFT JOIN RDB$INDEX_SEGMENTS s ON s.RDB$INDEX_NAME = i.RDB$INDEX_NAME
                WHERE COALESCE(i.RDB$SYSTEM_FLAG, 0)=0
                ORDER BY i.RDB$INDEX_NAME, s.RDB$FIELD_POSITION
            """)
        except Exception:
            index_rows = []
        grouped_indexes: dict[str, dict[str, Any]] = {}
        for index_name, relation_name, unique_flag, field_name, _position in index_rows:
            clean_index = _text(index_name)
            entry = grouped_indexes.setdefault(clean_index, {"relation": _text(relation_name), "unique": bool(unique_flag), "fields": []})
            if field_name:
                entry["fields"].append(_text(field_name))
        for index_name, entry in grouped_indexes.items():
            fields = entry["fields"]
            if fields:
                unique = "UNIQUE " if entry["unique"] else ""
                quoted_fields = ", ".join(f'"{field}"' for field in fields)
                ddl = f'CREATE {unique}INDEX "{index_name}" ON "{entry["relation"]}" ({quoted_fields})'
            else:
                ddl = f'-- INDEX {index_name}\n-- Expression index; review its expression in the source database.'
            objects.append(SchemaObject("INDEX", index_name, ddl))

        # Primary, unique and foreign-key constraints are reconstructed from
        # their backing index segments.  Check constraints remain visible even
        # when their trigger source cannot be recovered on an older catalog.
        try:
            constraint_rows = _rows(connection, """
                SELECT TRIM(rc.RDB$CONSTRAINT_NAME), TRIM(rc.RDB$CONSTRAINT_TYPE),
                       TRIM(rc.RDB$RELATION_NAME), TRIM(rc.RDB$INDEX_NAME),
                       TRIM(ref.RDB$CONST_NAME_UQ), TRIM(parent.RDB$RELATION_NAME)
                FROM RDB$RELATION_CONSTRAINTS rc
                LEFT JOIN RDB$REF_CONSTRAINTS ref ON ref.RDB$CONSTRAINT_NAME = rc.RDB$CONSTRAINT_NAME
                LEFT JOIN RDB$RELATION_CONSTRAINTS parent ON parent.RDB$CONSTRAINT_NAME = ref.RDB$CONST_NAME_UQ
                ORDER BY rc.RDB$CONSTRAINT_NAME
            """)
        except Exception:
            constraint_rows = []
        for name, constraint_type, relation, index_name, referenced_name, referenced_relation in constraint_rows:
            clean_name, clean_relation, clean_index = _text(name), _text(relation), _text(index_name)
            try:
                fields = [_text(row[0]) for row in _rows(connection, f"SELECT TRIM(RDB$FIELD_NAME) FROM RDB$INDEX_SEGMENTS WHERE RDB$INDEX_NAME = '{clean_index.replace(chr(39), chr(39) * 2)}' ORDER BY RDB$FIELD_POSITION")]
            except Exception:
                fields = []
            quoted_fields = ", ".join(f'"{field}"' for field in fields)
            kind = _text(constraint_type).upper()
            if kind == "PRIMARY KEY":
                ddl = f'ALTER TABLE "{clean_relation}" ADD CONSTRAINT "{clean_name}" PRIMARY KEY ({quoted_fields})'
            elif kind == "UNIQUE":
                ddl = f'ALTER TABLE "{clean_relation}" ADD CONSTRAINT "{clean_name}" UNIQUE ({quoted_fields})'
            elif kind == "FOREIGN KEY":
                target = _text(referenced_relation)
                ddl = f'ALTER TABLE "{clean_relation}" ADD CONSTRAINT "{clean_name}" FOREIGN KEY ({quoted_fields}) REFERENCES "{target}"'
                if referenced_name:
                    ddl += f' /* references constraint { _text(referenced_name) } */'
            else:
                ddl = f'-- CONSTRAINT {clean_name} ({kind})\n-- Review the check/source expression in the source database.'
            objects.append(SchemaObject("CONSTRAINT", clean_name, ddl))

        try:
            for (name,) in _rows(connection, "SELECT TRIM(RDB$GENERATOR_NAME) FROM RDB$GENERATORS WHERE COALESCE(RDB$SYSTEM_FLAG,0)=0 ORDER BY RDB$GENERATOR_NAME"):
                clean_name = _text(name)
                objects.append(SchemaObject("SEQUENCE", clean_name, f'CREATE SEQUENCE "{clean_name}";'))
        except Exception:
            pass
        try:
            for name, message in _rows(connection, "SELECT TRIM(RDB$EXCEPTION_NAME), RDB$MESSAGE FROM RDB$EXCEPTIONS WHERE COALESCE(RDB$SYSTEM_FLAG,0)=0 ORDER BY RDB$EXCEPTION_NAME"):
                clean_name = _text(name)
                escaped_message = _text(message).replace("'", "''")
                objects.append(SchemaObject("EXCEPTION", clean_name, f'CREATE EXCEPTION "{clean_name}" \'{escaped_message}\';'))
        except Exception:
            pass
        if profile.version != "2.5":
            try:
                for name, header, body in _rows(connection, "SELECT TRIM(RDB$PACKAGE_NAME), RDB$PACKAGE_HEADER_SOURCE, RDB$PACKAGE_BODY_SOURCE FROM RDB$PACKAGES ORDER BY RDB$PACKAGE_NAME"):
                    clean_name = _text(name)
                    ddl = _text(header) or f'-- PACKAGE "{clean_name}"'
                    if _text(body):
                        ddl += "\n\n" + _text(body)
                    objects.append(SchemaObject("PACKAGE", clean_name, ddl))
            except Exception:
                pass
    return objects


def load_table_metadata(profile: ConnectionProfile, password: str | None, table_name: str) -> SchemaObject:
    """Load one table's columns on demand after the fast catalog scan."""
    safe_name = _text(table_name).replace("'", "''")
    with open_database(profile, password) as connection:
        rows = _rows(connection, f"""
            SELECT TRIM(rf.RDB$FIELD_NAME), f.RDB$FIELD_TYPE, f.RDB$FIELD_LENGTH,
                   f.RDB$FIELD_SCALE, f.RDB$FIELD_PRECISION, rf.RDB$NULL_FLAG
            FROM RDB$RELATION_FIELDS rf JOIN RDB$FIELDS f ON f.RDB$FIELD_NAME = rf.RDB$FIELD_SOURCE
            WHERE rf.RDB$RELATION_NAME = '{safe_name}'
            ORDER BY rf.RDB$FIELD_POSITION
        """)
    columns = []
    definitions = []
    for name, field_type, length, scale, precision, null_flag in rows:
        type_name = _field_type(int(field_type), int(length), int(scale), int(precision) if precision is not None else None)
        columns.append((_text(name), type_name, str(length or ""), str(abs(scale or 0)), "NÃO" if null_flag else "SIM"))
        definitions.append(f'  "{_text(name)}" {type_name}')
    ddl = f'CREATE TABLE "{_text(table_name)}" (\n' + ",\n".join(definitions) + "\n)"
    return SchemaObject("TABLE", _text(table_name), ddl, columns=tuple(columns))


def load_object_definition(profile: ConnectionProfile, password: str | None, kind: str, object_name: str) -> SchemaObject:
    """Read one object's source/definition when it is selected in the tree.

    The initial catalog scan intentionally returns names only so a database
    with many objects opens quickly.  This function keeps the expensive DDL
    lookup lazy and works with the catalog columns available in Firebird 2.5+
    (functions on 2.5 do not expose source text).
    """
    clean_kind = kind.upper().strip()
    name = _text(object_name)
    safe_name = name.replace("'", "''")
    queries = {
        "VIEW": ("SELECT RDB$VIEW_SOURCE FROM RDB$RELATIONS WHERE RDB$RELATION_NAME = ?", f'CREATE VIEW "{name}" AS\n'),
        "PROCEDURE": ("SELECT RDB$PROCEDURE_SOURCE FROM RDB$PROCEDURES WHERE RDB$PROCEDURE_NAME = ?", f'CREATE PROCEDURE "{name}"\n'),
        "FUNCTION": ("SELECT RDB$FUNCTION_SOURCE FROM RDB$FUNCTIONS WHERE RDB$FUNCTION_NAME = ?", f'CREATE FUNCTION "{name}"\n'),
        "TRIGGER": ("SELECT RDB$TRIGGER_SOURCE FROM RDB$TRIGGERS WHERE RDB$TRIGGER_NAME = ?", f'CREATE TRIGGER "{name}"\n'),
        "SEQUENCE": ("SELECT RDB$GENERATOR_NAME FROM RDB$GENERATORS WHERE RDB$GENERATOR_NAME = ?", f'CREATE SEQUENCE "{name}";\n'),
        "GENERATOR": ("SELECT RDB$GENERATOR_NAME FROM RDB$GENERATORS WHERE RDB$GENERATOR_NAME = ?", f'CREATE SEQUENCE "{name}";\n'),
    }
    if clean_kind == "TABLE":
        return load_table_metadata(profile, password, name)
    if clean_kind == "EXCEPTION":
        with open_database(profile, password) as connection:
            try:
                rows = _rows(connection, f"SELECT RDB$MESSAGE FROM RDB$EXCEPTIONS WHERE RDB$EXCEPTION_NAME = '{safe_name}'")
            except Exception:
                rows = []
        message = _text(rows[0][0]) if rows else ""
        escaped_message = message.replace("'", "''")
        return SchemaObject(clean_kind, name, f'CREATE EXCEPTION "{name}" \'{escaped_message}\';')
    if clean_kind == "PACKAGE":
        with open_database(profile, password) as connection:
            try:
                rows = _rows(connection, f"SELECT RDB$PACKAGE_HEADER_SOURCE, RDB$PACKAGE_BODY_SOURCE FROM RDB$PACKAGES WHERE RDB$PACKAGE_NAME = '{safe_name}'")
            except Exception:
                rows = []
        if rows:
            header, body = (_text(value) for value in rows[0][:2])
            ddl = header or f'-- PACKAGE "{name}"'
            if body:
                ddl += "\n\n" + body
            return SchemaObject(clean_kind, name, ddl)
        return SchemaObject(clean_kind, name, f"-- PACKAGE {name}\n-- Não foi possível obter o cabeçalho/corpo no catálogo.")
    if clean_kind == "CONSTRAINT":
        with open_database(profile, password) as connection:
            safe = safe_name
            try:
                rows = _rows(connection, f"""
                    SELECT TRIM(rc.RDB$CONSTRAINT_TYPE), TRIM(rc.RDB$RELATION_NAME), TRIM(rc.RDB$INDEX_NAME),
                           TRIM(parent.RDB$RELATION_NAME)
                    FROM RDB$RELATION_CONSTRAINTS rc
                    LEFT JOIN RDB$REF_CONSTRAINTS ref ON ref.RDB$CONSTRAINT_NAME = rc.RDB$CONSTRAINT_NAME
                    LEFT JOIN RDB$RELATION_CONSTRAINTS parent ON parent.RDB$CONSTRAINT_NAME = ref.RDB$CONST_NAME_UQ
                    WHERE rc.RDB$CONSTRAINT_NAME = '{safe}'
                """)
            except Exception:
                rows = []
            if rows:
                constraint_type, relation, index_name, referenced_relation = rows[0]
                try:
                    fields = [_text(row[0]) for row in _rows(connection, f"SELECT TRIM(RDB$FIELD_NAME) FROM RDB$INDEX_SEGMENTS WHERE RDB$INDEX_NAME = '{_text(index_name).replace(chr(39), chr(39) * 2)}' ORDER BY RDB$FIELD_POSITION")]
                except Exception:
                    fields = []
                cols = ", ".join(f'"{field}"' for field in fields)
                kind_text = _text(constraint_type).upper()
                if kind_text == "PRIMARY KEY":
                    ddl = f'ALTER TABLE "{_text(relation)}" ADD CONSTRAINT "{name}" PRIMARY KEY ({cols})'
                elif kind_text == "UNIQUE":
                    ddl = f'ALTER TABLE "{_text(relation)}" ADD CONSTRAINT "{name}" UNIQUE ({cols})'
                elif kind_text == "FOREIGN KEY":
                    ddl = f'ALTER TABLE "{_text(relation)}" ADD CONSTRAINT "{name}" FOREIGN KEY ({cols}) REFERENCES "{_text(referenced_relation)}"'
                else:
                    ddl = f'-- CONSTRAINT {name} ({kind_text})\n-- Review the source expression in the source database.'
                return SchemaObject(clean_kind, name, ddl)
        return SchemaObject(clean_kind, name, f"-- CONSTRAINT {name}\n-- Não foi possível obter a definição no catálogo.")
    if clean_kind not in queries:
        return SchemaObject(clean_kind, name, f"-- {clean_kind} {name}\n-- DDL detalhado ainda não está disponível para este tipo.")
    query, prefix = queries[clean_kind]
    with open_database(profile, password) as connection:
        try:
            rows = _rows(connection, query.replace("?", f"'{safe_name}'"))
        except Exception:
            rows = []
    source = _text(rows[0][0]) if rows else ""
    if source:
        return SchemaObject(clean_kind, name, prefix + source)
    if clean_kind == "FUNCTION" and profile.version == "2.5":
        detail = "-- Firebird 2.5 não armazena o código-fonte de funções externas no catálogo."
    else:
        detail = "-- Não foi possível obter o código-fonte deste objeto no catálogo."
    return SchemaObject(clean_kind, name, f"-- {clean_kind} {name}\n{detail}")
