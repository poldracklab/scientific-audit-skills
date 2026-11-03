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
    kind: re.compile(rf"^\s*(?:{pat})\s*(?:[:.]\s*(?P<rest>.*?))?\s*$", re.IGNORECASE)
    for kind, pat in HEADINGS.items()
}


@dataclass
class Statement:
    kind: str
    heading: str
    text: str
    page: int


def match_heading(line: str) -> tuple[str, str] | None:
    """Return (kind, inline text) if the line is a heading, bare or run-in."""
    for kind, regex in HEADING_RES.items():
        m = regex.match(line)
        if m:
            return kind, m.group("rest") or ""
    return None


def page_lines(text: str) -> list[tuple[int, str]]:
    """Split into (page, text) pieces; blank physical lines have text ''.

    A form feed is transparent: it only advances the page number.
    """
    out, page = [], 1
    for line in text.split("\n"):
        segments = line.split("\f")
        if len(segments) == 1 and not line.strip():
            out.append((page, ""))
        for i, seg in enumerate(segments):
            page += i > 0
            if seg.strip():
                out.append((page, seg.strip()))
    return out


def _statement_text(pieces: list[tuple[int, str]], start: int, inline: str) -> str:
    body = [inline] if inline else []
    for _, line in pieces[start:]:
        if not line or match_heading(line):
            break
        body.append(line)
    return " ".join(body)[:MAX_CHARS]


def extract_statements(text: str) -> list[Statement]:
    pieces = page_lines(text)
    found = []
    for i, (page, line) in enumerate(pieces):
        hit = match_heading(line)
        if hit:
            kind, inline = hit
            heading = line[: len(line) - len(inline)].strip() if inline else line
            found.append(Statement(kind, heading, _statement_text(pieces, i + 1, inline), page))
    return found


def _section(stmt: Statement) -> str:
    title = stmt.kind.replace("_", " ").capitalize()
    return f"## {title} (p. {stmt.page})\n\n{stmt.text}\n"


def write_statements_md(statements: list[Statement], out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(_section(s) for s in statements))
    return out
