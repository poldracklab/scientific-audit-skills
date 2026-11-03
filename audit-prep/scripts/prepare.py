# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Execute a reviewed prep.yaml: move, rename, convert, fetch, then finalize the prepared folder."""
import dataclasses
import json
import os
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import crossref
import docs
import fetch_common
import fetch_github
import fetch_neurovault
import fetch_osf
import fetch_zenodo
import links
import manifest as mf
import prereg
import scan
import statements
from corpus import Corpus, CorpusError

PLAN_NAME = "prep.yaml"
STATEMENTS = "statements.md"
OWN_FILES = {PLAN_NAME, STATEMENTS}
LAYOUT_DIRS = {"paper", "data", "github", "preregistration"}
ARCHIVE_SUFFIXES = (".tar.gz", ".tar.bz2", ".tar.xz", ".tar.zst", ".tgz", ".tar", ".zip", ".zst", ".7z")
MOVE_ORDER = {"unsorted": 0, "data": 1, "archive": 1, "skip": 2, "paper": 3, "supplement": 3}
NOT_APPLICABLE = {"text": "not_applicable", "pages": "not_applicable",
                  "structured": "not_applicable", "statements": "not_applicable"}
LINK_STATUS = {"failed": "failed", "unsupported": "skipped", "skipped": "skipped"}


class PlanError(Exception):
    pass


@dataclass
class Clients:
    get_json: Callable = fetch_common.default_get_json
    get_bytes: Callable = fetch_common.default_get_bytes
    post_json: Callable = fetch_common.default_post_json
    run: Callable = subprocess.run
    tool_versions: Callable = docs.tool_versions


# --- scan --------------------------------------------------------------------


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


# --- locating and moving -----------------------------------------------------


def _is_under(path: Path, parent: Path) -> bool:
    return path.resolve().is_relative_to(parent.resolve())


def locate(target: Path, corpus: Corpus) -> tuple[Path, str]:
    target = Path(target)
    if target.exists():
        return target, "prepared" if _is_under(target, corpus.prepared) else "raw"
    moved = corpus.prepared_dir(target.name)
    if moved.exists():
        return moved, "prepared"
    raise CorpusError(f"{target} not found, and no {moved}")


def move_into_prepared(raw: Path, corpus: Corpus) -> Path:
    dest = corpus.prepared_dir(raw.name)
    if dest.exists():
        raise CorpusError(f"{dest} already exists; refusing to move {raw} over it")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(raw), str(dest))
    return dest


def checked_plan(folder: Path) -> dict:
    path = folder / PLAN_NAME
    if not path.is_file():
        raise PlanError(f"no {PLAN_NAME} in {folder}; run `prep.py scan` first")
    plan = scan.load_plan(path)
    problems = scan.unresolved(plan)
    if problems:
        raise PlanError("prep.yaml is not ready:\n" + "\n".join(f"- {p}" for p in problems))
    return plan


# --- file plan ---------------------------------------------------------------


def _rel(path: Path, base: Path) -> str:
    return path.relative_to(base).as_posix()


def _destination(entry: dict, prepared: Path, corpus: Corpus) -> Path | None:
    name, role = entry["path"], entry["role"]
    suffix = Path(name).suffix.lower()
    if role == "paper":
        return prepared / "paper" / f"paper{suffix}"
    if role == "supplement":
        return prepared / "paper" / f"supplement_{entry['order']}{suffix}"
    if role in ("data", "archive"):
        return prepared / "data" / Path(name).name
    if role == "unsorted":
        return corpus.unsorted_dir(prepared.name) / name
    return None


def _parked(prepared: Path, name: str) -> Path:
    return prepared / f".parked-{name}"


def _source(prepared: Path, name: str) -> Path:
    parked = _parked(prepared, name)
    return parked if parked.exists() else prepared / name


def _park_collisions(prepared: Path, planned: list[tuple[dict, Path]]) -> None:
    """Rename top-level raw items named like a layout dir (e.g. `data/`) out of the way first."""
    for entry, dest in planned:
        src = prepared / entry["path"]
        if entry["path"] in LAYOUT_DIRS and dest is not None and src.exists() and not dest.exists():
            src.rename(_parked(prepared, entry["path"]))


def _move(src: Path, dest: Path) -> str:
    if dest.exists():
        if src.exists() and not dest.is_relative_to(src):
            raise CorpusError(f"both {src} and {dest} exist; resolve by hand")
        return "skipped"
    if not src.exists():
        return "missing"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    return "ok"


