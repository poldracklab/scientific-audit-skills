"""Tests for audit-consensus/scripts/consensus.sh, the consensus launcher."""
import json
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "audit-consensus" / "scripts" / "consensus.sh"
FAKE_AGENT = """#!/usr/bin/env bash
pwd -P > "$FAKE_LOG.cwd"
echo "$(basename "$0")" > "$FAKE_LOG.name"
printf "%s\\0" "$@" > "$FAKE_LOG"
grep -ril claude-opus-5-5 "$FAKE_RUNS" > "$FAKE_LOG.grep" || true
for d in ../*/; do [ "$d" = "../$(basename "$PWD")/" ] || { cat "$d/inputs.json" > /dev/null 2>&1 && echo "$d"; }; done > "$FAKE_LOG.siblings"
[ -n "${FAKE_QMD:-}" ] && echo "# consensus" > consensus.qmd
[ -n "${FAKE_OUTPUT:-}" ] && printf "%b\\n" "$FAKE_OUTPUT"
exit "${FAKE_STATUS:-0}"
"""
FAKE_QUARTO = """#!/usr/bin/env bash
pwd -P > "$FAKE_LOG.quarto.cwd"
printf "%s\\0" "$@" > "$FAKE_LOG.quarto"
[ -f run_models.json ] && cp run_models.json "$FAKE_LOG.quarto.models"
exit 0
"""
RESULT_LINE = '{"type":"result","subtype":"success","result":"CONSENSUS DONE"}'
MODELS = {"a1": "claude-opus-5-5", "b2": "gpt-5.6-sol"}


def write_exe(path, text):
    path.write_text(text)
    path.chmod(0o755)


@pytest.fixture
def corpus(tmp_path, make_run):
    root = tmp_path / "my corpus"
    (root / "runs" / "P").mkdir(parents=True)
    (root / ".autoaudit-root").write_text("")
    lines = [json.dumps({"run_id": r, "paper_id": "P", "model": m}) for r, m in MODELS.items()]
    (root / "registry.jsonl").write_text("\n".join(lines) + "\n")
    for run_id, model in MODELS.items():
        make_run(root / "runs" / "P", run_id, log_lines=[json.dumps({"model": model}), '{"type":"result"}'])
    return root.resolve()


@pytest.fixture
def fake_env(tmp_path, corpus):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for name in ("claude", "codex", "opencode"):
        write_exe(bindir / name, FAKE_AGENT)
    write_exe(bindir / "quarto", FAKE_QUARTO)
    log = tmp_path / "agent.log"
    env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}", FAKE_LOG=str(log),
               FAKE_RUNS=str(corpus / "runs" / "P"))
    return env, log


def run_script(env, cwd, *args):
    return subprocess.run([str(SCRIPT), *args], env=env, cwd=cwd, capture_output=True, text=True)


def agent_call(log):
    args = log.read_bytes().decode().split("\0")[:-1]
    cwd = Path(log.with_name(log.name + ".cwd").read_text().strip())
    name = log.with_name(log.name + ".name").read_text().strip()
    return name, args, cwd


def flag_value(args, flag):
    return args[args.index(flag) + 1]


def add_dirs(args):
    return [args[i + 1] for i, a in enumerate(args) if a == "--add-dir"]


def consensus_dirs(corpus):
    return sorted((corpus / "runs" / "P" / "consensus").iterdir())


def test_script_is_executable():
    assert os.access(SCRIPT, os.X_OK)


@pytest.mark.parametrize("args", [(), ("a", "b", "c")])
def test_wrong_arguments_print_usage(fake_env, corpus, args):
    env, log = fake_env
    result = run_script(env, corpus, *args)
    assert result.returncode == 2
    assert "usage" in result.stderr.lower()
    assert not log.exists()


def test_must_run_from_corpus_root(fake_env, tmp_path):
    env, log = fake_env
    result = run_script(env, tmp_path, "P")
    assert result.returncode == 1
    assert ".autoaudit-root" in result.stderr
    assert not log.exists()


def test_default_model_is_claude_opus_5_5(fake_env, corpus):
    env, log = fake_env
    result = run_script(env, corpus, "P")
    assert result.returncode == 0, result.stderr
    name, args, _ = agent_call(log)
    assert name == "claude" and flag_value(args, "--model") == "claude-opus-5-5"


def test_claude_headless_flags(fake_env, corpus):
    env, log = fake_env
    result = run_script(env, corpus, "P", "claude-opus-5-5")
    assert result.returncode == 0, result.stderr
    _, args, cwd = agent_call(log)
    assert cwd == consensus_dirs(corpus)[0]
    assert "-p" in args and "--verbose" in args
    assert flag_value(args, "--permission-mode") == "auto"
    assert flag_value(args, "--output-format") == "stream-json"
    assert add_dirs(args) == [str(corpus / "runs" / "P" / r) for r in ("a1", "b2")]
    assert "Use the audit-consensus skill" in args[-1] and "audits of P" in args[-1]
    assert "Never read registry.jsonl" in args[-1]


