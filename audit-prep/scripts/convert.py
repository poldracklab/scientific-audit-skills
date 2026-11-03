# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Convert the paper and supplements, extract statements, and record Crossref metadata."""
import json
import shutil
from pathlib import Path
from typing import Callable

import crossref
import statements
from layout import STATEMENTS

import docs

NOT_APPLICABLE = {"text": "not_applicable", "pages": "not_applicable",
                  "structured": "not_applicable", "statements": "not_applicable"}
DONE = {"ok", "skipped"}  # `skipped` means an earlier run recorded the output as ok


def previous_conversions(manifest: dict) -> dict[str, dict]:
    """Conversion statuses of the manifest a rerun starts from, by document path."""
    docs_ = manifest.get("documents") or {}
    found = ([docs_["paper"]] if docs_.get("paper") else []) + list(docs_.get("supplements") or [])
    return {d["path"]: d.get("conversions") or {} for d in found}


def _attempt(action: Callable, label: str, m: dict) -> str:
    try:
        action()
    except Exception as e:  # a failed conversion is recorded, never raised
        m["warnings"].append(f"{label}: {e}")
        return "failed"
    return "ok"


def _present(path: Path) -> bool:
    return any(path.iterdir()) if path.is_dir() else path.exists()


def _clear(outputs: list[Path]) -> None:
    for path in outputs:
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()


def _convert(doc: dict, name: str, outputs: list[Path], action: Callable, ctx: tuple) -> None:
    """Keep an output an earlier run recorded as done; otherwise clear any partial output and convert."""
    m, prior = ctx
    if prior.get(name) in DONE and _present(outputs[0]):
        doc["conversions"][name] = "skipped"
        return
    _clear(outputs)
    doc["conversions"][name] = _attempt(action, f"{doc['path']} {name}", m)


def _structured(pdf: Path, out_dir: Path, run) -> None:
    result = docs.pdf_to_structured(pdf, out_dir, run=run)
    if result["status"] != "ok":
        raise RuntimeError(f"docling failed: {result['reason']}")


def _process_pdf(pdf: Path, work: Path, doc: dict, ctx: tuple, run) -> None:
    txt, pages = pdf.with_suffix(".txt"), work / "pages"
    _convert(doc, "text", [txt], lambda: docs.pdf_to_text(pdf, txt), ctx)
    _convert(doc, "pages", [pages], lambda: docs.pdf_to_pages(pdf, pages), ctx)
    structured = [work / f"{pdf.stem}.md", work / "figures", work / "tables"]
    _convert(doc, "structured", structured, lambda: _structured(pdf, work, run), ctx)
    doc["pages"] = len(list(pages.glob("p-*.png"))) or None


def _paper_statements(paper_dir: Path, doc: dict, m: dict) -> None:
    out = paper_dir / STATEMENTS

    def write():
        text = (paper_dir / "paper.txt").read_text(errors="replace")
        statements.write_statements_md(statements.extract_statements(text), out)

    label = f"{doc['path']} statements"
    doc["conversions"]["statements"] = "skipped" if out.exists() else _attempt(write, label, m)


def _process_supplement(prepared: Path, doc: dict, ctx: tuple, run) -> None:
    src = prepared / doc["path"]
    work, suffix = src.with_suffix(""), src.suffix.lower()
    doc["conversions"] = dict(NOT_APPLICABLE)
    if suffix == ".pdf":
        _process_pdf(src, work, doc, ctx, run)
    elif suffix == ".docx":
        md = src.with_suffix(".md")
        _convert(doc, "text", [md, work / "media"], lambda: docs.docx_to_md(src, md, work / "media"), ctx)
    elif suffix == ".xlsx":
        _convert(doc, "text", [work], lambda: docs.xlsx_to_csv(src, work), ctx)


def process_documents(prepared: Path, manifest: dict, run, previous: dict | None = None) -> None:
    """Convert every document; `previous` (from `previous_conversions`) says which outputs are done."""
    previous = previous or {}
    paper = manifest["documents"]["paper"]
    if paper:
        paper["conversions"] = dict(NOT_APPLICABLE)
        ctx = (manifest, previous.get(paper["path"], {}))
        _process_pdf(prepared / paper["path"], prepared / "paper", paper, ctx, run)
        _paper_statements(prepared / "paper", paper, manifest)
    for doc in manifest["documents"]["supplements"]:
        _process_supplement(prepared, doc, (manifest, previous.get(doc["path"], {})), run)


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
