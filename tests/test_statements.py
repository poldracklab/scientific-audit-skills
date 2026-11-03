import pytest

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


def test_empty_statements_md_says_none_found(tmp_path):
    out = write_statements_md(extract_statements("Intro\nNothing here.\n"), tmp_path / "statements.md")
    text = out.read_text()
    assert "were found" in text and "Read the paper text directly" in text


def test_acknowledgements_heading():
    s = extract_statements("Acknowledgements\nThis work was funded by NIH.")
    assert [(x.kind, x.text) for x in s] == [("acknowledgements", "This work was funded by NIH.")]


@pytest.mark.parametrize("heading", ["Acknowledgments", "Acknowledgement", "ACKNOWLEDGEMENTS:"])
def test_acknowledgement_spellings(heading):
    assert extract_statements(f"{heading}\nWe thank NSF.")[0].kind == "acknowledgements"


def test_data_and_materials_availability_run_in():
    s = extract_statements("Data and materials availability: All data are at https://osf.io/abcde.\n")
    assert [x.kind for x in s] == ["data_availability"] and s[0].text.startswith("All data are at")


@pytest.mark.parametrize("heading", [
    "Data and code availability", "Data availability", "Availability of data", "Availability of data and materials",
    "Data accessibility", "Data sharing", "Data sharing statement", "Transparency and openness",
    "Transparency and openness promotion", "Transparency and openness promotion statement",
])
def test_data_availability_heading_variants(heading):
    s = extract_statements(f"{heading}\nData are at OSF.")
    assert [(x.kind, x.text) for x in s] == [("data_availability", "Data are at OSF.")]


def test_acknowledgements_run_in_without_punctuation():
    s = extract_statements("Acknowledgements The authors thank the participants.\n")
    assert [x.kind for x in s] == ["acknowledgements"] and s[0].text.startswith("The authors")


def test_funding_run_in_without_punctuation():
    s = extract_statements("Funding This work was supported by NIH.\n")
    assert [(x.kind, x.text) for x in s] == [("funding", "This work was supported by NIH.")]


def test_sentence_starting_with_funding_is_not_a_heading():
    assert extract_statements("Funding was provided by NIH.\n") == []
