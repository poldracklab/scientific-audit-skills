import pytest

from manifest import new_manifest
from review import format_review, manifest_problems, review_manifest

OK_CONV = {"text": "ok", "pages": "ok", "structured": "ok", "statements": "ok"}
DOCLING = "paper/paper.pdf structured: docling failed: uvx disabled"


def _paper(conversions):
    return {"path": "paper/paper.pdf", "pages": 2, "conversions": dict(conversions)}


@pytest.fixture
def clean():
    m = new_manifest("P_2024", "human")
    m["documents"]["paper"] = _paper(OK_CONV)
    m["metadata"] = {"doi": "x"}
    m["data"] = [{"source": "osf", "id": "abcde", "status": "ok", "reason": None}]
    m["preregistration"] = [{"source": "osf", "id": "x4c56", "status": "ok"}]
    m["code"] = [{"url": "https://github.com/lab/repo", "status": "ok"}]
    return m


@pytest.fixture
def broken():
    m = new_manifest("P_2024", "human")
    m["documents"]["paper"] = _paper({**OK_CONV, "structured": "failed"})
    m["warnings"] = [DOCLING, "crossref metadata for 10.1/x unavailable: boom"]
    m["local_data"] = [{"path": "data/x.zip", "archive": True, "extracted": "failed", "reason": "bad zip"}]
    m["preregistration"] = [{"source": "osf", "id": "x4c56", "status": "unverified", "reason": "embargoed"}]
    m["code"] = [{"url": "https://gitlab.com/lab/code", "status": "unsupported", "reason": "..."}]
    m["data"] = [{"source": "osf", "id": "abcde", "status": "listed_only", "reason": "over size policy"},
                 {"source": "figshare", "id": "https://figshare.com/x/1", "status": "unsupported",
                  "reason": "no fetcher"}]
    return m


@pytest.fixture
def two_problems(clean):
    clean["data"] = [{"source": "osf", "id": "abcde", "status": "listed_only", "reason": "over size policy"}]
    clean["code"] = [{"url": "https://gitlab.com/lab/code", "status": "unsupported", "reason": "no fetcher"}]
    return clean


def test_clean_manifest_has_no_problems(clean):
    assert manifest_problems(clean) == []
    assert review_manifest(clean, {})["status"] == "ok"


def test_every_failure_kind_is_a_problem(broken):
    problems = manifest_problems(broken)
    assert [p.item for p in problems] == [
        "conversion paper/paper.pdf structured", "metadata crossref", "local_data data/x.zip",
        "preregistration osf x4c56", "code https://gitlab.com/lab/code", "data osf abcde",
        "data figshare https://figshare.com/x/1"]
    assert problems[0].detail == DOCLING
    assert problems[3].status == "unverified"
    assert problems[2].detail == "bad zip"


def test_missing_paper_is_a_problem(clean):
    clean["documents"]["paper"] = None
    problems = manifest_problems(clean)
    assert len(problems) == 1
    assert problems[0].item == "paper" and problems[0].kind == "paper"


def test_partial_data_is_a_problem(clean):
    clean["data"][0]["status"] = "partial"
    problems = manifest_problems(clean)
    assert len(problems) == 1 and problems[0].status == "partial"


def test_acceptance_moves_problem_to_accepted(two_problems):
    review = review_manifest(two_problems, {"accept_failures": {"data osf abcde": "12 GB; listing suffices"}})
    assert review["status"] == "failed" and len(review["problems"]) == 1
    assert review["accepted"][0]["accepted_reason"] == "12 GB; listing suffices"
    both = {"data osf abcde": "12 GB; listing suffices", "code https://gitlab.com/lab/code": "not public"}
    assert review_manifest(two_problems, {"accept_failures": both})["status"] == "ok"


def test_unused_acceptance_key_is_listed(clean):
    review = review_manifest(clean, {"accept_failures": {"data osf nope": "gone"}})
    assert review["unused"] == ["data osf nope"]
    assert format_review(review).endswith("unused accept_failures keys: data osf nope")


def test_format_review_prints_keys_to_paste(two_problems):
    text = format_review(review_manifest(two_problems, {}))
    assert "FAILED, 2 open problem(s)" in text and "accept_failures:" in text
    assert '  "data osf abcde": "<why this is acceptable>"' in text
    assert "- data osf abcde: listed_only — over size policy" in text.splitlines()
    two_problems["code"] = []
    ok = review_manifest(two_problems, {"accept_failures": {"data osf abcde": "a"}})
    assert format_review(ok) == "prep review: ok (1 accepted failure(s))"


def test_nested_archive_is_a_problem(clean):
    clean["local_data"] = [{"path": "data/d/inner.zip", "nested_archive": True}]
    problems = manifest_problems(clean)
    assert [(p.item, p.status) for p in problems] == [("local_data data/d/inner.zip", "not_extracted")]


PLAN = {"files": [], "links": [], "accept_failures": {"x": "y"}}
CLEAN_REVIEW = {"status": "ok", "problems": [], "accepted": [], "unused": []}
MODIFIED = {"kind": "plan", "item": "plan", "status": "modified",
            "detail": "prep.yaml changed after run (files, links or roles); rerun prep.py run"}


def test_folder_review_flags_missing_plan_hash(clean):
    from review import review_folder

    clean["review"] = dict(CLEAN_REVIEW)
    assert MODIFIED in review_folder(clean, PLAN)["problems"]


def test_folder_review_flags_changed_plan(clean):
    from review import plan_sha256, review_folder

    clean["review"] = dict(CLEAN_REVIEW)
    clean["plan_sha256"] = plan_sha256({"files": [], "links": [{"canonical": "x", "role": "skip"}]})
    assert MODIFIED in review_folder(clean, PLAN)["problems"]


def test_plan_hash_ignores_accept_failures(clean):
    from review import plan_sha256, review_folder

    clean["review"] = dict(CLEAN_REVIEW)
    clean["plan_sha256"] = plan_sha256({"files": [], "links": []})
    assert review_folder(clean, PLAN)["problems"] == []
    assert plan_sha256(PLAN) == plan_sha256({**PLAN, "accept_failures": {}})
