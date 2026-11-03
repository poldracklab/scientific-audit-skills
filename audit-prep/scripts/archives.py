# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Extract top-level local archives and list nested ones."""
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path

from layout import _rel

ARCHIVE_SUFFIXES = (".tar.gz", ".tar.bz2", ".tar.xz", ".tar.zst", ".tgz", ".tar", ".zip", ".zst", ".7z")


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