def _record_file(entry: dict, dest: Path, prepared: Path, corpus: Corpus, m: dict, previous: dict) -> None:
    role, name = entry["role"], entry["path"]
    if role in ("paper", "supplement"):
        doc = {"original_name": name, "path": _rel(dest, prepared), "pages": None, "conversions": {}}
        if role == "paper":
            m["documents"]["paper"] = doc
        else:
            m["documents"]["supplements"].append(doc)
    elif role == "data":
        m["local_data"].append({"original_path": name, "path": _rel(dest, prepared)})
    elif role == "archive":
        m["local_data"].append({"original_path": name, "path": _rel(dest, prepared), "archive": True,
                                "extracted": previous.get(name)})
    elif role == "unsorted":
        m["unsorted"].append({"original_path": name, "moved_to": _rel(dest, corpus.root),
                              "reason": entry.get("reason")})


def _planned(plan: dict, prepared: Path, corpus: Corpus) -> list[tuple[dict, Path | None]]:
    entries = [f for f in plan["files"] if f["path"] not in OWN_FILES]
    entries.sort(key=lambda f: MOVE_ORDER.get(f["role"], 2))
    return [(f, _destination(f, prepared, corpus)) for f in entries]


def apply_file_plan(prepared: Path, plan: dict, corpus: Corpus, manifest: dict) -> None:
    previous = {e["original_path"]: e.get("extracted") for e in manifest["local_data"] if e.get("archive")}
    manifest.update(documents={"paper": None, "supplements": []}, local_data=[], unsorted=[])
    planned = _planned(plan, prepared, corpus)
    _park_collisions(prepared, planned)
    for entry, dest in planned:
        if dest is None:
            manifest["warnings"].append(f"{entry['path']}: role {entry['role']}, left in place ({entry.get('reason')})")
            continue
        if _move(_source(prepared, entry["path"]), dest) == "missing":
            manifest["warnings"].append(f"{entry['path']}: listed in prep.yaml but not found")
            continue
        _record_file(entry, dest, prepared, corpus, manifest, previous)
    manifest["documents"]["supplements"].sort(key=lambda d: d["path"])
    _move(prepared / STATEMENTS, prepared / "paper" / STATEMENTS)


# --- archives ----------------------------------------------------------------


def _archive_stem(name: str) -> str | None:
    suffix = next((s for s in ARCHIVE_SUFFIXES if name.lower().endswith(s)), None)
    return name[: -len(suffix)] if suffix else None


