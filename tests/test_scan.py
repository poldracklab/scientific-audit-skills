import pytest

from scan import annotate_osf_links, build_plan, classify_files, has_supplement_marker, load_plan, unresolved, write_plan

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


def test_bare_host_link_reason():
    import links
    from scan import _link_dict

    entry = _link_dict(links.make_link("https://osf.io/", "p.pdf", 7), None)
    assert (entry["role"], entry["needs_review"]) == ("skip", False)
    assert entry["reason"] == "bare host, no identifier (likely a line-wrapped URL)"


ZENODO_LINK = "https://doi.org/10.5281/zenodo.4432816"
ARTICLE_LINK = "https://doi.org/10.1126/sciadv.abf4355"


@pytest.fixture
def crossref_only_article(crossref_fixture):
    """Crossref knows the article DOI; every other DOI is a 404 (DataCite deposits are not in Crossref)."""
    import urllib.error

    def get_json(url):
        if url.endswith("10.1126/sciadv.abf4355"):
            return crossref_fixture
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

    return get_json


def _links(plan):
    return {l["canonical"]: l for l in plan["links"]}


def _paper(plan):
    return [f for f in plan["files"] if f["role"] == "paper"][0]


def test_deposit_doi_is_never_the_paper_doi(raw_folder, crossref_only_article):
    plan = build_plan(raw_folder("paper_deposit_doi"), get_json=crossref_only_article)
    assert plan["doi"] is None and _paper(plan)["needs_review"] is True
    zenodo = _links(plan)[ZENODO_LINK]
    assert zenodo["role"] != "skip" and zenodo["reason"] != "the paper's own doi"


def test_article_doi_found_after_deposit_doi(raw_folder, crossref_only_article):
    plan = build_plan(raw_folder("paper_deposit_then_article"), get_json=crossref_only_article)
    assert plan["doi"] == "10.1126/sciadv.abf4355" and _paper(plan)["needs_review"] is False
    assert _links(plan)[ZENODO_LINK]["role"] != "skip"
    assert _links(plan)[ARTICLE_LINK]["role"] == "skip"


def test_own_doi_not_skipped_when_crossref_unconfirmed(raw_folder):
    def failing(url):
        raise OSError("boom")

    plan = build_plan(raw_folder("paper_supp"), get_json=failing)
    own = _links(plan)[ARTICLE_LINK]
    assert own["role"] != "skip" and own["needs_review"] is True


def test_own_doi_skipped_when_journal_article(raw_folder, crossref_fixture):
    plan = build_plan(raw_folder("paper_supp"), get_json=lambda u: crossref_fixture)
    own = _links(plan)[ARTICLE_LINK]
    assert (own["role"], own["needs_review"], own["reason"]) == ("skip", False, "the paper's own doi")


def _dir_with(raw, name, files):
    folder = raw / name
    folder.mkdir(parents=True)
    for f in files:
        (folder / f).write_text("x\n")
    return folder


@pytest.mark.parametrize("name", ["audit-fable", "figs_paper", "paper_files", ".quarto", "renv", "node_modules",
                                  ".ipynb_checkpoints", "osf_prereg", "venv", ".Rproj.user"])
def test_legacy_audit_dirs_are_residue(tmp_path, name):
    _dir_with(tmp_path, name, ["out.html"])
    entry = classify_files(tmp_path)[0]
    assert (entry["role"], entry["needs_review"]) == ("unsorted", False)


@pytest.mark.parametrize("name", ["Smith_audit.qmd", "Smith_audit.html", ".Rhistory"])
def test_legacy_audit_files_are_residue(tmp_path, name):
    (tmp_path / name).write_text("x\n")
    assert classify_files(tmp_path)[0]["role"] == "unsorted"


def test_dir_of_code_and_html_needs_review(tmp_path):
    _dir_with(tmp_path, "analysis", ["run.py", "report.html"])
    entry = classify_files(tmp_path)[0]
    assert (entry["role"], entry["needs_review"], entry["reason"]) == ("data", True, "directory: data or residue?")


def test_dir_of_csv_is_data(tmp_path):
    _dir_with(tmp_path, "behav", ["trials.csv"])
    (tmp_path / "behav" / "sub").mkdir()
    (tmp_path / "behav" / "sub" / "bold.nii.gz").write_text("x\n")
    entry = classify_files(tmp_path)[0]
    assert (entry["role"], entry["needs_review"]) == ("data", False)


def test_empty_dir_needs_review(tmp_path):
    (tmp_path / "empty").mkdir()
    assert classify_files(tmp_path)[0]["needs_review"] is True


