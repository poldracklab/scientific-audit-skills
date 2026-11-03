# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Shared size policy, download selection and HTTP helpers for all fetchers."""
import hashlib
import json
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

MB = 10**6
DEFAULT_SKIP_EXT = frozenset({"mp4", "mov", "avi", "wav", "mp3", "m4a"})
USER_AGENT = "audit-prep/1.0"


@dataclass
class RemoteFile:
    path: str
    size: int
    url: str
    remote_hash: str | None = None


@dataclass
class SizePolicy:
    max_file_mb: int = 500
    max_source_mb: int = 5000
    skip_ext: frozenset = DEFAULT_SKIP_EXT

    @classmethod
    def from_plan(cls, d: dict) -> "SizePolicy":
        base = cls()
        exts = d.get("skip_ext")
        skip = base.skip_ext if exts is None else frozenset(e.lower().lstrip(".") for e in exts)
        return cls(d.get("max_file_mb", base.max_file_mb), d.get("max_source_mb", base.max_source_mb), skip)

    def allows(self, f: RemoteFile) -> bool:
        ext = f.path.rsplit(".", 1)[-1].lower() if "." in f.path else ""
        return ext not in self.skip_ext and f.size <= self.max_file_mb * MB


@dataclass
class FetchResult:
    source: str
    id: str
    path: str
    status: str
    files: list[dict]
    reason: str = ""
    meta: dict = field(default_factory=dict)


def select_downloads(
    files: list[RemoteFile], policy: SizePolicy, must_have: tuple[str, ...] = ()
) -> tuple[list[RemoteFile], str]:
    """`ok` only when every listed file is selected; `partial` when the policy dropped some;
    `listed_only` when none is selected."""
    allowed = [f for f in files if policy.allows(f)]
    if sum(f.size for f in allowed) <= policy.max_source_mb * MB:
        if len(allowed) == len(files):
            return allowed, "ok"
        return allowed, "partial" if allowed else "listed_only"
    chosen = [f for f in allowed if any(m in f.path for m in must_have)]
    return (chosen, "partial") if chosen else ([], "listed_only")


def safe_join(dest: Path, rel: str) -> Path:
    """Join an untrusted relative path onto `dest`; raise ValueError if it could escape."""
    parts = PurePosixPath(rel).parts
    if not parts or PurePosixPath(rel).is_absolute() or ".." in parts:
        raise ValueError(f"unsafe path: {rel!r}")
    root = dest.resolve()
    target = (root / rel).resolve()
    if not target.is_relative_to(root) or target == root:
        raise ValueError(f"unsafe path: {rel!r}")
    return target


def download(url: str, dest: Path, get_bytes, rel: str | None = None) -> Path:
    """Write the bytes at `url` to `dest`, or to `dest/rel` confined by `safe_join` when `rel` is given."""
    if rel is not None:
        dest = safe_join(dest, rel)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(get_bytes(url))
    return dest


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _open(req: urllib.request.Request) -> bytes:
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def file_record(f: RemoteFile, sha: str | None = None, reason: str = "") -> dict:
    rec = {"path": f.path, "size": f.size, "remote_hash": f.remote_hash, "downloaded": sha is not None, "sha256": sha}
    return {**rec, "reason": reason} if reason else rec


def download_one(f: RemoteFile, dest: Path, get_bytes) -> dict:
    """Download one file confined to `dest`; a failure is recorded on the file, never raised."""
    try:
        return file_record(f, sha256_file(download(f.url, dest, get_bytes, f.path)))
    except Exception as e:
        return file_record(f, reason=str(e))


def file_records(files: list[RemoteFile], selected: list[RemoteFile], dest: Path, get_bytes) -> list[dict]:
    chosen = {id(f) for f in selected}
    return [download_one(f, dest, get_bytes) if id(f) in chosen else file_record(f) for f in files]


def default_get_bytes(url: str) -> bytes:
    return _open(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}))


def default_get_json(url: str) -> dict:
    return json.loads(default_get_bytes(url))


def default_post_json(url: str, payload: dict) -> dict:
    headers = {"User-Agent": USER_AGENT, "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
    return json.loads(_open(req))
