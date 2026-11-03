import os
import subprocess
from pathlib import Path

import pytest

from verify_run import verify

SCRIPT = Path(__file__).resolve().parent.parent / "audit-prep" / "scripts" / "verify_run.py"


def test_not_prepared(tmp_path):
    assert verify(tmp_path)[0] == "not_prepared"


def test_prepared_not_run(prepared_corpus):
    assert verify(prepared_corpus.prepared_dir("Paper_2024"))[0] == "prepared_not_run"


def test_run_ok_with_audit_outputs(run_folder):
    (run_folder / "audit/audit.qmd").write_text("x")
    (run_folder / "audit/cache").mkdir()
    assert verify(run_folder) == ("run_ok", [])


def test_run_dirty_on_stray_file(run_folder):
    (run_folder / "notes.md").write_text("x")
    assert verify(run_folder) == ("run_dirty", ["notes.md"])


def test_run_modified_on_changed_or_missing(run_folder):
    (run_folder / "paper/paper.pdf").write_text("changed")
    assert verify(run_folder) == ("run_modified", ["paper/paper.pdf"])
    (run_folder / "paper/paper.pdf").unlink()
    assert verify(run_folder) == ("run_modified", ["paper/paper.pdf"])


def test_modified_reported_before_dirty(run_folder):
    (run_folder / "notes.md").write_text("x")
    (run_folder / "paper/paper.pdf").write_text("changed")
    assert verify(run_folder)[0] == "run_modified"


def _cli(folder):
    cmd = ["uv", "run", "--quiet", str(SCRIPT), str(folder)]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300)


def test_cli_exit_codes(run_folder, tmp_path):
    ok = _cli(run_folder)
    assert ok.returncode == 0 and ok.stdout.splitlines()[0] == "run_ok"
    bad = _cli(tmp_path)
    assert bad.returncode == 1 and bad.stdout.splitlines()[0] == "not_prepared"


def test_edited_run_manifest_is_modified(run_folder):
    manifest = run_folder / "manifest.json"
    manifest.write_text(manifest.read_text() + " ")
    assert verify(run_folder) == ("run_modified", ["manifest.json"])


def test_edited_run_readme_is_modified(run_folder):
    readme = run_folder / "README.md"
    readme.write_text(readme.read_text() + "edit")
    assert verify(run_folder) == ("run_modified", ["README.md"])


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file modes")
def test_unreadable_audit_file_is_not_inspected(run_folder):
    secret = run_folder / "audit/secret.bin"
    secret.write_text("x")
    secret.chmod(0)
    assert verify(run_folder) == ("run_ok", [])
