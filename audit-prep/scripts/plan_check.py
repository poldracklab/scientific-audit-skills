# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Validate the shape of a hand-edited prep.yaml: roles, classes, supplement order, paper count."""
from collections import Counter

FILE_ROLES = ("paper", "supplement", "data", "archive", "unsorted", "skip")
LINK_ROLES = ("prereg", "code", "data", "unknown", "skip")
LINK_CLASSES = ("osf", "github", "zenodo", "figshare", "dryad", "openneuro", "neurovault", "aspredicted",
                "clinicaltrials", "prospero", "doi", "other")


def _bad_value(name: str, key: str, value, allowed: tuple[str, ...]) -> list[str]:
    if value in allowed:
        return []
    return [f"{name}: unknown {key} {value!r} (allowed: {', '.join(allowed)})"]


def _file_values(files: list[dict]) -> list[str]:
    return [m for f in files for m in _bad_value(f.get("path"), "role", f.get("role"), FILE_ROLES)]


def _link_values(plan_links: list[dict]) -> list[str]:
    return [m for l in plan_links
            for m in _bad_value(l.get("url"), "role", l.get("role"), LINK_ROLES)
            + _bad_value(l.get("url"), "class", l.get("class"), LINK_CLASSES)]


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _supplement_orders(files: list[dict]) -> list[str]:
    supplements = [f for f in files if f.get("role") == "supplement"]
    msgs = [f"{f.get('path')}: supplement order must be an integer" for f in supplements if not _is_int(f.get("order"))]
    counts = Counter(f["order"] for f in supplements if _is_int(f.get("order")))
    return msgs + [f"supplement order {n} is used more than once" for n, c in sorted(counts.items()) if c > 1]


def _paper_count(files: list[dict]) -> list[str]:
    papers = sum(f.get("role") == "paper" for f in files)
    if papers == 0:
        return ["no file with role paper"]
    return ["more than one file with role paper"] if papers > 1 else []


def plan_problems(plan: dict) -> list[str]:
    files, plan_links = plan.get("files", []), plan.get("links", [])
    return _file_values(files) + _link_values(plan_links) + _supplement_orders(files) + _paper_count(files)
