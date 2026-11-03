"""Tests for audit-consensus/scripts/consensus.py: preparing a consensus folder."""
import hashlib
import json
import random
from datetime import datetime, timezone

import pytest

from consensus import attach_models, main, make_consensus_id, prepare
from discover import ConsensusError

NOW = datetime(2026, 11, 3, 21, 0, 0, tzinfo=timezone.utc)
MODELS = {"a1": "claude-opus-5-5", "b2": "gpt-5.6-sol"}
UNFINISHED = ['{"type":"step_start"}']


@pytest.fixture
def corpus(tmp_path, make_run):
    root = tmp_path / "corpus"
    (root / "runs" / "P").mkdir(parents=True)
    (root / ".autoaudit-root").write_text("")
    _write_registry(root, MODELS)
    for run_id, model in MODELS.items():
        make_run(root / "runs" / "P", run_id, log_lines=[json.dumps({"model": model}), '{"type":"result"}'])
    return root


def _write_registry(root, models):
    lines = [json.dumps({"run_id": r, "paper_id": "P", "model": m}) for r, m in models.items()]
    (root / "registry.jsonl").write_text("\n".join(lines) + "\n")


def _log(root, run_id):
    return root / "runs" / "P" / run_id / "audit" / "agent_log.jsonl"


def _consensus_root(root):
    return root / "runs" / "P" / "consensus"


def test_prepare_creates_folder_and_inputs(corpus):
    out = prepare(corpus, "P", now=NOW, rng=random.Random(1))
    assert out.parent == _consensus_root(corpus)
    text = (out / "inputs.json").read_text()
    inputs = json.loads(text)
    qmd = corpus / "runs" / "P" / "a1" / "audit" / "audit.qmd"
    assert [r["run_id"] for r in inputs["runs"]] == ["a1", "b2"]
    assert inputs["runs"][0]["audit_qmd_sha256"] == hashlib.sha256(qmd.read_bytes()).hexdigest()
    assert inputs["paper_id"] == "P" and inputs["consensus_id"] == out.name
    assert "claude" not in text and "gpt" not in text


def test_prepare_redacts_logs(corpus):
    out = prepare(corpus, "P", now=NOW, rng=random.Random(1))
    assert '"a1"' in _log(corpus, "a1").read_text()
    assert json.loads((out / "inputs.json").read_text())["redactions"]["a1"] == {"audit/agent_log.jsonl": 1}


def test_prepare_skips_in_progress_run_with_warning(corpus, make_run, capsys):
    _write_registry(corpus, {**MODELS, "c3": "moonshotai/kimi-k3.1-pro"})
    running = make_run(corpus / "runs" / "P", "c3", log_lines=["kimi-k3.1-pro claude-opus-5-5", *UNFINISHED])
    before = (running / "audit" / "agent_log.jsonl").read_bytes()
    out = prepare(corpus, "P", now=NOW, rng=random.Random(1))
    assert "c3" in capsys.readouterr().err
    assert json.loads((out / "inputs.json").read_text())["skipped"] == ["c3"]
    assert (running / "audit" / "agent_log.jsonl").read_bytes() == before


def test_other_paper_runs_models_redacted_even_if_skipped(corpus, make_run):
    _write_registry(corpus, {**MODELS, "c3": "moonshotai/kimi-k3.1-pro"})
    make_run(corpus / "runs" / "P", "c3", log_lines=UNFINISHED)
    _log(corpus, "a1").write_text('mentions kimi-k3.1-pro\n{"type":"result"}\n')
    prepare(corpus, "P", now=NOW, rng=random.Random(1))
    assert "kimi" not in _log(corpus, "a1").read_text()


def test_prepare_needs_two_completed_runs(corpus):
    _log(corpus, "b2").write_text("\n".join(UNFINISHED))
    with pytest.raises(ConsensusError, match="at least 2"):
        prepare(corpus, "P", now=NOW)
    assert not _consensus_root(corpus).exists()


def test_prepare_stops_on_mismatched_manifests(corpus):
    (corpus / "runs" / "P" / "b2" / "run.json").write_text(json.dumps({"run_id": "b2", "manifest_sha256": "other"}))
    with pytest.raises(ConsensusError):
        prepare(corpus, "P", now=NOW)
    assert "claude-opus-5-5" in _log(corpus, "a1").read_text()


