import pytest

from corpus import CorpusError
from prepare import scan_folder


def no_network(url):
    raise AssertionError("No network expected for an empty input folder")


@pytest.mark.parametrize("name", ["prep.yaml", "statements.md"])
def test_scan_rejects_output_links_without_overwriting(tmp_path, name):
    raw = tmp_path / "raw"
    raw.mkdir()
    target = tmp_path / "outside"
    target.write_text("keep")
    (raw / name).symlink_to(target)
    with pytest.raises(CorpusError, match="symlink"):
        scan_folder(raw, no_network)
    assert target.read_text() == "keep"


def test_scan_rejects_symlinked_raw_root(tmp_path):
    target = tmp_path / "outside"
    target.mkdir()
    raw = tmp_path / "raw"
    raw.symlink_to(target)
    with pytest.raises(CorpusError, match="symlink"):
        scan_folder(raw, no_network)
    assert list(target.iterdir()) == []


def test_scan_rejects_dangling_output_link(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    target = tmp_path / "absent"
    (raw / "prep.yaml").symlink_to(target)
    with pytest.raises(CorpusError, match="symlink"):
        scan_folder(raw, no_network)
    assert not target.exists()


def test_ordinary_rescan_still_works(tmp_path):
    scan_folder(tmp_path, no_network)
    scan_folder(tmp_path, no_network)
    assert (tmp_path / "prep.yaml").read_text().startswith("schema_version:")
