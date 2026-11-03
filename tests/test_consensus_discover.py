"""Tests for audit-consensus/scripts/discover.py: finding completed audit runs."""
import pytest

from discover import ConsensusError, check_same_manifest, completed_runs, find_runs, is_completed, log_finished

CLAUDE_DONE = '{"type":"result","subtype":"success","result":"done"}'


@pytest.fixture
def paper_runs(tmp_path):
    path = tmp_path / "runs" / "Smith_2021"
    path.mkdir(parents=True)
    return path


def _log(tmp_path, *lines):
    log = tmp_path / "agent_log.jsonl"
    log.write_text("".join(l + "\n" for l in lines))
    return log


def test_find_runs_ignores_dirs_without_run_json(paper_runs, make_run):
    make_run(paper_runs, "b2")
    make_run(paper_runs, "a1")
    (paper_runs / "consensus" / "20261103T000000Z-abcd").mkdir(parents=True)
    (paper_runs / "stray").mkdir()
    assert [p.name for p in find_runs(paper_runs)] == ["a1", "b2"]


def test_run_without_html_is_not_completed(paper_runs, make_run):
    assert not is_completed(make_run(paper_runs, "a1", html=False))


def test_run_without_log_is_completed(paper_runs, make_run):
    assert is_completed(make_run(paper_runs, "a1"))


def test_claude_result_event_finishes_log(tmp_path):
    assert log_finished(_log(tmp_path, '{"type":"system"}', CLAUDE_DONE))


def test_codex_turn_completed_finishes_log(tmp_path):
    assert log_finished(_log(tmp_path, '{"type":"turn.started"}', '{"type":"turn.completed"}'))


def test_opencode_stop_finishes_log(tmp_path):
    assert log_finished(_log(tmp_path, '{"type":"step_finish","part":{"reason":"stop"}}'))


def test_opencode_tool_calls_step_does_not_finish_log(tmp_path):
    assert not log_finished(_log(tmp_path, '{"type":"step_finish","part":{"reason":"tool-calls"}}'))


def test_unfinished_log_means_in_progress(paper_runs, make_run):
    make_run(paper_runs, "a1")
    running = make_run(paper_runs, "b2", log_lines=['{"type":"step_start"}'])
    assert not is_completed(running)
    completed, skipped = completed_runs(paper_runs)
    assert [p.name for p in completed] == ["a1"]
    assert skipped == [running]


def test_trailing_garbage_line_is_ignored(tmp_path):
    assert log_finished(_log(tmp_path, CLAUDE_DONE, "not json {"))


def test_empty_log_is_not_finished(tmp_path):
    assert not log_finished(_log(tmp_path))


def test_mismatched_manifests_raise(paper_runs, make_run):
    runs = [make_run(paper_runs, "a1", manifest="m1"), make_run(paper_runs, "b2", manifest="m2")]
    with pytest.raises(ConsensusError) as exc:
        check_same_manifest(runs)
    assert "a1" in str(exc.value) and "b2" in str(exc.value)


def test_matching_manifests_pass(paper_runs, make_run):
    check_same_manifest([make_run(paper_runs, "a1"), make_run(paper_runs, "b2")])
