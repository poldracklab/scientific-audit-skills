# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Extract verbatim availability, preregistration and funding statements."""

import re
from dataclasses import dataclass
from pathlib import Path

MAX_CHARS = 2000
HEADINGS = {
    "data_availability": r"data (?:and code )?availability",
    "code_availability": r"code availability",
    "preregistration": r"pre-?registration",
    "funding": r"funding",
    "open_practices": r"open practices(?: statement)?",
}
HEADING_RES = {
    kind: re.compile(rf"^\s*{pat}\s*[:.]?\s*$", re.IGNORECASE) for kind, pat in HEADINGS.items()
}


@dataclass
class Statement:
    kind: str
    heading: str
    text: str
    page: int


def heading_kind(line: str) -> str | None:
    clean = line.replace("\f", "")
    for kind, regex in HEADING_RES.items():
        if regex.match(clean):
            return kind
    return None


def _statement_text(lines: list[str], start: int) -> str:
    body = []
    for line in lines[start:]:
        if not line.replace("\f", "").strip() or heading_kind(line):
            break
        body.append(line.strip())
    return " ".join(body)[:MAX_CHARS]


def extract_statements(text: str) -> list[Statement]:
    lines = text.replace("\f", "\n\f").split("\n")
    found, page = [], 1
    for i, line in enumerate(lines):
        page += line.count("\f")
        kind = heading_kind(line)
        if kind:
            heading = line.replace("\f", "").strip()
            found.append(Statement(kind, heading, _statement_text(lines, i + 1), page))
    return found


def _section(stmt: Statement) -> str:
    title = stmt.kind.replace("_", " ").capitalize()
    return f"## {title} (p. {stmt.page})\n\n{stmt.text}\n"


def write_statements_md(statements: list[Statement], out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(_section(s) for s in statements))
    return out
