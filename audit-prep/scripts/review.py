# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Review a manifest for prep problems and apply the plan's explicit `accept_failures`."""
import hashlib
import json
from dataclasses import asdict, dataclass

from plan_check import PLACEHOLDER, UNACCEPTABLE

EXTRACT_PROBLEMS = {"failed", "skipped"}
CODE_PROBLEMS = {"failed", "unsupported"}
FETCHED_ROLES = ("prereg", "code", "data")
INCOMPLETE = ("run", "run", "incomplete", "prep.py run did not reach its final step; rerun it")
MODIFIED = ("plan", "plan", "modified", "prep.yaml changed after run (files, links or roles); rerun prep.py run")
NESTED = "nested archive is listed, not extracted; extract by hand or accept"


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
    detail = _warning(m, lambda w: "crossref" in w or "doi" in w)
    return [Problem("metadata", "metadata crossref", "missing", detail)]


def _local_entry(m: dict, e: dict) -> Problem | None:
    if e.get("nested_archive"):
        return Problem("local_data", f"local_data {e['path']}", "not_extracted", NESTED)
    if e.get("extracted") not in EXTRACT_PROBLEMS:
        return None
    detail = e.get("reason") or _warning(m, lambda w: w.startswith(e["path"]))
    return Problem("local_data", f"local_data {e['path']}", e["extracted"], detail)


def _local_data(m: dict) -> list[Problem]:
    return [p for e in m.get("local_data") or [] if (p := _local_entry(m, e))]


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


def unfetched_links(m: dict, plan: dict) -> list[Problem]:
    """Plan links to fetch that the manifest has no record of (added to prep.yaml after `run`)."""
    seen = {link.get("canonical") for link in m.get("links") or []}
    return [Problem("link", f"link {l['canonical']}", "not_fetched", "link added after run; rerun prep.py run")
            for l in plan.get("links") or [] if l.get("role") in FETCHED_ROLES and l.get("canonical") not in seen]


def _marked_incomplete(review: dict) -> bool:
    return any(p.get("item") == "run" for p in review.get("problems", []) + review.get("accepted", []))


def run_incomplete(m: dict) -> Problem | None:
    """`run` resets `review` to None at its start and sets it only after its final step."""
    review = m.get("review")
    return Problem(*INCOMPLETE) if review is None or _marked_incomplete(review) else None


def plan_sha256(plan: dict) -> str:
    """Hash of the plan as `run` executed it; `accept_failures` is left out so acknowledging never trips it."""
    kept = {k: v for k, v in plan.items() if k != "accept_failures"}
    return hashlib.sha256(json.dumps(kept, sort_keys=True, default=str).encode()).hexdigest()


def plan_modified(m: dict, plan: dict) -> Problem | None:
    return None if m.get("plan_sha256") == plan_sha256(plan) else Problem(*MODIFIED)


def _review(problems: list[Problem], plan: dict) -> dict:
    accept = {key: reason for key, reason in (plan.get("accept_failures") or {}).items()
              if key not in UNACCEPTABLE}
    items = {p.item for p in problems}
    open_ = [asdict(p) for p in problems if p.item not in accept]
    accepted = [{**asdict(p), "accepted_reason": accept[p.item]} for p in problems if p.item in accept]
    return {"status": "failed" if open_ else "ok", "problems": open_, "accepted": accepted,
            "unused": [key for key in accept if key not in items]}


def review_manifest(m: dict, plan: dict) -> dict:
    """Split problems into open and accepted; list acceptance keys that match nothing. Writes nothing."""
    return _review(manifest_problems(m) + unfetched_links(m, plan), plan)


def review_folder(m: dict, plan: dict) -> dict:
    """`review_manifest` for a folder checked after the fact: also flags an unfinished run or an edited plan."""
    gate = [p for p in (run_incomplete(m), plan_modified(m, plan)) if p]
    return _review(gate + manifest_problems(m) + unfetched_links(m, plan), plan)


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
