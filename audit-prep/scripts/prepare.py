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
import scan
import statements
from archives import extract_archives
from convert import process_documents, record_metadata
from corpus import Corpus, CorpusError
from fetch_links import fetch_all
from layout import (
    OWN_FILES,
    PLAN_NAME,
    STATEMENTS,
    _planned,
    apply_file_plan,
    locate,
    move_into_prepared,
)

import docs


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


def checked_plan(folder: Path) -> dict:
    path = folder / PLAN_NAME
    if not path.is_file():
        raise PlanError(f"no {PLAN_NAME} in {folder}; run `prep.py scan` first")
    plan = scan.load_plan(path)
    problems = scan.unresolved(plan)
    if problems:
        raise PlanError("prep.yaml is not ready:\n" + "\n".join(f"- {p}" for p in problems))
    return plan


def print_plan(folder: Path, plan: dict, corpus: Corpus) -> None:
    prepared = corpus.prepared_dir(folder.name)
    show = lambda p: os.path.relpath(p, corpus.root)  # noqa: E731
    print(f"MOVE {folder} -> {show(prepared)}")
    for entry, dest in _planned(plan, prepared, corpus):
        print(f"MOVE {entry['path']} -> {show(dest)}" if dest else f"LEAVE {entry['path']} ({entry['role']})")
        if entry["role"] in ("paper", "supplement"):
            print(f"CONVERT {show(dest)}")
    for link in plan.get("links", []):
        if link.get("role") in ("prereg", "code", "data"):
            print(f"FETCH {link['role']} {link.get('class')} {link['canonical']}")


def _start_manifest(prepared: Path, plan: dict, clients: Clients) -> dict:
    m = mf.load_manifest(prepared) or mf.new_manifest(prepared.name, plan["reviewed_by"])
    m.update(prepared_by=plan["reviewed_by"], data_collection=plan.get("data_collection"),
             prep_versions=clients.tool_versions(), warnings=[])
    return m


def run_prep(target: Path, corpus: Corpus, clients: Clients | None = None, dry_run: bool = False) -> dict:
    clients = clients or Clients()
    folder, kind = locate(target, corpus)
    if mf.is_prepared(folder):
        raise CorpusError(f"{folder} is already finalized")
    plan = checked_plan(folder)
    if dry_run:
        print_plan(folder, plan, corpus)
        return mf.load_manifest(folder) or mf.new_manifest(folder.name, plan["reviewed_by"])
    prepared = move_into_prepared(folder, corpus) if kind == "raw" else folder
    m = _start_manifest(prepared, plan, clients)
    steps = [lambda: apply_file_plan(prepared, plan, corpus, m),
             lambda: extract_archives(prepared, m, clients.run),
             lambda: process_documents(prepared, m, clients.run),
             lambda: record_metadata(prepared, plan, m, clients.get_json),
             lambda: fetch_all(prepared, plan, m, clients)]
    for step in steps:
        step()
        mf.write_manifest(prepared, m)
    return m


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


def finalize(prepared: Path) -> dict:
    m = mf.load_manifest(prepared)
    if m is None:
        raise CorpusError(f"{prepared} has no manifest.json; run `prep.py run` first")
    if m.get("finalized"):
        return m
    _unlock_outputs(prepared)
    m["files"] = mf.hash_tree(prepared)
    (prepared / "README.md").write_text(mf.render_readme(m), encoding="utf-8")
    _make_readonly(prepared, keep=prepared / mf.MANIFEST_NAME)
    m["finalized"] = True
    _set_writable(mf.write_manifest(prepared, m), False)
    return m