@pytest.fixture
def settled_plan(raw_folder, crossref_fixture):
    plan = build_plan(raw_folder("paper_supp"), get_json=lambda u: crossref_fixture)
    for item in plan["files"] + plan["links"]:
        item["needs_review"] = False
    plan["reviewed_by"] = "human"
    assert unresolved(plan) == []
    return plan


def _file(plan, path):
    return next(f for f in plan["files"] if f["path"] == path)


def test_unresolved_rejects_unknown_file_role(settled_plan):
    _file(settled_plan, "paper_sm.pdf")["role"] = "supplementary"
    assert unresolved(settled_plan) == [
        "paper_sm.pdf: unknown role 'supplementary' (allowed: paper, supplement, data, archive, unsorted, skip)"]


def test_unresolved_rejects_unknown_link_role_and_class(settled_plan):
    link = settled_plan["links"][0]
    link["role"], link["class"] = "dataset", "dropbox"
    msgs = unresolved(settled_plan)
    assert f"{link['url']}: unknown role 'dataset' (allowed: prereg, code, data, unknown, skip)" in msgs
    assert any(m.startswith(f"{link['url']}: unknown class 'dropbox'") for m in msgs)


@pytest.mark.parametrize("order", [None, "1", 1.5, True])
def test_unresolved_rejects_bad_supplement_order(settled_plan, order):
    _file(settled_plan, "paper_sm.pdf")["order"] = order
    assert unresolved(settled_plan) == ["paper_sm.pdf: supplement order must be an integer"]


def test_unresolved_rejects_duplicate_supplement_order(settled_plan):
    settled_plan["files"].append({"path": "other_sm.pdf", "role": "supplement", "needs_review": False,
                                  "reason": "r", "order": 1})
    assert unresolved(settled_plan) == ["supplement order 1 is used more than once"]


def test_unresolved_rejects_two_papers(settled_plan):
    _file(settled_plan, "paper_sm.pdf").update(role="paper", order=None)
    assert unresolved(settled_plan) == ["more than one file with role paper"]


@pytest.fixture
def crossref_and_osf(osf_api, crossref_fixture):
    """Crossref knows the article DOI; every other URL goes to the recorded OSF routes (guids included)."""
    def get_json(url):
        return crossref_fixture if url.endswith("10.1126/sciadv.abf4355") else osf_api(url)

    return get_json


def _review_fields(link):
    return link["role"], link["needs_review"], link["reason"]


def test_scan_resolves_osf_links(raw_folder, crossref_and_osf):
    canon = _links(build_plan(raw_folder("paper_supp"), get_json=crossref_and_osf))
    assert _review_fields(canon["https://osf.io/abcde"]) == ("data", False, 'osf project "Trial data project"')
    assert _review_fields(canon["https://osf.io/x4c56"]) == (
        "prereg", False, 'osf registration "Preregistration: trial study"')


def _osf_plan_link(url, page):
    import links
    from scan import _link_dict

    return _link_dict(links.make_link(url, "paper.pdf", page), None)


def test_scan_adds_parent_project_for_file_links(osf_fixture):
    plan_links = [_osf_plan_link("https://osf.io/38vzr", 3), _osf_plan_link("https://osf.io/k9pqr", 5)]
    annotated = annotate_osf_links(plan_links, lambda u: osf_fixture("osf_guid_file.json"))
    assert len(annotated) == 3
    for child in annotated[:2]:
        assert _review_fields(child) == ("data", False, "osf file space_figure_3b.csv in project xu48j")
    parent = annotated[2]
    assert parent["canonical"] == "https://osf.io/xu48j" and parent["class"] == "osf" and parent["role"] == "data"
    assert parent["needs_review"] is True and parent["reason"].startswith("parent project of osf file links")
    assert "38vzr" in parent["reason"] and "k9pqr" in parent["reason"]
    assert parent["found_in"] == [{"file": "paper.pdf", "page": 3}, {"file": "paper.pdf", "page": 5}]


def test_scan_parent_project_not_duplicated(osf_api):
    plan_links = [_osf_plan_link("https://osf.io/38vzr", 3), _osf_plan_link("https://osf.io/xu48j", 4)]
    annotated = annotate_osf_links(plan_links, osf_api)
    assert [l["canonical"] for l in annotated] == ["https://osf.io/38vzr", "https://osf.io/xu48j"]


def test_scan_keeps_link_when_resolution_fails(raw_folder, crossref_only_article):
    canon = _links(build_plan(raw_folder("paper_supp"), get_json=crossref_only_article))
    assert _review_fields(canon["https://osf.io/abcde"]) == ("data", True, "osf project or registration?")
    link = _osf_plan_link("https://osf.io/abcde", 1)
    before = dict(link)

    def failing(url):
        raise OSError("boom")

    assert annotate_osf_links([link], failing) == [before]
