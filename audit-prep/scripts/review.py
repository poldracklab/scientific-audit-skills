# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Review a manifest for prep problems and apply the plan's explicit `accept_failures`."""
from dataclasses import asdict, dataclass

EXTRACT_PROBLEMS = {"failed", "skipped"}
CODE_PROBLEMS = {"failed", "unsupported"}
PLACEHOLDER = "<why this is acceptable>"


class ReviewError(Exception):
    pass


@dataclass
class Problem:
    kind: str
    item: str
    status: str
    detail: str


def _warning(m: dict, match) -> str:
    return next((w for w in m.get("warnings") or [] if match(w)), "")


def _paper(m: dict) -> list[Problem]:
    if (m.get("documents") or {}).get("paper"):
        return []
    return [Problem("paper", "paper", "missing", "no paper role in prep.yaml")]


def _documents(m: dict) -> list[dict]:
    docs = m.get("documents") or {}
    return ([docs["paper"]] if docs.get("paper") else []) + list(docs.get("supplements") or [])


def _conversions(m: dict) -> list[Problem]:
    return [Problem("conversion", f"conversion {doc['path']} {name}", status,
                    _warning(m, lambda w, label=f"{doc['path']} {name}": w.startswith(label)))
            for doc in _documents(m) for name, status in (doc.get("conversions") or {}).items()
            if status == "failed"]


def _metadata(m: dict) -> list[Problem]:
    if m.get("metadata") is not None:
        return []
    return [Problem("metadata", "metadata crossref", "missing", _warning(m, lambda w: "crossref" in w or "doi" in w))]


def _local_data(m: dict) -> list[Problem]:
    return [Problem("local_data", f"local_data {e['path']}", e["extracted"],
                    e.get("reason") or _warning(m, lambda w, path=e["path"]: w.startswith(path)))
            for e in m.get("local_data") or [] if e.get("extracted") in EXTRACT_PROBLEMS]


def _records(m: dict, key: str, kind: str, is_problem, item) -> list[Problem]:
    return [Problem(kind, item(r), r.get("status"), r.get("reason") or "")
            for r in m.get(key) or [] if is_problem(r.get("status"))]


def manifest_problems(m: dict) -> list[Problem]:
    """Every missing or failed prep product, in manifest order."""
    return (_paper(m) + _conversions(m) + _metadata(m) + _local_data(m)
            + _records(m, "preregistration", "preregistration", lambda s: s != "ok",
                       lambda r: f"preregistration {r['source']} {r['id']}")
            + _records(m, "code", "code", lambda s: s in CODE_PROBLEMS, lambda r: f"code {r['url']}")
            + _records(m, "data", "data", lambda s: s != "ok", lambda r: f"data {r['source']} {r['id']}"))


def review_manifest(m: dict, plan: dict) -> dict:
    """Split problems into open and accepted; list acceptance keys that match nothing. Writes nothing."""
    accept = plan.get("accept_failures") or {}
    problems = manifest_problems(m)
    items = {p.item for p in problems}
    open_ = [asdict(p) for p in problems if p.item not in accept]
    accepted = [{**asdict(p), "accepted_reason": accept[p.item]} for p in problems if p.item in accept]
    return {"status": "failed" if open_ else "ok", "problems": open_, "accepted": accepted,
            "unused": [key for key in accept if key not in items]}


def _failed_lines(problems: list[dict]) -> list[str]:
    lines = [f"prep review: FAILED, {len(problems)} open problem(s):"]
    lines += [f"- {p['item']}: {p['status']} — {p['detail']}" for p in problems]
    lines += ["", "Fix and rerun, or acknowledge each in prep.yaml (say what the auditor will be missing):",
              "accept_failures:"]
    return lines + [f'  "{p["item"]}": "{PLACEHOLDER}"' for p in problems]


def format_review(review: dict) -> str:
    if review["status"] == "ok":
        lines = [f"prep review: ok ({len(review['accepted'])} accepted failure(s))"]
    else:
        lines = _failed_lines(review["problems"])
    if review["unused"]:
        lines.append("unused accept_failures keys: " + ", ".join(review["unused"]))
    return "\n".join(lines)
