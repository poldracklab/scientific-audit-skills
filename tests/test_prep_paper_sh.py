"""Tests for audit-prep/scripts/prep_paper.sh, the Claude Code prep launcher."""
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "audit-prep" / "scripts" / "prep_paper.sh"
FAKE_AGENT = """#!/usr/bin/env bash
pwd -P > "$FAKE_LOG.cwd"
echo "$(basename "$0")" > "$FAKE_LOG.name"
printf "%s\\0" "$@" > "$FAKE_LOG"
[ -n "${FAKE_OUTPUT:-}" ] && printf "%b\\n" "$FAKE_OUTPUT"
exit "${FAKE_STATUS:-0}"
"""


@pytest.fixture
def fake_env(tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for name in ("claude", "codex", "opencode"):
        agent = bindir / name
        agent.write_text(FAKE_AGENT)
        agent.chmod(0o755)
    log = tmp_path / "agent.log"
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


def agent_call(log):
    args = log.read_bytes().decode().split("\0")[:-1]
    cwd = Path(log.with_name(log.name + ".cwd").read_text().strip())
    name = log.with_name(log.name + ".name").read_text().strip()
    return name, args, cwd


def claude_call(log):
    name, args, cwd = agent_call(log)
    assert name == "claude"
    return args, cwd


def flag_value(args, flag):
    return args[args.index(flag) + 1]


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


def test_codex_headless(fake_env, corpus):
    env, log = fake_env
    result = run_script(env, corpus / "Smith_2021", "gpt-5.5")
    assert result.returncode == 0, result.stderr
    name, args, cwd = agent_call(log)
    assert name == "codex" and cwd == corpus
    assert args[0] == "exec"
    assert flag_value(args, "-m") == "gpt-5.5"
    assert flag_value(args, "--sandbox") == "workspace-write"
    assert flag_value(args, "-c") == "sandbox_workspace_write.network_access=true"
    assert "--skip-git-repo-check" in args and "--json" in args
    assert_prep_prompt(args[-1], corpus, "gpt-5.5")
    assert len(prep_logs(corpus)) == 1


def test_openrouter_headless(fake_env, corpus):
    env, log = fake_env
    result = run_script(env, corpus / "Smith_2021", "qwen/qwen3-coder")
    assert result.returncode == 0, result.stderr
    name, args, cwd = agent_call(log)
    assert name == "opencode" and cwd == corpus
    assert args[0] == "run" and "--auto" in args
    assert flag_value(args, "--model") == "openrouter/qwen/qwen3-coder"
    assert flag_value(args, "--format") == "json"
    assert_prep_prompt(args[-1], corpus, "qwen/qwen3-coder")
    assert len(prep_logs(corpus)) == 1


def test_openrouter_headless_propagates_failure(fake_env, corpus):
    env, _ = fake_env
    env["FAKE_STATUS"] = "5"
    result = run_script(env, corpus / "Smith_2021", "qwen/qwen3-coder")
    assert result.returncode == 5


def test_harness_choice_ignores_case(fake_env, corpus):
    env, log = fake_env
    result = run_script(env, corpus / "Smith_2021", "anthropic/Claude-Sonnet-5-5")
    assert result.returncode == 0, result.stderr
    name, _, _ = agent_call(log)
    assert name == "claude"


def test_interactive_codex(fake_env, corpus):
    env, log = fake_env
    result = run_script(env, "--interactive", corpus / "Smith_2021", "gpt-5.5")
    assert result.returncode == 0, result.stderr
    name, args, cwd = agent_call(log)
    assert name == "codex" and cwd == corpus
    assert args[:2] == ["--model", "gpt-5.5"] and len(args) == 3
    assert_prep_prompt(args[2], corpus, "gpt-5.5")
    assert prep_logs(corpus) == []


def test_interactive_openrouter(fake_env, corpus):
    env, log = fake_env
    result = run_script(env, "--interactive", corpus / "Smith_2021", "qwen/qwen3-coder")
    assert result.returncode == 0, result.stderr
    name, args, cwd = agent_call(log)
    assert name == "opencode" and cwd == corpus
    assert args[:3] == ["run", "--model", "openrouter/qwen/qwen3-coder"] and len(args) == 4
    assert_prep_prompt(args[3], corpus, "qwen/qwen3-coder")
    assert prep_logs(corpus) == []


@pytest.fixture
def earlier_prep(corpus):
    """Leftovers of an earlier prep: a finalized (read-only) draft, scan outputs and transcripts."""
    raw = corpus / "Smith_2021"
    (raw / "paper.pdf").write_text("pdf")
    (raw / "prep.yaml").write_text("reviewed_by: someone\n")
    (raw / "statements.md").write_text("# statements\n")
    draft = corpus / "prepared" / "Smith_2021"
    (draft / "paper").mkdir(parents=True)
    (draft / "paper" / "paper.pdf").write_text("pdf")
    for path in (draft / "paper" / "paper.pdf", draft / "paper", draft):
        path.chmod(0o555 if path.is_dir() else 0o444)
    logs = corpus / "logs" / "prep"
    logs.mkdir(parents=True)
    (logs / "Smith_2021-20261101T000000Z.jsonl").write_text("old\n")
    (logs / "Smith_2021b-20261101T000000Z.jsonl").write_text("other paper\n")
    (corpus / "prepared" / "Jones_2020").mkdir()
    yield corpus
    for dirpath, dirnames, _ in os.walk(corpus):
        for name in dirnames:
            os.chmod(Path(dirpath) / name, 0o755)


def test_without_overwrite_earlier_prep_is_kept(fake_env, earlier_prep):
    env, _ = fake_env
    result = run_script(env, earlier_prep / "Smith_2021")
    assert result.returncode == 0, result.stderr
    assert (earlier_prep / "prepared" / "Smith_2021" / "paper" / "paper.pdf").exists()
    assert (earlier_prep / "Smith_2021" / "prep.yaml").exists()
    assert len(prep_logs(earlier_prep)) == 2


def test_overwrite_removes_earlier_prep_and_logs(fake_env, earlier_prep):
    env, log = fake_env
    result = run_script(env, "--overwrite", earlier_prep / "Smith_2021")
    assert result.returncode == 0, result.stderr
    assert not (earlier_prep / "prepared" / "Smith_2021").exists()
    assert not (earlier_prep / "Smith_2021" / "prep.yaml").exists()
    assert not (earlier_prep / "Smith_2021" / "statements.md").exists()
    [transcript] = prep_logs(earlier_prep)
    assert transcript.name != "Smith_2021-20261101T000000Z.jsonl"
    assert log.exists()


def test_overwrite_keeps_supplied_files_and_other_papers(fake_env, earlier_prep):
    env, _ = fake_env
    assert run_script(env, "--overwrite", earlier_prep / "Smith_2021").returncode == 0
    assert (earlier_prep / "Smith_2021" / "paper.pdf").read_text() == "pdf"
    assert (earlier_prep / "prepared" / "Jones_2020").is_dir()
    assert (earlier_prep / "logs" / "prep" / "Smith_2021b-20261101T000000Z.jsonl").exists()


@pytest.mark.parametrize("flags", [["--overwrite", "--interactive"], ["--interactive", "--overwrite"]])
def test_overwrite_combines_with_interactive(fake_env, earlier_prep, flags):
    env, log = fake_env
    result = run_script(env, *flags, earlier_prep / "Smith_2021")
    assert result.returncode == 0, result.stderr
    args, _ = claude_call(log)
    assert args[:2] == ["--model", "claude-opus-5-5"] and len(args) == 3
    assert not (earlier_prep / "prepared" / "Smith_2021").exists()
    assert prep_logs(earlier_prep) == []


def test_overwrite_warns_about_existing_audit_runs_and_keeps_them(fake_env, earlier_prep):
    env, _ = fake_env
    run = earlier_prep / "runs" / "Smith_2021" / "abcd2345"
    run.mkdir(parents=True)
    result = run_script(env, "--overwrite", earlier_prep / "Smith_2021")
    assert result.returncode == 0, result.stderr
    assert run.is_dir()
    assert "runs/Smith_2021" in result.stderr


def test_unknown_flag_prints_usage(fake_env, corpus):
    env, log = fake_env
    result = run_script(env, "--bogus", corpus / "Smith_2021")
    assert result.returncode == 2 and "usage" in result.stderr.lower()
    assert not log.exists()
