from prereg import fetch_aspredicted, fetch_clinicaltrials, fetch_prereg


def test_clinicaltrials(ctgov_fixture, tmp_path):
    r = fetch_clinicaltrials("NCT01234567", tmp_path / "ct", lambda u: ctgov_fixture)
    assert r["date_registered"] == "2019-03-04" and (tmp_path / "ct/NCT01234567.json").is_file()


def test_aspredicted_saves_pdf(tmp_path):
    r = fetch_aspredicted("https://aspredicted.org/abc12.pdf", tmp_path / "ap", lambda u: b"%PDF-1.4")
    assert r["status"] == "ok" and (tmp_path / "ap/abc12.pdf").read_bytes().startswith(b"%PDF")


def test_aspredicted_failure_recorded(tmp_path):
    def boom(u):
        raise OSError("403")

    link = {"class": "aspredicted", "canonical": "https://aspredicted.org/abc12.pdf"}
    assert fetch_prereg(link, tmp_path, None, boom)["status"] == "failed"


def test_dispatch_osf_non_registration(osf_api, tmp_path):
    r = fetch_prereg({"class": "osf", "canonical": "https://osf.io/abcde"}, tmp_path, osf_api, lambda u: b"")
    assert r["status"] == "failed" and "not a registration" in r["reason"]
