"""Unpack downloaded data with the same extractor used for supplied archives."""
from pathlib import Path

from archives import _archive_stem, _extract
from fetch_common import safe_join, sha256_file


def _unpack_download(prepared: Path, archive: Path, previous: dict, run, downloaded: set) -> dict:
    entry = {"path": archive.relative_to(prepared).as_posix(), "sha256": sha256_file(archive)}
    target = archive.with_name(_archive_stem(archive.name) or archive.name + ".d")
    output = target.relative_to(prepared).as_posix()
    owned = previous.get("extracted_to") == output
    if owned:
        entry["extracted_to"] = output
    try:
        if any(p == target or target in p.parents for p in downloaded):
            raise ValueError("extraction target overlaps another downloaded file")
        if target.exists() and not owned:
            raise ValueError("extraction target already exists and is not owned by this archive")
        if archive.name.lower().endswith(".7z"):
            return {**entry, "extracted": "skipped", "reason": "no extractor for .7z; extract by hand"}
        if not (owned and target.is_dir() and previous.get("extracted") == "ok"
                and previous.get("sha256") == entry["sha256"]):
            _extract(archive, target, run, replace=owned)
        entry.update(extracted="ok", extracted_to=output)
    except Exception as exc:
        entry.update(extracted="failed", reason=str(exc))
    return entry


def _nested(prepared: Path, entries: list[dict], downloaded: set) -> list[dict]:
    found = set()
    for entry in entries:
        if entry.get("extracted") != "ok":
            continue
        for path in (prepared / entry["extracted_to"]).rglob("*"):
            if path.is_file() and _archive_stem(path.name) and path not in downloaded:
                found.add(path.relative_to(prepared).as_posix())
    return [{"path": path, "nested_archive": True} for path in sorted(found)]


def extract_downloaded_archives(prepared: Path, manifest: dict, previous: list[dict], run) -> None:
    prepared = prepared.resolve()
    old = {e["path"]: e for source in previous for e in source.get("archives", [])}
    for source in manifest["data"]:
        if not source.get("path"):
            continue
        root = safe_join(prepared, source["path"])
        downloaded = {safe_join(root, f["path"]) for f in source.get("files", []) if f.get("downloaded")}
        entries = [_unpack_download(prepared, p, old.get(p.relative_to(prepared).as_posix(), {}), run, downloaded)
                   for p in sorted(downloaded) if _archive_stem(p.name)]
        source["archives"] = entries + _nested(prepared, entries, downloaded)
        manifest["warnings"].extend(f"{e['path']}: {e['reason']}" for e in entries if e.get("reason"))
