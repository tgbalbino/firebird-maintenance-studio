"""Firebird SQL completion vocabulary and word collection."""

from __future__ import annotations


# Common reserved words shared by Firebird 2.5 through 5.0. The list is
# intentionally additive so a query written for an older server still gets
# useful completion in a newer one.
FIREBIRD_RESERVED_WORDS = frozenset(
    """ADD ADMIN ALL ALTER AND ANY AS ASC AT AVG BEGIN BETWEEN BIGINT BLOB
    BOOLEAN BY CASE CAST CHAR CHARACTER CHECK CLOSE COLLATE COLUMN COMMIT
    COMPUTED CONNECT CONSTRAINT CONTAINING COUNT CREATE CROSS CURRENT CURRENT_DATE
    CURRENT_TIME CURRENT_TIMESTAMP CURRENT_USER CURSOR DATABASE DATE DAY DEC
    DECIMAL DECLARE DEFAULT DELETE DESC DISTINCT DO DOMAIN DOUBLE DROP ELSE
    END ESCAPE EXECUTE EXISTS EXIT EXTERNAL EXTRACT FETCH FILTER FIRST FLOAT FOR
    FOREIGN FROM FULL FUNCTION GRANT GROUP HAVING IF IN INNER INSERT INT INTEGER
    INTO IS JOIN KEY LANGUAGE LEFT LIKE LIST LONG LOWER MERGE MIN MINUTE MONTH
    NATURAL NO NOT NULL NUMERIC OF ON ONLY OPEN OR ORDER OUTER PACKAGE PAGE
    PLAN POSITION POST_EVENT PRECISION PRIMARY PROCEDURE RDB$DB_KEY READ REAL
    RECREATE RECURSIVE REFERENCES RELEASE RETURNING RETURNS REVOKE RIGHT ROLLBACK
    ROWS SAVEPOINT SECOND SELECT SET SIMILAR SMALLINT SOME START SUM TABLE THEN
    TIME TIMESTAMP TO TRAILING TRANSACTION TRIGGER TRIM UNION UNIQUE UPDATE
    USER USING VALUE VALUES VARCHAR VARIABLE VIEW WHEN WHERE WHILE WITH WORK
    YEAR""".split()
)

FIREBIRD_TYPES = frozenset(
    """BIGINT BINARY BOOLEAN CHAR DATE DECFLOAT DECIMAL DOUBLE FLOAT INTEGER INT
    NUMERIC SMALLINT TIME TIMESTAMP VARCHAR BLOB""".split()
)

# Frequently used system relations and context variables. These are available
# even when catalog loading intentionally hides system objects from the tree.
FIREBIRD_SYSTEM_OBJECTS = frozenset(
    """RDB$DATABASE RDB$RELATIONS RDB$RELATION_FIELDS RDB$FIELDS RDB$INDICES
    RDB$INDEX_SEGMENTS RDB$RELATION_CONSTRAINTS RDB$REF_CONSTRAINTS RDB$TRIGGERS
    RDB$PROCEDURES RDB$PROCEDURE_PARAMETERS RDB$FUNCTIONS RDB$FUNCTION_ARGUMENTS
    RDB$PACKAGES RDB$GENERATORS RDB$EXCEPTIONS RDB$ROLES RDB$USER_PRIVILEGES
    RDB$DEPENDENCIES RDB$VIEW_RELATIONS RDB$CHARACTER_SETS RDB$COLLATIONS RDB$TYPES
    MON$DATABASE MON$ATTACHMENTS MON$TRANSACTIONS MON$STATEMENTS MON$CALL_STACK
    MON$IO_STATS MON$RECORD_STATS MON$CONTEXT_VARIABLES""".split()
)

# Built-in functions, aggregates and context variables that are not reserved
# words but are typed constantly.
FIREBIRD_FUNCTIONS = frozenset(
    """ABS CEIL CEILING COALESCE CHAR_LENGTH CURRENT_CONNECTION CURRENT_ROLE
    CURRENT_TRANSACTION DATEADD DATEDIFF DECODE FLOOR GEN_ID GEN_UUID HASH IIF
    LEFT LPAD LTRIM MAX MOD NEXT NULLIF OVERLAY PARTITION RAND REPLACE REVERSE
    ROUND ROW_COUNT ROW_NUMBER RPAD RTRIM SEQUENCE SUBSTRING TRUNC UPPER
    UUID_TO_CHAR""".split()
)

WORD_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_$")


def word_bounds(line: str, column: int) -> tuple[int, int]:
    """Return ``(start, end)`` of the identifier touching ``column`` in ``line``.

    Firebird identifiers may contain ``$`` (RDB$RELATIONS), which Qt's own
    word detection treats as a separator.
    """
    column = max(0, min(column, len(line)))
    start = column
    while start > 0 and line[start - 1] in WORD_CHARS:
        start -= 1
    end = column
    while end < len(line) and line[end] in WORD_CHARS:
        end += 1
    return start, end


def completion_words(objects_by_profile, include_system=True, profile_name=None):
    """Return a stable, case-insensitive completion list for loaded metadata.

    When ``profile_name`` names a loaded profile, only that database's objects
    are offered; otherwise every loaded profile contributes.
    """
    words = set(FIREBIRD_RESERVED_WORDS) | set(FIREBIRD_TYPES) | set(FIREBIRD_FUNCTIONS)
    if profile_name in objects_by_profile:
        objects_by_profile = {profile_name: objects_by_profile[profile_name]}
    if include_system:
        words.update(FIREBIRD_SYSTEM_OBJECTS)
    for objects in objects_by_profile.values():
        for obj in objects:
            name = str(getattr(obj, "name", "")).strip()
            if name:
                words.add(name)
            for column in getattr(obj, "columns", ()):
                if column and column[0]:
                    words.add(str(column[0]).strip())
    return sorted((word for word in words if word), key=str.casefold)

