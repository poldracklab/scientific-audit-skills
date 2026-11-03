import json
import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import accept_all_problems, review_plan
from corpus import init_root
from manifest import is_prepared
from prepare import Clients, PlanError, checked_plan, finalize, run_prep, scan_folder, skill_commit
from review import ReviewError
from scan import load_plan, write_plan

REPO = Path(__file__).resolve().parent.parent
PREP = REPO / "audit-prep" / "scripts" / "prep.py"

def _edit_plan(prepped, edit):
    plan = load_plan(prepped.raw / "prep.yaml")
    edit(plan)
    write_plan(plan, prepped.raw / "prep.yaml")



def _run(p):
    return run_prep(p.raw, p.corpus, p.clients)


def _prepared(p):
    return p.corpus.prepared_dir(p.raw.name)


def test_scan_writes_plan_and_statements(prepped_raw):
    assert (prepped_raw.raw / "prep.yaml").is_file()
    assert "Data availability" in (prepped_raw.raw / "statements.md").read_text()
    plan_paths = {f["path"] for f in load_plan(prepped_raw.raw / "prep.yaml")["files"]}
    assert "statements.md" not in plan_paths and "prep.yaml" not in plan_paths


def test_run_refuses_unreviewed_plan(prepped_raw):
    with pytest.raises(PlanError, match="reviewed_by"):
        _run(prepped_raw)
    assert prepped_raw.raw.exists()


GHOST = {"path": "ghost.csv", "role": "data", "needs_review": False, "reason": "typo", "order": None}


def test_run_refuses_plan_listing_a_missing_file(reviewed_raw):
    _edit_plan(reviewed_raw, lambda plan: plan["files"].append(dict(GHOST)))
    with pytest.raises(PlanError, match="ghost.csv: listed in prep.yaml but not found"):
        _run(reviewed_raw)
    assert reviewed_raw.raw.exists()


def test_rerun_accepts_files_already_in_prepared_layout(reviewed_raw):
    _run(reviewed_raw)
    prepared = _prepared(reviewed_raw)
    plan = load_plan(prepared / "prep.yaml")
    plan["files"].append(dict(GHOST))
    write_plan(plan, prepared / "prep.yaml")
    with pytest.raises(PlanError) as err:
        run_prep(prepared, reviewed_raw.corpus, reviewed_raw.clients)
    assert str(err.value).count("not found") == 1 and "ghost.csv" in str(err.value)


def test_dry_run_moves_nothing(reviewed_raw, capsys):
    run_prep(reviewed_raw.raw, reviewed_raw.corpus, reviewed_raw.clients, dry_run=True)
    out = capsys.readouterr().out
    assert reviewed_raw.raw.exists() and not _prepared(reviewed_raw).exists()
    assert "paper/paper.pdf" in out and "FETCH" in out and "CONVERT" in out


LAYOUT = [
    "manifest.json", "prep.yaml", "paper/paper.pdf", "paper/paper.txt", "paper/pages/p-001.png",
    "paper/supplement_1.pdf", "paper/supplement_1.txt", "paper/metadata.json", "paper/links.json",
    "paper/statements.md", "github/lab__repo/.git", "data/osf_abcde/data/trials.csv",
]


def test_run_produces_layout(reviewed_raw):
    m = _run(reviewed_raw)
    p = _prepared(reviewed_raw)
    assert not reviewed_raw.raw.exists()
    for rel in LAYOUT:
        assert (p / rel).exists(), rel
    assert not (p / "statements.md").exists()
    assert m["documents"]["paper"]["original_name"] == "paper.pdf" and m["prepared_by"] == "human"
    assert m["preregistration"][0]["source"] == "osf" and m["preregistration"][0]["status"] == "ok"


