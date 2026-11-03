from crossref import fetch_metadata


def test_fetch_metadata_parses_fixture(crossref_fixture):
    m = fetch_metadata("10.1126/sciadv.abf4355", lambda url: crossref_fixture)
    assert m["published"] == "2021-05-12" and m["type"] == "journal-article"
    assert m["authors"][0]["family"] and m["journal"]
    assert m["relations"] == [{"type": "has-preprint", "doi": "10.1101/2020.01.01.123456"}]


def test_fetch_metadata_requests_works_endpoint():
    seen = []
    fetch_metadata("10.1/x", lambda url: (seen.append(url), {"message": {}})[1])
    assert seen == ["https://api.crossref.org/works/10.1/x"]
