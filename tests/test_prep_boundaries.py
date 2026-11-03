"""Preparation preserves sources and includes only explicitly selected artifacts."""
from pathlib import Path

import pytest

from conftest import accept_all_problems
from corpus import CorpusError
from manifest import hash_tree
from prepare import PlanError, finalize, run_prep
from scan import load_plan, write_plan
from verify_run import verify


def _append_file(raw, name, role):
    plan = load_plan(raw / "prep.yaml")
    plan["files"].append({"path": name, "role": role, "needs_review": False,
                          "reason": "reviewed", "order": None})
    write_plan(plan, raw / "prep.yaml")


def test_skipped_and_unlisted_files_never_enter_prepared(reviewed_raw):
    raw = reviewed_raw.raw
    (raw / "earlier-audit.txt").write_text("prior answer")
    (raw / "unlisted.txt").write_text("not reviewed")
    _append_file(raw, "earlier-audit.txt", "skip")
    before = {p.relative_to(raw): p.read_bytes() for p in raw.rglob("*") if p.is_file()}
    run_prep(raw, reviewed_raw.corpus, reviewed_raw.clients)
    prepared = reviewed_raw.corpus.prepared_dir(raw.name)
    assert not (prepared / "earlier-audit.txt").exists()
    assert not (prepared / "unlisted.txt").exists()
    assert {p.relative_to(raw): p.read_bytes() for p in raw.rglob("*") if p.is_file()} == before


def test_local_directory_named_data_needs_no_parking(reviewed_raw):
    raw = reviewed_raw.raw
    (raw / "data").mkdir()
    (raw / "data/trials.csv").write_text("trial\n1\n")
    _append_file(raw, "data", "data")
    run_prep(raw, reviewed_raw.corpus, reviewed_raw.clients)
    prepared = reviewed_raw.corpus.prepared_dir(raw.name)
    assert (raw / "data/trials.csv").is_file()
    assert (prepared / "data/data/trials.csv").read_text() == "trial\n1\n"
    assert not list(prepared.glob(".parked-*"))


@pytest.mark.parametrize("nested", [False, True])
def test_selected_symlink_is_rejected_before_copy(reviewed_raw, tmp_path, nested):
    raw = reviewed_raw.raw
    outside = tmp_path / "outside.txt"
    outside.write_text("external")
    if nested:
        (raw / "inputs").mkdir()
        (raw / "inputs/link").symlink_to(outside)
        name = "inputs"
    else:
        (raw / "link").symlink_to(outside)
        name = "link"
    _append_file(raw, name, "data")
    with pytest.raises((PlanError, CorpusError), match="symlink"):
        run_prep(raw, reviewed_raw.corpus, reviewed_raw.clients)
    assert not reviewed_raw.corpus.prepared_dir(raw.name).exists()
    assert outside.read_text() == "external"


def test_changed_file_selection_requires_fresh_draft(reviewed_raw):
    raw, corpus = reviewed_raw.raw, reviewed_raw.corpus
    run_prep(raw, corpus, reviewed_raw.clients)
    prepared = corpus.prepared_dir(raw.name)
    plan = load_plan(prepared / "prep.yaml")
    next(f for f in plan["files"] if f["role"] == "supplement")["role"] = "skip"
    write_plan(plan, prepared / "prep.yaml")
    with pytest.raises(PlanError, match="file selection changed.*fresh draft"):
        run_prep(prepared, corpus, reviewed_raw.clients)


def test_changed_raw_input_requires_fresh_draft(reviewed_raw):
    raw, corpus = reviewed_raw.raw, reviewed_raw.corpus
    run_prep(raw, corpus, reviewed_raw.clients)
    (raw / "paper.pdf").write_bytes(b"replacement")
    with pytest.raises(PlanError, match="raw inputs changed.*fresh draft"):
        run_prep(raw, corpus, reviewed_raw.clients)


