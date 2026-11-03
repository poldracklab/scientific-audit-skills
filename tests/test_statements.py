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


def test_run_in_heading_with_period():
    s = extract_statements("Data availability. All data are at https://osf.io/abcde.\n")
    assert [x.kind for x in s] == ["data_availability"]
    assert s[0].text.startswith("All data are at")


def test_run_in_heading_with_colon():
    s = extract_statements("Funding: NIH R01MH123.\n")
    assert (s[0].kind, s[0].text) == ("funding", "NIH R01MH123.")


def test_statement_continues_across_page_break():
    s = extract_statements("Data availability\nFirst part\fsecond part\n\nOther")
    assert (s[0].text, s[0].page) == ("First part second part", 1)


def test_heading_at_page_bottom_keeps_next_page_text():
    s = extract_statements("Funding\n\fNIH R01.\n\nOther")
    assert (s[0].text, s[0].page) == ("NIH R01.", 1)
