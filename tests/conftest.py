import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "audit-prep" / "scripts"))


@pytest.fixture
def corpus_root(tmp_path):
    return tmp_path / "corpus"


PAGE1 = (
    "Example Paper Title\ndoi: 10.1126/sciadv.abf4355\n"
    "Data are at https://osf.io/abcde/.\n"
    "Preregistered: 10.17605/OSF.IO/X4C56\nSee our code for details.\nUse hidden tool. Email author."
)
PAGE2 = (
    "Data availability\nAll data are available at https://zenodo.org/records/123456\n"
    "Code availability\nSee https://github.com/lab/repo\nFunding\nNIH R01."
)


def _annotate(page, words, uri):
    import pymupdf

    rect = page.search_for(words)[0]
    page.insert_link({"kind": pymupdf.LINK_URI, "from": rect, "uri": uri})


@pytest.fixture(scope="session")
def fixture_pdf(tmp_path_factory):
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), PAGE1, fontsize=10)
    rect = page.search_for("our code")[0]
    page.insert_link({"kind": pymupdf.LINK_URI, "from": rect, "uri": "https://github.com/lab/repo"})
    _annotate(page, "hidden tool", "https://github.com/lab/hidden-tool")
    _annotate(page, "Email author", "mailto:author@univ.edu")
    doc.new_page().insert_text((72, 72), PAGE2, fontsize=10)
    out = tmp_path_factory.mktemp("pdf") / "paper.pdf"
    doc.save(out)
    return out


@pytest.fixture(scope="session")
def fixture_docx(tmp_path_factory):
    import docx

    doc = docx.Document()
    doc.add_heading("Supplementary Methods", level=1)
    doc.add_paragraph("We describe the methods in detail here.")
    out = tmp_path_factory.mktemp("docx") / "supp.docx"
    doc.save(out)
    return out


@pytest.fixture(scope="session")
def fixture_xlsx(tmp_path_factory):
    import openpyxl

    wb = openpyxl.Workbook()
    wb.active.title = "Table S1"
    wb.active.append([1, 2])
    wb.active.append([3, 4])
    ws = wb.create_sheet("Table S2")
    ws.append([5, 6])
    ws.append([7, 8])
    out = tmp_path_factory.mktemp("xlsx") / "supp.xlsx"
    wb.save(out)
    return out


@pytest.fixture
def crossref_fixture():
    import json

    path = Path(__file__).resolve().parent / "fixtures" / "crossref_work.json"
    return json.loads(path.read_text())
