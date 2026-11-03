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
