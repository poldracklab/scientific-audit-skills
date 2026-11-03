import urllib.error

from prereg import fetch_aspredicted, fetch_clinicaltrials, fetch_prereg


def test_clinicaltrials(ctgov_fixture, tmp_path):
    r = fetch_clinicaltrials("NCT01234567", tmp_path / "ct", lambda u: ctgov_fixture)
    assert r["date_registered"] == "2019-03-04" and (tmp_path / "ct/NCT01234567.json").is_file()


def test_aspredicted_saves_pdf(tmp_path):
    r = fetch_aspredicted("https://aspredicted.org/abc12.pdf", tmp_path / "ap", lambda u: b"%PDF-1.4")
    assert r["status"] == "ok" and (tmp_path / "ap/abc12.pdf").read_bytes().startswith(b"%PDF")


def test_aspredicted_html_is_unverified(tmp_path):
    r = fetch_aspredicted("https://aspredicted.org/blind.php?x=abc12", tmp_path / "ap", lambda u: b"<html>login</html>")
    assert (tmp_path / "ap/abc12.html").is_file() and r["status"] == "unverified"
    assert r["reason"] == "HTML returned, not a PDF; the link may need its view token"


def test_aspredicted_failure_recorded(tmp_path):
    def boom(u):
        raise OSError("403")

    link = {"class": "aspredicted", "canonical": "https://aspredicted.org/abc12.pdf"}
    assert fetch_prereg(link, tmp_path, None, boom)["status"] == "failed"


def test_dispatch_osf_non_registration(osf_api, tmp_path):
    r = fetch_prereg({"class": "osf", "canonical": "https://osf.io/abcde"}, tmp_path, osf_api, lambda u: b"")
    assert r["status"] == "failed" and "not a registration" in r["reason"]


REG_ABCDE = "https://api.osf.io/v2/registrations/abcde/"


def test_dispatch_osf_forbidden_is_failed_not_non_registration(osf_router, tmp_path):
    get_json = osf_router({REG_ABCDE: urllib.error.HTTPError(REG_ABCDE, 403, "Forbidden", {}, None)})
    r = fetch_prereg({"class": "osf", "canonical": "https://osf.io/abcde"}, tmp_path, get_json, lambda u: b"")
    assert r["status"] == "failed" and r["reason"] != "not a registration" and "403" in r["reason"]


def test_dispatch_osf_gone_is_non_registration(osf_router, tmp_path):
    get_json = osf_router({REG_ABCDE: urllib.error.HTTPError(REG_ABCDE, 410, "Gone", {}, None)})
    r = fetch_prereg({"class": "osf", "canonical": "https://osf.io/abcde"}, tmp_path, get_json, lambda u: b"")
    assert r["status"] == "failed" and r["reason"] == "not a registration"


def test_aspredicted_unsafe_id_failed(tmp_path):
    link = {"class": "aspredicted", "canonical": "https://aspredicted.org/blind.php?x=/../../../foo"}
    r = fetch_prereg(link, tmp_path / "root", None, lambda u: b"%PDF-1.4")
    assert r["status"] == "failed" and r["reason"] == "unsafe id" and not any(tmp_path.rglob("foo*"))


def test_prospero_unsafe_id_failed(tmp_path):
    link = {"class": "prospero", "canonical": "https://www.crd.york.ac.uk/prospero/display_record.php?RecordID=../x"}
    r = fetch_prereg(link, tmp_path / "root", None, lambda u: b"<html>")
    assert r["status"] == "failed" and r["reason"] == "unsafe id"
