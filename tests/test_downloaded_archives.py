"""Downloaded archives use the same extraction machinery as supplied archives."""
import io
import tarfile
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import ZENODO
from prepare import run_prep
from review import review_manifest


def test_extraction_accepts_relative_prepared_path(tmp_path, monkeypatch):
    from downloaded_archives import extract_downloaded_archives

    monkeypatch.chdir(tmp_path)
    root = Path("prepared/data/source")
    root.mkdir(parents=True)
    (root / "data.zip").write_bytes(zip_bytes({"data.csv": "fixture"}))
    manifest = {"warnings": [], "data": [{"path": "data/source", "files": [
        {"path": "data.zip", "downloaded": True}]}]}
    extract_downloaded_archives(Path("prepared"), manifest, [], None)
    assert (root / "data/data.csv").read_text() == "fixture"


def zip_bytes(files):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return out.getvalue()


def tar_bytes():
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w:gz") as archive:
        data = b"trial,rt\n1,0.5\n"
        member = tarfile.TarInfo("trials.csv")
        member.size = len(data)
        archive.addfile(member, io.BytesIO(data))
    return out.getvalue()


@pytest.fixture
def downloaded_case(reviewed_raw):
    payload = {"name": "bundles/data.zip", "bytes": zip_bytes({"trials.csv": "trial,rt\n1,0.5\n"})}
    clients = reviewed_raw.clients
    get_json, get_bytes = clients.get_json, clients.get_bytes
    url = "https://zenodo.org/files/archive"

    def metadata(endpoint):
        if endpoint == ZENODO:
            return {"files": [{"key": payload["name"], "size": len(payload["bytes"]), "links": {"self": url}}]}
        return get_json(endpoint)

    clients.get_json = metadata
    clients.get_bytes = lambda source: payload["bytes"] if source == url else get_bytes(source)
    prepared = reviewed_raw.corpus.prepared_dir(reviewed_raw.raw.name)

    def run():
        return run_prep(reviewed_raw.raw, reviewed_raw.corpus, clients)

    return SimpleNamespace(payload=payload, prepared=prepared, run=run)


def archive_records(manifest):
    return next(d for d in manifest["data"] if d["source"] == "zenodo").get("archives", [])


def test_downloaded_zip_is_unpacked_and_recorded(downloaded_case):
    case = downloaded_case
    m = case.run()
    root = case.prepared / "data/zenodo_123456/bundles"
    assert (root / "data/trials.csv").read_text() == "trial,rt\n1,0.5\n"
    assert (root / "data.zip").read_bytes() == case.payload["bytes"]
    entry = archive_records(m)[0]
    assert entry["path"] == "data/zenodo_123456/bundles/data.zip"
    assert entry["extracted"] == "ok" and entry["extracted_to"] == "data/zenodo_123456/bundles/data"
    assert len(entry["sha256"]) == 64


def test_downloaded_tar_uses_local_extractor(downloaded_case):
    case = downloaded_case
    case.payload.update(name="data.tar.gz", bytes=tar_bytes())
    m = case.run()
    assert (case.prepared / "data/zenodo_123456/data/trials.csv").is_file()
    assert archive_records(m)[0]["extracted"] == "ok"


def test_unchanged_download_keeps_extraction_on_retry(downloaded_case):
    case = downloaded_case
    first = case.run()
    output = case.prepared / "data/zenodo_123456/bundles/data/trials.csv"
    before = output.stat().st_mtime_ns
    second = case.run()
    assert output.stat().st_mtime_ns == before
    assert archive_records(second) == archive_records(first)


def test_changed_download_replaces_owned_extraction_without_stale_files(downloaded_case):
    case = downloaded_case
    case.run()
    case.payload["bytes"] = zip_bytes({"updated.csv": "updated"})
    m = case.run()
    root = case.prepared / "data/zenodo_123456/bundles/data"
    assert (root / "updated.csv").read_text() == "updated"
    assert not (root / "trials.csv").exists()
    assert archive_records(m)[0]["extracted"] == "ok"


@pytest.mark.parametrize("name,content,status", [("bad.zip", b"not an archive", "failed"),
                                               ("unsupported.7z", b"7z", "skipped")])
def test_failed_or_unsupported_extraction_blocks_review(downloaded_case, name, content, status):
    case = downloaded_case
    case.payload.update(name=name, bytes=content)
    m = case.run()
    assert archive_records(m)[0]["extracted"] == status
    item = f"data_archive data/zenodo_123456/{name}"
    assert item in {p["item"] for p in m["review"]["problems"]}
    result = review_manifest(m, {"accept_failures": {item: "archive unavailable; originals retained"}})
    assert item in {p["item"] for p in result["accepted"]}


def test_failed_changed_archive_keeps_last_output_but_does_not_claim_success(downloaded_case):
    case = downloaded_case
    case.run()
    case.payload["bytes"] = b"corrupt update"
    failed = case.run()
    output = case.prepared / "data/zenodo_123456/bundles/data/trials.csv"
    assert output.exists()
    assert archive_records(failed)[0]["extracted"] == "failed"
    case.payload["bytes"] = zip_bytes({"updated.csv": "fixed"})
    fixed = case.run()
    assert archive_records(fixed)[0]["extracted"] == "ok"
    assert not output.exists()


def test_inner_archives_are_listed_without_recursive_expansion(downloaded_case):
    case = downloaded_case
    case.payload["bytes"] = zip_bytes({"inner.zip": zip_bytes({"hidden.csv": "x"})})
    m = case.run()
    nested = [e for e in archive_records(m) if e.get("nested_archive")]
    assert nested == [{"path": "data/zenodo_123456/bundles/data/inner.zip", "nested_archive": True}]
    assert not (case.prepared / "data/zenodo_123456/bundles/data/inner").exists()
    assert any(p["item"].endswith("inner.zip") for p in m["review"]["problems"])


def test_unrelated_extraction_target_is_not_overwritten(downloaded_case):
    case = downloaded_case
    case.payload.update(name="notes.txt", bytes=b"not an archive")
    case.run()
    root = case.prepared / "data/zenodo_123456/data"
    root.mkdir()
    (root / "manual.csv").write_text("keep")
    case.payload.update(name="data.zip", bytes=zip_bytes({"manual.csv": "replace"}))
    m = case.run()
    assert (root / "manual.csv").read_text() == "keep"
    assert archive_records(m)[0]["extracted"] == "failed"


def test_archive_cannot_escape_its_extraction_directory(downloaded_case):
    case = downloaded_case
    case.payload["bytes"] = zip_bytes({"../outside.csv": "fixture"})
    m = case.run()
    assert archive_records(m)[0]["extracted"] == "ok"
    assert not (case.prepared / "data/zenodo_123456/bundles/outside.csv").exists()


def test_downloaded_archive_results_appear_in_readme(downloaded_case):
    from manifest import render_readme

    text = render_readme(downloaded_case.run())
    assert "Downloaded archives" in text
    assert "data/zenodo_123456/bundles/data.zip" in text
    assert "data/zenodo_123456/bundles/data" in text
