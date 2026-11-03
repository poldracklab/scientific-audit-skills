# /// script
# requires-python = ">=3.11"
# dependencies = ["pymupdf"]
# ///
"""Extract, canonicalize and classify data/code/prereg links from papers."""
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

TRAILING = ".,;:)]}'\"/"
LINK_RE = re.compile(r"https?://[^\s<>\"]+|(?<![\w/])10\.\d{4,9}/[^\s<>\"]+", re.I)
DOI_RE = re.compile(r"(?:(?<![\w/])|(?<=doi\.org/))10\.\d{4,9}/[^\s<>\"]+")
OSF_DOI_RE = re.compile(r"^/10\.17605/osf\.io/(.+)$", re.I)

# (host suffix, class, role, needs_review)
HOST_RULES = [
    ("osf.io", "osf", "data", True),
    ("github.com", "github", "code", True),
    ("zenodo.org", "zenodo", "data", False),
    ("figshare.com", "figshare", "data", False),
    ("datadryad.org", "dryad", "data", False),
    ("openneuro.org", "openneuro", "data", False),
    ("neurovault.org", "neurovault", "data", False),
    ("aspredicted.org", "aspredicted", "prereg", False),
    ("clinicaltrials.gov", "clinicaltrials", "prereg", False),
    ("crd.york.ac.uk", "prospero", "prereg", False),
    ("doi.org", "doi", "unknown", True),
]


@dataclass
class Link:
    url: str
    canonical: str
    cls: str
    role: str
    needs_review: bool
    found_in: list[dict] = field(default_factory=list)


def _strip(text: str) -> str:
    return text.rstrip(TRAILING)


def _bare_doi_to_url(raw: str) -> str:
    return "https://doi.org/" + raw if re.match(r"10\.\d{4,9}/", raw) else raw


def _canonical_parts(raw: str) -> tuple[str, str, str]:
    parts = urlsplit(_bare_doi_to_url(_strip(raw.strip())))
    path = _strip(parts.path)
    path = path.removesuffix(".git")
    return parts.netloc.lower(), path, parts.query


def _osf_url(osf_id: str) -> str:
    return "https://osf.io/" + _strip(osf_id).lower()


def _lower_first_segment(path: str) -> str:
    head, sep, rest = path.lstrip("/").partition("/")
    return "/" + head.lower() + sep + rest


def canonicalize(url: str) -> str:
    host, path, query = _canonical_parts(url)
    osf_doi = OSF_DOI_RE.match(path)
    if host == "doi.org" and osf_doi:
        return _osf_url(osf_doi.group(1))
    if host == "osf.io":
        path = _lower_first_segment(path)
    return f"https://{host}{path}" + (f"?{query}" if query else "")


def _osf_role(canonical: str) -> tuple[str, str, bool]:
    if "registrations" in canonical.split("/")[3:]:
        return "osf", "prereg", False
    return "osf", "data", True


def classify(canonical: str) -> tuple[str, str, bool]:
    host = urlsplit(canonical).netloc
    for suffix, cls, role, review in HOST_RULES:
        if host == suffix or host.endswith("." + suffix):
            return _osf_role(canonical) if cls == "osf" else (cls, role, review)
    return "other", "unknown", True


def find_doi(text: str) -> str | None:
    match = DOI_RE.search(text)
    return _strip(match.group(0)) if match else None


def make_link(raw: str, file: str, page: int) -> Link:
    canonical = canonicalize(raw)
    cls, role, review = classify(canonical)
    return Link(_strip(raw), canonical, cls, role, review, [{"file": file, "page": page}])


def merge_links(links: list[Link]) -> list[Link]:
    merged: dict[str, Link] = {}
    for link in links:
        seen = merged.setdefault(link.canonical, link)
        if seen is not link:
            seen.found_in.extend(f for f in link.found_in if f not in seen.found_in)
    return sorted(merged.values(), key=lambda l: l.canonical)


def _links_on_page(text: str, file: str, page: int) -> list[Link]:
    return [make_link(m.group(0), file, page) for m in LINK_RE.finditer(text)]


def extract_links_from_text(text: str, file: str) -> list[Link]:
    links = []
    for page, page_text in enumerate(text.split("\f"), start=1):
        links.extend(_links_on_page(page_text, file, page))
    return merge_links(links)


def _is_web_uri(uri: str) -> bool:
    return bool(re.match(r"(https?://|10\.\d{4,9}/)", uri, re.I))


def _annotation_links(page, file: str, number: int) -> list[Link]:
    uris = (item.get("uri") for item in page.get_links())
    return [make_link(uri, file, number) for uri in uris if uri and _is_web_uri(uri)]


def extract_links_from_pdf(pdf: Path) -> list[Link]:
    import pymupdf

    links = []
    with pymupdf.open(pdf) as doc:
        for number, page in enumerate(doc, start=1):
            links.extend(_links_on_page(page.get_text(), pdf.name, number))
            links.extend(_annotation_links(page, pdf.name, number))
    return merge_links(links)
