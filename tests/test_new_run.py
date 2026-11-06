import json
import os
import random
import re
import shutil
import subprocess

import pytest

from corpus import CorpusError
from new_run import clone_tree, make_run_id, new_run, register_run, set_dropbox_ignored

MODEL = "fable-5.1"


def test_run_id_alphabet():
    assert re.fullmatch(r"[a-z2-7]{8}", make_run_id(random.Random(0)))


def test_clone_falls_back_to_rsync(tmp_path):
    calls = []

    def fake_run(cmd, **k):
        calls.append(cmd[0])
        if cmd[0] == "cp":
            return subprocess.CompletedProcess(cmd, 1)
        shutil.copytree(cmd[-2].rstrip("/"), cmd[-1].rstrip("/"), dirs_exist_ok=True)
        return subprocess.CompletedProcess(cmd, 0)

    (tmp_path / "src").mkdir()
    (tmp_path / "src/f").write_text("x")
    assert clone_tree(tmp_path / "src", tmp_path / "dst", run=fake_run) == "rsync"
    assert calls == ["cp", "rsync"] and (tmp_path / "dst/f").read_text() == "x"


def test_clone_falls_back_when_cp_raises(tmp_path):
    def fake_run(cmd, **k):
        if cmd[0] == "cp":
            raise OSError("no cp")
        return subprocess.run(cmd, **k)

    (tmp_path / "src").mkdir()
    (tmp_path / "src/f").write_text("x")
    assert clone_tree(tmp_path / "src", tmp_path / "dst", run=fake_run) == "rsync"
    assert (tmp_path / "dst/f").read_text() == "x"


def test_clone_raises_when_rsync_fails(tmp_path):
    (tmp_path / "src").mkdir()

    def fail(cmd, **k):
        return subprocess.CompletedProcess(cmd, 1)

    with pytest.raises(CorpusError):
        clone_tree(tmp_path / "src", tmp_path / "dst", run=fail)


def test_xattr_failure_is_not_fatal(tmp_path):
    def boom(*a, **k):
        raise FileNotFoundError("xattr")

    assert set_dropbox_ignored(tmp_path, run=boom) is False


def test_xattr_nonzero_is_false(tmp_path):
    def fail(cmd, **k):
        return subprocess.CompletedProcess(cmd, 1)

    assert set_dropbox_ignored(tmp_path, run=fail) is False


def test_register_run_appends_lines(tmp_path):
    reg = tmp_path / "registry.jsonl"
    register_run(reg, {"a": 1})
    register_run(reg, {"a": 2})
    assert [json.loads(x)["a"] for x in reg.read_text().splitlines()] == [1, 2]


def _all_text(folder):
    files = (p for p in folder.rglob("*") if p.is_file())
    return "".join(p.read_bytes().decode(errors="ignore") for p in files)


def test_new_run_layout_registry_and_blinding(prepared_corpus):
    run_path = new_run(prepared_corpus, "Paper_2024", MODEL, rng=random.Random(1))
    assert run_path.parent == prepared_corpus.runs_dir("Paper_2024") and (run_path / "audit").is_dir()
    assert os.access(run_path / "paper/paper.pdf", os.W_OK)
    rj = json.loads((run_path / "run.json").read_text())
    assert set(rj) == {"run_id", "paper_id", "created", "manifest_sha256", "readme_sha256"} and rj["run_id"] == run_path.name
    assert MODEL not in "".join(str(p) for p in run_path.rglob("*"))
    assert MODEL not in _all_text(run_path)
    line = json.loads(prepared_corpus.registry.read_text().splitlines()[-1])
    assert line["model"] == MODEL and line["run_id"] == run_path.name
    assert line["run_path"] == str(run_path) and line["clone_method"] in {"clonefile", "rsync"}


def test_new_run_refuses_unfinalized(corpus_with_unfinalized):
    with pytest.raises(CorpusError, match="finalize"):
        new_run(corpus_with_unfinalized, "Paper_2024", "m")


def test_runs_root_override(prepared_corpus, tmp_path):
    run_path = new_run(prepared_corpus, "Paper_2024", "m", runs_root=tmp_path / "elsewhere")
    assert run_path.is_relative_to(tmp_path / "elsewhere")


