import json

from fetch_common import SizePolicy
from fetch_neurovault import fetch_neurovault, neurovault_id
from fetch_zenodo import fetch_zenodo, zenodo_id


def test_zenodo_id():
    assert zenodo_id("https://zenodo.org/records/123456") == "123456"
    assert zenodo_id("https://zenodo.org/record/123456") == "123456"
    assert zenodo_id("https://doi.org/10.5281/zenodo.123456") == "123456"


def test_zenodo_lists_and_downloads(zenodo_fixture, tmp_path):
    dest = tmp_path / "zenodo_123456"
    r = fetch_zenodo("123456", dest, SizePolicy(), lambda u: zenodo_fixture, lambda u: b"d")
    assert r.status == "ok" and r.meta["version_doi"] == "10.5281/zenodo.123456"
    assert r.meta["concept_doi"] == "10.5281/zenodo.123455" and r.meta["title"] == "Trial data"
    assert all(f["remote_hash"].startswith("md5:") for f in r.files)
    assert {f["path"]: f["downloaded"] for f in r.files}["demo.mp4"] is False
    assert (dest / "data/trials.csv").read_bytes() == b"d"


def test_zenodo_without_files_is_failed(zenodo_fixture, tmp_path):
    record = {k: v for k, v in zenodo_fixture.items() if k != "files"}
    r = fetch_zenodo("123456", tmp_path / "z", SizePolicy(), lambda u: record, lambda u: b"d")
    assert r.status == "failed" and r.reason == "no files listed (restricted?)"


def test_neurovault_id():
    assert neurovault_id("https://neurovault.org/collections/1234/") == "1234"


def test_neurovault_downloads_all_pages(neurovault_api, tmp_path):
    dest = tmp_path / "neurovault_1234"
    r = fetch_neurovault("1234", dest, neurovault_api, lambda u: b"nii")
    assert r.status == "ok" and r.source == "neurovault" and r.path == str(dest)
    assert (dest / "map1.nii.gz").read_bytes() == b"nii" and (dest / "map2.nii.gz").exists()
    assert (dest / "collection.json").exists()
    assert len(json.loads((dest / "images.json").read_text())) == 2
