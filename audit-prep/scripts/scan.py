# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml", "pymupdf"]
# ///
"""Scan a raw paper folder into a draft prep.yaml plan for review."""
from pathlib import Path
from typing import Callable

import pymupdf
import yaml

import crossref
import links

RESIDUE_NAMES = {".git", ".venv", ".pytest_cache", "__pycache__", ".DS_Store"}
SUPPLEMENT_MARKERS = ("supp", "_sm", "som", "mmc", "esm", "moesm", "supplement")
ARCHIVE_SUFFIXES = (".zip", ".tar", ".tar.gz", ".tgz", ".tar.zst", ".zst", ".7z")
DOI_PAGES = 2
SIZE_POLICY = {
    "max_file_mb": 500,
    "max_source_mb": 5000,
    "skip_ext": ["mp4", "mov", "avi", "wav", "mp3", "m4a"],
}
LINK_REVIEW_REASONS = {
    "osf": "osf project or registration?",
    "github": "paper's code or a cited tool?",
    "doi": "doi of unknown target: data, prereg, related paper or citation?",
    "other": "unrecognized host: data, code or citation?",
}


def _entry(path: str, role: str, reason: str, needs_review: bool = False) -> dict:
    return {"path": path, "role": role, "needs_review": needs_review, "reason": reason, "order": None}


def has_supplement_marker(name: str) -> bool:
    stem = Path(name).stem.lower()
    return any(marker in stem for marker in SUPPLEMENT_MARKERS)


def _marker_reason(name: str) -> str:
    stem = Path(name).stem.lower()
    return "name marker " + next(m for m in SUPPLEMENT_MARKERS if m in stem)


def pdf_info(pdf: Path) -> tuple[str | None, int]:
    """DOI found on the first pages, and the page count."""
    with pymupdf.open(pdf) as doc:
        text = "\n".join(doc[i].get_text() for i in range(min(DOI_PAGES, len(doc))))
        return links.find_doi(text), len(doc)


def _is_archive(name: str) -> bool:
    return name.lower().endswith(ARCHIVE_SUFFIXES)


def _is_residue(entry: Path) -> bool:
    if entry.name in RESIDUE_NAMES:
        return True
    return entry.suffix.lower() == ".txt" and entry.with_suffix(".pdf").exists()


def _classify_other(entry: Path) -> dict:
    if _is_residue(entry):
        return _entry(entry.name, "unsorted", "residue")
    if _is_archive(entry.name):
        return _entry(entry.name, "archive", "archive extension")
    if entry.is_dir():
        return _entry(entry.name, "data", "directory")
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


def _confirm_paper(paper: dict, doi: str | None, get_json: Callable[[str], dict]) -> None:
    if doi is None:
        paper.update(needs_review=True, reason="no doi found on first pages")
        return
    kind = crossref.fetch_metadata(doi, get_json)["type"]
    if kind == "journal-article":
        paper.update(needs_review=False, reason="DOI resolves to journal-article")
    else:
        paper.update(needs_review=True, reason=f"doi type is {kind}, not journal-article")


def _link_reason(link: links.Link) -> str:
    if link.needs_review:
        return LINK_REVIEW_REASONS.get(link.cls, "ambiguous link")
    return f"{link.cls} host implies {link.role}"


def _link_dict(link: links.Link, paper_doi: str | None) -> dict:
    entry = {
        "url": link.url, "canonical": link.canonical, "class": link.cls, "role": link.role,
        "needs_review": link.needs_review, "found_in": link.found_in, "reason": _link_reason(link),
    }
    if paper_doi and link.canonical == links.canonicalize(paper_doi):
        entry.update(role="skip", needs_review=False, reason="the paper's own doi")
    return entry


def _plan_links(raw: Path, files: list[dict], paper_doi: str | None) -> list[dict]:
    pdfs = [raw / f["path"] for f in files if f["path"].lower().endswith(".pdf")]
    found = [link for pdf in pdfs for link in links.extract_links_from_pdf(pdf)]
    return [_link_dict(link, paper_doi) for link in links.merge_links(found)]


def _paper_doi(raw: Path, files: list[dict], get_json) -> str | None:
    paper = next((f for f in files if f["role"] == "paper"), None)
    if paper is None:
        return None
    doi = pdf_info(raw / paper["path"])[0]
    _confirm_paper(paper, doi, get_json)
    return doi


def build_plan(raw: Path, get_json: Callable[[str], dict]) -> dict:
    files = classify_files(raw)
    doi = _paper_doi(raw, files, get_json)
    return {
        "schema_version": 1,
        "paper_id": raw.name,
        "reviewed_by": None,
        "doi": doi,
        "data_collection": {"start": None, "end": None, "source_quote": None, "page": None},
        "size_policy": {**SIZE_POLICY, "skip_ext": list(SIZE_POLICY["skip_ext"])},
        "files": files,
        "links": _plan_links(raw, files, doi),
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
