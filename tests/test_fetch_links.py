import dataclasses

import links
from conftest import _load_fixture
from fetch_links import fetch_all


def _link(raw: str, role: str | None = None) -> dict:
    l = links.make_link(raw, "paper.pdf", 1)
    return {"url": l.url, "canonical": l.canonical, "class": l.cls, "role": role or l.role,
            "needs_review": False, "found_in": l.found_in, "reason": "test"}


def _manifest() -> dict:
    return {"warnings": [], "metadata": None}


def test_zenodo_doi_link_is_fetched_by_the_zenodo_fetcher(tmp_path, clients):
    m = _manifest()
    fetch_all(tmp_path, {"links": [_link("https://doi.org/10.5281/zenodo.123456")]}, m, clients)
    rec = m["data"][0]
    assert rec["source"] == "zenodo" and rec["path"] == "data/zenodo_123456"
    assert rec["status"] != "unsupported"


def test_non_github_code_link_is_unsupported_with_url(tmp_path, clients):
    m = _manifest()
    fetch_all(tmp_path, {"links": [_link("https://gitlab.com/lab/code", role="code")]}, m, clients)
    rec = m["code"][0]
    assert rec["status"] == "unsupported" and rec["url"] == "https://gitlab.com/lab/code"
    assert rec["reason"] == "code links are fetched from GitHub only; fetch manually"
    assert m["links"][0]["status"] == "unsupported"


def test_listed_only_data_record_has_no_path(tmp_path, clients):
    m = _manifest()
    plan = {"size_policy": {"max_source_mb": 0}, "links": [_link("https://osf.io/abcde", role="data")]}
    fetch_all(tmp_path, plan, m, clients)
    rec = m["data"][0]
    assert rec["status"] == "listed_only" and rec["path"] is None


def _openneuro_post(url, payload):
    return _load_fixture("openneuro_snapshot.json" if "snapshot(" in payload["query"] else "openneuro_dataset.json")


def test_openneuro_link_lands_in_data_dir(tmp_path, clients):
    c = dataclasses.replace(clients, post_json=_openneuro_post, get_bytes=lambda u: b"x")
    canonical = "https://openneuro.org/datasets/ds000001/versions/1.0.0"
    link = {"url": canonical, "canonical": canonical, "class": "openneuro", "role": "data", "needs_review": False}
    m = _manifest()
    fetch_all(tmp_path, {"links": [link]}, m, c)
    assert m["data"][0]["path"] == "data/openneuro_ds000001" and m["data"][0]["status"] == "ok"
    assert m["links"][0]["fetched_to"] == "data/openneuro_ds000001"
    assert (tmp_path / "data/openneuro_ds000001/dataset.json").exists()
