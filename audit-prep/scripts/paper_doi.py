# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Choose the paper's own DOI among the candidates on its first pages, confirmed via Crossref."""
import urllib.error
from dataclasses import dataclass
from typing import Callable

import crossref

JOURNAL_ARTICLE = "journal-article"


@dataclass
class DoiChoice:
    doi: str | None
    confirmed: bool
    reason: str


def _crossref_type(doi: str, get_json: Callable[[str], dict]) -> str:
    """The Crossref work type; a 404 means the DOI is not a Crossref work (e.g. a DataCite deposit)."""
    try:
        return crossref.fetch_metadata(doi, get_json)["type"] or "no type"
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return "not in Crossref"
        raise


def _unconfirmed(tried: list[str], failure: tuple[str, Exception] | None) -> DoiChoice:
    if failure:
        return DoiChoice(failure[0], False, f"crossref lookup failed: {failure[1]}")
    return DoiChoice(None, False, "no doi on first pages resolves to journal-article: " + ", ".join(tried))


def choose_paper_doi(dois: list[str], get_json: Callable[[str], dict]) -> DoiChoice:
    """First candidate Crossref types as journal-article; else None (or, on a lookup failure, the first
    candidate that could not be checked, unconfirmed)."""
    if not dois:
        return DoiChoice(None, False, "no doi found on first pages")
    tried, failure = [], None
    for doi in dois:
        try:
            kind = _crossref_type(doi, get_json)
        except (OSError, ValueError) as err:
            failure = failure or (doi, err)
            continue
        if kind == JOURNAL_ARTICLE:
            return DoiChoice(doi, True, "DOI resolves to journal-article")
        tried.append(f"{doi} ({kind})")
    return _unconfirmed(tried, failure)
