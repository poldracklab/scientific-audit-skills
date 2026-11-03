# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Fetch and normalise Crossref work metadata."""
from typing import Callable

from fetch_common import default_get_json

API = "https://api.crossref.org/works/"


def _first(values) -> str:
    return values[0] if values else ""


def _authors(message: dict) -> list[dict]:
    return [
        {"family": a.get("family", ""), "given": a.get("given", "")}
        for a in message.get("author", [])
    ]


def _published(message: dict) -> str | None:
    parts = (message.get("issued", {}).get("date-parts") or [[]])[0]
    if not parts or parts[0] is None:
        return None
    y, m, d = (list(parts) + [1, 1])[:3]
    return f"{y:04d}-{m:02d}-{d:02d}"


def _relations(message: dict) -> list[dict]:
    return [
        {"type": rel_type, "doi": entry["id"]}
        for rel_type, entries in message.get("relation", {}).items()
        for entry in entries
        if entry.get("id-type") == "doi"
    ]


def fetch_metadata(doi: str, get_json: Callable[[str], dict]) -> dict:
    message = get_json(API + doi).get("message", {})
    return {
        "doi": doi,
        "title": _first(message.get("title")),
        "authors": _authors(message),
        "journal": _first(message.get("container-title")),
        "published": _published(message),
        "type": message.get("type"),
        "relations": _relations(message),
        "url": message.get("URL"),
    }
