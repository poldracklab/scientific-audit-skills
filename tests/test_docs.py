import json
import shutil

import pytest

from docs import (
    _index_docling,
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


def test_tool_versions_keys(monkeypatch):
    """The docling probe (`uvx ... docling --version`) may download; stub it so no network is used."""
    import docs

    real, real_which, probed = docs._first_line, shutil.which, []

    def first_line(cmd, timeout):
        if cmd[0] == "uvx":
            probed.append(cmd)
            return "docling 0.0-stub"
        return real(cmd, timeout)

    monkeypatch.setattr(docs, "_first_line", first_line)
    monkeypatch.setattr(docs.shutil, "which", lambda tool: "/stub/uvx" if tool == "uvx" else real_which(tool))
    versions = tool_versions()
    assert set(versions) == {"pdftotext", "pdftoppm", "pandoc", "zstd", "docling", "git"}
    assert versions["docling"] == "docling 0.0-stub" and probed


def test_disabled_structured_conversion_never_probes_docling(monkeypatch):
    import docs

    def version(tool):
        assert tool != "docling", "disabled Docling must not be downloaded for a version probe"
        return "test"

    monkeypatch.setattr(docs, "_tool_version", version)
    assert tool_versions(structured=False)["docling"] is None


PNG = b"\x89PNG\r\n\x1a\nfakepng"


@pytest.fixture
def docling_dir(tmp_path):
    work = tmp_path / "work"
    (work / "paper_artifacts").mkdir(parents=True)
    (work / "paper_artifacts" / "image_000000_ab.png").write_bytes(PNG)
    doc = {
        "texts": [{"text": "Figure 1. A brain."}, {"text": "Table 1. Results."}],
        "pictures": [
            {
                "image": {"uri": "paper_artifacts/image_000000_ab.png"},
                "captions": [{"$ref": "#/texts/0"}],
                "prov": [{"page_no": 3}],
            }
        ],
        "tables": [
            {
                "data": {"grid": [[{"text": "a"}, {"text": "b"}], [{"text": "1"}, {"text": "2"}]]},
                "captions": [{"$ref": "#/texts/1"}],
                "prov": [{"page_no": 5}],
            }
        ],
    }
    (work / "paper.json").write_text(json.dumps(doc))
    out = tmp_path / "out"
    out.mkdir()
    (out / "paper.md").write_text("Text\n\n![Image](paper_artifacts/image_000000_ab.png)\n")
    return work / "paper.json", out


def test_index_docling_figures_and_tables(docling_dir):
    json_path, out = docling_dir
    assert _index_docling(json_path, out) == (1, 1)
    assert (out / "figures" / "fig-01.png").read_bytes() == PNG
    assert "| fig-01.png | 3 | Figure 1. A brain. |" in (out / "figures" / "figures.md").read_text()
    assert (out / "tables" / "table-01.csv").read_text().splitlines() == ["a,b", "1,2"]
    assert "| table-01.csv | 5 | Table 1. Results. |" in (out / "tables" / "tables.md").read_text()


def test_index_docling_rewrites_markdown_image_links(docling_dir):
    json_path, out = docling_dir
    _index_docling(json_path, out)
    text = (out / "paper.md").read_text()
    assert "![Image](figures/fig-01.png)" in text and "paper_artifacts" not in text
