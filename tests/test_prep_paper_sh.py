"""Tests for audit-prep/scripts/prep_paper.sh, the Claude Code prep launcher."""
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "audit-prep" / "scripts" / "prep_paper.sh"
FAKE_CLAUDE = """#!/usr/bin/env bash
pwd -P > "$FAKE_LOG.cwd"
printf "%s\\0" "$@" > "$FAKE_LOG"
[ -n "${FAKE_OUTPUT:-}" ] && printf "%b\\n" "$FAKE_OUTPUT"
exit "${FAKE_STATUS:-0}"
"""


@pytest.fixture
def fake_env(tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    claude = bindir / "claude"
    claude.write_text(FAKE_CLAUDE)
    claude.chmod(0o755)
    log = tmp_path / "claude.log"
    env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}", FAKE_LOG=str(log))
    return env, log


@pytest.fixture
def corpus(tmp_path):
    root = tmp_path / "my corpus"
    (root / "Smith_2021").mkdir(parents=True)
    (root / ".autoaudit-root").write_text("")
    return root.resolve()


def run_script(env, *args, cwd=None):
    return subprocess.run(
        [str(SCRIPT), *map(str, args)], env=env, cwd=cwd, capture_output=True, text=True
    )


def claude_call(log):
    args = log.read_bytes().decode().split("\0")[:-1]
    cwd = Path(log.with_name(log.name + ".cwd").read_text().strip())
    return args, cwd


def test_script_is_executable():
    assert os.access(SCRIPT, os.X_OK)


def test_no_arguments_prints_usage(fake_env):
    env, log = fake_env
    result = run_script(env)
    assert result.returncode == 2
    assert "usage" in result.stderr.lower()
    assert not log.exists()


def test_too_many_arguments_prints_usage(fake_env, corpus):
    env, log = fake_env
    result = run_script(env, corpus / "Smith_2021", "m", "extra")
    assert result.returncode == 2 and not log.exists()


def test_missing_directory_is_rejected(fake_env, tmp_path):
    env, log = fake_env
    result = run_script(env, tmp_path / "nope")
    assert result.returncode == 2
    assert "nope" in result.stderr
    assert not log.exists()


def test_uninitialized_corpus_is_rejected(fake_env, tmp_path):
    env, log = fake_env
    paper = tmp_path / "plain" / "Smith_2021"
    paper.mkdir(parents=True)
    result = run_script(env, paper)
    assert result.returncode == 1
    assert "prep.py init" in result.stderr
    assert not log.exists()


def test_nested_paper_directory_is_rejected(fake_env, corpus):
    env, log = fake_env
    nested = corpus / "Smith_2021" / "sub"
    nested.mkdir()
    result = run_script(env, nested)
    assert result.returncode == 1
    assert "directly inside" in result.stderr
    assert not log.exists()


RESULT_LINE = '{"type":"result","subtype":"success","result":"PREP DONE"}'


def prep_logs(corpus):
    return sorted((corpus / "logs" / "prep").glob("Smith_2021-*.jsonl"))


def assert_prep_prompt(prompt, corpus, model):
    assert "Use the audit-prep skill to prepare Smith_2021" in prompt
    assert f"corpus root: {corpus}" in prompt
    assert "structured_conversion: true" in prompt
    assert f"reviewed_by: {model}" in prompt
    assert "Finalize if review is clean" in prompt


def test_headless_is_the_default(fake_env, corpus):
    env, log = fake_env
    env["FAKE_OUTPUT"] = RESULT_LINE
    result = run_script(env, "Smith_2021", cwd=corpus)
    assert result.returncode == 0, result.stderr
    args, cwd = claude_call(log)
    assert cwd == corpus
    assert "-p" in args and "--verbose" in args
    assert args[args.index("--model") + 1] == "claude-opus-5-5"
    assert args[args.index("--permission-mode") + 1] == "auto"
    assert args[args.index("--output-format") + 1] == "stream-json"
    assert_prep_prompt(args[-1], corpus, "claude-opus-5-5")


def test_headless_writes_transcript_log(fake_env, corpus):
    env, _ = fake_env
    env["FAKE_OUTPUT"] = RESULT_LINE
    result = run_script(env, corpus / "Smith_2021")
    assert result.returncode == 0, result.stderr
    [transcript] = prep_logs(corpus)
    assert transcript.read_text().strip() == RESULT_LINE
    assert str(transcript) in result.stdout


def test_headless_prints_final_result(fake_env, corpus):
    env, _ = fake_env
    env["FAKE_OUTPUT"] = '{"type":"system"}\n' + RESULT_LINE
    result = run_script(env, corpus / "Smith_2021")
    assert "PREP DONE" in result.stdout


def test_headless_propagates_agent_failure(fake_env, corpus):
    env, _ = fake_env
    env["FAKE_STATUS"] = "3"
    result = run_script(env, corpus / "Smith_2021")
    assert result.returncode == 3
    assert len(prep_logs(corpus)) == 1


def test_interactive_flag_launches_session(fake_env, corpus):
    env, log = fake_env
    result = run_script(env, "--interactive", "Smith_2021", cwd=corpus)
    assert result.returncode == 0, result.stderr
    args, cwd = claude_call(log)
    assert args[:2] == ["--model", "claude-opus-5-5"] and len(args) == 3
    assert cwd == corpus
    assert_prep_prompt(args[2], corpus, "claude-opus-5-5")
    assert prep_logs(corpus) == []


def test_model_can_be_overridden(fake_env, corpus):
    env, log = fake_env
    result = run_script(env, corpus / "Smith_2021", "claude-sonnet-5-5")
    assert result.returncode == 0, result.stderr
    args, _ = claude_call(log)
    assert args[args.index("--model") + 1] == "claude-sonnet-5-5"
    assert "reviewed_by: claude-sonnet-5-5" in args[-1]
