import json

import pytest
from conftest import _load_fixture

from fetch_common import SizePolicy
from fetch_openneuro import FILES_URL, GRAPHQL, fetch_openneuro, file_url, openneuro_id, openneuro_tag

DD_URL = "https://s3.example/dd.json"


def _served(url: str) -> bytes:
    return f"bytes of {url}".encode()


def _root_url(name: str) -> str:
    return FILES_URL.format(ds="ds000001", tag="1.0.0", name=name)


@pytest.fixture
def post_router():
    """A post_json that answers dataset and snapshot queries from fixtures and records every call."""
    calls = []

    def post_json(url, payload):
        calls.append((url, payload))
        name = "openneuro_snapshot.json" if "snapshot(" in payload["query"] else "openneuro_dataset.json"
        return _load_fixture(name)

    post_json.calls = calls
    return post_json


def _get_bytes(fail: set[str] = frozenset()):
    def get_bytes(url):
        if url in fail:
            raise OSError(f"cannot fetch {url}")
        return _served(url)

    return get_bytes


def _fetch(dest, post_json, get_bytes=None, tag=None):
    return fetch_openneuro("ds000001", dest, SizePolicy(), post_json, get_bytes or _get_bytes(), tag=tag)


def test_openneuro_id_and_tag():
    versioned = "https://openneuro.org/datasets/ds000001/versions/1.0.0"
    assert openneuro_id(versioned) == "ds000001" and openneuro_tag(versioned) == "1.0.0"
    bare = "https://openneuro.org/datasets/ds000001"
    assert openneuro_id(bare) == "ds000001" and openneuro_tag(bare) is None
    doi = "https://doi.org/10.18112/openneuro.ds000001.v1.0.0"
    assert openneuro_id(doi) == "ds000001" and openneuro_tag(doi) == "1.0.0"
    assert openneuro_id("https://openneuro.org/") is None


def test_fetch_latest_snapshot_writes_metadata(tmp_path, post_router):
    dest = tmp_path / "on"
    r = _fetch(dest, post_router)
    assert len(post_router.calls) == 2 and all(url == GRAPHQL for url, _ in post_router.calls)
    assert post_router.calls[1][1]["variables"] == {"id": "ds000001", "tag": "1.0.0"}
    meta = json.loads((dest / "dataset.json").read_text())
    assert meta["scope"] == "metadata" and meta["summary"]["totalFiles"] == 42
    assert meta["dataset_doi"] == "10.18112/openneuro.ds000001.v1.0.0"
    assert meta["dataset"]["name"] == "Balloon Analog Risk-taking Task"
    assert (dest / "README").read_text() == "# BART\nBalloon task."
    listing = json.loads((dest / "files.json").read_text())
    assert len(listing) == 8 and "sub-01/anat/sub-01_T1w.nii.gz" in [e["path"] for e in listing]
    assert not (dest / "sub-01").exists()
    assert (dest / "dataset_description.json").read_bytes() == _served(DD_URL)
    assert (dest / "participants.tsv").read_bytes() == _served(_root_url("participants.tsv"))
    assert r.status == "ok"
    assert [f["path"] for f in r.files] == ["dataset_description.json", "participants.tsv", "README", "CHANGES"]
    assert all(f["downloaded"] and f["sha256"] for f in r.files)
    assert r.meta["subjects"] == 2 and r.meta["tag"] == "1.0.0"


def test_explicit_tag_skips_dataset_query(tmp_path, post_router):
    _fetch(tmp_path / "on", post_router, tag="1.0.0")
    assert len(post_router.calls) == 1


def test_graphql_error_is_failed(tmp_path):
    r = _fetch(tmp_path / "on", lambda url, payload: {"errors": [{"message": "Dataset not found"}]})
    assert r.status == "failed" and r.reason == "Dataset not found"
    assert not (tmp_path / "on").exists()


def test_root_download_failure_is_partial(tmp_path, post_router):
    dest = tmp_path / "on"
    r = _fetch(dest, post_router, _get_bytes({_root_url("participants.tsv")}))
    assert r.status == "partial"
    by_path = {f["path"]: f for f in r.files}
    assert by_path["participants.tsv"]["downloaded"] is False
    assert all(f["downloaded"] for p, f in by_path.items() if p != "participants.tsv") and len(by_path) == 4
    assert (dest / "files.json").exists()


def test_file_url_fallback_uses_colon_paths():
    entry = {"filename": "derivatives/fmriprep/x.json", "urls": None}
    assert file_url("ds000001", "1.0.0", entry) == _root_url("derivatives:fmriprep:x.json")


def _post_with_extra_root(entry: dict):
    def post_json(url, payload):
        if "snapshot(" not in payload["query"]:
            return _load_fixture("openneuro_dataset.json")
        snap = _load_fixture("openneuro_snapshot.json")
        snap["data"]["snapshot"]["files"].append(entry)
        return snap

    return post_json


def test_reserved_root_names_are_not_downloaded(tmp_path):
    dest = tmp_path / "on"
    entry = {"id": "f9", "filename": "files.json", "size": 10, "directory": False, "annexed": False, "urls": None}
    r = _fetch(dest, _post_with_extra_root(entry))
    assert isinstance(json.loads((dest / "files.json").read_text()), list)
    rec = next(f for f in r.files if f["path"] == "files.json")
    assert rec["downloaded"] is False and rec["reason"] == "name reserved for prep metadata"
    assert r.status == "partial"
