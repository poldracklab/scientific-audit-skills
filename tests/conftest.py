import shutil
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


def _nodoi_pdf(out: Path) -> None:
    import pymupdf

    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "A manuscript without identifiers.", fontsize=10)
    doc.save(out)


def _tar_dir(src: Path, out: Path) -> None:
    import tarfile

    with tarfile.open(out, "w:gz") as tar:
        tar.add(src, arcname=src.name)


def _shape_paper_supp(raw: Path, pdf: Path, docx: Path) -> None:
    shutil.copy(pdf, raw / "paper.pdf")
    shutil.copy(pdf, raw / "paper_sm.pdf")


def _shape_paper_data_archive(raw: Path, pdf: Path, docx: Path) -> None:
    shutil.copy(pdf, raw / "paper.pdf")
    (raw / "mydata").mkdir()
    (raw / "mydata" / "trials.csv").write_text("trial,rt\n1,0.5\n")
    _tar_dir(raw / "mydata", raw / "mydata.tar.gz")


def _shape_paper_residue(raw: Path, pdf: Path, docx: Path) -> None:
    shutil.copy(pdf, raw / "paper.pdf")
    (raw / ".venv").mkdir()
    (raw / ".venv" / "pyvenv.cfg").write_text("home = /usr/bin\n")
    (raw / ".git").mkdir()
    (raw / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    (raw / "paper.txt").write_text("text dump of paper.pdf\n")


def _shape_paper_nodoi(raw: Path, pdf: Path, docx: Path) -> None:
    _nodoi_pdf(raw / "nodoi.pdf")


def _shape_paper_supp_docx(raw: Path, pdf: Path, docx: Path) -> None:
    shutil.copy(pdf, raw / "paper.pdf")
    shutil.copy(docx, raw / "1-s2.0-S1878929323001421-mmc1.docx")


SHAPES = {
    "paper_supp": _shape_paper_supp,
    "paper_data_archive": _shape_paper_data_archive,
    "paper_residue": _shape_paper_residue,
    "paper_nodoi": _shape_paper_nodoi,
    "paper_supp_docx": _shape_paper_supp_docx,
}


def _git(*args: str, cwd: Path) -> None:
    import subprocess

    ident = ["-c", "user.email=t@example.com", "-c", "user.name=T"]
    subprocess.run(["git", *ident, *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture(scope="session")
def bare_repo(tmp_path_factory):
    base = tmp_path_factory.mktemp("gitrepo")
    work = base / "work"
    work.mkdir()
    _git("init", "-q", cwd=work)
    (work / "README.md").write_text("Archive: 10.5281/zenodo.7654321\n")
    _git("add", "README.md", cwd=work)
    _git("commit", "-q", "-m", "init", cwd=work)
    bare = base / "repo.git"
    _git("clone", "--bare", "-q", str(work), str(bare), cwd=base)
    return bare


@pytest.fixture
def raw_folder(tmp_path, fixture_pdf, fixture_docx):
    def make(shape: str) -> Path:
        raw = tmp_path / shape / "Paper_2024"
        raw.mkdir(parents=True)
        SHAPES[shape](raw, fixture_pdf, fixture_docx)
        return raw

    return make


FIXTURES = Path(__file__).resolve().parent / "fixtures"
OSF = "https://api.osf.io/v2"
OSF_ROUTES = {
    f"{OSF}/nodes/abcde/": "osf_node.json",
    f"{OSF}/nodes/abcde/files/osfstorage/": "osf_files_page1.json",
    f"{OSF}/nodes/abcde/files/osfstorage/?page=2": "osf_files_page2.json",
    f"{OSF}/nodes/abcde/files/osfstorage/f0lder/": "osf_files_folder.json",
    f"{OSF}/registrations/x4c56/": "osf_registration.json",
    f"{OSF}/registrations/x4c56/files/osfstorage/": "osf_registration_files.json",
}


def _load_fixture(name: str) -> dict:
    import json

    return json.loads((FIXTURES / name).read_text())


def _osf_get_json(overrides: dict):
    import urllib.error

    def get_json(url: str) -> dict:
        if url in overrides:
            value = overrides[url]
            if isinstance(value, Exception):
                raise value
            return value
        if url in OSF_ROUTES:
            return _load_fixture(OSF_ROUTES[url])
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

    return get_json


@pytest.fixture
def osf_api():
    return _osf_get_json({})


@pytest.fixture
def osf_router():
    """Build an OSF get_json whose `overrides` (URL -> dict or exception) win over the recorded routes."""
    return _osf_get_json


@pytest.fixture
def osf_fixture():
    return _load_fixture


def osf_file_entry(fid: str, name: str, size: int, extra: dict) -> dict:
    attrs = {"kind": "file", "name": name, "size": size, "extra": extra}
    return {"id": fid, "type": "files", "attributes": attrs, "links": {"download": f"https://osf.io/download/{fid}/"}}


@pytest.fixture
def osf_entry():
    return osf_file_entry


@pytest.fixture
def ctgov_fixture():
    return _load_fixture("ctgov_study.json")


NV = "https://neurovault.org/api/collections/1234"
NV_ROUTES = {
    f"{NV}/": "neurovault_collection.json",
    f"{NV}/images/?format=json": "neurovault_images_p1.json",
    f"{NV}/images/?format=json&page=2": "neurovault_images_p2.json",
}


@pytest.fixture
def zenodo_fixture():
    return _load_fixture("zenodo_record.json")


@pytest.fixture
def neurovault_api():
    import urllib.error

    def get_json(url: str) -> dict:
        if url not in NV_ROUTES:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        return _load_fixture(NV_ROUTES[url])

    return get_json
