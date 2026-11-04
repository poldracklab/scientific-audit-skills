"""Copy selected raw inputs into a draft; raw folders are never moved."""
import shutil
from pathlib import Path

import manifest as mf
from corpus import Corpus, CorpusError

PLAN_NAME = "prep.yaml"
STATEMENTS = "statements.md"
OWN_FILES = {PLAN_NAME, STATEMENTS}
SELECTED_ROLES = {"paper", "supplement", "corrigendum", "data", "archive"}
DOCUMENT_LISTS = {"supplement": "supplements", "corrigendum": "corrigenda"}


def locate(target: Path, corpus: Corpus) -> tuple[Path, str]:
    target = Path(target).absolute()
    prepared = corpus.prepared_dir(target.name).absolute()
    raw = (corpus.root / target.name).absolute()
    if target not in (raw, prepared):
        raise CorpusError(f"{target} is not a raw or prepared paper folder in {corpus.root}")
    for path in (raw, corpus.prepared, prepared):
        if path.is_symlink():
            raise CorpusError(f"symlink not permitted: {path}")
        if not path.resolve().is_relative_to(corpus.root.resolve()):
            raise CorpusError(f"{path} is outside corpus {corpus.root}")
    if prepared.exists():
        return prepared, "prepared"
    if target == raw and raw.is_dir():
        return raw, "raw"
    raise CorpusError(f"{target} not found, and no {prepared}")


def _rel(path: Path, base: Path) -> str:
    return path.relative_to(base).as_posix()


def _destination(entry: dict, prepared: Path) -> Path | None:
    name, role = entry["path"], entry["role"]
    suffix = Path(name).suffix.lower()
    if role == "paper":
        return prepared / "paper" / f"paper{suffix}"
    if role in DOCUMENT_LISTS:
        return prepared / "paper" / f"{role}_{entry['order']}{suffix}"
    if role in ("data", "archive"):
        return prepared / "data" / name
    return None


def _planned(plan: dict, prepared: Path) -> list[tuple[dict, Path | None]]:
    return [(f, _destination(f, prepared)) for f in plan["files"] if f["path"] not in OWN_FILES]


def missing_files(plan: dict, folder: Path, corpus: Corpus) -> list[str]:
    raw = corpus.root / folder.name
    return [f"{e['path']}: listed in prep.yaml but not found" for e in plan["files"]
            if e["role"] in SELECTED_ROLES and not (raw / e["path"]).exists()]


def source_snapshot(raw: Path, plan: dict) -> dict:
    """Pin selected source bytes and layout so retries cannot reuse stale conversions."""
    selection, files = [], []
    for entry in plan["files"]:
        if entry["role"] not in SELECTED_ROLES:
            continue
        selection.append({k: entry.get(k) for k in ("path", "role", "order")})
        src = raw / entry["path"]
        mf.reject_symlinks(src)
        if src.is_dir():
            files.extend({**f, "path": f"{entry['path']}/{f['path']}"} for f in mf.hash_tree(src, exclude=()))
        else:
            files.append({"path": entry["path"], "size": src.stat().st_size, "sha256": mf._sha256(src)})
    return {"selection": sorted(selection, key=lambda e: e["path"]),
            "files": sorted(files, key=lambda e: e["path"]),
            "structured_conversion": plan.get("structured_conversion", True)}


def _copy(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dest, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dest)


def _record_file(entry: dict, dest: Path, prepared: Path, m: dict, previous: dict) -> None:
    role, name = entry["role"], entry["path"]
    if role == "paper" or role in DOCUMENT_LISTS:
        doc = {"original_name": name, "path": _rel(dest, prepared), "pages": None, "conversions": {}}
        if role == "paper":
            m["documents"]["paper"] = doc
        else:
            m["documents"][DOCUMENT_LISTS[role]].append(doc)
    else:
        record = {"original_path": name, "path": _rel(dest, prepared)}
        if role == "archive":
            record.update(archive=True, extracted=previous.get(name))
        m["local_data"].append(record)


def apply_file_plan(prepared: Path, plan: dict, corpus: Corpus, manifest: dict) -> None:
    raw = corpus.root / prepared.name
    previous = {e["original_path"]: e.get("extracted") for e in manifest["local_data"] if e.get("archive")}
    manifest.update(documents={"paper": None, "supplements": [], "corrigenda": []}, local_data=[], unsorted=[])
    for entry, dest in _planned(plan, prepared):
        if dest is None:
            manifest["unsorted"].append({"original_path": entry["path"],
                                        "left_at": f"{prepared.name}/{entry['path']}",
                                        "reason": entry.get("reason")})
            continue
        _copy(raw / entry["path"], dest)
        _record_file(entry, dest, prepared, manifest, previous)
    for key in DOCUMENT_LISTS.values():
        manifest["documents"][key].sort(key=lambda d: d["path"])


def create_draft(raw: Path, prepared: Path) -> Path:
    prepared.mkdir(parents=True)
    shutil.copy2(raw / PLAN_NAME, prepared / PLAN_NAME)
    return prepared
