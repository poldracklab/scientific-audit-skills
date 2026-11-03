# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""List and download Zenodo record files, recording version and concept DOIs."""
import re
from pathlib import Path

from fetch_common import FetchResult, RemoteFile, SizePolicy, file_records, select_downloads

API = "https://zenodo.org/api/records"
ZENODO_ID_RE = re.compile(r"(?:zenodo\.org/records?/|10\.5281/zenodo\.)(\d+)", re.I)
NO_FILES = "no files listed (restricted?)"


def zenodo_id(canonical: str) -> str | None:
    m = ZENODO_ID_RE.search(canonical)
    return m.group(1) if m else None


def _remote_file(entry: dict) -> RemoteFile:
    return RemoteFile(entry["key"], entry.get("size") or 0, entry["links"]["self"], entry.get("checksum"))


def record_meta(record: dict) -> dict:
    """Version DOI, concept DOI and title; None when the record lacks them."""
    meta = record.get("metadata") or {}
    concept = record.get("conceptdoi")
    if not concept and record.get("conceptrecid"):
        concept = f"10.5281/zenodo.{record['conceptrecid']}"
    return {"version_doi": meta.get("doi") or record.get("doi"), "concept_doi": concept, "title": meta.get("title")}


def fetch_zenodo(zid: str, dest: Path, policy: SizePolicy, get_json, get_bytes) -> FetchResult:
    try:
        record = get_json(f"{API}/{zid}")
        meta = record_meta(record)
        if not record.get("files"):
            return FetchResult("zenodo", zid, str(dest), "failed", [], NO_FILES, meta)
        files = [_remote_file(e) for e in record["files"]]
    except Exception as e:  # any API error is recorded, never raised
        return FetchResult("zenodo", zid, str(dest), "failed", [], str(e))
    selected, status = select_downloads(files, policy)
    return FetchResult("zenodo", zid, str(dest), status, file_records(files, selected, dest, get_bytes), meta=meta)
