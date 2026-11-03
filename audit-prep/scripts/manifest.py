# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Manifest schema v1: creation, tree hashing, persistence and README rendering."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
MANIFEST_NAME = "manifest.json"
DEFAULT_EXCLUDE = ("manifest.json", "README.md")
OS_METADATA = frozenset({".DS_Store", "Icon\r", ".dropbox", ".dropbox.cache"})


def new_manifest(paper_id: str, prepared_by: str) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "paper_id": paper_id,
        "prepared_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "prep_versions": {},
        "prepared_by": prepared_by,
        "finalized": False,
        "metadata": None,
        "documents": {"paper": None, "supplements": []},
        "links": [],
        "preregistration": [],
        "data_collection": None,
        "code": [],
        "data": [],
        "local_data": [],
        "unsorted": [],
        "files": [],
        "warnings": [],
        "review": None,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_excluded(rel: Path, exclude: tuple[str, ...]) -> bool:
    return len(rel.parts) == 1 and rel.name in exclude


def is_os_metadata(rel: Path) -> bool:
    """Finder or Dropbox bookkeeping (.DS_Store, Icon\\r, .dropbox, .dropbox.cache) at any depth."""
    return any(part in OS_METADATA for part in rel.parts)


def hash_tree(root: Path, exclude: tuple[str, ...] = DEFAULT_EXCLUDE, prune: tuple[str, ...] = ()) -> list[dict]:
    entries = []
    for p in root.rglob("*"):
        rel = p.relative_to(root)
        if rel.parts[0] in prune or is_os_metadata(rel):
            continue
        if p.is_symlink() or not p.is_file() or _is_excluded(rel, exclude):
            continue
        entries.append({"path": rel.as_posix(), "size": p.stat().st_size, "sha256": _sha256(p)})
    return sorted(entries, key=lambda e: e["path"])


def write_manifest(prepared: Path, m: dict) -> Path:
    out = Path(prepared) / MANIFEST_NAME
    out.write_text(json.dumps(m, indent=2, sort_keys=False, ensure_ascii=False), encoding="utf-8")
    return out


def load_manifest(folder: Path) -> dict | None:
    try:
        data = json.loads((Path(folder) / MANIFEST_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def is_prepared(folder: Path) -> bool:
    m = load_manifest(folder)
    return bool(m) and m.get("schema_version") == SCHEMA_VERSION and m.get("finalized") is True


def _cell(value) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _table(headers: list[str], rows: list[list]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(_cell(c) for c in row) + " |" for row in rows]
    return lines


def _section(title: str, body: list[str], empty: str) -> list[str]:
    return [f"## {title}", ""] + (body or [empty]) + [""]


def _header(m: dict) -> list[str]:
    meta = m.get("metadata")
    lines = [f"# {m['paper_id']}", ""]
    if meta:
        lines += [f"- Title: {meta.get('title') or 'unknown'}", f"- DOI: {meta.get('doi') or 'unknown'}",
                  f"- Journal: {meta.get('journal') or 'unknown'}", f"- Published: {meta.get('published') or 'unknown'}"]
    else:
        lines.append("- metadata: not fetched")
    versions = ", ".join(f"{k} {v}" for k, v in (m.get("prep_versions") or {}).items()) or "not recorded"
    lines += [f"- Prepared by: {m.get('prepared_by')}", f"- Prepared at: {m.get('prepared_at')}",
              f"- Tool versions: {versions}", ""]
    return lines


def _doc_row(role: str, doc: dict) -> list:
    conv = ", ".join(f"{k}={v}" for k, v in (doc.get("conversions") or {}).items())
    return [role, doc.get("path"), doc.get("pages"), conv]


def _documents(m: dict) -> list[str]:
    docs = m.get("documents") or {}
    rows = [_doc_row("paper", docs["paper"])] if docs.get("paper") else []
    rows += [_doc_row("supplement", d) for d in docs.get("supplements") or []]
    body = _table(["Role", "File", "Pages", "Conversions"], rows) if rows else []
    return _section("Documents", body, "none")


def _preregistration(m: dict) -> list[str]:
    rows = [[p.get("source"), p.get("id"), p.get("date_registered"), p.get("status")]
            for p in m.get("preregistration") or []]
    body = _table(["Source", "ID", "Date registered", "Status"], rows) if rows else []
    return _section("Preregistration", body, "none found")


def _code(m: dict) -> list[str]:
    rows = [[c.get("url"), c.get("commit"), c.get("status")] for c in m.get("code") or []]
    body = _table(["URL", "Commit", "Status"], rows) if rows else []
    return _section("Code", body, "none found")


def _counts(files: list[dict]) -> str:
    done = sum(1 for f in files if f.get("downloaded"))
    return f"{done} of {len(files)}"


def _data(m: dict) -> list[str]:
    rows = [[d.get("source"), d.get("id"), d.get("status"), _counts(d.get("files") or []), d.get("reason")]
            for d in m.get("data") or []]
    body = _table(["Source", "ID", "Status", "Downloaded", "Reason"], rows) if rows else []
    return _section("Data", body, "none found")


def _local_data(m: dict) -> list[str]:
    rows = [[d.get("original_path"), d.get("path"), d.get("extracted", "")] for d in m.get("local_data") or []]
    body = _table(["Original", "Path", "Extracted"], rows) if rows else []
    return _section("Local data", body, "none")


def _unsorted(m: dict) -> list[str]:
    rows = [[u.get("original_path"), u.get("moved_to"), u.get("reason")] for u in m.get("unsorted") or []]
    body = _table(["Original", "Moved to", "Reason"], rows) if rows else []
    return _section("Unsorted", body, "none")


def _data_collection(m: dict) -> list[str]:
    dc = m.get("data_collection")
    if not dc:
        return _section("Data collection", [], "not recorded")
    body = [f"- Start: {dc.get('start')}", f"- End: {dc.get('end')}",
            f"- Quote: {dc.get('source_quote')} (page {dc.get('page')})"]
    return _section("Data collection", body, "not recorded")


def _review_body(review: dict) -> list[str]:
    ok = review.get("status") == "ok"
    rows = [[a.get("item"), a.get("status"), a.get("detail"), a.get("accepted_reason")]
            for a in review.get("accepted") or []]
    body = [f"- Status: {'ok' if ok else 'FAILED'}", ""]
    body += _table(["Item", "Status", "Detail", "Accepted because"], rows) if rows else ["no accepted failures"]
    if not ok:
        open_rows = [[p.get("item"), p.get("status"), p.get("detail")] for p in review.get("problems") or []]
        body += [""] + _table(["Item", "Status", "Detail"], open_rows)
    return body


def _prep_review(m: dict) -> list[str]:
    review = m.get("review")
    return _section("Prep review", _review_body(review) if review else [], "not run")


def _warnings(m: dict) -> list[str]:
    return _section("Warnings", [f"- {w}" for w in m.get("warnings") or []], "none")


def render_readme(m: dict) -> str:
    parts = [_header(m), _documents(m), _preregistration(m), _code(m), _data(m),
             _local_data(m), _unsorted(m), _data_collection(m), _prep_review(m), _warnings(m)]
    return "\n".join(line for part in parts for line in part).rstrip() + "\n"
