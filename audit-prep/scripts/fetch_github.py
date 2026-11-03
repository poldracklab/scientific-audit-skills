# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Clone a GitHub repository and record its commit and any Zenodo DOI."""
import re
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from public_http import public_addresses, validate_url

GITHUB_RE = re.compile(r"^https?://(?:www\.)?github\.com/([^/\s]+)/([^/\s#?]+)")
ZENODO_RE = re.compile(r"10\.5281/zenodo\.\d+")


def parse_github_url(url: str) -> tuple[str, str] | None:
    m = GITHUB_RE.match(url)
    if not m:
        return None
    return m.group(1), m.group(2).removesuffix(".git")


def find_zenodo_doi(text: str) -> str | None:
    m = ZENODO_RE.search(text)
    return m.group(0) if m else None


def _git_out(dest: Path, run, *args: str) -> str:
    r = run(["git", "-C", str(dest), *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def _readme_doi(dest: Path) -> str | None:
    for f in sorted(dest.iterdir()):
        if f.is_file() and f.name.lower().startswith("readme"):
            return find_zenodo_doi(f.read_text(errors="replace"))
    return None


def _record(url: str, dest: Path, status: str, reason: str = "") -> dict:
    return {
        "url": url, "path": str(dest), "commit": None, "branch": None,
        "cloned_at": None, "status": status, "reason": reason, "zenodo_doi": None,
    }  # fmt: skip


def _fill_repo_info(rec: dict, dest: Path, run) -> dict:
    rec["commit"] = _git_out(dest, run, "rev-parse", "HEAD")
    rec["branch"] = _git_out(dest, run, "rev-parse", "--abbrev-ref", "HEAD")
    rec["zenodo_doi"] = _readme_doi(dest)
    return rec


def _github_address(url: str) -> str:
    parts = validate_url(url)
    if parts.scheme != "https" or parts.hostname != "github.com" or parts.port not in (None, 443):
        raise ValueError("only HTTPS github.com repositories are supported")
    if not re.fullmatch(r"/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?", parts.path) or parts.query or parts.fragment:
        raise ValueError("use the GitHub repository root URL")
    address = public_addresses("github.com", 443)[0][4][0]
    return f"[{address}]" if ":" in address else address


def _git_environment() -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_") and not k.lower().endswith("_proxy")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0")
    return env


def _clone_command(url: str, dest: Path, address: str) -> list[str]:
    config = ["http.followRedirects=false", "http.proxy=", "protocol.allow=never",
              "protocol.https.allow=always", "http.sslVerify=true", "credential.helper=",
              "core.hooksPath=/dev/null", "transfer.bundleURI=false",
              f"http.curloptResolve=github.com:443:{address}"]
    options = [arg for setting in config for arg in ("-c", setting)]
    return ["git", *options, "clone", "--no-recurse-submodules", "--", url, str(dest)]


def clone_repo(url: str, dest: Path, run=subprocess.run) -> dict:
    try:
        address = _github_address(url)
    except (ValueError, OSError) as exc:
        return _record(url, dest, "failed", str(exc))
    if (dest / ".git").exists():
        return _fill_repo_info(_record(url, dest, "skipped", "exists"), dest, run)
    r = run(_clone_command(url, dest, address), capture_output=True, text=True, env=_git_environment())
    if r.returncode != 0:
        return _record(url, dest, "failed", (r.stderr or "git clone failed").strip())
    rec = _fill_repo_info(_record(url, dest, "ok"), dest, run)
    rec["cloned_at"] = datetime.now(timezone.utc).isoformat()
    return rec
