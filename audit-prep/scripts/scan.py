# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml", "pymupdf"]
# ///
"""Scan a raw paper folder into a draft prep.yaml plan for review."""
import re
from pathlib import Path
from typing import Callable

import pymupdf
import yaml

import links
import residue
from paper_doi import DoiChoice, choose_paper_doi

SUPPLEMENT_MARKERS = ("supp", "_sm", "som", "mmc", "esm", "moesm", "supplement")
TOKEN_SPLIT = re.compile(r"[-_.\s]+")
ARCHIVE_SUFFIXES = (".zip", ".tar", ".tar.gz", ".tgz", ".tar.zst", ".zst", ".7z")
DOI_PAGES = 2
SIZE_POLICY = {
    "max_file_mb": 500,
    "max_source_mb": 5000,
    "skip_ext": ["mp4", "mov", "avi", "wav", "mp3", "m4a"],
}
BARE_HOST_REASON = "bare host, no identifier (likely a line-wrapped URL)"
LINK_REVIEW_REASONS = {
    "osf": "osf project or registration?",
    "github": "paper's code or a cited tool?",
    "doi": "doi of unknown target: data, prereg, related paper or citation?",
    "other": "unrecognized host: data, code or citation?",
}


def _entry(path: str, role: str, reason: str, needs_review: bool = False) -> dict:
    return {"path": path, "role": role, "needs_review": needs_review, "reason": reason, "order": None}


def _token_matches(token: str, marker: str) -> bool:
    """A token is a marker, a marker plus digits (mmc1), or a supp* word (supplementary)."""
    bare = marker.lstrip("_")
    return bool(re.fullmatch(re.escape(bare) + r"\d*", token)) or (bare == "supp" and token.startswith(bare))


def _matching_marker(name: str) -> str | None:
    tokens = TOKEN_SPLIT.split(Path(name).stem.lower())
    return next((m for m in SUPPLEMENT_MARKERS for t in tokens if _token_matches(t, m)), None)


def has_supplement_marker(name: str) -> bool:
    return _matching_marker(name) is not None


def _marker_reason(name: str) -> str:
    return "name marker " + _matching_marker(name)


def _first_pages(pdf: Path) -> tuple[str, int]:
    with pymupdf.open(pdf) as doc:
        return "\n".join(doc[i].get_text() for i in range(min(DOI_PAGES, len(doc)))), len(doc)


def pdf_info(pdf: Path) -> tuple[str | None, int]:
    """First non-deposit DOI found on the first pages, and the page count."""
    text, pages = _first_pages(pdf)
    return links.find_doi(text), pages


def _is_archive(name: str) -> bool:
    return name.lower().endswith(ARCHIVE_SUFFIXES)


def _is_residue(entry: Path) -> bool:
    if residue.is_residue_name(entry.name):
        return True
    return entry.suffix.lower() == ".txt" and entry.with_suffix(".pdf").exists()


def _classify_dir(entry: Path) -> dict:
    if residue.is_data_only_dir(entry):
        return _entry(entry.name, "data", "directory of data files")
    return _entry(entry.name, "data", "directory: data or residue?", True)


def _classify_other(entry: Path) -> dict:
    if _is_residue(entry):
        return _entry(entry.name, "unsorted", "residue")
    if _is_archive(entry.name):
        return _entry(entry.name, "archive", "archive extension")
    if entry.is_dir():
        return _classify_dir(entry)
    if has_supplement_marker(entry.name):
        return _entry(entry.name, "supplement", _marker_reason(entry.name))
    return _entry(entry.name, "data", "unrecognized file; data or residue?", True)


def _pick_paper(candidates: list[tuple[Path, str | None, int]]):
    """Longest PDF with a DOI, else longest PDF without one."""
    with_doi = [c for c in candidates if c[1]]
    pool = with_doi or candidates
    return max(pool, key=lambda c: (c[2], c[0].name)) if pool else None


def _candidate_entry(cand, paper) -> dict:
    pdf, doi, _ = cand
    if cand is paper and doi:
        return _entry(pdf.name, "paper", f"doi {doi} on first pages")
    if cand is paper:
        return _entry(pdf.name, "paper", "no doi found; only paper candidate", True)
    if doi and doi == paper[1]:
        return _entry(pdf.name, "supplement", "same doi as paper")
    return _entry(pdf.name, "supplement", "second pdf without marker; supplement or other paper?", True)


