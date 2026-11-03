import shutil

import pytest

from docs import (
    docx_to_md,
    pdf_to_pages,
    pdf_to_structured,
    pdf_to_text,
    tool_versions,
    xlsx_to_csv,
)


def test_pdf_to_text_layout_has_form_feeds(fixture_pdf, tmp_path):
    out = pdf_to_text(fixture_pdf, tmp_path / "paper.txt")
    assert out.read_text().count("\f") >= 1 and "Example Paper Title" in out.read_text()


def test_pdf_to_pages_names_and_count(fixture_pdf, tmp_path):
    pages = pdf_to_pages(fixture_pdf, tmp_path / "pages")
    assert [p.name for p in pages] == ["p-001.png", "p-002.png"]


def test_xlsx_to_csv_one_file_per_sheet(fixture_xlsx, tmp_path):
    files = xlsx_to_csv(fixture_xlsx, tmp_path / "s")
    assert sorted(f.name for f in files) == ["Table_S1.csv", "Table_S2.csv"]


def test_docx_to_md(fixture_docx, tmp_path):
    out = docx_to_md(fixture_docx, tmp_path / "s.md", tmp_path / "s_media")
    assert "Supplementary Methods" in out.read_text()


def test_structured_records_failure_when_docling_unavailable(fixture_pdf, tmp_path):
    def failing_run(*a, **k):
        raise FileNotFoundError("uvx")

    r = pdf_to_structured(fixture_pdf, tmp_path / "out", run=failing_run)
    assert r["status"] == "failed" and "uvx" in r["reason"]


@pytest.mark.slow
def test_structured_smoke(fixture_pdf, tmp_path):
    if not shutil.which("uvx"):
        pytest.skip("uvx missing")
    r = pdf_to_structured(fixture_pdf, tmp_path / "out")
    assert r["status"] == "ok" and (tmp_path / "out" / "figures" / "figures.md").is_file()


def test_tool_versions_keys():
    assert set(tool_versions()) == {"pdftotext", "pdftoppm", "pandoc", "zstd", "docling", "git"}
