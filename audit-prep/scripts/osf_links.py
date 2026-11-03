# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Annotate scanned OSF links: resolve each guid to project, registration or file at scan time."""
from fetch_osf import osf_id, resolve_guid

OSF_REVIEW = {
    "nodes": lambda i: ("data", f'osf project "{i["title"]}"'),
    "registrations": lambda i: ("prereg", f'osf registration "{i["title"]}"'),
    "files": lambda i: ("data", f"osf file {i['name']} in project {i['node_id']}"),
}


def _resolved(link: dict, get_json) -> dict | None:
    guid = osf_id(link["canonical"]) if link["class"] == "osf" else None
    try:
        return resolve_guid(guid, get_json) if guid else None
    except Exception:  # an unresolvable guid keeps the scanner's guess
        return None


def _found_in_union(children: list[dict]) -> list[dict]:
    found = []
    for child in children:
        found += [f for f in child["found_in"] if f not in found]
    return found


def _parent_link(node_id: str, children: list[dict]) -> dict:
    url, ids = f"https://osf.io/{node_id}", ", ".join(osf_id(c["canonical"]) for c in children)
    return {"url": url, "canonical": url, "class": "osf", "role": "data", "needs_review": True,
            "found_in": _found_in_union(children),
            "reason": f"parent project of osf file links {ids}; fetch the whole project?"}


def annotate_osf_links(plan_links: list[dict], get_json) -> list[dict]:
    """Resolve osf guids to project, registration or file; add each file's parent project for review."""
    out, children = [], {}
    for link in plan_links:
        info = _resolved(link, get_json)
        if info and info["type"] in OSF_REVIEW:
            role, reason = OSF_REVIEW[info["type"]](info)
            link = {**link, "role": role, "needs_review": False, "reason": reason}
            if info["type"] == "files":
                children.setdefault(info["node_id"], []).append(link)
        out.append(link)
    known = {link["canonical"] for link in out}
    return out + [_parent_link(n, c) for n, c in children.items() if f"https://osf.io/{n}" not in known]
