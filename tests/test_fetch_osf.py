from fetch_common import SizePolicy
from fetch_osf import fetch_osf_files, fetch_osf_registration, list_osf_files, osf_id


def test_osf_id():
    assert osf_id("https://osf.io/abcde") == "abcde" and osf_id("https://osf.io/x4c56/registrations") == "x4c56"


def test_list_osf_files_follows_pagination_and_folders(osf_api):
    files = list_osf_files("abcde", osf_api)
    assert sorted(f.path for f in files) == ["data/trials.csv", "readme.txt", "video.mp4"]


def test_fetch_osf_files_applies_policy(osf_api, tmp_path):
    r = fetch_osf_files("abcde", tmp_path / "osf_abcde", SizePolicy(), osf_api, lambda u: b"content")
    assert r.status == "ok" and {f["path"]: f["downloaded"] for f in r.files}["video.mp4"] is False
    assert (tmp_path / "osf_abcde/data/trials.csv").read_bytes() == b"content"


def test_registration_hash_verified(osf_api, tmp_path):
    r = fetch_osf_registration("x4c56", tmp_path / "osf_x4c56", osf_api, lambda u: b"prereg-bytes")
    assert r["date_registered"].startswith("20") and r["files"][0]["verified"] is True and r["status"] == "ok"


def test_registration_hash_mismatch_flagged(osf_api, tmp_path):
    r = fetch_osf_registration("x4c56", tmp_path / "x", osf_api, lambda u: b"tampered")
    assert r["files"][0]["verified"] is False and r["status"] == "hash_mismatch"
