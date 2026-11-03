import json

import pytest

from corpus import CorpusError, find_root, init_root


def test_init_root_creates_operator_layout_without_harness_settings(corpus_root):
    c = init_root(corpus_root)
    assert (corpus_root / ".autoaudit-root").is_file()
    assert c.prepared.is_dir() and c.runs.is_dir()
    assert c.registry.is_file() and c.registry.read_text() == ""
    assert not (corpus_root / ".claude").exists()
    assert not (corpus_root / "unsorted").exists()


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
