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


PAGE1 = "https://api.osf.io/v2/nodes/abcde/files/osfstorage/"
REG = "https://api.osf.io/v2/registrations/x4c56/"
REG_FILES = REG + "files/osfstorage/"


def _listing(entries):
    return {"data": entries, "links": {"next": None, "meta": {"total": len(entries)}}}


def test_fetch_osf_files_skips_unsafe_name(osf_router, osf_fixture, osf_entry, tmp_path):
    page1 = osf_fixture("osf_files_page1.json")
    page1["data"].append(osf_entry("e1", "../evil.txt", 5, {}))
    r = fetch_osf_files("abcde", tmp_path / "osf", SizePolicy(), osf_router({PAGE1: page1}), lambda u: b"content")
    by_path = {f["path"]: f for f in r.files}
    assert by_path["../evil.txt"]["downloaded"] is False and by_path["../evil.txt"]["reason"]
    assert by_path["data/trials.csv"]["downloaded"] is True and by_path["readme.txt"]["downloaded"] is True
    assert not (tmp_path / "evil.txt").exists() and r.status == "ok"


def test_fetch_osf_files_keeps_listing_when_one_download_fails(osf_api, tmp_path):
    def get_bytes(url):
        if url == "https://osf.io/download/t1/":
            raise OSError("connection reset")
        return b"content"

    r = fetch_osf_files("abcde", tmp_path / "osf", SizePolicy(), osf_api, get_bytes)
    by_path = {f["path"]: f for f in r.files}
    assert sorted(by_path) == ["data/trials.csv", "readme.txt", "video.mp4"] and r.status == "ok"
    trials = by_path["data/trials.csv"]
    assert trials["downloaded"] is False and "connection reset" in trials["reason"]
    assert by_path["readme.txt"]["downloaded"] is True and (tmp_path / "osf/readme.txt").read_bytes() == b"content"


def test_fetch_osf_files_listing_failure(osf_router, tmp_path):
    get_json = osf_router({PAGE1: OSError("timeout")})
    r = fetch_osf_files("abcde", tmp_path / "osf", SizePolicy(), get_json, lambda u: b"")
    assert r.status == "failed" and "timeout" in r.reason


def test_registration_without_frozen_hash_unverified(osf_router, osf_entry, tmp_path):
    get_json = osf_router({REG_FILES: _listing([osf_entry("p1", "prereg.pdf", 12, {"hashes": {}})])})
    r = fetch_osf_registration("x4c56", tmp_path / "r", get_json, lambda u: b"prereg-bytes")
    assert r["files"][0]["verified"] is None and r["status"] == "unverified"


def test_registration_with_no_files_unverified(osf_router, tmp_path):
    r = fetch_osf_registration("x4c56", tmp_path / "r", osf_router({REG_FILES: _listing([])}), lambda u: b"")
    assert r["files"] == [] and r["status"] == "unverified"


def test_registration_mismatch_wins_over_unhashed(osf_router, osf_fixture, osf_entry, tmp_path):
    listing = osf_fixture("osf_registration_files.json")
    listing["data"].append(osf_entry("p2", "notes.txt", 3, {}))
    r = fetch_osf_registration("x4c56", tmp_path / "r", osf_router({REG_FILES: listing}), lambda u: b"tampered")
    assert [f["verified"] for f in r["files"]] == [False, None] and r["status"] == "hash_mismatch"
