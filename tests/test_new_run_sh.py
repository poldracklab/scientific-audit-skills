"""Behavior shared by the reproducibility and neuroimaging audit launchers."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ("reproducibility-audit", "neuroimaging-validity-audit")
FAKE_AGENT = """#!/usr/bin/env bash
pwd -P > "$FAKE_LOG.cwd"
echo "$(basename "$0")" > "$FAKE_LOG.name"
printf "%s\\0" "$@" > "$FAKE_LOG"
[ -n "${FAKE_OUTPUT:-}" ] && printf "%b\\n" "$FAKE_OUTPUT"
exit "${FAKE_STATUS:-0}"
"""
STUB_NEW_RUN = """import sys
from pathlib import Path
args = sys.argv[1:]
root = Path(args[args.index("--root") + 1])
Path(root, "new_run_args").write_text("\\0".join(args))
run = root / "runs" / args[0] / "abcd2345"
(run / "audit").mkdir(parents=True)
print(run)
"""
STUB_VERIFY = """import os, sys
print(os.environ.get("FAKE_VERIFY", "run_ok"))
print("detail line")
"""
RESULT_LINE = '{"type":"result","subtype":"success","result":"AUDIT DONE"}'


def write_exe(path, text):
    path.write_text(text)
    path.chmod(0o755)


@pytest.fixture(params=SKILLS)
def skill_name(request):
    return request.param


@pytest.fixture
def installed(tmp_path, skill_name):
    """A skills tree holding a copy of the script and stub audit-prep scripts."""
    skills = tmp_path / "skills"
    (skills / skill_name / "scripts").mkdir(parents=True)
    prep = skills / "audit-prep" / "scripts"
    prep.mkdir(parents=True)
    script = skills / skill_name / "scripts" / "new_run.sh"
    shutil.copy2(ROOT / skill_name / "scripts" / "new_run.sh", script)
    (prep / "new_run.py").write_text(STUB_NEW_RUN)
    (prep / "verify_run.py").write_text(STUB_VERIFY)
    return script


@pytest.fixture
def fake_env(tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for name in ("claude", "codex", "opencode"):
        write_exe(bindir / name, FAKE_AGENT)
    log = tmp_path / "agent.log"
    env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}", FAKE_LOG=str(log))
    return env, log


@pytest.fixture
def corpus(tmp_path):
    root = tmp_path / "my corpus"
    root.mkdir()
    (root / ".autoaudit-root").write_text("")
    return root.resolve()


def run_script(script, env, cwd, *args):
    return subprocess.run(
        [str(script), *args], env=env, cwd=cwd, capture_output=True, text=True
    )


def agent_call(log):
    args = log.read_bytes().decode().split("\0")[:-1]
    cwd = Path(log.with_name(log.name + ".cwd").read_text().strip())
    name = log.with_name(log.name + ".name").read_text().strip()
    return name, args, cwd


def run_dir(corpus):
    return corpus / "runs" / "Smith_2021" / "abcd2345"


def flag_value(args, flag):
    return args[args.index(flag) + 1]


def test_script_is_executable(skill_name):
    assert os.access(ROOT / skill_name / "scripts" / "new_run.sh", os.X_OK)


@pytest.mark.parametrize("args", [(), ("Smith_2021",), ("a", "b", "c")])
def test_wrong_arguments_print_usage(installed, fake_env, corpus, args):
    env, log = fake_env
    result = run_script(installed, env, corpus, *args)
    assert result.returncode == 2
    assert "usage" in result.stderr.lower()
    assert not log.exists() and not (corpus / "runs").exists()


def test_must_run_from_corpus_root(installed, fake_env, tmp_path):
    env, log = fake_env
    result = run_script(installed, env, tmp_path, "Smith_2021", "claude-opus-5-5")
    assert result.returncode == 1
    assert ".autoaudit-root" in result.stderr
    assert not log.exists()


def test_creates_run_with_sibling_audit_prep(installed, fake_env, corpus):
    env, _ = fake_env
    result = run_script(installed, env, corpus, "Smith_2021", "claude-opus-5-5")
    assert result.returncode == 0, result.stderr
    args = (corpus / "new_run_args").read_text().split("\0")
    assert args == ["Smith_2021", "--model", "claude-opus-5-5", "--root", str(corpus)]


def test_unverified_run_does_not_launch(installed, fake_env, corpus):
    env, log = fake_env
    env["FAKE_VERIFY"] = "run_dirty"
    result = run_script(installed, env, corpus, "Smith_2021", "claude-opus-5-5")
    assert result.returncode == 1
    assert "run_dirty" in result.stdout + result.stderr
    assert not log.exists()


def test_claude_headless_by_default(installed, fake_env, corpus, skill_name):
    env, log = fake_env
    env["FAKE_OUTPUT"] = RESULT_LINE
    result = run_script(installed, env, corpus, "Smith_2021", "claude-opus-5-5")
    assert result.returncode == 0, result.stderr
    name, args, cwd = agent_call(log)
    assert name == "claude" and cwd == run_dir(corpus)
    assert "-p" in args and "--verbose" in args
    assert flag_value(args, "--model") == "claude-opus-5-5"
    assert flag_value(args, "--permission-mode") == "auto"
    assert flag_value(args, "--output-format") == "stream-json"
    assert f"Use the {skill_name} skill" in args[-1]
    assert "audit-prep run for Smith_2021" in args[-1]
    assert "verify_run.py" in args[-1] and "run_ok" in args[-1]
    assert "leave every other file in the run folder unchanged" in args[-1]
    assert "audit/audit.html" in args[-1] and "Do not publish" in args[-1]


def test_headless_log_goes_under_audit(installed, fake_env, corpus):
    env, _ = fake_env
    env["FAKE_OUTPUT"] = RESULT_LINE
    result = run_script(installed, env, corpus, "Smith_2021", "claude-opus-5-5")
    transcript = run_dir(corpus) / "audit" / "agent_log.jsonl"
    assert transcript.read_text().strip() == RESULT_LINE
    assert str(transcript) in result.stdout
    assert "AUDIT DONE" in result.stdout


def test_codex_headless(installed, fake_env, corpus):
    env, log = fake_env
    result = run_script(installed, env, corpus, "Smith_2021", "gpt-5.5")
    assert result.returncode == 0, result.stderr
    name, args, cwd = agent_call(log)
    assert name == "codex" and cwd == run_dir(corpus)
    assert args[0] == "exec"
    assert flag_value(args, "-m") == "gpt-5.5"
    assert flag_value(args, "--sandbox") == "workspace-write"
    assert flag_value(args, "-c") == "sandbox_workspace_write.network_access=true"
    assert "--skip-git-repo-check" in args and "--json" in args
    assert (run_dir(corpus) / "audit" / "agent_log.jsonl").exists()


def test_opencode_headless(installed, fake_env, corpus):
    env, log = fake_env
    result = run_script(installed, env, corpus, "Smith_2021", "qwen/qwen3-coder")
    assert result.returncode == 0, result.stderr
    name, args, _ = agent_call(log)
    assert name == "opencode" and args[0] == "run"
    assert flag_value(args, "--model") == "openrouter/qwen/qwen3-coder"
    assert flag_value(args, "--format") == "json"
    assert "--auto" in args


def test_headless_propagates_agent_failure(installed, fake_env, corpus):
    env, _ = fake_env
    env["FAKE_STATUS"] = "4"
    result = run_script(installed, env, corpus, "Smith_2021", "claude-opus-5-5")
    assert result.returncode == 4


def test_interactive_claude(installed, fake_env, corpus):
    env, log = fake_env
    result = run_script(installed, env, corpus, "--interactive", "Smith_2021", "claude-opus-5-5")
    assert result.returncode == 0, result.stderr
    name, args, cwd = agent_call(log)
    assert name == "claude" and cwd == run_dir(corpus)
    assert args[:2] == ["--model", "claude-opus-5-5"] and len(args) == 3
    assert not (run_dir(corpus) / "audit" / "agent_log.jsonl").exists()


def test_interactive_codex(installed, fake_env, corpus):
    env, log = fake_env
    result = run_script(installed, env, corpus, "--interactive", "Smith_2021", "gpt-5.5")
    assert result.returncode == 0, result.stderr
    name, args, _ = agent_call(log)
    assert name == "codex" and args[:2] == ["--model", "gpt-5.5"] and len(args) == 3
