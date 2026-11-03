# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Fetch an OpenNeuro snapshot's metadata, full file listing and root-level files; never imaging files."""
import json
import re
from pathlib import Path

from fetch_common import FetchResult, RemoteFile, SizePolicy, download_one, file_record, sha256_file

GRAPHQL = "https://openneuro.org/crn/graphql"
FILES_URL = "https://openneuro.org/crn/datasets/{ds}/snapshots/{tag}/files/{name}"
DATASET_QUERY = "query($id: ID!) { dataset(id: $id) { id name created public latestSnapshot { tag } } }"
SNAPSHOT_QUERY = (
    "query($id: ID!, $tag: String!) { snapshot(datasetId: $id, tag: $tag) { id tag created hexsha size readme "
    "description { Name BIDSVersion License Authors SeniorAuthor Acknowledgements HowToAcknowledge Funding "
    "ReferencesAndLinks DatasetDOI DatasetType EthicsApprovals } "
    "summary { modalities primaryModality secondaryModalities sessions subjects tasks size totalFiles dataProcessed } "
    "files(recursive: true) { id filename size directory annexed urls } } }"
)
NOT_FOUND = "dataset not found"
NO_SNAPSHOT = "dataset has no snapshot"
RESERVED = {"dataset.json", "files.json"}
RESERVED_REASON = "name reserved for prep metadata"
OPENNEURO_ID_RE = re.compile(r"(?:openneuro\.org/datasets/|10\.18112/openneuro\.)(ds\d{6})", re.I)
TAG_RE = re.compile(r"openneuro\.org/datasets/ds\d{6}/versions/([^/?#\s]+)"
                    r"|10\.18112/openneuro\.ds\d{6}\.v([^/?#\s]+)", re.I)


class GraphQLError(Exception):
    """An OpenNeuro GraphQL response carried errors or no requested node."""


def openneuro_id(canonical: str) -> str | None:
    m = OPENNEURO_ID_RE.search(canonical)
    return m.group(1).lower() if m else None


def openneuro_tag(canonical: str) -> str | None:
    m = TAG_RE.search(canonical)
    return (m.group(1) or m.group(2)) if m else None


def normalize_path(filename: str) -> str:
    """OpenNeuro lists nested files as `a:b:c`; use `/` unless the name already does."""
    return filename if "/" in filename else filename.replace(":", "/")


def file_url(ds: str, tag: str, entry: dict) -> str:
    if entry.get("urls"):
        return entry["urls"][0]
    return FILES_URL.format(ds=ds, tag=tag, name=normalize_path(entry["filename"]).replace("/", ":"))


def _query(post_json, query: str, variables: dict, key: str) -> dict:
    resp = post_json(GRAPHQL, {"query": query, "variables": variables})
    if resp.get("errors"):
        raise GraphQLError(resp["errors"][0].get("message") or NOT_FOUND)
    node = (resp.get("data") or {}).get(key)
    if node is None:
        raise GraphQLError(NOT_FOUND)
    return node


def _resolve(ds: str, tag: str | None, post_json) -> tuple[dict | None, dict]:
    """The dataset node (only when the latest tag had to be looked up) and the snapshot node."""
    dataset = None
    if tag is None:
        dataset = _query(post_json, DATASET_QUERY, {"id": ds}, "dataset")
        tag = (dataset.get("latestSnapshot") or {}).get("tag")
        if not tag:
            raise GraphQLError(NO_SNAPSHOT)
    return dataset, _query(post_json, SNAPSHOT_QUERY, {"id": ds, "tag": tag}, "snapshot")


def _pick(node: dict | None, keys: tuple[str, ...]) -> dict | None:
    return None if node is None else {k: node.get(k) for k in keys}


def _dataset_json(dataset: dict | None, snapshot: dict) -> dict:
    description = snapshot.get("description") or {}
    return {"scope": "metadata", "dataset": _pick(dataset, ("id", "name", "created", "public")),
            "snapshot": _pick(snapshot, ("id", "tag", "created", "hexsha", "size")),
            "description": snapshot.get("description"), "summary": snapshot.get("summary"),
            "dataset_doi": description.get("DatasetDOI")}


def _listing(ds: str, snapshot: dict) -> list[dict]:
    return [{"path": normalize_path(e["filename"]), "size": e.get("size") or 0, "directory": bool(e.get("directory")),
             "annexed": bool(e.get("annexed")), "url": file_url(ds, snapshot["tag"], e)}
            for e in snapshot.get("files") or []]


def _write_metadata(dest: Path, dataset: dict | None, snapshot: dict, listing: list[dict]) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "dataset.json").write_text(json.dumps(_dataset_json(dataset, snapshot), indent=2))
    if snapshot.get("readme") is not None:
        (dest / "README").write_text(snapshot["readme"])
    (dest / "files.json").write_text(json.dumps(listing, indent=2))


def _root_files(listing: list[dict]) -> list[RemoteFile]:
    return [RemoteFile(e["path"], e["size"], e["url"]) for e in listing if not e["directory"] and "/" not in e["path"]]


def _written_names(snapshot: dict) -> set[str]:
    """Root files already written from the snapshot metadata (the README text is the README file)."""
    return {"README"} if snapshot.get("readme") is not None else set()


def _root_record(f: RemoteFile, dest: Path, policy: SizePolicy, get_bytes, written: set[str]) -> dict:
    if f.path in RESERVED:
        return file_record(f, reason=RESERVED_REASON)
    if f.path in written:
        return file_record(f, sha256_file(dest / f.path))
    return download_one(f, dest, get_bytes) if policy.allows(f) else file_record(f)


def _download_roots(listing: list[dict], dest: Path, policy: SizePolicy, get_bytes, written: set[str]) -> list[dict]:
    """Root-level files in listing order; a skipped or failed file is recorded `downloaded: False`."""
    return [_root_record(f, dest, policy, get_bytes, written) for f in _root_files(listing)]


def _meta(snapshot: dict) -> dict:
    description, summary = snapshot.get("description") or {}, snapshot.get("summary") or {}
    return {"scope": "metadata", "tag": snapshot.get("tag"), "dataset_doi": description.get("DatasetDOI"),
            "name": description.get("Name"), "subjects": len(summary.get("subjects") or []),
            "modalities": summary.get("modalities"), "total_files": summary.get("totalFiles"),
            "size": summary.get("size")}


def fetch_openneuro(ds: str, dest: Path, policy: SizePolicy, post_json, get_bytes,
                    tag: str | None = None) -> FetchResult:
    try:
        dataset, snapshot = _resolve(ds, tag, post_json)
        listing = _listing(ds, snapshot)
        _write_metadata(dest, dataset, snapshot, listing)
    except Exception as e:  # any API error is recorded, never raised
        return FetchResult("openneuro", ds, str(dest), "failed", [], str(e))
    records = _download_roots(listing, dest, policy, get_bytes, _written_names(snapshot))
    status = "ok" if all(r["downloaded"] for r in records) else "partial"
    return FetchResult("openneuro", ds, str(dest), status, records, meta=_meta(snapshot))
