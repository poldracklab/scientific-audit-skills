import urllib.error

from paper_doi import choose_paper_doi


def _crossref(types: dict):
    """get_json answering Crossref works lookups with the given type per DOI; others 404."""
    def get_json(url):
        doi = url.removeprefix("https://api.crossref.org/works/")
        if doi not in types:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        return {"message": {"type": types[doi]}}

    return get_json


def test_tries_each_doi_until_journal_article():
    get_json = _crossref({"10.1101/pre": "posted-content", "10.1/article": "journal-article"})
    choice = choose_paper_doi(["10.1101/pre", "10.1/article"], get_json)
    assert (choice.doi, choice.confirmed) == ("10.1/article", True)


def test_no_journal_article_gives_no_doi():
    get_json = _crossref({"10.1101/pre": "posted-content"})
    choice = choose_paper_doi(["10.1101/pre", "10.9/missing"], get_json)
    assert choice.doi is None and choice.confirmed is False
    assert "10.1101/pre (posted-content)" in choice.reason


def test_no_candidates():
    choice = choose_paper_doi([], _crossref({}))
    assert choice.doi is None and choice.reason == "no doi found on first pages"


def test_network_failure_keeps_first_candidate_unconfirmed():
    def failing(url):
        raise OSError("boom")

    choice = choose_paper_doi(["10.1/a", "10.1/b"], failing)
    assert (choice.doi, choice.confirmed) == ("10.1/a", False)
    assert "crossref lookup failed: boom" in choice.reason
