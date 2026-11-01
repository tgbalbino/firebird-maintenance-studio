"""Split an ISQL-style script into the pieces the editor can run.

The server only understands one DSQL statement per call.  Scripts written for
isql also carry client commands (SET TERM, COMMIT, QUIT ...) and use `;` both
as statement end and inside EXECUTE BLOCK / procedure bodies, which is why
SET TERM exists.  This module follows the same rules isql does.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_ISQL_SET = re.compile(
    r"^SET\s+(?:AUTODDL|ECHO|LIST|STATS|BAIL|COUNT|WARNINGS|WIDTH|BLOBDISPLAY|NAMES|SQL\s+DIALECT|PLANONLY|PLAN)\b",
    re.IGNORECASE,
)
_SET_TERM = re.compile(r"^SET\s+TERM\s+(\S+?)\s*;?$", re.IGNORECASE)
_COMMIT = re.compile(r"^COMMIT(?:\s+(?:WORK|RETAIN|SNAPSHOT|TRANSACTION))*$", re.IGNORECASE)
_ROLLBACK = re.compile(r"^ROLLBACK(?:\s+(?:WORK|RETAIN|SNAPSHOT|TRANSACTION))*$", re.IGNORECASE)
_QUIT = re.compile(r"^(?:QUIT|EXIT)$", re.IGNORECASE)


@dataclass(slots=True)
class ScriptItem:
    kind: str  # sql | commit | rollback | set_term | ignore | quit
    text: str


def _without_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    return re.sub(r"--[^\r\n]*", " ", text).strip()


def _classify(piece: str, terminator: str) -> tuple[ScriptItem | None, str]:
    """Return the item for one terminated piece and the terminator to use next."""
    bare = _without_comments(piece)
    if not bare:
        return None, terminator
    match = _SET_TERM.match(bare)
    if match:
        return ScriptItem("set_term", bare), match.group(1)
    if _QUIT.match(bare):
        return ScriptItem("quit", bare), terminator
    if _COMMIT.match(bare):
        return ScriptItem("commit", bare), terminator
    if _ROLLBACK.match(bare):
        return ScriptItem("rollback", bare), terminator
    if _ISQL_SET.match(bare):
        return ScriptItem("ignore", bare), terminator
    return ScriptItem("sql", piece.strip()), terminator


def split_script(text: str) -> list[ScriptItem]:
    items: list[ScriptItem] = []
    terminator = ";"
    start = 0
    position = 0
    length = len(text)
    while position < length:
        char = text[position]
        if char == "'" or char == '"':
            position += 1
            while position < length:
                if text[position] == char:
                    if text[position + 1:position + 2] == char:  # doubled quote
                        position += 2
                        continue
                    break
                position += 1
            position += 1
        elif text.startswith("--", position):
            end = text.find("\n", position)
            position = length if end < 0 else end + 1
        elif text.startswith("/*", position):
            end = text.find("*/", position + 2)
            position = length if end < 0 else end + 2
        elif text.startswith(terminator, position):
            closing = terminator
            item, terminator = _classify(text[start:position], terminator)
            position += len(closing)  # the old terminator ends this command
            start = position
            if item is not None:
                items.append(item)
                if item.kind == "quit":
                    return items
        else:
            position += 1
    item, _ = _classify(text[start:], terminator)
    if item is not None:
        items.append(item)
    return items


def is_script(text: str) -> bool:
    """True when `text` needs the script runner rather than a single DSQL call."""
    items = split_script(text)
    return len(items) > 1 or any(item.kind != "sql" for item in items)
