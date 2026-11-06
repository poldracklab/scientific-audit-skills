"""Packaging check; agent behavior is tested with the scenario protocol."""
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_router_is_discoverable_by_skill_installers():
    skills = {p.parent.name: p for p in ROOT.glob("*/SKILL.md")}
    assert "audit-routing" in skills
    metadata = yaml.safe_load(skills["audit-routing"].read_text().split("---", 2)[1])
    assert metadata["name"] == "audit-routing"
    assert isinstance(metadata["description"], str)
    assert 0 < len(metadata["description"]) <= 1024
