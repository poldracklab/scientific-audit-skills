"""Tests for audit-consensus/scripts/redact.py: blinding source runs before consensus."""
import json
import os

import pytest

from redact import (
    OTHER_PLACEHOLDER,
    aliases,
    load_models,
    outside_audit_leaks,
    plan_redaction,
    redact_run,
    remaining_leaks,
)

CLAUDE = "claude-opus-5-5"
GEMINI = "google/gemini-4-argon"


@pytest.fixture
def run(tmp_path, make_run):
    return make_run(tmp_path / "runs" / "P", "a1")


@pytest.fixture
def plan(run):
    return plan_redaction(run, CLAUDE, [GEMINI])


def _registry(tmp_path, *entries):
    path = tmp_path / "registry.jsonl"
    path.write_text("".join(json.dumps(e) + "\n" for e in entries))
    return path


def test_load_models_dedupes_and_filters_paper(tmp_path):
    a1 = {"run_id": "a1", "paper_id": "P", "model": CLAUDE}
    registry = _registry(tmp_path, a1, {"run_id": "b2", "paper_id": "P", "model": GEMINI}, a1,
                         {"run_id": "z9", "paper_id": "Other", "model": "gpt-5.6-sol"})
    assert load_models(registry, "P") == {"a1": CLAUDE, "b2": GEMINI}


def test_aliases_strip_provider_prefix():
    assert aliases(GEMINI) == ["google/gemini-4-argon", "gemini-4-argon"]
    assert aliases(CLAUDE) == [CLAUDE]


def test_plan_drops_own_aliases_from_others(run):
    plan = plan_redaction(run, CLAUDE, [CLAUDE, GEMINI])
    assert plan["own_aliases"] == [CLAUDE]
    assert plan["other_aliases"] == ["google/gemini-4-argon", "gemini-4-argon"]


def test_redacts_own_and_other_models_in_log(run, plan):
    log = run / "audit" / "agent_log.jsonl"
    log.write_text('{"model":"Claude-Opus-5-5"} see gemini-4-argon\n')
    assert redact_run(run, "a1", plan) == {"audit/agent_log.jsonl": 2}
    assert log.read_text() == '{"model":"a1"} see [redacted-model]\n'
    assert OTHER_PLACEHOLDER == "[redacted-model]"


def test_redacts_every_text_file_under_audit(run, plan):
    note = run / "audit" / "notes" / "x.md"
    note.parent.mkdir()
    note.write_text("written by claude-opus-5-5")
    redact_run(run, "a1", plan)
    assert note.read_text() == "written by a1"


def test_full_alias_replaced_before_bare(run, plan):
    log = run / "audit" / "agent_log.jsonl"
    log.write_text("openrouter/google/gemini-4-argon")
    redact_run(run, "a1", plan)
    assert log.read_text() == "openrouter/[redacted-model]"


def test_outside_audit_leak_is_reported_not_changed(run, plan):
    paper = run / "paper" / "paper.txt"
    paper.parent.mkdir()
    paper.write_text("tested with claude-opus-5-5")
    assert outside_audit_leaks(run, [CLAUDE]) == ["paper/paper.txt"]
    redact_run(run, "a1", plan)
    assert paper.read_text() == "tested with claude-opus-5-5"


def test_binary_file_hit_is_left_and_reported(run, plan):
    rds = run / "audit" / "cache" / "x.rds"
    rds.parent.mkdir()
    data = b"\xff\xfe\x00" + CLAUDE.encode() + b"\x80"
    rds.write_bytes(data)
    redact_run(run, "a1", plan)
    assert rds.read_bytes() == data
    assert remaining_leaks(run, [CLAUDE]) == ["audit/cache/x.rds"]


def test_remaining_leaks_empty_after_text_redaction(run, plan):
    (run / "audit" / "agent_log.jsonl").write_text("CLAUDE-OPUS-5-5")
    redact_run(run, "a1", plan)
    assert remaining_leaks(run, [CLAUDE, *aliases(GEMINI)]) == []


def test_redaction_is_idempotent(run, plan):
    (run / "audit" / "agent_log.jsonl").write_text("claude-opus-5-5")
    redact_run(run, "a1", plan)
    assert redact_run(run, "a1", plan) == {}


def test_read_only_file_is_redacted_and_mode_restored(run, plan):
    log = run / "audit" / "agent_log.jsonl"
    log.write_text("claude-opus-5-5")
    log.chmod(0o444)
    redact_run(run, "a1", plan)
    assert log.read_text() == "a1"
    assert log.stat().st_mode & 0o777 == 0o444


def test_mtime_untouched_for_files_without_hits(run, plan):
    qmd = run / "audit" / "audit.qmd"
    os.utime(qmd, (1_000_000, 1_000_000))
    redact_run(run, "a1", plan)
    assert qmd.stat().st_mtime == 1_000_000


def test_own_prefix_does_not_capture_other_model(run):
    plan = plan_redaction(run, "claude-opus-5", ["claude-opus-5-5"])
    log = run / "audit" / "agent_log.jsonl"
    log.write_text("me claude-opus-5, other claude-opus-5-5")
    redact_run(run, "a1", plan)
    assert log.read_text() == "me a1, other [redacted-model]"


def test_short_alias_not_matched_inside_word(run):
    plan = plan_redaction(run, "o3", [])
    log = run / "audit" / "agent_log.jsonl"
    log.write_text("photo3 and o3")
    redact_run(run, "a1", plan)
    assert log.read_text() == "photo3 and a1"
    assert remaining_leaks(run, ["o3"]) == []


def test_name_at_sentence_end_is_redacted(run, plan):
    log = run / "audit" / "agent_log.jsonl"
    log.write_text("Audited by claude-opus-5-5.")
    redact_run(run, "a1", plan)
    assert log.read_text() == "Audited by a1."


def test_version_continuation_is_not_a_match(run):
    plan = plan_redaction(run, "gpt-5", [])
    log = run / "audit" / "agent_log.jsonl"
    log.write_text("gpt-5.6 differs")
    redact_run(run, "a1", plan)
    assert log.read_text() == "gpt-5.6 differs"


def test_remaining_leaks_ignores_outside_audit(run):
    (run / "README.md").write_text("Prepared by: claude-opus-5-5")
    assert remaining_leaks(run, [CLAUDE]) == []


def test_leak_found_across_chunk_boundary(run, monkeypatch):
    import redact
    monkeypatch.setattr(redact, "CHUNK_SIZE", 16)
    data = b"\xff" * 10 + CLAUDE.encode() + b"\x80" * 30
    (run / "data.bin").write_bytes(data)
    assert outside_audit_leaks(run, [CLAUDE]) == ["data.bin"]


def test_no_false_leak_when_chunk_splits_a_longer_word(run, monkeypatch):
    import redact
    monkeypatch.setattr(redact, "CHUNK_SIZE", 12)
    (run / "data.bin").write_bytes(b"\xff" * 10 + b"o3x" + b"\x80" * 20)
    assert outside_audit_leaks(run, ["o3"]) == []


def test_file_that_is_only_the_name_is_a_leak(run):
    (run / "audit" / "name.bin").write_bytes(CLAUDE.encode())
    assert remaining_leaks(run, [CLAUDE]) == ["audit/name.bin"]
