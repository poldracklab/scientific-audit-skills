# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Verify a prepared or run folder against its manifest and report its status."""
import hashlib
import json
import sys
from pathlib import Path

from manifest import has_clean_review, hash_tree, is_os_metadata, load_manifest

ALLOWED_EXTRA = ("run.json", "audit")
NO_REVIEW = "manifest has no clean prep review; run prep.py review"


def _is_allowed_extra(rel: str) -> bool:
    return rel in ALLOWED_EXTRA or is_os_metadata(Path(rel))


def _modified(expected: dict, actual: dict) -> list[str]:
    return sorted(p for p, sha in expected.items() if actual.get(p) != sha)


def _dirty(expected: dict, actual: dict) -> list[str]:
    return sorted(p for p in actual if p not in expected and not _is_allowed_extra(p))


def _file_sha(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _stale_pinned(folder: Path) -> list[str]:
    pins = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    pinned = (("manifest.json", "manifest_sha256"), ("README.md", "readme_sha256"))
    return [name for name, key in pinned if _file_sha(folder / name) != pins.get(key)]


def _compare(folder: Path, m: dict) -> tuple[str, list[str]]:
    actual = {f["path"]: f["sha256"] for f in hash_tree(folder, prune=("audit",))}
    expected = {f["path"]: f["sha256"] for f in m.get("files", [])}
    if modified := _stale_pinned(folder) + _modified(expected, actual):
        return "run_modified", modified
    if dirty := _dirty(expected, actual):
        return "run_dirty", dirty
    return "run_ok", []


def verify(folder: Path) -> tuple[str, list[str]]:
    folder = Path(folder)
    m = load_manifest(folder)
    if m is None or not m.get("finalized"):
        return "not_prepared", ["no finalized manifest.json"]
    if not has_clean_review(m):
        return "not_prepared", [NO_REVIEW]
    if not (folder / "run.json").is_file():
        return "prepared_not_run", []
    return _compare(folder, m)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: verify_run.py <folder>", file=sys.stderr)
        return 2
    status, details = verify(Path(args[0]))
    print("\n".join([status, *details]))
    return 0 if status == "run_ok" else 1


if __name__ == "__main__":
    sys.exit(main())
