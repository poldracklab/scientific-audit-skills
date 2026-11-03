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
    "Preregistered: 10.17605/OSF.IO/X4C56\nSee our code for details."
)
PAGE2 = (
    "Data availability\nAll data are available at https://zenodo.org/records/123456\n"
    "Code availability\nSee https://github.com/lab/repo\nFunding\nNIH R01."
)


@pytest.fixture(scope="session")
def fixture_pdf(tmp_path_factory):
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), PAGE1, fontsize=10)
    rect = page.search_for("our code")[0]
    page.insert_link({"kind": pymupdf.LINK_URI, "from": rect, "uri": "https://github.com/lab/repo"})
    doc.new_page().insert_text((72, 72), PAGE2, fontsize=10)
    out = tmp_path_factory.mktemp("pdf") / "paper.pdf"
    doc.save(out)
    return out