def test_run_records_documents_and_fetches(reviewed_raw):
    m = _run(reviewed_raw)
    paper = m["documents"]["paper"]
    assert paper["path"] == "paper/paper.pdf" and paper["pages"] == 2
    assert paper["conversions"] == {"text": "ok", "pages": "ok", "structured": "failed", "statements": "skipped"}
    supp = m["documents"]["supplements"][0]
    assert supp["original_name"] == "paper_sm.pdf" and supp["path"] == "paper/supplement_1.pdf"
    assert supp["conversions"]["statements"] == "not_applicable"
    assert (_prepared(reviewed_raw) / "paper/supplement_1/pages/p-001.png").is_file()
    assert m["code"][0]["path"] == "github/lab__repo" and m["code"][0]["status"] == "ok"
    assert {d["source"]: d["path"] for d in m["data"]} == {"osf": "data/osf_abcde", "zenodo": "data/zenodo_123456"}


def test_statements_regenerated_when_missing(reviewed_raw):
    (reviewed_raw.raw / "statements.md").unlink()
    m = _run(reviewed_raw)
    assert m["documents"]["paper"]["conversions"]["statements"] == "ok"
    assert "Data availability" in (_prepared(reviewed_raw) / "paper/statements.md").read_text()


def test_links_augmented_with_fetch_status(reviewed_raw):
    m = _run(reviewed_raw)
    by_canonical = {link["canonical"]: link for link in m["links"]}
    assert by_canonical["https://osf.io/abcde"]["fetched_to"] == "data/osf_abcde"
    assert by_canonical["https://osf.io/abcde"]["status"] == "partial"
    assert by_canonical["https://github.com/lab/hidden-tool"]["status"] == "skipped"
    assert by_canonical["https://github.com/lab/hidden-tool"]["fetched_to"] is None
    relation = [link for link in m["links"] if "10.1101/2020.01.01.123456" in link["url"]]
    assert relation and relation[0]["status"] == "skipped" and relation[0]["role"] == "unknown"
    assert relation[0]["class"] == "doi" and "crossref relation has-preprint" in relation[0]["reason"]
    links_json = json.loads((_prepared(reviewed_raw) / "paper/links.json").read_text())
    assert links_json == m["links"]


def test_metadata_json_is_crossref_record(reviewed_raw):
    m = _run(reviewed_raw)
    meta = json.loads((_prepared(reviewed_raw) / "paper/metadata.json").read_text())
    assert meta["doi"] == "10.1126/sciadv.abf4355" and m["metadata"] == meta


def test_plan_fields_copied_to_manifest(reviewed_raw):
    dates = {"start": "2019-01", "end": "2019-06", "source_quote": "We tested in 2019.", "page": 3}
    _edit_plan(reviewed_raw, lambda plan: plan.update(data_collection=dates))
    m = _run(reviewed_raw)
    assert m["data_collection"] == dates and m["prep_versions"] == {"skill": skill_commit()}


def _add_figshare(plan):
    plan["links"].append({"url": "https://figshare.com/x/1", "canonical": "https://figshare.com/x/1",
                          "class": "figshare", "role": "data", "needs_review": False, "found_in": [], "reason": "t"})


def test_unsupported_data_source_recorded(reviewed_raw):
    _edit_plan(reviewed_raw, _add_figshare)
    m = _run(reviewed_raw)
    fig = [d for d in m["data"] if d["source"] == "figshare"][0]
    assert fig["status"] == "unsupported" and fig["path"] is None and fig["files"] == []
    assert fig["reason"] == "no fetcher for figshare; fetch manually if needed"


def test_fetch_exception_recorded_as_warning(reviewed_raw, monkeypatch):
    import fetch_links

    def boom(*args, **kwargs):
        raise RuntimeError("zenodo down")

    monkeypatch.setattr(fetch_links.fetch_zenodo, "fetch_zenodo", boom)
    m = _run(reviewed_raw)
    zen = [d for d in m["data"] if d["source"] == "zenodo"][0]
    assert zen["status"] == "failed" and "zenodo down" in zen["reason"]
    assert any("zenodo down" in w for w in m["warnings"])


