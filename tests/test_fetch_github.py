from fetch_github import clone_repo, parse_github_url


def test_parse_github_url():
    assert parse_github_url("https://github.com/lab/repo") == ("lab", "repo")
    assert parse_github_url("https://github.com/lab/repo/tree/main/x") == ("lab", "repo")
    assert parse_github_url("https://gitlab.com/x/y") is None


def test_clone_records_commit_and_zenodo(bare_repo, tmp_path):
    r = clone_repo(str(bare_repo), tmp_path / "github" / "lab__repo")
    assert r["status"] == "ok" and len(r["commit"]) == 40 and r["zenodo_doi"] == "10.5281/zenodo.7654321"
    assert (tmp_path / "github/lab__repo/.git").exists()


def test_clone_failure_recorded(tmp_path):
    r = clone_repo("/nonexistent/repo.git", tmp_path / "x")
    assert r["status"] == "failed" and r["reason"]
