import json
import os
import random
import shutil
from pathlib import Path

from conftest import accept_all_problems
from corpus import init_root
from new_run import new_run
from prepare import finalize, run_prep
from scan import build_plan, write_plan
from verify_run import verify

ROLES = {
    "https://osf.io/abcde": "data",
    "https://osf.io/x4c56": "prereg",
    "https://github.com/lab/repo": "code",
    "https://github.com/lab/hidden-tool": "skip",
}


def _review(plan, bare_repo):
    assert set(ROLES) <= {link["canonical"] for link in plan["links"]}
    plan["reviewed_by"] = "human"
    for item in plan["files"] + plan["links"]:
        item["needs_review"] = False
    for link in plan["links"]:
        link["role"] = ROLES.get(link["canonical"], link["role"])
        if link["canonical"] == "https://github.com/lab/repo":
            link["url"] = str(bare_repo)
    return plan


def _prepare(tmp_path, raw_folder, clients, bare_repo, writable_after):
    corpus = init_root(tmp_path / "corpus")
    raw = Path(shutil.move(raw_folder("paper_supp"), corpus.root / "Paper_2024"))
    plan = _review(build_plan(raw, clients.get_json), bare_repo)
    write_plan(plan, raw / "prep.yaml")
    run_prep(raw, corpus, clients)
    prepared = corpus.prepared_dir("Paper_2024")
    _check_prep_outcomes(prepared)
    writable_after(prepared)
    accept_all_problems(prepared)
    finalize(prepared)
    return corpus, prepared


def _check_prep_outcomes(prepared: Path) -> None:
    assert (prepared / "data" / "osf_abcde").is_dir()
    assert (prepared / "preregistration" / "osf_x4c56" / "registration.json").is_file()
    assert (prepared / "github" / "lab__repo" / ".git").exists()
    assert not any("hidden-tool" in str(p) for p in prepared.rglob("*"))
    manifest = json.loads((prepared / "manifest.json").read_text())
    assert manifest["documents"]["paper"]["conversions"]["structured"] == "failed"


def _texts_under(root: Path):
    for p in root.rglob("*"):
        yield str(p.relative_to(root))
        if p.is_file() and not p.is_symlink():
            yield p.read_bytes().decode("utf-8", errors="ignore")


def _mentions(root: Path, word: str) -> bool:
    return any(word in text for text in _texts_under(root))


def test_full_cycle(tmp_path, raw_folder, osf_api, crossref_fixture, bare_repo, clients, writable_after):
    corpus, prepared = _prepare(tmp_path, raw_folder, clients, bare_repo, writable_after)
    run_a = new_run(corpus, "Paper_2024", "model-a", rng=random.Random(1))
    assert verify(run_a)[0] == "run_ok"
    (run_a / "audit" / "x.html").write_text("<p>audit</p>")
    assert verify(run_a)[0] == "run_ok"
    run_b = new_run(corpus, "Paper_2024", "model-b", rng=random.Random(2))
    assert run_b.name != run_a.name and verify(run_b)[0] == "run_ok"
    assert not _mentions(corpus.runs, "model-a") and not _mentions(corpus.runs, "model-b")
    registry = corpus.registry.read_text()
    assert "model-a" in registry and "model-b" in registry
    assert not os.access(prepared / "paper" / "paper.pdf", os.W_OK)
    assert verify(prepared)[0] == "prepared_not_run"