def _classify_pdfs(pdfs: list[Path]) -> list[dict]:
    marked = [_entry(p.name, "supplement", _marker_reason(p.name)) for p in pdfs if has_supplement_marker(p.name)]
    candidates = [(p, *pdf_info(p)) for p in pdfs if not has_supplement_marker(p.name)]
    paper = _pick_paper(candidates)
    return marked + [_candidate_entry(c, paper) for c in candidates]


def _number_supplements(entries: list[dict]) -> None:
    supplements = sorted((e for e in entries if e["role"] == "supplement"), key=lambda e: e["path"])
    for order, entry in enumerate(supplements, start=1):
        entry["order"] = order


def _is_pdf(entry: Path) -> bool:
    return entry.is_file() and entry.suffix.lower() == ".pdf"


def classify_files(raw: Path) -> list[dict]:
    entries = sorted(raw.iterdir())
    pdfs = [e for e in entries if _is_pdf(e)]
    classified = _classify_pdfs(pdfs) + [_classify_other(e) for e in entries if not _is_pdf(e)]
    _number_supplements(classified)
    return sorted(classified, key=lambda e: e["path"])


def _link_reason(link: links.Link) -> str:
    if links.is_bare_host(link.canonical):
        return BARE_HOST_REASON
    if link.needs_review:
        return LINK_REVIEW_REASONS.get(link.cls, "ambiguous link")
    return f"{link.cls} host implies {link.role}"


def _link_dict(link: links.Link, paper_doi: str | None, confirmed: bool = True) -> dict:
    """`paper_doi` is pre-set to skip only once Crossref confirmed it as a journal-article."""
    entry = {
        "url": link.url, "canonical": link.canonical, "class": link.cls, "role": link.role,
        "needs_review": link.needs_review, "found_in": link.found_in, "reason": _link_reason(link),
    }
    if paper_doi and link.canonical == links.canonicalize(paper_doi):
        if confirmed:
            entry.update(role="skip", needs_review=False, reason="the paper's own doi")
        else:
            entry.update(needs_review=True, reason="may be the paper's own doi; Crossref did not confirm it")
    return entry


def _plan_links(raw: Path, files: list[dict], choice: DoiChoice) -> list[dict]:
    pdfs = [raw / f["path"] for f in files if f["path"].lower().endswith(".pdf")]
    found = [link for pdf in pdfs for link in links.extract_links_from_pdf(pdf)]
    return [_link_dict(link, choice.doi, choice.confirmed) for link in links.merge_links(found)]


def _paper_doi(raw: Path, files: list[dict], get_json) -> DoiChoice:
    paper = next((f for f in files if f["role"] == "paper"), None)
    if paper is None:
        return DoiChoice(None, False, "no paper")
    choice = choose_paper_doi(links.find_dois(_first_pages(raw / paper["path"])[0]), get_json)
    paper.update(needs_review=not choice.confirmed, reason=choice.reason)
    return choice


def build_plan(raw: Path, get_json: Callable[[str], dict]) -> dict:
    files = classify_files(raw)
    choice = _paper_doi(raw, files, get_json)
    return {
        "schema_version": 1,
        "paper_id": raw.name,
        "reviewed_by": None,
        "doi": choice.doi,
        "data_collection": {"start": None, "end": None, "source_quote": None, "page": None},
        "size_policy": {**SIZE_POLICY, "skip_ext": list(SIZE_POLICY["skip_ext"])},
        "files": files,
        "links": _plan_links(raw, files, choice),
    }


def write_plan(plan: dict, path: Path) -> Path:
    path.write_text(yaml.safe_dump(plan, sort_keys=False, allow_unicode=True))
    return path


def load_plan(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def _pending(items: list[dict], key: str) -> list[str]:
    return [f"{item[key]}: needs_review" for item in items if item.get("needs_review")]


def unresolved(plan: dict) -> list[str]:
    msgs = [] if plan.get("reviewed_by") else ["reviewed_by is not set"]
    msgs += _pending(plan.get("files", []), "path") + _pending(plan.get("links", []), "url")
    if not any(f.get("role") == "paper" for f in plan.get("files", [])):
        msgs.append("no file with role paper")
    return msgs
