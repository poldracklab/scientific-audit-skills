import os

from manifest import (
    hash_tree,
    is_prepared,
    load_manifest,
    new_manifest,
    render_readme,
    write_manifest,
)


def test_new_manifest_has_all_keys():
    m = new_manifest("X_2020", "human")
    assert set(m) >= {"schema_version", "paper_id", "prepared_at", "prep_versions", "prepared_by", "finalized", "metadata", "documents", "links", "preregistration", "data_collection", "code", "data", "local_data", "unsorted", "files", "warnings"}
    assert m["finalized"] is False and m["schema_version"] == 1
    assert m["documents"] == {"paper": None, "supplements": []}


def test_hash_tree_excludes_manifest_and_readme(tmp_path):
    (tmp_path / "a.txt").write_text("a"); (tmp_path / "manifest.json").write_text("{}"); (tmp_path / "README.md").write_text("r")
    (tmp_path / "d").mkdir(); (tmp_path / "d/b.txt").write_text("b")
    assert [f["path"] for f in hash_tree(tmp_path)] == ["a.txt", "d/b.txt"]


def test_hash_tree_entries_git_and_symlinks(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "code/.git").mkdir(parents=True)
    (tmp_path / "code/.git/HEAD").write_text("ref")
    (tmp_path / "code/manifest.json").write_text("nested")
    os.symlink(tmp_path / "a.txt", tmp_path / "link.txt")
    entries = hash_tree(tmp_path)
    assert [e["path"] for e in entries] == ["a.txt", "code/.git/HEAD", "code/manifest.json"]
    assert entries[0]["size"] == 1
    assert entries[0]["sha256"] == "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb"


def test_write_load_is_prepared(tmp_path):
    m = new_manifest("X_2020", "human"); write_manifest(tmp_path, m)
    assert load_manifest(tmp_path)["paper_id"] == "X_2020" and not is_prepared(tmp_path)
    m["finalized"] = True; write_manifest(tmp_path, m); assert is_prepared(tmp_path)


def test_load_manifest_missing_or_corrupt(tmp_path):
    assert load_manifest(tmp_path) is None
    (tmp_path / "manifest.json").write_text("{not json")
    assert load_manifest(tmp_path) is None and not is_prepared(tmp_path)


def test_is_prepared_rejects_other_schema(tmp_path):
    m = new_manifest("X_2020", "human"); m["finalized"] = True; m["schema_version"] = 99
    write_manifest(tmp_path, m)
    assert not is_prepared(tmp_path)


def test_readme_states_absences():
    text = render_readme(new_manifest("X_2020", "human"))
    assert "Preregistration" in text and "none found" in text and "X_2020" in text


def test_readme_renders_content():
    m = new_manifest("X_2020", "human")
    m["metadata"] = {"doi": "10.1/x", "title": "A Title", "journal": "J", "published": "2020"}
    m["preregistration"] = [{"source": "osf", "id": "abcde", "date_registered": "2019-01-02", "status": "ok"}]
    m["code"] = [{"url": "https://github.com/a/b", "commit": "deadbeef", "status": "ok"}]
    m["data"] = [{"source": "osf", "id": "q", "status": "partial", "reason": "too big",
                  "files": [{"downloaded": True}, {"downloaded": False}]}]
    m["unsorted"] = [{"original_path": "x.bin", "moved_to": "unsorted/X_2020/x.bin", "reason": "unknown"}]
    m["warnings"] = ["watch out"]
    text = render_readme(m)
    for s in ("A Title", "10.1/x", "2019-01-02", "deadbeef", "partial", "1 of 2", "unsorted/X_2020/x.bin", "watch out"):
        assert s in text
