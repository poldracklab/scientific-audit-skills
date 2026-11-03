# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Create a blinded audit run: clone a finalized prepared folder under a random run id.

The model name goes only into the corpus registry, never inside the run folder.
"""
import argparse
import hashlib
import json
import random
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from corpus import Corpus, CorpusError, find_root
from manifest import MANIFEST_NAME, is_prepared

ALPHABET = "abcdefghijklmnopqrstuvwxyz234567"


def make_run_id(rng: random.Random | None = None) -> str:
    rng = rng or random.SystemRandom()
    return "".join(rng.choice(ALPHABET) for _ in range(8))


def _try_clonefile(src: Path, dest: Path, run) -> bool:
    try:
        return run(["cp", "-Rc", f"{src}/.", str(dest)], capture_output=True).returncode == 0
    except OSError:
        return False


def _try_rsync(src: Path, dest: Path, run) -> bool:
    try:
        return run(["rsync", "-a", f"{src}/", f"{dest}/"], capture_output=True).returncode == 0
    except OSError:
        return False


def _clear_partial(dest: Path) -> None:
    """Keep our reservation while removing only the contents we partially copied."""
    restore_write(dest)
    for child in dest.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def clone_tree(src: Path, dest: Path, run=subprocess.run) -> str:
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        dest.mkdir()
    except FileExistsError as exc:
        raise CorpusError(f"destination already exists: {dest}") from exc
    try:
        if _try_clonefile(src, dest, run):
            return "clonefile"
        _clear_partial(dest)
        if _try_rsync(src, dest, run):
            return "rsync"
        raise CorpusError(f"could not copy {src} to {dest}")
    except Exception:
        _clear_partial(dest)
        dest.rmdir()
        raise


def restore_write(dest: Path) -> None:
    for p in (dest, *dest.rglob("*")):
        if not p.is_symlink():
            p.chmod(p.stat().st_mode | 0o200)


def set_dropbox_ignored(dest: Path, run=subprocess.run) -> bool:
    try:
        return run(["xattr", "-w", "com.dropbox.ignored", "1", str(dest)], capture_output=True).returncode == 0
    except Exception:
        return False


def register_run(registry: Path, entry: dict) -> None:
    with registry.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")


def _write_run_json(dest: Path, info: dict) -> None:
    (dest / "run.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")


def _sha(prepared: Path, name: str) -> str:
    return hashlib.sha256((prepared / name).read_bytes()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_run(corpus: Corpus, paper_id: str, model: str, runs_root: Path | None = None,
            run=subprocess.run, rng: random.Random | None = None) -> Path:
    prepared = corpus.prepared_dir(paper_id)
    if not is_prepared(prepared):
        raise CorpusError(f"{paper_id} is not prepared; run `prep.py finalize` first")
    run_id = make_run_id(rng)
    dest = Path(runs_root or corpus.runs) / paper_id / run_id
    method = clone_tree(prepared, dest, run)
    restore_write(dest)
    (dest / "audit").mkdir()
    info = {"run_id": run_id, "paper_id": paper_id, "created": _now(), "manifest_sha256": _sha(prepared, MANIFEST_NAME),
            "readme_sha256": _sha(prepared, "README.md")}
    _write_run_json(dest, info)
    set_dropbox_ignored(dest, run)
    register_run(corpus.registry, {**info, "model": model, "run_path": str(dest), "clone_method": method})
    return dest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="new_run.py", description=__doc__.splitlines()[0])
    parser.add_argument("paper_id")
    parser.add_argument("--model", required=True)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--runs-root", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        corpus = find_root(Path.cwd(), explicit=args.root)
        print(new_run(corpus, args.paper_id, args.model, runs_root=args.runs_root))
    except CorpusError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
