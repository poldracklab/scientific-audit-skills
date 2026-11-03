"""Blind source runs: replace model names with run IDs before a consensus agent reads them."""
import json
import re
from pathlib import Path

OTHER_PLACEHOLDER = "[redacted-model]"
CHUNK_SIZE = 8 * 1024 * 1024


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


def _pattern(strings: list[str]) -> str:
    """Whole-token match: no letter or digit on either side, and no ".<digit>" version tail."""
    alternatives = "|".join(re.escape(s) for s in _longest_first(strings))
    return rf"(?<![A-Za-z0-9])(?:{alternatives})(?![A-Za-z0-9])(?!\.[0-9])"


def _byte_regex(strings: list[str]) -> re.Pattern:
    return re.compile(_pattern(strings).encode(), re.IGNORECASE)


def _chunks(path: Path):
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK_SIZE):
            yield chunk


def _accepted(match: re.Match, size: int, carried: bool) -> bool:
    # Matches touching either edge of a partial buffer are judged in the buffer that holds their context.
    return match.end() < size - 1 and not (carried and match.start() == 0)


def _file_matches(path: Path, regex: re.Pattern, overlap: int) -> bool:
    buf, carried = b"", False
    for chunk in _chunks(path):
        buf += chunk
        if any(_accepted(m, len(buf), carried) for m in regex.finditer(buf)):
            return True
        carried = carried or len(buf) > overlap
        buf = buf[-overlap:]
    return any(not (carried and m.start() == 0) for m in regex.finditer(buf))


def _leaks(run: Path, files, strings: list[str]) -> list[str]:
    if not strings:
        return []
    regex, overlap = _byte_regex(strings), max(len(s) for s in strings) + 4
    return [p.relative_to(run).as_posix() for p in files if _file_matches(p, regex, overlap)]


def outside_audit_leaks(run: Path, strings: list[str]) -> list[str]:
    run = Path(run)
    audit = run / "audit"
    return _leaks(run, [p for p in _files(run) if audit not in p.parents], strings)


def remaining_leaks(run: Path, strings: list[str]) -> list[str]:
    """Model names still present under <run>/audit/ (outside it is checked before redaction)."""
    return _leaks(Path(run), _files(Path(run) / "audit"), strings)


def _substitute(text: str, plan: dict, run_id: str) -> tuple[str, int]:
    own = {a.lower() for a in plan["own_aliases"]}
    strings = plan["own_aliases"] + plan["other_aliases"]
    if not strings:
        return text, 0
    regex = re.compile(_pattern(strings), re.IGNORECASE)
    return regex.subn(lambda m: run_id if m.group(0).lower() in own else OTHER_PLACEHOLDER, text)


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
