# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Fetch every reviewed link by role and class, and record per-link fetch status."""
import dataclasses
import json
import re
from pathlib import Path

import fetch_common
import fetch_github
import fetch_neurovault
import fetch_osf
import fetch_zenodo
import links
import prereg

LINK_STATUS = {"failed": "failed", "unsupported": "skipped", "skipped": "skipped"}


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", text).strip(".") or "repo"



def _repo_dir(canonical: str) -> str:
    parts = fetch_github.parse_github_url(canonical) or (canonical.rstrip("/").rsplit("/", 1)[-1],)
    return "github/" + "__".join(_slug(p) for p in parts)



def _clone(prepared: Path, link: dict, clients) -> dict:
    rel = _repo_dir(link["canonical"])
    rec = fetch_github.clone_repo(link["url"], prepared / rel, run=clients.run)
    return {**rec, "path": None if rec["status"] == "failed" else rel}



def _data_fetchers(policy, clients) -> dict:
    gj, gb = clients.get_json, clients.get_bytes
    return {
        "osf": (fetch_osf.osf_id, lambda i, d: fetch_osf.fetch_osf_files(i, d, policy, gj, gb)),
        "zenodo": (fetch_zenodo.zenodo_id, lambda i, d: fetch_zenodo.fetch_zenodo(i, d, policy, gj, gb)),
        "neurovault": (fetch_neurovault.neurovault_id, lambda i, d: fetch_neurovault.fetch_neurovault(i, d, gj, gb)),
    }



def _failure(link: dict, status: str, reason: str) -> dict:
    return {"source": link.get("class"), "id": link["canonical"], "url": link["url"], "path": None,
            "status": status, "files": [], "reason": reason}



def _fetch_data(prepared: Path, link: dict, clients, policy) -> dict:
    cls = link.get("class")
    fetchers = _data_fetchers(policy, clients)
    if cls not in fetchers:
        rec = _failure(link, "unsupported", f"no fetcher for {cls}; fetch manually if needed")
        return {k: rec[k] for k in ("source", "id", "path", "status", "files", "reason")}
    id_of, fetch = fetchers[cls]
    ident = id_of(link["canonical"])
    if not ident:
        return _failure(link, "failed", f"no {cls} id in {link['canonical']}")
    rel = f"data/{cls}_{ident}"
    rec = dataclasses.asdict(fetch(ident, prepared / rel))
    return {**rec, "path": None if rec["status"] == "failed" else rel}



def _dispatch(prepared: Path, link: dict, clients, policy) -> tuple[str, dict]:
    role, cls = link.get("role"), link.get("class")
    if role == "prereg":
        return "preregistration", prereg.fetch_prereg(link, prepared, clients.get_json, clients.get_bytes)
    if cls == "github" and role in ("code", "data"):
        return "code", _clone(prepared, link, clients)
    if role == "code":
        return "code", _failure(link, "skipped", f"no fetcher for {cls}; fetch manually if needed")
    return "data", _fetch_data(prepared, link, clients, policy)



def _manifest_key(role: str, cls: str) -> str:
    return {"prereg": "preregistration", "code": "code"}.get(role, "code" if cls == "github" else "data")



def _fetch_link(prepared: Path, link: dict, m: dict, clients, policy) -> dict:
    if link.get("role") not in ("prereg", "code", "data"):
        return {**link, "status": "skipped", "fetched_to": None}
    try:
        key, rec = _dispatch(prepared, link, clients, policy)
    except Exception as e:  # a single failed fetch never stops the run
        key, rec = _manifest_key(link["role"], link.get("class")), _failure(link, "failed", str(e))
    if rec["status"] == "failed":
        m["warnings"].append(f"{link['canonical']}: fetch failed: {rec.get('reason')}")
    m[key].append(rec)
    return {**link, "status": LINK_STATUS.get(rec["status"], "ok"), "fetched_to": rec.get("path")}



def _relation_links(meta: dict | None) -> list[dict]:
    return [{"url": r["doi"], "canonical": links.canonicalize(r["doi"]), "class": "doi", "role": "unknown",
             "needs_review": False, "found_in": [], "reason": f"crossref relation {r['type']}",
             "status": "skipped", "fetched_to": None} for r in (meta or {}).get("relations", [])]



def fetch_all(prepared: Path, plan: dict, manifest: dict, clients) -> None:
    manifest.update(preregistration=[], code=[], data=[])
    policy = fetch_common.SizePolicy.from_plan(plan.get("size_policy") or {})
    fetched = [_fetch_link(prepared, link, manifest, clients, policy) for link in plan.get("links", [])]
    manifest["links"] = fetched + _relation_links(manifest.get("metadata"))
    out = prepared / "paper" / "links.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest["links"], indent=2, ensure_ascii=False))
