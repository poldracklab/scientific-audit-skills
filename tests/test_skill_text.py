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
    assert "## Intake" in text and "verify_run.py" in text and "audit-prep" in text
    for old in ["osf_fetch.py", "figs_paper/", "prereg.txt", "~/Projects/<topic>_audits"]: assert old not in text, old
    for new in ["paper/paper.txt", "paper/pages/", "data/osf_", "preregistration/", "audit/audit.qmd", "registry.jsonl"]: assert new in text, new


def test_reproducibility_template_is_blind():
    t = (SKILLS / "reproducibility-audit/templates/audit_template.qmd").read_text()
    assert "MODEL" not in t and "identity recorded in the run registry" in t


def test_reproducibility_scripts_dir_holds_only_launcher():
    # Fetch scripts moved to audit-prep; only the operator's run launcher remains.
    scripts = SKILLS / "reproducibility-audit/scripts"
    assert sorted(p.name for p in scripts.iterdir()) == ["new_run.sh"]


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


AUDIT_SKILLS = ["reproducibility-audit", "neuroimaging-validity-audit"]


def _intake(skill: str) -> str:
    text = (SKILLS / skill / "SKILL.md").read_text()
    return text.split("## Intake\n", 1)[1].split("\n## ", 1)[0]


def _flat(text: str) -> str:
    return " ".join(text.split())


def test_auditors_require_operator_created_runs():
    for skill in AUDIT_SKILLS:
        intake = _flat(_intake(skill))
        assert "Only `run_ok` permits auditing" in intake, skill
        assert "operator" in intake and "before the evaluated session" in intake, skill
        assert "new_run.py" not in intake and "--model" not in intake, skill
        assert "invoke the `audit-prep` skill" not in intake, skill
        assert ".claude/settings.json" not in intake, skill
    assert _intake("reproducibility-audit") == _intake("neuroimaging-validity-audit")


def test_operator_setup_keeps_registry_outside_auditor_access():
    text = _flat((SKILLS / "audit-prep/SKILL.md").read_text())
    assert "before the evaluated session" in text
    assert "registry.jsonl" in text and "inaccessible" in text
    assert "run folder" in text and "operator" in text
    assert ".claude/settings.json" not in text


def test_both_audits_allow_additional_evidence_and_retries():
    for skill in AUDIT_SKILLS:
        text = _flat((SKILLS / skill / "SKILL.md").read_text())
        assert "## Additional evidence" in text, skill
        assert "may retrieve additional relevant evidence" in text, skill
        assert "retry sources that prep could not retrieve" in text, skill
        assert "audit/additional-evidence/" in text, skill
        assert "prepared inputs unchanged" in text, skill
        assert "supplied evidence" in text and "discovered evidence" in text, skill


def test_reports_have_additional_evidence_provenance_table():
    for skill in AUDIT_SKILLS:
        for relative in ["references/report.md", "templates/audit_template.qmd"]:
            text = (SKILLS / skill / relative).read_text()
            assert "Source URL | Retrieval date | Local file | Findings" in text, (skill, relative)
            assert "audit/additional-evidence/" in text, (skill, relative)


def test_prep_documents_copy_selection_and_immutable_raw_inputs():
    text = _flat((SKILLS / "audit-prep/SKILL.md").read_text())
    assert "Raw folders stay in place" in text
    assert "`skip` and `unsorted`" in text and "excluded" in text
    assert "authoritative" in text and "fresh draft" in text
    assert "symbolic links" in text
    assert "unsorted/<Paper_Year>/" not in text


def test_structured_conversion_is_explicit_and_documented():
    for relative in ["audit-prep/SKILL.md", "audit-prep/references/prep-yaml.md"]:
        text = (SKILLS / relative).read_text()
        assert "structured_conversion" in text and "true" in text and "false" in text
        assert "corpus" in text
    assert "not_requested" in (SKILLS / "audit-prep/references/manifest.md").read_text()


def test_reproducibility_specialized_recipes_are_loaded_when_relevant():
    text = (SKILLS / "reproducibility-audit/SKILL.md").read_text()
    assert "references/analysis-recipes.md" in text
    assert "One-factor selection-model tipping point" not in text
    recipes = SKILLS / "reproducibility-audit/references/analysis-recipes.md"
    assert recipes.is_file()
    for guidance in ["lavaan labels", "Lee bounds", "Outcome × finding matrix"]:
        assert guidance in recipes.read_text(), guidance


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


CONSENSUS = SKILLS / "audit-consensus"
CONSENSUS_SECTIONS = [
    "## AI-generated — not for publication", "## Preliminary & unvetted analysis",
    "# Bottom line", "# Claims", "# Confirmed issues", "# Disputed and refuted findings",
    "# Agreed minor issues", "# Noticed during adjudication", "# Finding cross-walk {.appendix}",
    "# Adjudication analyses {.appendix}", "# Provenance {.appendix}", "# Session info {.appendix}",
]


def test_consensus_skill_frontmatter_and_rules():
    text = (CONSENSUS / "SKILL.md").read_text()
    assert text.startswith("---\nname: audit-consensus\n") and "description:" in text
    for phrase in ["inputs.json", "registry.jsonl", "Disputed", "Converged", "untested",
                   "partly confirmed", "weak or unsupported", "strong → moderate", "cross-walk"]:
        assert phrase in text, phrase
    assert "letter grade" not in text.lower()


def test_consensus_template_sections_in_order():
    t = (CONSENSUS / "templates/consensus_template.qmd").read_text()
    positions = [t.index(s) for s in CONSENSUS_SECTIONS]
    assert positions == sorted(positions)


def test_consensus_template_is_blind():
    t = (CONSENSUS / "templates/consensus_template.qmd").read_text()
    assert "run_models.json" in t and "Model mapping attached after the consensus run." in t
    assert "MODEL" not in t


def test_consensus_scripts_dir_contents():
    names = sorted(p.name for p in (CONSENSUS / "scripts").iterdir() if p.name != "__pycache__")
    assert names == ["consensus.py", "consensus.sh", "discover.py", "redact.py"]


def test_top_level_readme_documents_consensus_launcher():
    text = (SKILLS / "README.md").read_text()
    assert "### 4. Reconcile the audits into a consensus report" in text
    assert "audit-consensus/scripts/consensus.sh" in text


def test_consensus_skill_forbids_other_consensus_folders():
    text = _flat((CONSENSUS / "SKILL.md").read_text())
    assert "Never read other folders under `consensus/`" in text
