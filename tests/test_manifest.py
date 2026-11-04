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
    assert m["documents"] == {"paper": None, "supplements": [], "corrigenda": []}


def test_hash_tree_excludes_manifest_and_readme(tmp_path):
    (tmp_path / "a.txt").write_text("a"); (tmp_path / "manifest.json").write_text("{}"); (tmp_path / "README.md").write_text("r")
    (tmp_path / "d").mkdir(); (tmp_path / "d/b.txt").write_text("b")
    assert [f["path"] for f in hash_tree(tmp_path)] == ["a.txt", "d/b.txt"]


def test_hash_tree_entries_include_git(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "code/.git").mkdir(parents=True)
    (tmp_path / "code/.git/HEAD").write_text("ref")
    (tmp_path / "code/manifest.json").write_text("nested")
    entries = hash_tree(tmp_path)
    assert [e["path"] for e in entries] == ["a.txt", "code/.git/HEAD", "code/manifest.json"]
    assert entries[0]["size"] == 1
    assert entries[0]["sha256"] == "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb"


def test_write_load_is_prepared(tmp_path):
    m = new_manifest("X_2020", "human"); write_manifest(tmp_path, m)
    assert load_manifest(tmp_path)["paper_id"] == "X_2020" and not is_prepared(tmp_path)
    m["finalized"] = True; m["review"] = {"status": "ok"}; write_manifest(tmp_path, m); assert is_prepared(tmp_path)


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


def test_hash_tree_prunes_finder_and_dropbox_metadata(tmp_path):
    from manifest import hash_tree

    (tmp_path / "data" / "sub").mkdir(parents=True)
    (tmp_path / "data" / "sub" / "trials.csv").write_text("x")
    for junk in [".DS_Store", "data/.DS_Store", "data/sub/Icon\r", ".dropbox"]:
        (tmp_path / junk).write_bytes(b"\x00")
    (tmp_path / "data" / ".dropbox.cache").mkdir()
    (tmp_path / "data" / ".dropbox.cache" / "blob").write_bytes(b"x")
    assert [e["path"] for e in hash_tree(tmp_path)] == ["data/sub/trials.csv"]


def test_new_manifest_has_review_none():
    assert new_manifest("X_2020", "human")["review"] is None


def test_readme_renders_prep_review():
    m = new_manifest("X_2020", "human")
    assert "## Prep review" in render_readme(m) and "not run" in render_readme(m).split("## Prep review")[1]
    accepted = {"kind": "data", "item": "data osf abcde", "status": "listed_only", "detail": "over size policy",
                "accepted_reason": "12 GB; listing suffices"}
    m["review"] = {"status": "ok", "problems": [], "accepted": [accepted], "unused": []}
    text = render_readme(m)
    section = text.split("## Prep review")[1].split("## Warnings")[0]
    assert "- Status: ok" in section and "data osf abcde" in section and "12 GB; listing suffices" in section
    assert text.index("## Data collection") < text.index("## Prep review") < text.index("## Warnings")


def test_readme_renders_failed_review_with_open_problems():
    m = new_manifest("X_2020", "human")
    problem = {"kind": "code", "item": "code https://gitlab.com/a/b", "status": "unsupported", "detail": "no fetcher"}
    m["review"] = {"status": "failed", "problems": [problem], "accepted": [], "unused": []}
    section = render_readme(m).split("## Prep review")[1].split("## Warnings")[0]
    assert "- Status: FAILED" in section and "no accepted failures" in section
    assert "| Item | Status | Detail |" in section and "code https://gitlab.com/a/b" in section


CLEAN_REVIEW = {"status": "ok", "problems": [], "accepted": [], "unused": []}


def test_is_prepared_requires_clean_review(tmp_path):
    m = new_manifest("X_2020", "human"); m["finalized"] = True
    write_manifest(tmp_path, m)
    assert not is_prepared(tmp_path)
    m["review"] = {**CLEAN_REVIEW, "status": "failed"}; write_manifest(tmp_path, m)
    assert not is_prepared(tmp_path)


def _data_row(meta, reason):
    m = new_manifest("X_2020", "human")
    m["data"] = [{"source": "openneuro", "id": "ds000001", "status": "ok", "reason": reason,
                  "files": [{"downloaded": True}], "meta": meta}]
    return next(line for line in render_readme(m).splitlines() if "ds000001" in line)


def test_readme_says_openneuro_is_metadata_only():
    assert _data_row({"scope": "metadata"}, None).endswith("| metadata only |")
    assert _data_row({"scope": "metadata"}, "README missing").endswith("| metadata only; README missing |")
    assert "metadata only" not in _data_row({}, None)


def test_readme_lists_corrigendum_and_tells_auditor_to_use_it():
    m = new_manifest("X_2020", "human")
    m["documents"]["corrigenda"] = [{"original_name": "x_corrigendum.pdf", "path": "paper/corrigendum_1.pdf",
                                     "pages": 1, "conversions": {"text": "ok"}}]
    text = render_readme(m)
    assert "| corrigendum | paper/corrigendum_1.pdf |" in text
    assert "correction" in text.lower() and "paper/corrigendum_1.pdf" in text.split("|")[0]


def test_readme_without_corrigendum_has_no_correction_notice():
    m = new_manifest("X_2020", "human")
    assert "corrigend" not in render_readme(m).lower()


def test_readme_renders_legacy_documents_without_corrigenda():
    m = new_manifest("X_2020", "human")
    m["documents"] = {"paper": None, "supplements": []}
    assert "# X_2020" in render_readme(m)
