"""Tests for audit-consensus/scripts/unblind.py: naming the models in a finished consensus report."""
import json

import pytest

from consensus import main
from unblind import display_names, unblind_report, unblind_text

MODELS = {"abcd2345": "claude-opus-5-5", "wxyz6789": "gpt-5.6-sol"}


def test_display_names_are_model_names():
    assert display_names(MODELS) == MODELS


def test_display_names_disambiguate_repeated_models():
    names = display_names({"abcd2345": "gpt-5.5", "wxyz6789": "gpt-5.5", "qrst2345": "o4"})
    assert names == {"abcd2345": "gpt-5.5 (abcd2345)", "wxyz6789": "gpt-5.5 (wxyz6789)", "qrst2345": "o4"}


def test_unblind_text_replaces_run_ids_in_prose_and_tables():
    text = "<th>abcd2345</th><td>abcd2345 F2; wxyz6789 F1.</td>"
    assert unblind_text(text, MODELS) == (
        "<th>claude-opus-5-5</th><td>claude-opus-5-5 F2; gpt-5.6-sol F1.</td>")


def test_unblind_text_leaves_longer_tokens_alone():
    text = "xabcd2345 abcd2345x abcd2345_1 abcd2345-2"
    assert unblind_text(text, MODELS) == text


def test_unblind_text_leaves_paths_and_base64_alone():
    text = '../../abcd2345/audit <img src="data:image/png;base64,QUJD+abcd2345/wxyz6789=">'
    assert unblind_text(text, MODELS) == text


@pytest.fixture
def finished(tmp_path):
    out = tmp_path / "consensus" / "20261104T000000Z-abcd"
    out.mkdir(parents=True)
    (out / "run_models.json").write_text(json.dumps(MODELS))
    (out / "consensus.html").write_text("<p>Raised by abcd2345 F2 and wxyz6789 F1.</p>")
    return out


def test_unblind_report_writes_named_copy_and_keeps_blinded_report(finished):
    path = unblind_report(finished)
    assert path == finished / "consensus_unblinded.html"
    assert path.read_text() == "<p>Raised by claude-opus-5-5 F2 and gpt-5.6-sol F1.</p>"
    assert (finished / "consensus.html").read_text() == "<p>Raised by abcd2345 F2 and wxyz6789 F1.</p>"


def test_unblind_report_needs_rendered_report(finished):
    (finished / "consensus.html").unlink()
    with pytest.raises(FileNotFoundError):
        unblind_report(finished)


def test_cli_unblind_prints_path(finished, tmp_path, monkeypatch, capsys):
    (tmp_path / ".autoaudit-root").write_text("")
    monkeypatch.chdir(tmp_path)
    assert main(["unblind", str(finished)]) == 0
    assert capsys.readouterr().out.strip() == str(finished / "consensus_unblinded.html")
