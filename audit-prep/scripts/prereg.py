# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Fetch preregistrations: OSF registrations, AsPredicted, ClinicalTrials.gov, PROSPERO."""
import json
import re
import urllib.error
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qs, urlsplit

from fetch_osf import fetch_osf_registration, osf_id, registration_attributes

CTGOV_API = "https://clinicaltrials.gov/api/v2/studies/"
NCT_RE = re.compile(r"NCT\d{8}")
SAFE_ID_RE = re.compile(r"[A-Za-z0-9_-]+")
NOT_FOUND = (404, 410)


def _result(source: str, ident: str | None, path, date=None, status="ok", reason="") -> dict:
    return {"source": source, "id": ident, "path": path, "date_registered": date, "status": status, "reason": reason}


def _query_param(url: str, name: str) -> str | None:
    values = parse_qs(urlsplit(url).query).get(name)
    return values[0] if values else None


def _last_segment(url: str) -> str:
    return PurePosixPath(urlsplit(url).path).name


def aspredicted_id(url: str) -> str | None:
    return _query_param(url, "x") or PurePosixPath(_last_segment(url)).stem or None


def nct_id(url: str) -> str | None:
    m = NCT_RE.search(url)
    return m.group(0) if m else None


def prospero_id(url: str) -> str | None:
    return _query_param(url, "RecordID") or _last_segment(url) or None


def _save(dest: Path, name: str, data: bytes) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / name).write_bytes(data)


def fetch_aspredicted(url: str, dest: Path, get_bytes) -> dict:
    ident = aspredicted_id(url)
    data = get_bytes(url)
    _save(dest, f"{ident}.pdf" if data.startswith(b"%PDF") else f"{ident}.html", data)
    return _result("aspredicted", ident, str(dest))


def fetch_clinicaltrials(nct: str, dest: Path, get_json) -> dict:
    record = get_json(CTGOV_API + nct)
    _save(dest, f"{nct}.json", json.dumps(record, indent=2).encode())
    date = record["protocolSection"]["statusModule"].get("studyFirstSubmitDate")
    return _result("clinicaltrials", nct, str(dest), date)


def fetch_prospero(url: str, dest: Path, get_bytes) -> dict:
    ident = prospero_id(url)
    _save(dest, f"{ident}.html", get_bytes(url))
    return _result("prospero", ident, str(dest))


def _fetch_osf(url: str, dest: Path, get_json, get_bytes) -> dict:
    reg = osf_id(url)
    try:
        registration_attributes(reg, get_json)
    except urllib.error.HTTPError as e:
        reason = "not a registration" if e.code in NOT_FOUND else str(e)
        return _result("osf", reg, None, status="failed", reason=reason)
    return fetch_osf_registration(reg, dest, get_json, get_bytes)


FETCHERS = {
    "osf": (osf_id, _fetch_osf),
    "aspredicted": (aspredicted_id, lambda url, dest, gj, gb: fetch_aspredicted(url, dest, gb)),
    "clinicaltrials": (nct_id, lambda url, dest, gj, gb: fetch_clinicaltrials(nct_id(url), dest, gj)),
    "prospero": (prospero_id, lambda url, dest, gj, gb: fetch_prospero(url, dest, gb)),
}


def _relative(result: dict, rel: str) -> dict:
    return {**result, "path": None if result["status"] == "failed" else rel}


def fetch_prereg(link: dict, dest_root: Path, get_json, get_bytes) -> dict:
    """Fetch one prereg link into `dest_root/preregistration/<source>_<id>`; never raises."""
    source, url = link["class"], link["canonical"]
    if source not in FETCHERS:
        return _result(source, None, None, status="failed", reason=f"unsupported prereg source: {source}")
    id_of, fetch = FETCHERS[source]
    ident = id_of(url)
    if not ident:
        return _result(source, None, None, status="failed", reason=f"no {source} id in {url}")
    if not SAFE_ID_RE.fullmatch(ident):
        return _result(source, ident, None, status="failed", reason="unsafe id")
    rel = f"preregistration/{source}_{ident}"
    try:
        return _relative(fetch(url, dest_root / rel, get_json, get_bytes), rel)
    except Exception as e:  # any fetch error is recorded, never raised
        return _result(source, ident, None, status="failed", reason=str(e))
