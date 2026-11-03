import hashlib

from fetch_common import RemoteFile, SizePolicy, download, select_downloads, sha256_file


def test_policy_skips_video_and_big_files():
    p = SizePolicy()
    assert not p.allows(RemoteFile("a.mp4", 10, "u")) and not p.allows(RemoteFile("a.nii", 600 * 10**6, "u"))
    assert p.allows(RemoteFile("a.csv", 10, "u"))


def test_select_all_when_under_cap():
    files = [RemoteFile("a.csv", 10, "u"), RemoteFile("b.mp4", 10, "u")]
    sel, status = select_downloads(files, SizePolicy())
    assert [f.path for f in sel] == ["a.csv"] and status == "ok"


def test_select_listed_only_when_source_too_big():
    files = [RemoteFile(f"s{i}.nii.gz", 400 * 10**6, "u") for i in range(20)]
    assert select_downloads(files, SizePolicy()) == ([], "listed_only")


def test_select_partial_with_must_have():
    files = [RemoteFile(f"sub-{i}/func.nii.gz", 400 * 10**6, "u") for i in range(20)] + [
        RemoteFile("derivatives/group_map.nii.gz", 1000, "u")
    ]
    sel, status = select_downloads(files, SizePolicy(), must_have=("group_map",))
    assert [f.path for f in sel] == ["derivatives/group_map.nii.gz"] and status == "partial"


def test_download_writes_bytes(tmp_path):
    out = download("u", tmp_path / "d" / "f.bin", lambda u: b"xyz")
    assert out.read_bytes() == b"xyz" and sha256_file(out) == hashlib.sha256(b"xyz").hexdigest()


def test_from_plan():
    plan = {"max_file_mb": 1, "max_source_mb": 2, "skip_ext": ["zip"]}
    assert SizePolicy.from_plan(plan).skip_ext == frozenset({"zip"})
