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
    assert r.status == "partial" and r.meta["version_doi"] == "10.5281/zenodo.123456"
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
    assert (dest / "1_map1.nii.gz").read_bytes() == b"nii" and (dest / "2_map2.nii.gz").exists()
    assert (dest / "collection.json").exists()
    assert len(json.loads((dest / "images.json").read_text())) == 2


IMAGES_URL = "https://neurovault.org/api/collections/1234/images/?format=json"
MEDIA = "https://neurovault.org/media/images/1234"


def _image(iid: int, folder: str = "a") -> dict:
    return {"id": iid, "file": f"{MEDIA}/{folder}/map.nii.gz"}


def _router(pages: dict):
    return lambda url: {"id": 1234} if url.endswith("/1234/") else pages[url]


def test_neurovault_same_basename_does_not_collide(tmp_path):
    pages = {IMAGES_URL: {"next": None, "results": [_image(1, "a"), _image(2, "b")]}}
    data = {f"{MEDIA}/a/map.nii.gz": b"one", f"{MEDIA}/b/map.nii.gz": b"two"}
    r = fetch_neurovault("1234", tmp_path / "nv", _router(pages), data.__getitem__)
    paths = [f["path"] for f in r.files]
    assert paths == ["1_map.nii.gz", "2_map.nii.gz"]
    assert [(tmp_path / "nv" / p).read_bytes() for p in paths] == [b"one", b"two"]
    assert r.files[0]["sha256"] != r.files[1]["sha256"]


def test_neurovault_failed_image_download_is_partial(tmp_path):
    pages = {IMAGES_URL: {"next": None, "results": [_image(1, "a"), _image(2, "b")]}}

    def get_bytes(url):
        if "/b/" in url:
            raise OSError("reset")
        return b"one"

    r = fetch_neurovault("1234", tmp_path / "nv", _router(pages), get_bytes)
    assert r.status == "partial" and [f["downloaded"] for f in r.files] == [True, False]


def test_neurovault_pagination_loop_terminates(tmp_path):
    pages = {IMAGES_URL: {"next": IMAGES_URL, "results": [_image(1)]}}
    r = fetch_neurovault("1234", tmp_path / "nv", _router(pages), lambda u: b"x")
    assert r.reason == "pagination loop detected" and len(r.files) == 1