def _unzstd(archive: Path, dest: Path, run) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / archive.name[: -len(".zst")]
        r = run(["zstd", "-d", "-q", "-o", str(out), str(archive)], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError((r.stderr or "zstd failed").strip())
        if tarfile.is_tarfile(out):
            with tarfile.open(out) as tar:
                tar.extractall(dest, filter="data")
        else:
            dest.mkdir(parents=True)
            shutil.move(str(out), str(dest / out.name))


def _unpack(archive: Path, dest: Path, run) -> None:
    name = archive.name.lower()
    if name.endswith(".zip"):
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(dest)
    elif name.endswith(".zst"):
        _unzstd(archive, dest, run)
    else:
        with tarfile.open(archive) as tar:
            tar.extractall(dest, filter="data")


def _extract(archive: Path, target: Path, run) -> None:
    partial = target.with_name(f".{target.name}.partial")
    shutil.rmtree(partial, ignore_errors=True)
    try:
        _unpack(archive, partial, run)
    except Exception:
        shutil.rmtree(partial, ignore_errors=True)
        raise
    partial.rename(target)


def _extract_entry(prepared: Path, entry: dict, m: dict, run) -> None:
    archive = prepared / entry["path"]
    target = archive.with_name(_archive_stem(archive.name) or archive.name + ".d")
    if target.exists():
        entry["extracted"] = "ok" if entry.get("extracted") == "ok" else "pre-existing"
    elif archive.name.lower().endswith(".7z"):
        entry["extracted"] = "skipped"
        m["warnings"].append(f"{entry['path']}: no extractor for .7z; extract by hand")
    else:
        try:
            _extract(archive, target, run)
            entry["extracted"] = "ok"
        except Exception as e:
            entry.update(extracted="failed", reason=str(e))
            m["warnings"].append(f"{entry['path']}: extraction failed: {e}")


def _nested_archives(prepared: Path, m: dict) -> list[dict]:
    dirs = {e["path"] for e in m["local_data"] if not e.get("archive") and not e.get("nested_archive")}
    dirs |= {e["path"].rsplit("/", 1)[0] + "/" + _archive_stem(Path(e["path"]).name)
             for e in m["local_data"] if e.get("archive") and _archive_stem(Path(e["path"]).name)}
    found = [p for d in sorted(dirs) if (prepared / d).is_dir() for p in sorted((prepared / d).rglob("*"))
             if p.is_file() and _archive_stem(p.name)]
    return [{"path": _rel(p, prepared), "nested_archive": True} for p in found]


def extract_archives(prepared: Path, manifest: dict, run) -> None:
    for entry in manifest["local_data"]:
        if entry.get("archive"):
            _extract_entry(prepared, entry, manifest, run)
    manifest["local_data"] += _nested_archives(prepared, manifest)


# --- documents ---------------------------------------------------------------


def _step(done: bool, action: Callable, label: str, m: dict) -> str:
    if done:
        return "skipped"
    try:
        action()
    except Exception as e:  # a failed conversion is recorded, never raised
        m["warnings"].append(f"{label}: {e}")
        return "failed"
    return "ok"


def _structured(pdf: Path, out_dir: Path, run) -> None:
    result = docs.pdf_to_structured(pdf, out_dir, run=run)
    if result["status"] != "ok":
        raise RuntimeError(f"docling failed: {result['reason']}")


def _process_pdf(pdf: Path, work: Path, doc: dict, m: dict, run) -> None:
    txt, pages = pdf.with_suffix(".txt"), work / "pages"
    conv = doc["conversions"]
    conv["text"] = _step(txt.exists(), lambda: docs.pdf_to_text(pdf, txt), f"{doc['path']} text", m)
    conv["pages"] = _step(any(pages.glob("p-*.png")), lambda: docs.pdf_to_pages(pdf, pages),
                          f"{doc['path']} pages", m)
    conv["structured"] = _step((work / f"{pdf.stem}.md").exists(), lambda: _structured(pdf, work, run),
                               f"{doc['path']} structured", m)
    doc["pages"] = len(list(pages.glob("p-*.png"))) or None


def _paper_statements(paper_dir: Path, doc: dict, m: dict) -> None:
    out = paper_dir / STATEMENTS

    def write():
        text = (paper_dir / "paper.txt").read_text(errors="replace")
        statements.write_statements_md(statements.extract_statements(text), out)

    doc["conversions"]["statements"] = _step(out.exists(), write, f"{doc['path']} statements", m)


def _process_supplement(prepared: Path, doc: dict, m: dict, run) -> None:
    src = prepared / doc["path"]
    work, suffix = src.with_suffix(""), src.suffix.lower()
    doc["conversions"] = dict(NOT_APPLICABLE)
    label = f"{doc['path']} text"
    if suffix == ".pdf":
        _process_pdf(src, work, doc, m, run)
    elif suffix == ".docx":
        md = src.with_suffix(".md")
        doc["conversions"]["text"] = _step(md.exists(), lambda: docs.docx_to_md(src, md, work / "media"), label, m)
    elif suffix == ".xlsx":
        doc["conversions"]["text"] = _step(any(work.glob("*.csv")), lambda: docs.xlsx_to_csv(src, work), label, m)


def process_documents(prepared: Path, manifest: dict, run) -> None:
    paper = manifest["documents"]["paper"]
    if paper:
        paper["conversions"] = dict(NOT_APPLICABLE)
        _process_pdf(prepared / paper["path"], prepared / "paper", paper, manifest, run)
        _paper_statements(prepared / "paper", paper, manifest)
    for doc in manifest["documents"]["supplements"]:
        _process_supplement(prepared, doc, manifest, run)


def record_metadata(prepared: Path, plan: dict, manifest: dict, get_json: Callable) -> None:
    meta, doi = None, plan.get("doi")
    try:
        meta = crossref.fetch_metadata(doi, get_json) if doi else None
    except Exception as e:  # metadata is optional; record why it is missing
        manifest["warnings"].append(f"crossref metadata for {doi} unavailable: {e}")
    if doi is None:
        manifest["warnings"].append("no doi in prep.yaml; crossref metadata not fetched")
    manifest["metadata"] = meta
    out = prepared / "paper" / "metadata.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(meta or {}, indent=2, ensure_ascii=False))


# --- fetching ----------------------------------------------------------------


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", text).strip(".") or "repo"


def _repo_dir(canonical: str) -> str:
    parts = fetch_github.parse_github_url(canonical) or (canonical.rstrip("/").rsplit("/", 1)[-1],)
    return "github/" + "__".join(_slug(p) for p in parts)


def _clone(prepared: Path, link: dict, clients: Clients) -> dict:
    rel = _repo_dir(link["canonical"])
    rec = fetch_github.clone_repo(link["url"], prepared / rel, run=clients.run)
    return {**rec, "path": None if rec["status"] == "failed" else rel}


def _data_fetchers(policy, clients: Clients) -> dict:
    gj, gb = clients.get_json, clients.get_bytes
    return {
        "osf": (fetch_osf.osf_id, lambda i, d: fetch_osf.fetch_osf_files(i, d, policy, gj, gb)),
        "zenodo": (fetch_zenodo.zenodo_id, lambda i, d: fetch_zenodo.fetch_zenodo(i, d, policy, gj, gb)),
        "neurovault": (fetch_neurovault.neurovault_id, lambda i, d: fetch_neurovault.fetch_neurovault(i, d, gj, gb)),
    }


def _failure(link: dict, status: str, reason: str) -> dict:
    return {"source": link.get("class"), "id": link["canonical"], "url": link["url"], "path": None,
            "status": status, "files": [], "reason": reason}


def _fetch_data(prepared: Path, link: dict, clients: Clients, policy) -> dict:
    cls = link.get("class")
    fetchers = _data_fetchers(policy, clients)
    if cls not in fetchers:
        rec = _failure(link, "unsupported", f"no fetcher for {cls}; fetch manually if needed")
        return {k: rec[k] for k in ("source", "id", "path", "status", "files", "reason")}
    id_of, fetch = fetchers[cls]
    ident = id_of(link["canonical"])
    if not ident:
        return _failure(link, "failed", f"no {cls} id in {link['canonical']}")
    rel = f"data/{cls}_{ident}"
    rec = dataclasses.asdict(fetch(ident, prepared / rel))
    return {**rec, "path": None if rec["status"] == "failed" else rel}


def _dispatch(prepared: Path, link: dict, clients: Clients, policy) -> tuple[str, dict]:
    role, cls = link.get("role"), link.get("class")
    if role == "prereg":
        return "preregistration", prereg.fetch_prereg(link, prepared, clients.get_json, clients.get_bytes)
    if cls == "github" and role in ("code", "data"):
        return "code", _clone(prepared, link, clients)
    if role == "code":
        return "code", _failure(link, "skipped", f"no fetcher for {cls}; fetch manually if needed")
    return "data", _fetch_data(prepared, link, clients, policy)


def _manifest_key(role: str, cls: str) -> str:
    return {"prereg": "preregistration", "code": "code"}.get(role, "code" if cls == "github" else "data")


def _fetch_link(prepared: Path, link: dict, m: dict, clients: Clients, policy) -> dict:
    if link.get("role") not in ("prereg", "code", "data"):
        return {**link, "status": "skipped", "fetched_to": None}
    try:
        key, rec = _dispatch(prepared, link, clients, policy)
    except Exception as e:  # a single failed fetch never stops the run
        key, rec = _manifest_key(link["role"], link.get("class")), _failure(link, "failed", str(e))
    if rec["status"] == "failed":
        m["warnings"].append(f"{link['canonical']}: fetch failed: {rec.get('reason')}")
    m[key].append(rec)
    return {**link, "status": LINK_STATUS.get(rec["status"], "ok"), "fetched_to": rec.get("path")}


def _relation_links(meta: dict | None) -> list[dict]:
    return [{"url": r["doi"], "canonical": links.canonicalize(r["doi"]), "class": "doi", "role": "unknown",
             "needs_review": False, "found_in": [], "reason": f"crossref relation {r['type']}",
             "status": "skipped", "fetched_to": None} for r in (meta or {}).get("relations", [])]


def fetch_all(prepared: Path, plan: dict, manifest: dict, clients: Clients) -> None:
    manifest.update(preregistration=[], code=[], data=[])
    policy = fetch_common.SizePolicy.from_plan(plan.get("size_policy") or {})
    fetched = [_fetch_link(prepared, link, manifest, clients, policy) for link in plan.get("links", [])]
    manifest["links"] = fetched + _relation_links(manifest.get("metadata"))
    out = prepared / "paper" / "links.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest["links"], indent=2, ensure_ascii=False))


# --- run and finalize --------------------------------------------------------


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


def _make_readonly(root: Path) -> None:
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        for name in filenames + dirnames:
            target = Path(dirpath) / name
            if not target.is_symlink():
                os.chmod(target, stat.S_IMODE(target.lstat().st_mode) & ~0o222)
    os.chmod(root, stat.S_IMODE(root.lstat().st_mode) & ~0o222)


def finalize(prepared: Path) -> dict:
    m = mf.load_manifest(prepared)
    if m is None:
        raise CorpusError(f"{prepared} has no manifest.json; run `prep.py run` first")
    if m.get("finalized"):
        return m
    m.update(files=mf.hash_tree(prepared), finalized=True)
    mf.write_manifest(prepared, m)
    (prepared / "README.md").write_text(mf.render_readme(m), encoding="utf-8")
    _make_readonly(prepared)
    return m
