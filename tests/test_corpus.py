import json

import pytest

from corpus import CorpusError, find_root, init_root


def test_init_root_creates_marker_dirs_registry_and_deny_rule(corpus_root):
    c = init_root(corpus_root)
    assert (corpus_root / ".autoaudit-root").is_file()
    assert c.prepared.is_dir() and c.runs.is_dir() and c.unsorted.is_dir()
    assert c.registry.is_file() and c.registry.read_text() == ""
    settings = json.loads((corpus_root / ".claude/settings.json").read_text())
    assert settings["permissions"]["deny"] == ["Read(/registry.jsonl)"]


def test_find_root_walks_up_from_nested_folder(corpus_root):
    init_root(corpus_root)
    nested = corpus_root / "Bissett_2021" / "sub"
    nested.mkdir(parents=True)
    assert find_root(nested).root == corpus_root


def test_find_root_without_marker_raises(tmp_path):
    with pytest.raises(CorpusError, match="prep.py init"):
        find_root(tmp_path)


def test_explicit_root_without_marker_raises(tmp_path):
    with pytest.raises(CorpusError):
        find_root(tmp_path, explicit=tmp_path)


def test_paper_paths(corpus_root):
    c = init_root(corpus_root)
    assert c.prepared_dir("X_2020") == corpus_root / "prepared" / "X_2020"
    assert c.runs_dir("X_2020") == corpus_root / "runs" / "X_2020"
    assert c.unsorted_dir("X_2020") == corpus_root / "unsorted" / "X_2020"
