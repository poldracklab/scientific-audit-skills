import pytest

from scan import build_plan, classify_files, has_supplement_marker, load_plan, unresolved, write_plan

SUPPLEMENT_NAMES = [
    "abf4355_sm.pdf",
    "Eisenberg_2019_SOM.pdf",
    "41562_2023_1760_MOESM1_ESM.pdf",
    "imag_a_00262-supp.pdf",
    "1-s2.0-S1878929323001421-mmc1.docx",
    "Laumann_2015_supplement.pdf",
    "tom.som.pdf",
    "imag.a.958_supp.pdf",
    "netn_a_00412-supp.pdf",
]
NON_SUPPLEMENT_NAMES = [
    "s41562-022-01510-8.pdf",
    "sciadv.abf4355.pdf",
    "Jaffe_2025.pdf",
    "tometal.pdf",
    "Somerville_2018.pdf",
    "Desmond_2003.pdf",
]


@pytest.mark.parametrize("name", SUPPLEMENT_NAMES)
def test_supplement_marker_matches_corpus_supplements(name):
    assert has_supplement_marker(name)


@pytest.mark.parametrize("name", NON_SUPPLEMENT_NAMES)
def test_supplement_marker_ignores_author_names(name):
    assert not has_supplement_marker(name)


def test_classify_non_pdf_supplement(raw_folder):
    files = {f["path"]: f for f in classify_files(raw_folder("paper_supp_docx"))}
    supp = files["1-s2.0-S1878929323001421-mmc1.docx"]
    assert supp["role"] == "supplement" and supp["needs_review"] is False and supp["order"] == 1


def test_build_plan_survives_crossref_failure(raw_folder):
    def failing(url):
        raise OSError("boom")

    plan = build_plan(raw_folder("paper_supp"), get_json=failing)
    paper = [f for f in plan["files"] if f["role"] == "paper"][0]
    assert plan["doi"] == "10.1126/sciadv.abf4355"
    assert paper["needs_review"] is True and "crossref lookup failed: boom" in paper["reason"]


def test_classify_paper_and_supplement(raw_folder):
    roles = {f["path"]: f["role"] for f in classify_files(raw_folder("paper_supp"))}
    assert roles == {"paper.pdf": "paper", "paper_sm.pdf": "supplement"}


def test_classify_data_dir_archive_and_residue(raw_folder):
    roles = {f["path"]: f["role"] for f in classify_files(raw_folder("paper_data_archive"))}
    assert roles["mydata"] == "data" and roles["mydata.tar.gz"] == "archive"
    roles = {f["path"]: f["role"] for f in classify_files(raw_folder("paper_residue"))}
    assert roles[".venv"] == "unsorted" and roles[".git"] == "unsorted" and roles["paper.txt"] == "unsorted"


def test_build_plan_nodoi_marks_paper_needs_review(raw_folder):
    plan = build_plan(raw_folder("paper_nodoi"), get_json=lambda u: {"message": {}})
    paper = [f for f in plan["files"] if f["role"] == "paper"][0]
    assert paper["needs_review"] and plan["doi"] is None


def test_build_plan_links_and_defaults(raw_folder, crossref_fixture):
    plan = build_plan(raw_folder("paper_supp"), get_json=lambda u: crossref_fixture)
    assert plan["doi"] == "10.1126/sciadv.abf4355" and plan["reviewed_by"] is None
    assert plan["size_policy"]["max_file_mb"] == 500
    canon = {l["canonical"]: l for l in plan["links"]}
    assert canon["https://osf.io/abcde"]["needs_review"] is True
    assert canon["https://github.com/lab/repo"]["role"] == "code"


def test_unresolved_lists_blockers(raw_folder, crossref_fixture):
    plan = build_plan(raw_folder("paper_supp"), get_json=lambda u: crossref_fixture)
    msgs = unresolved(plan)
    assert any("reviewed_by" in m for m in msgs) and any("needs_review" in m for m in msgs)
    for l in plan["links"]:
        l["needs_review"] = False
    plan["reviewed_by"] = "human"
    assert unresolved(plan) == []


def test_write_and_load_roundtrip(tmp_path):
    p = {"schema_version": 1, "files": [], "links": []}
    assert load_plan(write_plan(p, tmp_path / "prep.yaml")) == p
