"""Text contracts for the skills' SKILL.md files."""
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[1]


def test_audit_prep_skill_frontmatter_and_commands():
    text = (SKILLS / "audit-prep/SKILL.md").read_text()
    assert text.startswith("---\nname: audit-prep\n") and "description:" in text
    for cmd in ["prep.py init", "prep.py scan", "prep.py run", "prep.py finalize", "new_run.py", "verify_run.py", "--dry-run"]:
        assert cmd in text, cmd
    assert "reviewed_by" in text and "never delete" in text.lower() and "registry.jsonl" in text


def test_audit_prep_skill_has_no_zsh_path_loop():
    assert "for path in" not in (SKILLS / "audit-prep/SKILL.md").read_text()


def test_reproducibility_audit_has_intake_and_new_layout():
    text = (SKILLS / "reproducibility-audit/SKILL.md").read_text()
    assert "## Intake" in text and "verify_run.py" in text and "new_run.py" in text and "audit-prep" in text
    for old in ["osf_fetch.py", "figs_paper/", "prereg.txt", "~/Projects/<topic>_audits"]: assert old not in text, old
    for new in ["paper/paper.txt", "paper/pages/", "data/osf_", "preregistration/", "audit/audit.qmd", "registry.jsonl"]: assert new in text, new


def test_reproducibility_template_is_blind():
    t = (SKILLS / "reproducibility-audit/templates/audit_template.qmd").read_text()
    assert "MODEL" not in t and "identity recorded in the run registry" in t


def test_no_scripts_dir_left(): assert not (SKILLS / "reproducibility-audit/scripts").exists()


def test_neuroimaging_audit_has_intake_and_is_blind():
    text = (SKILLS / "neuroimaging-validity-audit/SKILL.md").read_text()
    assert "## Intake" in text and "verify_run.py" in text and "audit-prep" in text
    assert "audit-<llm>" not in text and '"-audit"' not in text and "audit/" in text
    t = (SKILLS / "neuroimaging-validity-audit/templates/audit_template.qmd").read_text()
    assert "MODEL" not in t and "identity recorded in the run registry" in t


def test_review_rules_check_doi_is_not_a_deposit_doi():
    for doc in ["audit-prep/SKILL.md", "audit-prep/references/prep-yaml.md"]:
        text = (SKILLS / doc).read_text()
        assert "confirm `doi` is the article's own DOI, not a deposit DOI" in text, doc


PREREG_DOCS = ["audit-prep/references/manifest.md", "reproducibility-audit/SKILL.md",
               "reproducibility-audit/templates/audit_template.qmd"]


def test_prereg_docs_name_status_and_per_file_verified():
    for doc in PREREG_DOCS:
        text = (SKILLS / doc).read_text()
        assert "hash_verified" not in text and "verified" in text, doc


def test_manifest_doc_matches_emitted_keys():
    text = (SKILLS / "audit-prep/references/manifest.md").read_text()
    versions = next(l for l in text.splitlines() if l.startswith("| `prep_versions`"))
    for key in ["skill", "pdftotext", "pdftoppm", "pandoc", "zstd", "docling", "git"]:
        assert f"`{key}`" in versions, key
    assert "poppler" not in versions
    links_row = next(l for l in text.splitlines() if l.startswith("| `links`"))
    assert "decision" not in links_row


CWD_RULE = ("Start the audit session with the corpus root as the working directory so "
            "`.claude/settings.json` applies; then `cd` into the run folder.")


def _intake(skill: str) -> str:
    text = (SKILLS / skill / "SKILL.md").read_text()
    return text.split("## Intake\n", 1)[1].split("\n## ", 1)[0]


def _flat(text: str) -> str:
    return " ".join(text.split())


def test_session_cwd_rule_stated_in_prep_and_both_intakes():
    assert CWD_RULE in _flat((SKILLS / "audit-prep/SKILL.md").read_text())
    for skill in ["reproducibility-audit", "neuroimaging-validity-audit"]:
        assert CWD_RULE in _flat(_intake(skill)), skill
    assert _intake("reproducibility-audit") == _intake("neuroimaging-validity-audit")


def _unsupported_host_sentence(text: str) -> str:
    assert "Any other data" in text
    return text.split("Any other data", 1)[1].split("status: unsupported", 1)[0]


def test_audit_prep_skill_lists_openneuro_as_a_fetcher():
    text = (SKILLS / "audit-prep/SKILL.md").read_text()
    assert "openneuro_<dsid>/" in text
    assert "OpenNeuro" not in _unsupported_host_sentence(text)


def test_accept_failures_documented_and_intakes_read_prep_review():
    assert "accept_failures" in (SKILLS / "audit-prep/SKILL.md").read_text()
    assert "accept_failures" in (SKILLS / "audit-prep/references/prep-yaml.md").read_text()
    assert "prep.py review" in (SKILLS / "audit-prep/SKILL.md").read_text()
    for skill in ["reproducibility-audit", "neuroimaging-validity-audit"]:
        assert "Prep review" in _intake(skill), skill


def test_review_exit_codes_and_incomplete_run_documented():
    skill = _flat((SKILLS / "audit-prep/SKILL.md").read_text())
    assert "exit 0 ok, 1 open problems, 2 plan or corpus error" in skill
    assert "An interrupted `run` leaves `review: null`" in skill and "`run: incomplete`" in skill
    row = next(l for l in (SKILLS / "audit-prep/references/manifest.md").read_text().splitlines()
               if l.startswith("| `review`"))
    for word in ["`run`", "`link`", "`not_extracted`"]:
        assert word in row, word