def test_residue_moved_to_unsorted(reviewed_residue):
    m = _run(reviewed_residue)
    unsorted = reviewed_residue.corpus.unsorted_dir(reviewed_residue.raw.name)
    assert (unsorted / ".venv").exists() and (unsorted / "paper.txt").is_file()
    assert {u["original_path"] for u in m["unsorted"]} == {".git", ".venv", "paper.txt"}
    assert (_prepared(reviewed_residue) / "paper/paper.txt").read_text() != "text dump of paper.pdf\n"


def test_local_data_and_preexisting_archive(reviewed_data_archive):
    m = _run(reviewed_data_archive)
    p = _prepared(reviewed_data_archive)
    assert (p / "data/mydata").is_dir() and (p / "data/mydata.tar.gz").is_file()
    assert [a["extracted"] for a in m["local_data"] if a.get("archive")] == ["pre-existing"]
    assert {"original_path": "mydata", "path": "data/mydata"} in m["local_data"]


def _drop_file(path):
    return lambda plan: plan.update(files=[f for f in plan["files"] if f["path"] != path])


def test_archive_extracted_when_no_sibling(make_prepped, bare_repo):
    p = make_prepped("paper_data_archive")
    shutil.rmtree(p.raw / "mydata")
    _edit_plan(p, _drop_file("mydata"))
    m = _run(review_plan(p, bare_repo))
    assert (_prepared(p) / "data/mydata/mydata/trials.csv").is_file()
    assert [a["extracted"] for a in m["local_data"] if a.get("archive")] == ["ok"]


def test_nested_archive_listed_not_extracted(make_prepped, bare_repo):
    p = make_prepped("paper_data_archive")
    shutil.move(p.raw / "mydata.tar.gz", p.raw / "mydata" / "inner.tar.gz")
    _edit_plan(p, _drop_file("mydata.tar.gz"))
    m = _run(review_plan(p, bare_repo))
    assert {"path": "data/mydata/inner.tar.gz", "nested_archive": True} in m["local_data"]
    assert not (_prepared(p) / "data/mydata/inner").exists()


def test_rerun_after_move_resumes(reviewed_raw):
    first = _run(reviewed_raw)
    m2 = _run(reviewed_raw)
    assert m2["documents"]["paper"]["conversions"]["text"] == "skipped"
    assert len(m2["data"]) == len(first["data"]) and len(m2["links"]) == len(first["links"])
    assert len(m2["local_data"]) == len(first["local_data"]) and m2["code"][0]["status"] == "skipped"


def test_finalize_sets_readonly_and_hashes(reviewed_raw, writable_after):
    _run(reviewed_raw)
    p = _prepared(reviewed_raw)
    writable_after(p)
    accept_all_problems(p)
    m = finalize(p)
    assert m["finalized"] and is_prepared(p) and (p / "README.md").is_file()
    assert not os.access(p / "paper/paper.pdf", os.W_OK)
    assert not os.access(p / "paper", os.W_OK) and os.access(p / "paper", os.R_OK | os.X_OK)
    assert {f["path"] for f in m["files"]} >= {"paper/paper.pdf", "prep.yaml"}


def _cli(*args, cwd):
    cmd = ["uv", "run", "--quiet", str(PREP), *map(str, args)]
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=300)


def test_cli_init_scan_run_finalize(tmp_path, raw_folder):
    root = tmp_path / "corpus"
    assert _cli("init", root, cwd=tmp_path).returncode == 0
    assert (root / ".autoaudit-root").is_file()
    raw = Path(shutil.move(raw_folder("paper_nodoi"), root / "Paper_2024"))
    scanned = _cli("scan", raw, "--root", root, cwd=tmp_path)
    assert scanned.returncode == 0, scanned.stderr
    assert (raw / "prep.yaml").is_file() and (raw / "statements.md").is_file()
    assert "paper_id: Paper_2024" in scanned.stdout
    ran = _cli("run", raw, "--root", root, cwd=tmp_path)
    assert ran.returncode == 2 and "reviewed_by" in ran.stderr
    fin = _cli("finalize", raw, "--root", root, cwd=tmp_path)
    assert fin.returncode == 2 and fin.stderr