def test_finalize_refuses_downloaded_symlink(reviewed_raw):
    run_prep(reviewed_raw.raw, reviewed_raw.corpus, reviewed_raw.clients)
    prepared = reviewed_raw.corpus.prepared_dir(reviewed_raw.raw.name)
    (prepared / "data/external").symlink_to(reviewed_raw.raw)
    accept_all_problems(prepared)
    with pytest.raises(CorpusError, match="symlink"):
        finalize(prepared)


def test_hash_tree_refuses_dangling_symlink(tmp_path):
    (tmp_path / "dangling").symlink_to(tmp_path / "absent")
    with pytest.raises(CorpusError, match="symlink"):
        hash_tree(tmp_path)


def test_verifier_rejects_extra_symlink(run_folder, tmp_path):
    (run_folder / "external").symlink_to(tmp_path)
    status, details = verify(run_folder)
    assert status == "run_dirty"
    assert any("symlink" in detail for detail in details)


def test_additional_evidence_does_not_change_prepared_input(run_folder):
    evidence = run_folder / "audit/additional-evidence"
    evidence.mkdir()
    (evidence / "replication.txt").write_text("Retrieved evidence")
    (evidence / "sources.md").write_text("URL | Retrieved | Local file | Findings\n")
    assert verify(run_folder) == ("run_ok", [])


def test_structured_conversion_can_be_disabled(reviewed_raw, monkeypatch):
    import docs

    plan = load_plan(reviewed_raw.raw / "prep.yaml")
    plan["structured_conversion"] = False
    write_plan(plan, reviewed_raw.raw / "prep.yaml")

    def unexpected(*args, **kwargs):
        pytest.fail("structured conversion was explicitly disabled")

    monkeypatch.setattr(docs, "pdf_to_structured", unexpected)
    m = run_prep(reviewed_raw.raw, reviewed_raw.corpus, reviewed_raw.clients)
    assert m["documents"]["paper"]["conversions"]["structured"] == "not_requested"
    assert not any("structured" in p["item"] for p in m["review"]["problems"])


def test_structured_conversion_option_is_boolean(reviewed_raw):
    plan = load_plan(reviewed_raw.raw / "prep.yaml")
    plan["structured_conversion"] = "false"
    write_plan(plan, reviewed_raw.raw / "prep.yaml")
    with pytest.raises(PlanError, match="structured_conversion must be a boolean"):
        run_prep(reviewed_raw.raw, reviewed_raw.corpus, reviewed_raw.clients)


def test_conversion_choice_is_fixed_for_draft(reviewed_raw):
    raw, corpus = reviewed_raw.raw, reviewed_raw.corpus
    run_prep(raw, corpus, reviewed_raw.clients)
    prepared = corpus.prepared_dir(raw.name)
    plan = load_plan(prepared / "prep.yaml")
    plan["structured_conversion"] = False
    write_plan(plan, prepared / "prep.yaml")
    with pytest.raises(PlanError, match="conversion choice changed.*fresh draft"):
        run_prep(prepared, corpus, reviewed_raw.clients)


@pytest.mark.parametrize("name", ["../outside.txt", "/tmp/outside.txt", "nested/file.txt", ".."])
def test_plan_paths_must_be_top_level_raw_names(reviewed_raw, name):
    from prepare import checked_plan

    _append_file(reviewed_raw.raw, name, "data")
    with pytest.raises(PlanError, match="top-level name"):
        checked_plan(reviewed_raw.raw, reviewed_raw.corpus)


def test_rerun_rejects_symlink_before_writing_outside_draft(reviewed_raw, tmp_path):
    raw, corpus = reviewed_raw.raw, reviewed_raw.corpus
    run_prep(raw, corpus, reviewed_raw.clients)
    external = tmp_path / "external.pdf"
    external.write_bytes(b"untouched")
    copied = corpus.prepared_dir(raw.name) / "paper/paper.pdf"
    copied.unlink()
    copied.symlink_to(external)
    with pytest.raises(CorpusError, match="symlink"):
        run_prep(raw, corpus, reviewed_raw.clients)
    assert external.read_bytes() == b"untouched"
