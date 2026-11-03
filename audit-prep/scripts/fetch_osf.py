# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""List and download OSF project files; fetch and hash-verify OSF registrations."""
import json
import re
from pathlib import Path

from fetch_common import FetchResult, RemoteFile, SizePolicy, download, file_records, select_downloads, sha256_file

API = "https://api.osf.io/v2"
OSF_ID_RE = re.compile(r"osf\.io/([a-z0-9]{5})(?=[/?#]|$)", re.I)


def osf_id(canonical: str) -> str | None:
    m = OSF_ID_RE.search(canonical)
    return m.group(1).lower() if m else None


def _remote_file(entry: dict, rel: str) -> RemoteFile:
    a = entry["attributes"]
    hashes = (a.get("extra") or {}).get("hashes") or {}
    return RemoteFile(f"{rel}{a['name']}", a.get("size") or 0, entry["links"]["download"], hashes.get("sha256"))


def walk_listing(url: str | None, get_json, rel: str = "") -> list[RemoteFile]:
    """Walk an osfstorage listing, following `links.next` and recursing into folders."""
    files = []
    while url:
        page = get_json(url)
        for entry in page["data"]:
            if entry["attributes"]["kind"] == "folder":
                child = entry["relationships"]["files"]["links"]["related"]["href"]
                files += walk_listing(child, get_json, f"{rel}{entry['attributes']['name']}/")
            else:
                files.append(_remote_file(entry, rel))
        url = page["links"].get("next")
    return files


def list_osf_files(node_id: str, get_json) -> list[RemoteFile]:
    return walk_listing(f"{API}/nodes/{node_id}/files/osfstorage/", get_json)


def fetch_osf_files(node_id: str, dest: Path, policy: SizePolicy, get_json, get_bytes) -> FetchResult:
    try:
        files = list_osf_files(node_id, get_json)
    except Exception as e:  # any API error is recorded, never raised
        return FetchResult("osf", node_id, str(dest), "failed", [], str(e))
    selected, status = select_downloads(files, policy)
    return FetchResult("osf", node_id, str(dest), status, file_records(files, selected, dest, get_bytes))


def node_registration_count(node_id: str, get_json) -> int:
    return get_json(f"{API}/nodes/{node_id}/registrations/")["links"]["meta"]["total"]


def registration_attributes(reg_id: str, get_json) -> dict:
    """Return the registration's attributes; raises if `reg_id` is not a registration."""
    return get_json(f"{API}/registrations/{reg_id}/")["data"]["attributes"]


def _summary(attrs: dict) -> dict:
    return {
        "title": attrs.get("title"),
        "date_registered": attrs.get("date_registered"),
        "type": attrs.get("registration_supplement"),
        "withdrawn": attrs.get("withdrawn"),
    }


def _verify(f: RemoteFile, dest: Path, get_bytes) -> dict:
    actual = sha256_file(download(f.url, dest, get_bytes, f.path))
    verified = None if f.remote_hash is None else f.remote_hash == actual
    return {"name": f.path, "sha256_expected": f.remote_hash, "sha256_actual": actual, "verified": verified}


def _registration_record(reg_id: str, dest: Path) -> dict:
    empty = dict.fromkeys(["title", "date_registered", "type", "withdrawn"])
    return {"source": "osf", "id": reg_id, "path": str(dest), **empty, "files": [], "status": "failed", "reason": ""}


def _write_metadata(dest: Path, rec: dict, attrs: dict) -> None:
    """registration.json: summary, frozen and actual hashes, and the full attributes."""
    meta = {k: rec[k] for k in ("id", "title", "date_registered", "type", "withdrawn", "files")}
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "registration.json").write_text(json.dumps({**meta, "attributes": attrs}, indent=2))


def fetch_osf_registration(reg_id: str, dest: Path, get_json, get_bytes) -> dict:
    rec = _registration_record(reg_id, dest)
    try:
        attrs = registration_attributes(reg_id, get_json)
        rec.update(_summary(attrs))
        listing = walk_listing(f"{API}/registrations/{reg_id}/files/osfstorage/", get_json)
        rec["files"] = [_verify(f, dest, get_bytes) for f in listing]
        _write_metadata(dest, rec, attrs)
    except Exception as e:  # any API or download error is recorded, never raised
        return {**rec, "reason": str(e)}
    status = verification_status([f["verified"] for f in rec["files"]])
    return {**rec, "status": status, "reason": unverified_reason(attrs, rec["files"]) if status == "unverified" else ""}


def unverified_reason(attrs: dict, files: list[dict]) -> str:
    """Why a registration could not be verified, when its attributes or empty listing say so."""
    if attrs.get("embargoed"):
        return "embargoed"
    if attrs.get("withdrawn"):
        return "withdrawn"
    return "" if files else "no files in registration"


def verification_status(verified: list[bool | None]) -> str:
    """hash_mismatch if any False; ok if files exist and all True; otherwise unverified."""
    if False in verified:
        return "hash_mismatch"
    return "ok" if verified and all(v is True for v in verified) else "unverified"
