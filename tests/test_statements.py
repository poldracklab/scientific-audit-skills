from statements import extract_statements, write_statements_md

TEXT = (
    "Intro\fData availability\nAll data are available at https://zenodo.org/records/1.\n\n"
    "Code availability\nSee GitHub.\n\nFunding\nNIH.\n"
)


def test_extract_kinds_and_pages():
    s = extract_statements(TEXT)
    assert [(x.kind, x.page) for x in s] == [
        ("data_availability", 2),
        ("code_availability", 2),
        ("funding", 2),
    ]
    assert s[0].text.startswith("All data are available")


def test_preregistration_variants():
    s = extract_statements("Pre-registration\nThe study was preregistered.")
    assert s[0].kind == "preregistration"


def test_write_md_has_page_markers(tmp_path):
    out = write_statements_md(extract_statements(TEXT), tmp_path / "statements.md")
    assert "## Data availability (p. 2)" in out.read_text()
