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
    RDB$PROCEDURES RDB$FUNCTIONS RDB$PACKAGES RDB$GENERATORS RDB$EXCEPTIONS
    RDB$ROLES RDB$USERS RDB$ATTACHMENTS RDB$TRANSACTIONS RDB$SQL_REQUESTS
    RDB$MON$ATTACHMENTS RDB$MON$TRANSACTIONS RDB$MON$STATEMENTS""".split()
)


def completion_words(objects_by_profile, include_system=True):
    """Return a stable, case-insensitive completion list for loaded metadata."""
    words = set(FIREBIRD_RESERVED_WORDS) | set(FIREBIRD_TYPES)
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

