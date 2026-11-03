"""Blind source runs: replace model names with run IDs before a consensus agent reads them."""
import json
import re
from pathlib import Path

OTHER_PLACEHOLDER = "[redacted-model]"


def load_models(registry: Path, paper_id: str) -> dict[str, str]:
    """run_id -> model for one paper; duplicate registry lines collapse, the last one wins."""
    models = {}
    for line in Path(registry).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry.get("paper_id") == paper_id:
            models[entry["run_id"]] = entry["model"]
    return models


def _longest_first(strings) -> list[str]:
    unique = list(dict.fromkeys(strings))
    return sorted(unique, key=len, reverse=True)


def aliases(model: str) -> list[str]:
    return _longest_first([model, model.rsplit("/", 1)[-1]])


def plan_redaction(run: Path, own: str, others: list[str]) -> dict[str, list[str]]:
    own_aliases = aliases(own)
    owned = {a.lower() for a in own_aliases}
    other = [a for m in others for a in aliases(m) if a.lower() not in owned]
    return {"own_aliases": own_aliases, "other_aliases": _longest_first(other)}


def _files(root: Path):
    return sorted(p for p in Path(root).rglob("*") if p.is_file() and not p.is_symlink())


def _hits(path: Path, needles: list[bytes]) -> bool:
    data = path.read_bytes().lower()
    return any(n in data for n in needles)


def _leaks(run: Path, files, strings: list[str]) -> list[str]:
    needles = [s.lower().encode() for s in strings]
    return [p.relative_to(run).as_posix() for p in files if _hits(p, needles)]


def outside_audit_leaks(run: Path, strings: list[str]) -> list[str]:
    run = Path(run)
    audit = run / "audit"
    return _leaks(run, [p for p in _files(run) if audit not in p.parents], strings)


def remaining_leaks(run: Path, strings: list[str]) -> list[str]:
    return _leaks(Path(run), _files(run), strings)


def _substitute(text: str, plan: dict, run_id: str) -> tuple[str, int]:
    total = 0
    pairs = [(a, run_id) for a in plan["own_aliases"]] + [(a, OTHER_PLACEHOLDER) for a in plan["other_aliases"]]
    for alias, replacement in pairs:
        text, n = re.subn(re.escape(alias), lambda _: replacement, text, flags=re.IGNORECASE)
        total += n
    return text, total


def _write_preserving_mode(path: Path, text: str) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | 0o200)
    try:
        path.write_text(text, encoding="utf-8")
    finally:
        path.chmod(mode)


def _redact_file(path: Path, plan: dict, run_id: str) -> int:
    try:
        text = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        return 0
    new, count = _substitute(text, plan, run_id)
    if count:
        _write_preserving_mode(path, new)
    return count


def redact_run(run: Path, run_id: str, plan: dict) -> dict[str, int]:
    """Redact text files under <run>/audit/ only; returns path -> replacements for changed files."""
    run = Path(run)
    counts = {}
    for path in _files(run / "audit"):
        if n := _redact_file(path, plan, run_id):
            counts[path.relative_to(run).as_posix()] = n
    return counts
