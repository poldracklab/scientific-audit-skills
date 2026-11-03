import links
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
