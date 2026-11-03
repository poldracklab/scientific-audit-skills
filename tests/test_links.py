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


def test_extract_from_text_records_pages():
    text = "a https://osf.io/abcde/.\fb https://zenodo.org/records/1"
    links = extract_links_from_text(text, "paper.txt")
    assert [(l.canonical, l.found_in[0]["page"]) for l in links] == [
        ("https://osf.io/abcde", 1), ("https://zenodo.org/records/1", 2)]


def test_extract_from_pdf_includes_hidden_annotation(fixture_pdf):
    canon = {l.canonical for l in extract_links_from_pdf(fixture_pdf)}
    assert "https://github.com/lab/repo" in canon
    assert "https://osf.io/x4c56" in canon


def test_merge_unions_found_in():
    a = Link("u", "https://osf.io/abcde", "osf", "data", True, [{"file": "p", "page": 1}])
    b = Link("u", "https://osf.io/abcde", "osf", "data", True, [{"file": "s", "page": 2}])
    merged = merge_links([a, b])
    assert len(merged) == 1 and len(merged[0].found_in) == 2