def test_cli_refuses_without_root(tmp_path, raw_folder):
    res = _cli("scan", raw_folder("paper_nodoi"), cwd=tmp_path)
    assert res.returncode == 2 and "init" in res.stderr


def _links_json(p):
    return {link["canonical"]: link for link in json.loads((_prepared(p) / "paper/links.json").read_text())}


def test_listed_only_status_kept_in_links(reviewed_raw):
    _edit_plan(reviewed_raw, lambda plan: plan["size_policy"].update(max_source_mb=0))
    m = _run(reviewed_raw)
    osf = _links_json(reviewed_raw)["https://osf.io/abcde"]
    assert osf["status"] == "listed_only" and osf["fetched_to"] is None
    assert {link["canonical"]: link for link in m["links"]}["https://osf.io/abcde"] == osf


def test_unsupported_status_and_url_kept(reviewed_raw):
    _edit_plan(reviewed_raw, _add_figshare)
    m = _run(reviewed_raw)
    fig = [d for d in m["data"] if d["source"] == "figshare"][0]
    assert fig["status"] == "unsupported" and fig["url"] == "https://figshare.com/x/1"
    link = _links_json(reviewed_raw)["https://figshare.com/x/1"]
    assert link["status"] == "unsupported" and link["fetched_to"] is None


def test_finalize_failure_leaves_folder_unprepared(reviewed_raw, monkeypatch, writable_after):
    import manifest

    _run(reviewed_raw)
    p = _prepared(reviewed_raw)
    writable_after(p)
    accept_all_problems(p)
    original = manifest.render_readme

    def boom(m):
        raise RuntimeError("readme failed")

    monkeypatch.setattr(manifest, "render_readme", boom)
    with pytest.raises(RuntimeError, match="readme failed"):
        finalize(p)
    assert not is_prepared(p)
    monkeypatch.setattr(manifest, "render_readme", original)
    m = finalize(p)
    assert m["finalized"] and is_prepared(p) and not os.access(p / "manifest.json", os.W_OK)


SCRIPTS = REPO / "audit-prep" / "scripts"


def test_prep_versions_records_skill_commit(reviewed_raw):
    head = subprocess.run(["git", "-C", str(SCRIPTS), "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()
    assert head and _run(reviewed_raw)["prep_versions"]["skill"] == head


def test_skill_commit_none_outside_a_repo(tmp_path):
    from prepare import skill_commit

    assert skill_commit(tmp_path) is None


def test_run_prep_records_review_and_finalize_refuses(reviewed_raw, writable_after):
    _edit_plan(reviewed_raw, _add_figshare)
    m = _run(reviewed_raw)
    assert m["review"]["status"] == "failed"
    assert "data figshare https://figshare.com/x/1" in [p["item"] for p in m["review"]["problems"]]
    p = _prepared(reviewed_raw)
    writable_after(p)
    with pytest.raises(ReviewError, match="accept_failures:"):
        finalize(p)
    assert json.loads((p / "manifest.json").read_text())["finalized"] is False
    accept_all_problems(p)
    m = finalize(p)
    assert m["finalized"] is True and m["review"]["status"] == "ok"
    assert len(m["review"]["accepted"]) >= 1
    readme = (p / "README.md").read_text()
    assert "## Prep review" in readme and "test environment" in readme


def test_plan_rejects_empty_acceptance_reason(reviewed_raw):
    _edit_plan(reviewed_raw, lambda plan: plan.update(accept_failures={"data osf abcde": ""}))
    with pytest.raises(PlanError, match="accept_failures: data osf abcde: reason required"):
        checked_plan(reviewed_raw.raw, reviewed_raw.corpus)