def test_prepare_stops_on_run_missing_from_registry(corpus):
    _write_registry(corpus, {"a1": MODELS["a1"]})
    with pytest.raises(ConsensusError, match="b2"):
        prepare(corpus, "P", now=NOW)
    assert "claude-opus-5-5" in _log(corpus, "a1").read_text()
    assert not _consensus_root(corpus).exists()


def test_prepare_stops_on_leak_outside_audit(corpus):
    paper = corpus / "runs" / "P" / "b2" / "paper" / "paper.txt"
    paper.parent.mkdir()
    paper.write_text("compared against GPT-5.6-sol")
    with pytest.raises(ConsensusError, match="paper/paper.txt"):
        prepare(corpus, "P", now=NOW)
    assert "claude-opus-5-5" in _log(corpus, "a1").read_text()


def test_prepare_stops_if_leak_survives_redaction(corpus):
    rds = corpus / "runs" / "P" / "a1" / "audit" / "cache.rds"
    rds.write_bytes(b"\xff\x80claude-opus-5-5")
    with pytest.raises(ConsensusError, match="cache.rds"):
        prepare(corpus, "P", now=NOW)
    assert not _consensus_root(corpus).exists()


def test_prepare_twice_gives_distinct_folders(corpus):
    first = prepare(corpus, "P", now=NOW, rng=random.Random(1))
    first_inputs = (first / "inputs.json").read_text()
    second = prepare(corpus, "P", now=NOW, rng=random.Random(2))
    assert first != second
    assert (first / "inputs.json").read_text() == first_inputs
    assert json.loads((second / "inputs.json").read_text())["redactions"] == {"a1": {}, "b2": {}}


def test_consensus_ids_sort_chronologically():
    later = NOW.replace(hour=22)
    ids = [make_consensus_id(later, random.Random(1)), make_consensus_id(NOW, random.Random(2))]
    assert sorted(ids)[0].startswith("20261103T210000Z-")
    assert len(ids[0].split("-")[1]) == 4


def test_attach_models_writes_mapping(corpus):
    out = prepare(corpus, "P", now=NOW, rng=random.Random(1))
    path = attach_models(corpus, out)
    assert path == out / "run_models.json"
    assert json.loads(path.read_text()) == MODELS


def test_cli_prepare_prints_folder(corpus, monkeypatch, capsys):
    monkeypatch.chdir(corpus)
    assert main(["prepare", "P"]) == 0
    out = capsys.readouterr().out.strip()
    assert (corpus / "runs" / "P" / "consensus").resolve() in [p.resolve() for p in [__import__("pathlib").Path(out).parent]]


def test_cli_error_exits_2(corpus, monkeypatch, capsys):
    monkeypatch.chdir(corpus)
    _write_registry(corpus, {"a1": MODELS["a1"]})
    assert main(["prepare", "P"]) == 2
    assert capsys.readouterr().err.startswith("error:")


def test_cli_requires_corpus_root(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["prepare", "P"]) == 2
    assert ".autoaudit-root" in capsys.readouterr().err


def test_identical_provenance_outside_audit_is_allowed(corpus):
    for run_id in MODELS:
        run = corpus / "runs" / "P" / run_id
        (run / "README.md").write_text("- Prepared by: claude-opus-5-5\n")
        (run / "prep.yaml").write_text("reviewed_by: claude-opus-5-5\n")
        (run / "manifest.json").write_text('{"prepared_by": "claude-opus-5-5"}')
    out = prepare(corpus, "P", now=NOW, rng=random.Random(1))
    assert out.is_dir()
    assert (corpus / "runs" / "P" / "a1" / "README.md").read_text() == "- Prepared by: claude-opus-5-5\n"


def test_differing_file_outside_audit_still_stops(corpus):
    for run_id, text in [("a1", "made by claude-opus-5-5"), ("b2", "made by gpt-5.6-sol")]:
        (corpus / "runs" / "P" / run_id / "notes.txt").write_text(text)
    with pytest.raises(ConsensusError, match="notes.txt"):
        prepare(corpus, "P", now=NOW)
