# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Execute a reviewed prep.yaml: scan, check the plan, run every step, then finalize."""
import os
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import fetch_common
import manifest as mf
import plan_check
import review
import scan
import statements
from archives import extract_archives
from convert import previous_conversions, process_documents, record_metadata
from corpus import Corpus, CorpusError
from fetch_links import fetch_all
from layout import (
    OWN_FILES,
    PLAN_NAME,
    STATEMENTS,
    _planned,
    apply_file_plan,
    locate,
    missing_files,
    create_draft,
    source_snapshot,
)

import docs


SCRIPTS_DIR = Path(__file__).resolve().parent


class PlanError(Exception):
    pass


@dataclass
class Clients:
    get_json: Callable = fetch_common.default_get_json
    get_bytes: Callable = fetch_common.default_get_bytes
    post_json: Callable = fetch_common.default_post_json
    run: Callable = subprocess.run
    tool_versions: Callable = docs.tool_versions


def write_statements(pdf: Path, out: Path) -> Path:
    with tempfile.TemporaryDirectory() as tmp:
        text = docs.pdf_to_text(pdf, Path(tmp) / "paper.txt").read_text(errors="replace")
    return statements.write_statements_md(statements.extract_statements(text), out)


def _paper_entry(plan: dict) -> dict | None:
    return next((f for f in plan["files"] if f.get("role") == "paper"), None)


def scan_folder(raw: Path, get_json: Callable) -> dict:
    """Write `prep.yaml` and, when a paper candidate exists, `statements.md` into the raw folder."""
    plan = scan.build_plan(raw, get_json)
    plan["files"] = [f for f in plan["files"] if f["path"] not in OWN_FILES]
    scan.write_plan(plan, raw / PLAN_NAME)
    paper = _paper_entry(plan)
    if paper:
        write_statements(raw / paper["path"], raw / STATEMENTS)
    return plan


def _refuse_if(problems: list[str]) -> None:
    if problems:
        raise PlanError(f"{PLAN_NAME} is not ready:\n" + "\n".join(f"- {p}" for p in problems))


def checked_plan(folder: Path, corpus: Corpus) -> dict:
    path = folder / PLAN_NAME
    if not path.is_file():
        raise PlanError(f"no {PLAN_NAME} in {folder}; run `prep.py scan` first")
    plan = scan.load_plan(path)
    _refuse_if(scan.unresolved(plan))
    _refuse_if(missing_files(plan, folder, corpus))
    return plan


def print_plan(folder: Path, plan: dict, corpus: Corpus) -> None:
    prepared = corpus.prepared_dir(folder.name)
    show = lambda p: os.path.relpath(p, corpus.root)  # noqa: E731
    print(f"COPY selected inputs from {corpus.root / folder.name} -> {show(prepared)}")
    for entry, dest in _planned(plan, prepared):
        print(f"COPY {entry['path']} -> {show(dest)}" if dest else f"EXCLUDE {entry['path']} ({entry['role']})")
        if entry["role"] in ("paper", "supplement"):
            print(f"CONVERT {show(dest)}")
    for link in plan.get("links", []):
        if link.get("role") in ("prereg", "code", "data"):
            print(f"FETCH {link['role']} {link.get('class')} {link['canonical']}")