def test_codex_harness_selection(fake_env, corpus):
    env, log = fake_env
    assert run_script(env, corpus, "P", "gpt-5.6-sol").returncode == 0
    name, args, _ = agent_call(log)
    assert name == "codex" and args[0] == "exec"
    assert flag_value(args, "-m") == "gpt-5.6-sol"
    assert flag_value(args, "--sandbox") == "workspace-write"
    assert flag_value(args, "-c") == "sandbox_workspace_write.network_access=true"
    assert "--skip-git-repo-check" in args and "--json" in args


def test_opencode_harness_selection(fake_env, corpus):
    env, log = fake_env
    assert run_script(env, corpus, "P", "qwen/qwen3-coder").returncode == 0
    name, args, _ = agent_call(log)
    assert name == "opencode" and args[0] == "run"
    assert flag_value(args, "--model") == "openrouter/qwen/qwen3-coder"
    assert flag_value(args, "--format") == "json" and "--auto" in args


def test_runs_redacted_before_agent_starts(fake_env, corpus):
    env, log = fake_env
    assert run_script(env, corpus, "P").returncode == 0
    assert log.with_name(log.name + ".grep").read_text() == ""


def test_headless_log_in_consensus_dir_and_result_printed(fake_env, corpus):
    env, _ = fake_env
    env["FAKE_OUTPUT"] = RESULT_LINE
    result = run_script(env, corpus, "P")
    transcript = consensus_dirs(corpus)[0] / "agent_log.jsonl"
    assert transcript.read_text().strip() == RESULT_LINE
    assert str(transcript) in result.stdout and "CONSENSUS DONE" in result.stdout


def test_models_attached_and_report_rendered_after_agent(fake_env, corpus):
    env, log = fake_env
    env["FAKE_QMD"] = "1"
    assert run_script(env, corpus, "P").returncode == 0
    out = consensus_dirs(corpus)[0]
    assert json.loads((out / "run_models.json").read_text()) == MODELS
    assert log.with_name(log.name + ".quarto").read_bytes().decode().split("\0")[:-1] == ["render", "consensus.qmd"]
    assert Path(log.with_name(log.name + ".quarto.cwd").read_text().strip()) == out
    assert log.with_name(log.name + ".quarto.models").exists()


def test_no_render_when_agent_wrote_no_report(fake_env, corpus):
    env, log = fake_env
    assert run_script(env, corpus, "P").returncode == 0
    assert not log.with_name(log.name + ".quarto").exists()
    assert (consensus_dirs(corpus)[0] / "run_models.json").exists()


def test_prepare_failure_launches_no_agent(fake_env, corpus):
    env, log = fake_env
    (corpus / "runs" / "P" / "b2" / "audit" / "audit.html").unlink()
    result = run_script(env, corpus, "P")
    assert result.returncode == 1
    assert "at least 2" in result.stderr
    assert not log.exists()


def test_agent_failure_status_propagates(fake_env, corpus):
    env, _ = fake_env
    env["FAKE_STATUS"] = "4"
    assert run_script(env, corpus, "P").returncode == 4
    assert (consensus_dirs(corpus)[0] / "run_models.json").exists()


def test_interactive_runs_post_steps(fake_env, corpus):
    env, log = fake_env
    env["FAKE_QMD"] = "1"
    result = run_script(env, corpus, "--interactive", "P")
    assert result.returncode == 0, result.stderr
    name, args, _ = agent_call(log)
    assert name == "claude" and args[:2] == ["--model", "claude-opus-5-5"] and "-p" not in args
    assert add_dirs(args) == [str(corpus / "runs" / "P" / r) for r in ("a1", "b2")]
    out = consensus_dirs(corpus)[0]
    assert (out / "run_models.json").exists() and not (out / "agent_log.jsonl").exists()
    assert log.with_name(log.name + ".quarto").exists()


def test_earlier_consensus_hidden_during_agent_and_restored(fake_env, corpus):
    env, log = fake_env
    assert run_script(env, corpus, "P").returncode == 0
    earlier = consensus_dirs(corpus)[0]
    mode = earlier.stat().st_mode
    assert run_script(env, corpus, "P").returncode == 0
    assert log.with_name(log.name + ".siblings").read_text() == ""
    assert earlier.stat().st_mode == mode and (earlier / "inputs.json").exists()


def test_prompt_forbids_other_consensus_folders(fake_env, corpus):
    env, log = fake_env
    assert run_script(env, corpus, "P").returncode == 0
    _, args, _ = agent_call(log)
    assert "Never read other folders under ../" in args[-1]
