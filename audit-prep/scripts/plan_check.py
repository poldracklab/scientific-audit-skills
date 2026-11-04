# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Validate a hand-edited prep.yaml: roles, classes, supplement and corrigendum order, paper count, accept_failures."""
from collections import Counter
from pathlib import Path

FILE_ROLES = ("paper", "supplement", "corrigendum", "data", "archive", "unsorted", "skip")
NUMBERED_ROLES = ("supplement", "corrigendum")
LINK_ROLES = ("prereg", "code", "data", "unknown", "skip")
LINK_CLASSES = ("osf", "github", "zenodo", "figshare", "dryad", "openneuro", "neurovault", "aspredicted",
                "clinicaltrials", "prospero", "doi", "other")
PLACEHOLDER = "<why this is acceptable>"
UNACCEPTABLE = ("run", "plan")


def _bad_value(name: str, key: str, value, allowed: tuple[str, ...]) -> list[str]:
    if value in allowed:
        return []
    return [f"{name}: unknown {key} {value!r} (allowed: {', '.join(allowed)})"]


def _file_values(files: list[dict]) -> list[str]:
    return [m for f in files for m in _bad_value(f.get("path"), "role", f.get("role"), FILE_ROLES)]


def _file_paths(files: list[dict]) -> list[str]:
    return [f"{f.get('path')}: path must be a top-level name in the raw folder" for f in files
            if not isinstance(f.get("path"), str) or f["path"] in ("", ".", "..")
            or Path(f["path"]).name != f["path"]]


def _link_values(plan_links: list[dict]) -> list[str]:
    return [m for l in plan_links
            for m in _bad_value(l.get("url"), "role", l.get("role"), LINK_ROLES)
            + _bad_value(l.get("url"), "class", l.get("class"), LINK_CLASSES)]


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _orders(files: list[dict], role: str) -> list[str]:
    numbered = [f for f in files if f.get("role") == role]
    msgs = [f"{f.get('path')}: {role} order must be an integer" for f in numbered if not _is_int(f.get("order"))]
    counts = Counter(f["order"] for f in numbered if _is_int(f.get("order")))
    return msgs + [f"{role} order {n} is used more than once" for n, c in sorted(counts.items()) if c > 1]


def _paper_count(files: list[dict]) -> list[str]:
    papers = sum(f.get("role") == "paper" for f in files)
    if papers == 0:
        return ["no file with role paper"]
    return ["more than one file with role paper"] if papers > 1 else []


def acceptance_problems(plan: dict) -> list[str]:
    """`accept_failures`, when present, maps each review item string to a non-empty reason."""
    accept = plan.get("accept_failures")
    if accept is None:
        return []
    if not isinstance(accept, dict):
        return ["accept_failures must be a mapping of item -> reason"]
    return [msg for key, reason in accept.items() if (msg := _acceptance_problem(key, reason))]


def _acceptance_problem(key, reason) -> str | None:
    if key in UNACCEPTABLE:
        return f"accept_failures: {key}: cannot be accepted; rerun prep.py run instead"
    if not isinstance(key, str) or not isinstance(reason, str) or not reason.strip():
        return f"accept_failures: {key}: reason required"
    if reason.strip() == PLACEHOLDER:
        return f"accept_failures: {key}: replace the placeholder with what the auditor will be missing"
    return None


def plan_problems(plan: dict) -> list[str]:
    files, plan_links = plan.get("files", []), plan.get("links", [])
    options = [] if isinstance(plan.get("structured_conversion", True), bool) else ["structured_conversion must be a boolean"]
    return (options + _file_paths(files) + _file_values(files) + _link_values(plan_links)
            + [m for role in NUMBERED_ROLES for m in _orders(files, role)] + _paper_count(files)
            + acceptance_problems(plan))
