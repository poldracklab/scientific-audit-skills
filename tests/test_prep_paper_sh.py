"""Tests for audit-prep/scripts/prep_paper.sh, the Claude Code prep launcher."""
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "audit-prep" / "scripts" / "prep_paper.sh"
FAKE_CLAUDE = '#!/usr/bin/env bash\npwd -P > "$FAKE_LOG.cwd"\nprintf "%s\\0" "$@" > "$FAKE_LOG"\n'


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


def test_launches_claude_with_default_model(fake_env, corpus, tmp_path):
    env, log = fake_env
    result = run_script(env, "Smith_2021", cwd=corpus)
    assert result.returncode == 0, result.stderr
    args, cwd = claude_call(log)
    assert args[:2] == ["--model", "claude-opus-5-5"] and len(args) == 3
    assert cwd == corpus
    prompt = args[2]
    assert "Use the audit-prep skill to prepare Smith_2021" in prompt
    assert f"corpus root: {corpus}" in prompt
    assert "structured_conversion: true" in prompt
    assert "reviewed_by: claude-opus-5-5" in prompt
    assert "Finalize if review is clean" in prompt


def test_model_can_be_overridden(fake_env, corpus):
    env, log = fake_env
    result = run_script(env, corpus / "Smith_2021", "claude-sonnet-5-5")
    assert result.returncode == 0, result.stderr
    args, _ = claude_call(log)
    assert args[:2] == ["--model", "claude-sonnet-5-5"]
    assert "reviewed_by: claude-sonnet-5-5" in args[2]