def skill_commit(scripts_dir: Path = SCRIPTS_DIR) -> str | None:
    """Short git commit of the audit-prep checkout, or None when it is not a git checkout."""
    try:
        out = subprocess.run(["git", "-C", str(scripts_dir), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None if out.returncode == 0 else None


def _start_manifest(prepared: Path, plan: dict, clients: Clients) -> dict:
    m = mf.load_manifest(prepared) or mf.new_manifest(prepared.name, plan["reviewed_by"])
    m.update(prepared_by=plan["reviewed_by"], data_collection=plan.get("data_collection"),
             prep_versions={**clients.tool_versions(structured=plan.get("structured_conversion", True)),
                            "skill": skill_commit()}, warnings=[], review=None,
             finalized=False, plan_sha256=review.plan_sha256(plan))
    return m


def run_prep(target: Path, corpus: Corpus, clients: Clients | None = None, dry_run: bool = False) -> dict:
    clients = clients or Clients()
    folder, kind = locate(target, corpus)
    if kind == "prepared":
        mf.reject_symlinks(folder)
    if mf.is_prepared(folder):
        raise CorpusError(f"{folder} is already finalized")
    plan = checked_plan(folder, corpus)
    snapshot = _check_sources(folder, plan, corpus)
    if dry_run:
        print_plan(folder, plan, corpus)
        return mf.load_manifest(folder) or mf.new_manifest(folder.name, plan["reviewed_by"])
    prepared = create_draft(folder, corpus.prepared_dir(folder.name)) if kind == "raw" else folder
    m = _start_manifest(prepared, plan, clients)
    m["source_snapshot"] = snapshot
    previous = previous_conversions(m)
    mf.write_manifest(prepared, m)
    steps = [lambda: apply_file_plan(prepared, plan, corpus, m),
             lambda: extract_archives(prepared, m, clients.run),
             lambda: process_documents(prepared, m, clients.run, previous,
                                       structured=plan.get("structured_conversion", True)),
             lambda: record_metadata(prepared, plan, m, clients.get_json),
             lambda: fetch_all(prepared, plan, m, clients)]
    for step in steps:
        step()
        mf.write_manifest(prepared, m)
    m["review"] = review.review_manifest(m, plan)
    mf.write_manifest(prepared, m)
    return m


def _check_sources(folder: Path, plan: dict, corpus: Corpus) -> dict:
    snapshot = source_snapshot(corpus.root / folder.name, plan)
    snapshot["retrieval_sources"] = _retrieval_sources(plan)
    manifest = mf.load_manifest(folder) or {}
    previous = manifest.get("source_snapshot")
    if previous and previous["selection"] != snapshot["selection"]:
        raise PlanError("file selection changed; move the draft aside and create a fresh draft from raw inputs")
    if previous and previous["files"] != snapshot["files"]:
        raise PlanError("raw inputs changed; move the draft aside and create a fresh draft from raw inputs")
    if previous and previous.get("structured_conversion", True) != snapshot["structured_conversion"]:
        raise PlanError("conversion choice changed; move the draft aside and create a fresh draft from raw inputs")
    prior_sources = (previous or {}).get("retrieval_sources", _retrieval_sources(manifest))
    if any(source not in snapshot["retrieval_sources"] for source in prior_sources):
        raise PlanError("retrieval source changed; move the draft aside and create a fresh draft from raw inputs")
    return snapshot


def _retrieval_sources(record: dict) -> list[dict]:
    return [{key: link.get(key) for key in ("url", "canonical", "class", "role")}
            for link in record.get("links", []) if link.get("role") in ("data", "code", "prereg")]


def _set_writable(target: Path, writable: bool) -> None:
    mode = stat.S_IMODE(target.lstat().st_mode)
    os.chmod(target, mode | 0o200 if writable else mode & ~0o222)


def _make_readonly(root: Path, keep: Path) -> None:
    """Remove write bits from everything under `root` except `keep` (written last)."""
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        for name in filenames + dirnames:
            target = Path(dirpath) / name
            if target != keep and not target.is_symlink():
                _set_writable(target, False)
    _set_writable(root, False)


def _unlock_outputs(prepared: Path) -> None:
    """After a crashed finalize, let README.md and manifest.json be rewritten."""
    for name in ("README.md", mf.MANIFEST_NAME):
        if (prepared / name).is_file():
            _set_writable(prepared / name, True)


def _manifest(folder: Path) -> dict:
    m = mf.load_manifest(folder)
    if m is None:
        raise CorpusError(f"{folder} has no manifest.json; run `prep.py run` first")
    return m


def _plan(folder: Path) -> dict:
    if not (folder / PLAN_NAME).is_file():
        raise CorpusError(f"{folder} has no {PLAN_NAME}")
    plan = scan.load_plan(folder / PLAN_NAME)
    _refuse_if(plan_check.acceptance_problems(plan))
    return plan


def load_prepared(folder: Path) -> tuple[dict, dict]:
    """The manifest and prep.yaml of a folder that `run` has written to."""
    return _manifest(folder), _plan(folder)


def _gate(prepared: Path, m: dict, plan: dict) -> None:
    """Record the review; refuse while any problem is open."""
    m["review"] = review.review_folder(m, plan)
    mf.write_manifest(prepared, m)
    if m["review"]["status"] != "ok":
        raise review.ReviewError(review.format_review(m["review"]))


def finalize(prepared: Path) -> dict:
    mf.reject_symlinks(prepared)
    m = _manifest(prepared)
    if mf.is_prepared(prepared):
        return m
    plan = _plan(prepared)
    _unlock_outputs(prepared)
    _gate(prepared, m, plan)
    m["files"] = mf.hash_tree(prepared)
    (prepared / "README.md").write_text(mf.render_readme(m), encoding="utf-8")
    _make_readonly(prepared, keep=prepared / mf.MANIFEST_NAME)
    m["finalized"] = True
    _set_writable(mf.write_manifest(prepared, m), False)
    return m
