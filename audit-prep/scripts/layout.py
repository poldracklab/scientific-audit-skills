# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Locate a paper folder, move it into prepared/, and apply the prep.yaml file plan."""
import shutil
from pathlib import Path

from corpus import Corpus, CorpusError

PLAN_NAME = "prep.yaml"
STATEMENTS = "statements.md"
OWN_FILES = {PLAN_NAME, STATEMENTS}
LAYOUT_DIRS = {"paper", "data", "github", "preregistration"}
MOVE_ORDER = {"unsorted": 0, "data": 1, "archive": 1, "skip": 2, "paper": 3, "supplement": 3}


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
