# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Clone a GitHub repository and record its commit and any Zenodo DOI."""
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

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


def clone_repo(url: str, dest: Path, run=subprocess.run) -> dict:
    if (dest / ".git").exists():
        return _fill_repo_info(_record(url, dest, "skipped", "exists"), dest, run)
    r = run(["git", "clone", "--recurse-submodules", url, str(dest)], capture_output=True, text=True)
    if r.returncode != 0:
        return _record(url, dest, "failed", (r.stderr or "git clone failed").strip())
    rec = _fill_repo_info(_record(url, dest, "ok"), dest, run)
    rec["cloned_at"] = datetime.now(timezone.utc).isoformat()
    return rec
