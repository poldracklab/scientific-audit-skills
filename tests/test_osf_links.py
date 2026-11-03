from osf_links import annotate_osf_links


def _review_fields(link):
    return link["role"], link["needs_review"], link["reason"]


def _osf_plan_link(url, page):
    import links
    from scan import _link_dict

    return _link_dict(links.make_link(url, "paper.pdf", page), None)


def test_scan_adds_parent_project_for_file_links(osf_fixture):
    plan_links = [_osf_plan_link("https://osf.io/38vzr", 3), _osf_plan_link("https://osf.io/k9pqr", 5)]
    annotated = annotate_osf_links(plan_links, lambda u: osf_fixture("osf_guid_file.json"))
    assert len(annotated) == 3
    for child in annotated[:2]:
        assert _review_fields(child) == ("data", False, "osf file space_figure_3b.csv in project xu48j")
    parent = annotated[2]
    assert parent["canonical"] == "https://osf.io/xu48j" and parent["class"] == "osf" and parent["role"] == "data"
    assert parent["needs_review"] is True and parent["reason"].startswith("parent project of osf file links")
    assert "38vzr" in parent["reason"] and "k9pqr" in parent["reason"]
    assert parent["found_in"] == [{"file": "paper.pdf", "page": 3}, {"file": "paper.pdf", "page": 5}]


def test_scan_parent_project_not_duplicated(osf_api):
    plan_links = [_osf_plan_link("https://osf.io/38vzr", 3), _osf_plan_link("https://osf.io/xu48j", 4)]
    annotated = annotate_osf_links(plan_links, osf_api)
    assert [l["canonical"] for l in annotated] == ["https://osf.io/38vzr", "https://osf.io/xu48j"]


def test_parent_project_present_under_a_longer_url_is_not_duplicated(osf_api):
    storage = "https://osf.io/xu48j/files/osfstorage"
    plan_links = [_osf_plan_link("https://osf.io/38vzr", 3), _osf_plan_link(storage, 4)]
    annotated = annotate_osf_links(plan_links, osf_api)
    assert [l["canonical"] for l in annotated] == ["https://osf.io/38vzr", storage]


def test_annotate_keeps_link_when_resolution_fails():
    link = _osf_plan_link("https://osf.io/abcde", 1)
    before = dict(link)

    def failing(url):
        raise OSError("boom")

    assert annotate_osf_links([link], failing) == [before]
