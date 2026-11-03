import prep
import prepare
from conftest import accept_all_problems


def test_cli_run_and_finalize_fail_until_problems_accepted(reviewed_raw, clients, monkeypatch, capsys, writable_after):
    monkeypatch.setattr(prepare, "Clients", lambda: clients)
    root = str(reviewed_raw.corpus.root)
    assert prep.main(["run", str(reviewed_raw.raw), "--root", root]) == 1
    assert "prep review: FAILED" in capsys.readouterr().err
    prepared = reviewed_raw.corpus.prepared_dir("Paper_2024")
    writable_after(prepared)
    assert prep.main(["finalize", str(prepared), "--root", root]) == 1
    assert "accept_failures:" in capsys.readouterr().err
    accept_all_problems(prepared)
    assert prep.main(["review", str(prepared), "--root", root]) == 0
    assert "prep review: ok" in capsys.readouterr().out
    assert prep.main(["finalize", str(prepared), "--root", root]) == 0


def test_cli_review_without_manifest_is_exit_2(reviewed_raw, capsys):
    root = str(reviewed_raw.corpus.root)
    assert prep.main(["review", str(reviewed_raw.raw), "--root", root]) == 2
    assert "manifest.json" in capsys.readouterr().err
