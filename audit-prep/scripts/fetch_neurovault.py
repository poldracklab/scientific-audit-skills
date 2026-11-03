# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Download every statistical map of a NeuroVault collection, with collection and image metadata."""
import json
import re
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

from fetch_common import FetchResult, RemoteFile, download_one

API = "https://neurovault.org/api/collections"
LOOP_REASON = "pagination loop detected"
NEUROVAULT_ID_RE =re.compile(r"neurovault\.org/collections/(\d+)", re.I)


def neurovault_id(canonical: str) -> str | None:
    m = NEUROVAULT_ID_RE.search(canonical)
    return m.group(1) if m else None


def list_images(collection_id: str, get_json) -> tuple[list[dict], bool]:
    """Image metadata across all pages, following `next`; the flag is True if `next` looped."""
    images, seen, url = [], set(), f"{API}/{collection_id}/images/?format=json"
    while url:
        if url in seen:
            return images, True
        seen.add(url)
        page = get_json(url)
        images += page["results"]
        url = page.get("next")
    return images, False


def _remote_file(image: dict) -> RemoteFile:
    """Prefix the basename with the image id so same-named images and metadata files never collide."""
    name = PurePosixPath(urlparse(image["file"]).path).name
    return RemoteFile(f"{image['id']}_{name}", 0, image["file"])


def _write_json(dest: Path, name: str, data) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / name).write_text(json.dumps(data, indent=2))


def fetch_neurovault(collection_id: str, dest: Path, get_json, get_bytes) -> FetchResult:
    try:
        collection = get_json(f"{API}/{collection_id}/")
        images, looped = list_images(collection_id, get_json)
        files = [_remote_file(i) for i in images]
        _write_json(dest, "collection.json", collection)
        _write_json(dest, "images.json", images)
    except Exception as e:  # any API error is recorded, never raised
        return FetchResult("neurovault", collection_id, str(dest), "failed", [], str(e))
    records = [download_one(f, dest, get_bytes) for f in files]
    reason = LOOP_REASON if looped else ""
    return FetchResult("neurovault", collection_id, str(dest), _status(records, looped), records, reason)


def _status(records: list[dict], looped: bool) -> str:
    """failed when a looped listing yielded nothing; partial when any image failed to download."""
    if not records:
        return "failed" if looped else "ok"
    return "ok" if all(r["downloaded"] for r in records) else "partial"
