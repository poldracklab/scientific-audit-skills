# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Convert the paper and supplements, extract statements, and record Crossref metadata."""
import json
from pathlib import Path
from typing import Callable

import crossref
import statements
from layout import STATEMENTS

import docs

NOT_APPLICABLE = {"text": "not_applicable", "pages": "not_applicable",
                  "structured": "not_applicable", "statements": "not_applicable"}


def _step(done: bool, action: Callable, label: str, m: dict) -> str:
    if done:
        return "skipped"
    try:
        action()
    except Exception as e:  # a failed conversion is recorded, never raised
        m["warnings"].append(f"{label}: {e}")
        return "failed"
    return "ok"


def _structured(pdf: Path, out_dir: Path, run) -> None:
    result = docs.pdf_to_structured(pdf, out_dir, run=run)
    if result["status"] != "ok":
        raise RuntimeError(f"docling failed: {result['reason']}")


def _process_pdf(pdf: Path, work: Path, doc: dict, m: dict, run) -> None:
    txt, pages = pdf.with_suffix(".txt"), work / "pages"
    conv = doc["conversions"]
    conv["text"] = _step(txt.exists(), lambda: docs.pdf_to_text(pdf, txt), f"{doc['path']} text", m)
    conv["pages"] = _step(any(pages.glob("p-*.png")), lambda: docs.pdf_to_pages(pdf, pages),
                          f"{doc['path']} pages", m)
    conv["structured"] = _step((work / f"{pdf.stem}.md").exists(), lambda: _structured(pdf, work, run),
                               f"{doc['path']} structured", m)
    doc["pages"] = len(list(pages.glob("p-*.png"))) or None


def _paper_statements(paper_dir: Path, doc: dict, m: dict) -> None:
    out = paper_dir / STATEMENTS

    def write():
        text = (paper_dir / "paper.txt").read_text(errors="replace")
        statements.write_statements_md(statements.extract_statements(text), out)

    doc["conversions"]["statements"] = _step(out.exists(), write, f"{doc['path']} statements", m)


def _process_supplement(prepared: Path, doc: dict, m: dict, run) -> None:
    src = prepared / doc["path"]
    work, suffix = src.with_suffix(""), src.suffix.lower()
    doc["conversions"] = dict(NOT_APPLICABLE)
    label = f"{doc['path']} text"
    if suffix == ".pdf":
        _process_pdf(src, work, doc, m, run)
    elif suffix == ".docx":
        md = src.with_suffix(".md")
        doc["conversions"]["text"] = _step(md.exists(), lambda: docs.docx_to_md(src, md, work / "media"), label, m)
    elif suffix == ".xlsx":
        doc["conversions"]["text"] = _step(any(work.glob("*.csv")), lambda: docs.xlsx_to_csv(src, work), label, m)


def process_documents(prepared: Path, manifest: dict, run) -> None:
    paper = manifest["documents"]["paper"]
    if paper:
        paper["conversions"] = dict(NOT_APPLICABLE)
        _process_pdf(prepared / paper["path"], prepared / "paper", paper, manifest, run)
        _paper_statements(prepared / "paper", paper, manifest)
    for doc in manifest["documents"]["supplements"]:
        _process_supplement(prepared, doc, manifest, run)


def record_metadata(prepared: Path, plan: dict, manifest: dict, get_json: Callable) -> None:
    meta, doi = None, plan.get("doi")
    try:
        meta = crossref.fetch_metadata(doi, get_json) if doi else None
    except Exception as e:  # metadata is optional; record why it is missing
        manifest["warnings"].append(f"crossref metadata for {doi} unavailable: {e}")
    if doi is None:
        manifest["warnings"].append("no doi in prep.yaml; crossref metadata not fetched")
    manifest["metadata"] = meta
    out = prepared / "paper" / "metadata.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(meta or {}, indent=2, ensure_ascii=False))
