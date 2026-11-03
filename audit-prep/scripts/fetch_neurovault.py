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
NEUROVAULT_ID_RE = re.compile(r"neurovault\.org/collections/(\d+)", re.I)


def neurovault_id(canonical: str) -> str | None:
    m = NEUROVAULT_ID_RE.search(canonical)
    return m.group(1) if m else None


def list_images(collection_id: str, get_json) -> list[dict]:
    """Image metadata across all pages, following `next`."""
    images, url = [], f"{API}/{collection_id}/images/?format=json"
    while url:
        page = get_json(url)
        images += page["results"]
        url = page.get("next")
    return images


def _remote_file(image: dict) -> RemoteFile:
    return RemoteFile(PurePosixPath(urlparse(image["file"]).path).name, 0, image["file"])


def _write_json(dest: Path, name: str, data) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / name).write_text(json.dumps(data, indent=2))


def fetch_neurovault(collection_id: str, dest: Path, get_json, get_bytes) -> FetchResult:
    try:
        collection = get_json(f"{API}/{collection_id}/")
        images = list_images(collection_id, get_json)
        files = [_remote_file(i) for i in images]
        _write_json(dest, "collection.json", collection)
        _write_json(dest, "images.json", images)
    except Exception as e:  # any API error is recorded, never raised
        return FetchResult("neurovault", collection_id, str(dest), "failed", [], str(e))
    records = [download_one(f, dest, get_bytes) for f in files]
    return FetchResult("neurovault", collection_id, str(dest), "ok", records)