def test_failed_clone_leaves_no_dest(tmp_path):
    src, dest = tmp_path / "src", tmp_path / "dst"
    src.mkdir()

    def fail(cmd, **k):
        if cmd[0] == "cp":
            (dest / "sub").mkdir(parents=True)
            (dest / "sub/f").write_text("x")
            (dest / "sub").chmod(0o555)
        return subprocess.CompletedProcess(cmd, 1)

    with pytest.raises(CorpusError):
        clone_tree(src, dest, run=fail)
    assert not dest.exists()


def test_new_run_refuses_folder_finalized_before_the_gate(prepared_corpus):
    import json
    import os

    prepared = prepared_corpus.prepared_dir("Paper_2024")
    manifest = prepared / "manifest.json"
    os.chmod(manifest, 0o644)
    m = json.loads(manifest.read_text())
    m.pop("review")
    manifest.write_text(json.dumps(m))
    with pytest.raises(CorpusError, match="finalize"):
        new_run(prepared_corpus, "Paper_2024", "m")


@pytest.mark.parametrize("kind", ["directory", "file", "symlink", "dangling"])
def test_clone_refuses_existing_destination_without_touching_it(tmp_path, kind):
    src, dest = tmp_path / "src", tmp_path / "dst"
    src.mkdir()
    external = tmp_path / "outside"
    external.mkdir()
    (external / "keep").write_text("keep")
    if kind == "directory":
        dest.mkdir()
        (dest / "keep").write_text("keep")
    elif kind == "file":
        dest.write_text("keep")
    else:
        dest.symlink_to(external if kind == "symlink" else tmp_path / "absent")
    calls = []

    def fail(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 1)

    with pytest.raises(CorpusError, match="exists"):
        clone_tree(src, dest, run=fail)
    assert calls == []
    assert dest.exists() or dest.is_symlink()
    assert (external / "keep").read_text() == "keep"
    if kind == "directory":
        assert (dest / "keep").read_text() == "keep"
    elif kind == "file":
        assert dest.read_text() == "keep"


def test_run_id_collision_preserves_previous_audit(prepared_corpus):
    first = new_run(prepared_corpus, "Paper_2024", "m", rng=random.Random(7))
    (first / "audit/notes.txt").write_text("completed work")
    registry = prepared_corpus.registry.read_bytes()
    with pytest.raises(CorpusError, match="exists"):
        new_run(prepared_corpus, "Paper_2024", "m", rng=random.Random(7))
    assert (first / "audit/notes.txt").read_text() == "completed work"
    assert prepared_corpus.registry.read_bytes() == registry


def test_destination_is_reserved_before_copy_and_stays_reserved_during_fallback(tmp_path):
    src, dest = tmp_path / "src", tmp_path / "dst"
    src.mkdir()
    (src / "file").write_text("source")
    inode = []

    def copy(cmd, **kwargs):
        assert dest.is_dir()
        inode.append(dest.stat().st_ino)
        if cmd[0] == "cp":
            (dest / "partial").write_text("partial")
            return subprocess.CompletedProcess(cmd, 1)
        assert not (dest / "partial").exists()
        shutil.copytree(src, dest, dirs_exist_ok=True)
        return subprocess.CompletedProcess(cmd, 0)

    assert clone_tree(src, dest, run=copy) == "rsync"
    assert inode[0] == inode[1]
    assert (dest / "file").read_text() == "source"


@pytest.mark.parametrize("skill", ["reproducibility-audit", "neuroimaging-validity-audit"])
def test_cli_records_selected_skill_in_registry(prepared_corpus, skill, capsys):
    from new_run import main

    assert main(["Paper_2024", "--model", MODEL, "--root", str(prepared_corpus.root),
                 "--skill", skill]) == 0
    entry = json.loads(prepared_corpus.registry.read_text().splitlines()[-1])
    assert entry["skill"] == skill
    assert entry["model"] == MODEL
    assert entry["run_path"] == capsys.readouterr().out.strip()
    assert MODEL not in _all_text(prepared_corpus.runs_dir("Paper_2024"))


def test_unspecified_skill_is_explicitly_unknown(prepared_corpus):
    new_run(prepared_corpus, "Paper_2024", MODEL)
    entry = json.loads(prepared_corpus.registry.read_text().splitlines()[-1])
    assert entry["skill"] is None
