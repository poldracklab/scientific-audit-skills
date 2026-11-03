# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Prepare a blinded consensus folder for one paper's audits, or attach the model mapping.

usage: consensus.py prepare <paper_id> [--root R]
       consensus.py attach-models <consensus_dir> [--root R]
"""
import argparse
import hashlib
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

from discover import ConsensusError, check_same_manifest, completed_runs
from redact import aliases, load_models, outside_audit_leaks, plan_redaction, redact_run, remaining_leaks

ALPHABET = "abcdefghijklmnopqrstuvwxyz234567"
ROOT_MARKER = ".autoaudit-root"


def make_consensus_id(now: datetime, rng: random.Random) -> str:
    suffix = "".join(rng.choice(ALPHABET) for _ in range(4))
    return f"{now.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}-{suffix}"


def _paper_runs(root: Path, paper_id: str) -> Path:
    path = root / "runs" / paper_id
    if not path.is_dir():
        raise ConsensusError(f"no runs folder for {paper_id}: {path}")
    return path


def _select_runs(paper_runs: Path) -> tuple[list[Path], list[Path]]:
    completed, skipped = completed_runs(paper_runs)
    for run in skipped:
        print(f"warning: skipping {run.name}: audit not completed", file=sys.stderr)
    if len(completed) < 2:
        raise ConsensusError(f"need at least 2 completed runs, found {len(completed)}")
    check_same_manifest(completed)
    return completed, skipped


def _models_for(root: Path, paper_id: str, runs: list[Path]) -> dict[str, str]:
    models = load_models(root / "registry.jsonl", paper_id)
    if missing := [r.name for r in runs if r.name not in models]:
        raise ConsensusError(f"no registry entry for run(s) {', '.join(missing)}; cannot blind them")
    return models


def _all_aliases(models: dict[str, str]) -> list[str]:
    return [a for m in models.values() for a in aliases(m)]


def _check_outside_audit(runs: list[Path], strings: list[str]) -> None:
    leaks = [f"{r.name}/{p}" for r in runs for p in outside_audit_leaks(r, strings)]
    if leaks:
        raise ConsensusError(f"model names in prepared inputs (not redacted): {', '.join(leaks)}")


def _redact_all(runs: list[Path], models: dict[str, str]) -> dict[str, dict[str, int]]:
    others = list(models.values())
    return {r.name: redact_run(r, r.name, plan_redaction(r, models[r.name], others)) for r in runs}


def _check_remaining(runs: list[Path], strings: list[str]) -> None:
    leaks = [f"{r.name}/{p}" for r in runs for p in remaining_leaks(r, strings)]
    if leaks:
        raise ConsensusError(f"model names remain after redaction: {', '.join(leaks)}")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inputs(cid: str, paper_id: str, now: datetime, runs, skipped, redactions) -> dict:
    return {"consensus_id": cid, "paper_id": paper_id, "created": now.isoformat(timespec="seconds"),
            "runs": [{"run_id": r.name, "audit_qmd_sha256": _sha256(r / "audit" / "audit.qmd")} for r in runs],
            "skipped": [r.name for r in skipped], "redactions": redactions}


def _create_folder(paper_runs: Path, now: datetime, rng: random.Random) -> Path:
    while True:
        out = paper_runs / "consensus" / make_consensus_id(now, rng)
        if not out.exists():
            out.mkdir(parents=True)
            return out


def prepare(root: Path, paper_id: str, now: datetime | None = None, rng: random.Random | None = None) -> Path:
    now, rng = now or datetime.now(timezone.utc), rng or random.SystemRandom()
    paper_runs = _paper_runs(Path(root), paper_id)
    runs, skipped = _select_runs(paper_runs)
    models = _models_for(Path(root), paper_id, runs)
    strings = _all_aliases(models)
    _check_outside_audit(runs, strings)
    redactions = _redact_all(runs, models)
    _check_remaining(runs, strings)
    out = _create_folder(paper_runs, now, rng)
    inputs = _inputs(out.name, paper_id, now, runs, skipped, redactions)
    (out / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n", encoding="utf-8")
    return out


def attach_models(root: Path, consensus_dir: Path) -> Path:
    inputs = json.loads((Path(consensus_dir) / "inputs.json").read_text(encoding="utf-8"))
    models = load_models(Path(root) / "registry.jsonl", inputs["paper_id"])
    mapping = {r["run_id"]: models.get(r["run_id"], "unknown") for r in inputs["runs"]}
    path = Path(consensus_dir) / "run_models.json"
    path.write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")
    return path


def _root(explicit: Path | None) -> Path:
    root = (explicit or Path.cwd()).resolve()
    if not (root / ROOT_MARKER).exists():
        raise ConsensusError(f"not a corpus root (no {ROOT_MARKER} in {root})")
    return root


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="consensus.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare").add_argument("paper_id")
    sub.add_parser("attach-models").add_argument("consensus_dir", type=Path)
    for name in ("prepare", "attach-models"):
        sub.choices[name].add_argument("--root", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        root = _root(args.root)
        if args.command == "prepare":
            print(prepare(root, args.paper_id))
        else:
            print(attach_models(root, args.consensus_dir))
    except ConsensusError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
