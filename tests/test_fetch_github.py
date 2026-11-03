import socket
import subprocess

import pytest

from fetch_github import clone_repo, parse_github_url


def test_parse_github_url():
    assert parse_github_url("https://github.com/lab/repo") == ("lab", "repo")
    assert parse_github_url("https://github.com/lab/repo/tree/main/x") == ("lab", "repo")
    assert parse_github_url("https://gitlab.com/x/y") is None


def test_clone_records_commit_and_zenodo(github_transport, tmp_path):
    r = clone_repo("https://github.com/lab/repo", tmp_path / "github" / "lab__repo", run=github_transport)
    assert r["status"] == "ok" and len(r["commit"]) == 40 and r["zenodo_doi"] == "10.5281/zenodo.7654321"
    assert (tmp_path / "github/lab__repo/.git").exists()


def test_clone_failure_recorded(tmp_path):
    r = clone_repo("/nonexistent/repo.git", tmp_path / "x")
    assert r["status"] == "failed" and r["reason"]


@pytest.mark.parametrize("url", ["/tmp/repo", "file:///tmp/repo", "http://github.com/lab/repo",
                               "https://127.0.0.1/repo", "https://github.com.attacker.test/lab/repo",
                               "https://user:secret@github.com/lab/repo", "-u/bin/command"])
def test_git_rejects_non_github_https_sources_before_subprocess(tmp_path, url):
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 1, stderr="failed")

    result = clone_repo(url, tmp_path / "repo", run=run)
    assert result["status"] == "failed"
    assert calls == []


def test_git_rejects_private_dns_before_subprocess(tmp_path, monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))])
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 1, stderr="failed")

    assert clone_repo("https://github.com/lab/repo", tmp_path / "repo", run=run)["status"] == "failed"
    assert calls == []


def test_git_pins_public_address_and_disables_redirects_submodules_and_rewrites(tmp_path, github_transport, monkeypatch):
    calls = []
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "url.file:///private/.insteadOf")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "https://github.com/")

    def run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return github_transport(cmd, **kwargs)

    result = clone_repo("https://github.com/lab/repo", tmp_path / "repo", run=run)
    assert result["status"] == "ok"
    cmd, options = calls[0]
    assert "--recurse-submodules" not in cmd and "--no-recurse-submodules" in cmd
    assert "http.curloptResolve=github.com:443:93.184.216.34" in cmd
    assert "http.followRedirects=false" in cmd and "http.proxy=" in cmd
    assert options["env"]["GIT_CONFIG_NOSYSTEM"] == "1"
    assert options["env"]["GIT_CONFIG_GLOBAL"] == "/dev/null"
    assert "GIT_CONFIG_COUNT" not in options["env"]
    assert "GIT_CONFIG_PARAMETERS" not in options["env"]
