"""Operator-owned corpus layout and path helpers."""

from dataclasses import dataclass
from pathlib import Path

ROOT_MARKER = ".autoaudit-root"
NO_ROOT_MSG = (
    "no corpus root found (missing {marker}); "
    "create one with: uv run prep.py init <dir>"
)


class CorpusError(Exception):
    pass


@dataclass(frozen=True)
class Corpus:
    root: Path

    @property
    def prepared(self) -> Path:
        return self.root / "prepared"

    @property
    def runs(self) -> Path:
        return self.root / "runs"

    @property
    def registry(self) -> Path:
        return self.root / "registry.jsonl"

    def prepared_dir(self, paper_id: str) -> Path:
        return self.prepared / paper_id

    def runs_dir(self, paper_id: str) -> Path:
        return self.runs / paper_id


def init_root(root: Path) -> Corpus:
    root = Path(root)
    corpus = Corpus(root)
    for folder in (root, corpus.prepared, corpus.runs):
        folder.mkdir(parents=True, exist_ok=True)
    (root / ROOT_MARKER).touch()
    if not corpus.registry.exists():
        corpus.registry.write_text("")
    return corpus


def _no_root_error() -> CorpusError:
    return CorpusError(NO_ROOT_MSG.format(marker=ROOT_MARKER))


def find_root(start: Path, explicit: Path | None = None) -> Corpus:
    if explicit is not None:
        if not (Path(explicit) / ROOT_MARKER).is_file():
            raise _no_root_error()
        return Corpus(Path(explicit))
    start = Path(start).resolve()
    for folder in (start, *start.parents):
        if (folder / ROOT_MARKER).is_file():
            return Corpus(folder)
    raise _no_root_error()
