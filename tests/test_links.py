import pytest

from links import (
    Link,
    canonicalize,
    classify,
    extract_links_from_pdf,
    extract_links_from_text,
    find_doi,
    merge_links,
)


@pytest.mark.parametrize("raw,expected", [
    ("https://osf.io/abcde/.", "https://osf.io/abcde"),
    ("10.17605/OSF.IO/X4C56", "https://osf.io/x4c56"),
    ("http://osf.io/ABCDE", "https://osf.io/abcde"),
    ("https://doi.org/10.1126/sciadv.abf4355", "https://doi.org/10.1126/sciadv.abf4355"),
    ("https://github.com/lab/repo.git", "https://github.com/lab/repo"),
    ("https://osf.io/x4c56/registrations/", "https://osf.io/x4c56/registrations"),
])
def test_canonicalize(raw, expected):
    assert canonicalize(raw) == expected


@pytest.mark.parametrize("url,cls,role,review", [
    ("https://osf.io/abcde", "osf", "data", True),
    ("https://osf.io/x4c56/registrations", "osf", "prereg", False),
    ("https://github.com/lab/repo", "github", "code", True),
    ("https://zenodo.org/records/123456", "zenodo", "data", False),
    ("https://openneuro.org/datasets/ds000001/versions/1.0.0", "openneuro", "data", False),
    ("https://neurovault.org/collections/1234", "neurovault", "data", False),
    ("https://aspredicted.org/abc12.pdf", "aspredicted", "prereg", False),
    ("https://clinicaltrials.gov/study/NCT01234567", "clinicaltrials", "prereg", False),
    ("https://doi.org/10.1126/sciadv.abf4355", "doi", "unknown", True),
    ("https://example.org/x", "other", "unknown", True),
])
def test_classify(url, cls, role, review):
    assert classify(url) == (cls, role, review)


def test_find_doi():
    assert find_doi("see doi:10.1126/sciadv.abf4355. Next") == "10.1126/sciadv.abf4355"


def test_find_doi_in_doi_url():
    assert find_doi("https://doi.org/10.1126/sciadv.abf4355") == "10.1126/sciadv.abf4355"


def test_extract_from_text_records_pages():
    text = "a https://osf.io/abcde/.\fb https://zenodo.org/records/1"
    links = extract_links_from_text(text, "paper.txt")
    assert [(l.canonical, l.found_in[0]["page"]) for l in links] == [
        ("https://osf.io/abcde", 1), ("https://zenodo.org/records/1", 2)]


def test_extract_from_pdf_includes_hidden_annotation(fixture_pdf):
    canon = {l.canonical for l in extract_links_from_pdf(fixture_pdf)}
    assert "https://github.com/lab/repo" in canon
    assert "https://osf.io/x4c56" in canon


def test_pdf_annotation_only_uri_is_extracted(fixture_pdf):
    links = {l.canonical: l for l in extract_links_from_pdf(fixture_pdf)}
    assert links["https://github.com/lab/hidden-tool"].found_in[0]["page"] == 1


def test_pdf_mailto_annotation_is_ignored(fixture_pdf):
    assert not [l for l in extract_links_from_pdf(fixture_pdf) if "author@" in l.canonical]


def test_merge_unions_found_in():
    a = Link("u", "https://osf.io/abcde", "osf", "data", True, [{"file": "p", "page": 1}])
    b = Link("u", "https://osf.io/abcde", "osf", "data", True, [{"file": "s", "page": 2}])
    merged = merge_links([a, b])
    assert len(merged) == 1 and len(merged[0].found_in) == 2


@pytest.mark.parametrize("raw,cls", [
    ("https://osf.io", "osf"), ("https://osf.io/", "osf"), ("https://github.com/", "github"),
    ("https://zenodo.org", "zenodo"), ("https://neurovault.org/", "neurovault"),
    ("https://openneuro.org", "openneuro"), ("https://figshare.com/", "figshare"),
    ("https://datadryad.org", "dryad"),
])
def test_bare_host_is_skipped(raw, cls):
    assert classify(canonicalize(raw)) == (cls, "skip", False)


@pytest.mark.parametrize("deposit", [
    "10.5281/zenodo.4432816", "10.17605/OSF.IO/X4C56", "10.6084/m9.figshare.123",
    "10.5061/dryad.abc12", "10.18112/openneuro.ds000001.v1.0.0",
])
def test_find_doi_ignores_repository_dois(deposit):
    assert find_doi(f"data at {deposit} and doi 10.1126/sciadv.abf4355") == "10.1126/sciadv.abf4355"
    assert find_doi(f"only {deposit} here") is None


def test_find_dois_lists_article_candidates_in_order():
    from links import find_dois

    text = "10.5281/zenodo.1 then 10.1101/pre.1 and 10.1126/x.2, again 10.1101/pre.1"
    assert find_dois(text) == ["10.1101/pre.1", "10.1126/x.2"]
