# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Verify a prepared or run folder against its manifest and report its status."""
import sys
from pathlib import Path

from manifest import hash_tree, load_manifest

ALLOWED_EXTRA = ("run.json", "audit")


def _is_allowed_extra(rel: str) -> bool:
    return rel in ALLOWED_EXTRA or rel.split("/", 1)[0] == "audit"


def _modified(expected: dict, actual: dict) -> list[str]:
    return sorted(p for p, sha in expected.items() if actual.get(p) != sha)


def _dirty(expected: dict, actual: dict) -> list[str]:
    return sorted(p for p in actual if p not in expected and not _is_allowed_extra(p))


def _compare(folder: Path, m: dict) -> tuple[str, list[str]]:
    actual = {f["path"]: f["sha256"] for f in hash_tree(folder)}
    expected = {f["path"]: f["sha256"] for f in m.get("files", [])}
    if modified := _modified(expected, actual):
        return "run_modified", modified
    if dirty := _dirty(expected, actual):
        return "run_dirty", dirty
    return "run_ok", []


def verify(folder: Path) -> tuple[str, list[str]]:
    folder = Path(folder)
    m = load_manifest(folder)
    if m is None or not m.get("finalized"):
        return "not_prepared", ["no finalized manifest.json"]
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
