"""Discover the completed audit runs of one paper for a consensus report."""
import json
from pathlib import Path


class ConsensusError(Exception):
    """A paper's runs cannot be reconciled as they stand."""


def _opencode_stop(event: dict) -> bool:
    part = event.get("part")
    return event.get("type") == "step_finish" and isinstance(part, dict) and part.get("reason") == "stop"


def COMPLETION_EVENTS(event: dict) -> bool:
    """True for the final event each headless harness emits when the agent finished."""
    return event.get("type") in ("result", "turn.completed") or _opencode_stop(event)


def find_runs(paper_runs: Path) -> list[Path]:
    """Run folders (those holding run.json) under runs/<paper_id>/, sorted by name."""
    return sorted(p for p in Path(paper_runs).iterdir() if p.is_dir() and (p / "run.json").is_file())


def _last_event(log: Path) -> dict | None:
    for line in reversed(log.read_text(encoding="utf-8", errors="replace").splitlines()):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict):
            # Claude can emit command bookkeeping after its final result.
            if event.get("type") == "command_lifecycle" and event.get("state") == "completed":
                continue
            return event
    return None


def log_finished(log: Path) -> bool:
    event = _last_event(Path(log))
    return event is not None and COMPLETION_EVENTS(event)


def is_completed(run: Path) -> bool:
    audit = Path(run) / "audit"
    if not ((audit / "audit.qmd").is_file() and (audit / "audit.html").is_file()):
        return False
    log = audit / "agent_log.jsonl"
    return not log.exists() or log_finished(log)


def completed_runs(paper_runs: Path) -> tuple[list[Path], list[Path]]:
    runs = find_runs(paper_runs)
    return [r for r in runs if is_completed(r)], [r for r in runs if not is_completed(r)]


def _manifest(run: Path) -> str | None:
    return json.loads((run / "run.json").read_text(encoding="utf-8")).get("manifest_sha256")


def check_same_manifest(runs: list[Path]) -> None:
    by_manifest = {}
    for run in runs:
        by_manifest.setdefault(_manifest(run), []).append(run.name)
    if len(by_manifest) > 1:
        groups = "; ".join(f"{sha}: {', '.join(ids)}" for sha, ids in by_manifest.items())
        raise ConsensusError(f"runs were made from different prepared inputs ({groups})")
