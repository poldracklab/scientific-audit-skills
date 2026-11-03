# audit-prep Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `audit-prep` skill (scripts + SKILL.md) that turns a raw paper folder into a read-only prepared folder with a manifest, creates blinded per-model run clones, and verifies them; then rewire both audit skills to use it.

**Architecture:** Small single-purpose Python scripts in `audit-prep/scripts/` that import each other as sibling modules. Every network fetcher takes injectable `get_json` / `get_bytes` callables so tests never touch the network. Heavy document conversion (docling) runs as a subprocess via `uvx`, so it is an optional, recorded step. The model's judgment is confined to editing `prep.yaml` between `scan` and `run`.

**Tech Stack:** Python 3.12 via uv (PEP 723 inline deps per script + root `pyproject.toml` dev group), pymupdf, pyyaml, openpyxl, poppler (`pdftotext`, `pdftoppm`), pandoc, git, zstd, docling via `uvx`, pytest.

**Spec:** `docs/superpowers/specs/2026-11-02-audit-prep-design.md`

## Global Constraints

- Python managed and run with uv only: `uv run pytest`, `uv run <script>.py`. Never bare `python3` (the shim on this machine is broken).
- TDD with the RED phase proven: write test, run it and see it fail, **commit the test**, implement, run it and see it pass, commit. Tests are functions, not classes; persistent objects are fixtures. Never alter a test to make it pass.
- No code or imports in any `__init__.py`. `audit-prep/scripts/` is not a package; tests import via `tests/conftest.py` path injection.
- Short, modular functions. One responsibility per file.
- Every script starts with a PEP 723 block (`# /// script` ... `# ///`) listing only the third-party packages that script imports directly.
- No network in tests. Fetchers take `get_json: Callable[[str], dict]`, `get_bytes: Callable[[str], bytes]`, or `post_json` and tests pass recorded fixtures.
- Nothing inside a run folder may contain the model name. Model identity appears only in `registry.jsonl`.
- Prep never deletes user material. Unclassified files move to `unsorted/<Paper_Year>/`.
- Size policy defaults: `max_file_mb=500`, `max_source_mb=5000`, skip extensions `mp4 mov avi wav mp3 m4a`.
- Corpus scripts refuse to write without a `.autoaudit-root` marker.
- Commit messages: conventional prefix (`test:`, `feat:`, `docs:`, `refactor:`), ending with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Work on a branch `audit-prep` (create via superpowers:using-git-worktrees at execution start); never commit to `main` directly.
- In zsh snippets inside any SKILL.md, never use `path` as a loop variable.

## Review Focus

1. A paper PDF with no DOI in its first two pages (e.g. `Jaffe_2025.pdf`): scan must still produce a plan, with the paper candidate marked `needs_review`, not crash. → test in Task 6.
2. A prereg DOI of the form `10.17605/OSF.IO/X4C56` and a URL split or ending with a period in pdftotext output: canonicalization must yield `https://osf.io/x4c56` and strip the trailing period. → tests in Task 2.
3. Rerunning `prep.py run` after a previous run already moved the raw folder into `prepared/` must resume, not fail or re-process. → test in Task 12.
4. `new_run.py` on a filesystem without clonefile (or Linux) must fall back to rsync, and a failing `xattr` must not fail the run. → tests in Task 13.
5. `verify_run.py` must report `run_ok` when `audit/` contains arbitrary files and `run.json` exists, `run_dirty` for any other extra file, `run_modified` if a manifest file is missing or changed. → tests in Task 14.

## Trim amendment (2026-11-02, approved by the user after Task 8)

The user judged the fetcher breadth and task count excessive. Changes, which override the task text below where they conflict:

- **Task 9** becomes "Zenodo and NeuroVault fetchers": create only `fetch_zenodo.py` and `fetch_neurovault.py` (interfaces as written in Tasks 9 and 10). Figshare, Dryad and OpenNeuro fetchers are **dropped**. `fetch_all` (Task 12) records any `data`-role link whose class has no fetcher (`figshare`, `dryad`, `openneuro`, `doi`, `other`) in `manifest["data"]` with `status: "unsupported"`, the URL, and `reason: "no fetcher for <class>; fetch manually if needed"`, so the auditor still sees it.
- **Task 10** is merged into Task 9 (NeuroVault only; the OpenNeuro GraphQL walker is dropped).
- **Tasks 13 and 14** are executed as one task (`new_run.py` + `verify_run.py`), one implementer dispatch, one review.
- **Tasks 16 and 17** are executed as one batched dispatch (both audit-skill rewires), one review.
- Task numbering below is unchanged so the ledger and brief files stay valid.

---

## File structure

```
pyproject.toml                                  # root; dev deps; pytest config (markers: slow)
tests/conftest.py                               # sys.path += audit-prep/scripts; shared fixtures
tests/fixtures/                                 # recorded API JSON (osf, zenodo, crossref, ...)
tests/test_corpus.py ... one test file per script
audit-prep/
  SKILL.md
  references/prep-yaml.md                       # field reference + review guidance for the model
  references/manifest.md                        # manifest schema v1
  scripts/
    corpus.py        # root marker, init, Corpus paths, .claude/settings.json deny rule
    links.py         # URL/DOI extraction (text + PDF annotations), canonicalize, classify
    docs.py          # pdftotext, pdftoppm, docling (uvx), pandoc, xlsx->csv, tool versions
    statements.py    # verbatim availability/prereg/funding statements with pages
    crossref.py      # metadata + relations
    scan.py          # file classification, prep.yaml draft, unresolved()
    fetch_common.py  # RemoteFile, SizePolicy, select_downloads, download, FetchResult, default getters
    fetch_github.py
    fetch_osf.py     # moved from reproducibility-audit/scripts/osf_fetch.py and adapted
    prereg.py        # aspredicted / clinicaltrials / prospero + dispatcher incl. OSF registrations
    fetch_zenodo.py
    fetch_neurovault.py        # figshare/dryad/openneuro dropped by the trim amendment
    manifest.py      # skeleton, hash_tree, write/load, render_readme, is_prepared
    prepare.py       # orchestration: move, apply plan, archives, documents, fetch_all, finalize
    prep.py          # CLI: init | scan | run | finalize
    new_run.py       # CLI + functions
    verify_run.py    # CLI + verify()
reproducibility-audit/SKILL.md, templates/audit_template.qmd   # modified; scripts/ removed
neuroimaging-validity-audit/SKILL.md, templates/audit_template.qmd  # modified
```

---

### Task 1: Project scaffolding and corpus root

**Files:**
- Create: `pyproject.toml`, `tests/conftest.py`, `tests/test_corpus.py`, `audit-prep/scripts/corpus.py`

**Interfaces:**
- Produces: `ROOT_MARKER = ".autoaudit-root"`; `class CorpusError(Exception)`; `@dataclass(frozen=True) Corpus(root: Path)` with properties `prepared`, `runs`, `unsorted`, `registry` (= root/`prepared`, `runs`, `unsorted`, `registry.jsonl`) and methods `prepared_dir(paper_id) -> Path`, `runs_dir(paper_id) -> Path`, `unsorted_dir(paper_id) -> Path`; `init_root(root: Path) -> Corpus`; `find_root(start: Path, explicit: Path | None = None) -> Corpus`.

- [ ] **Step 1: Write `pyproject.toml`** with `[project]` name `my-skills`, `requires-python = ">=3.12"`, no package build (`[tool.uv] package = false`), `[dependency-groups] dev = ["pytest>=8", "pymupdf>=1.24", "pyyaml>=6", "openpyxl>=3.1", "python-docx>=1.1"]`, and `[tool.pytest.ini_options] testpaths = ["tests"]`, `markers = ["slow: needs external tools (docling, pandoc)"]`.

- [ ] **Step 2: Write `tests/conftest.py`** inserting `<repo>/audit-prep/scripts` at `sys.path[0]`, and a fixture `corpus_root(tmp_path)` that returns `tmp_path / "corpus"` (unmade).

- [ ] **Step 3: Write the failing tests** in `tests/test_corpus.py`:

```python
def test_init_root_creates_marker_dirs_registry_and_deny_rule(corpus_root):
    c = init_root(corpus_root)
    assert (corpus_root / ".autoaudit-root").is_file()
    assert c.prepared.is_dir() and c.runs.is_dir() and c.unsorted.is_dir()
    assert c.registry.is_file() and c.registry.read_text() == ""
    settings = json.loads((corpus_root / ".claude/settings.json").read_text())
    assert "Read(./registry.jsonl)" in settings["permissions"]["deny"]

def test_find_root_walks_up_from_nested_folder(corpus_root):
    init_root(corpus_root)
    nested = corpus_root / "Bissett_2021" / "sub"; nested.mkdir(parents=True)
    assert find_root(nested).root == corpus_root

def test_find_root_without_marker_raises(tmp_path):
    with pytest.raises(CorpusError, match="prep.py init"):
        find_root(tmp_path)

def test_explicit_root_without_marker_raises(tmp_path):
    with pytest.raises(CorpusError):
        find_root(tmp_path, explicit=tmp_path)

def test_paper_paths(corpus_root):
    c = init_root(corpus_root)
    assert c.prepared_dir("X_2020") == corpus_root / "prepared" / "X_2020"
    assert c.runs_dir("X_2020") == corpus_root / "runs" / "X_2020"
    assert c.unsorted_dir("X_2020") == corpus_root / "unsorted" / "X_2020"
```

- [ ] **Step 4: Run** `uv run pytest tests/test_corpus.py -v`. Expected: FAIL, `ModuleNotFoundError: corpus`.
- [ ] **Step 5: Commit** `pyproject.toml`, `tests/conftest.py`, `tests/test_corpus.py` — `test: corpus root marker and paths`.
- [ ] **Step 6: Implement `corpus.py`** per Interfaces. `init_root` is idempotent (existing files untouched). The error message for a missing marker must contain `prep.py init`. The settings file content is `{"permissions": {"deny": ["Read(./registry.jsonl)"]}}`; merge into an existing file rather than overwrite.
- [ ] **Step 7: Run** `uv run pytest tests/test_corpus.py -v`. Expected: PASS.
- [ ] **Step 8: Commit** — `feat: corpus root marker, layout and registry deny rule`.

---

### Task 2: Link extraction and classification

**Files:**
- Create: `audit-prep/scripts/links.py`, `tests/test_links.py`
- Modify: `tests/conftest.py` (add `fixture_pdf` fixture)

**Interfaces:**
- Produces: `@dataclass Link(url: str, canonical: str, cls: str, role: str, needs_review: bool, found_in: list[dict])` where `found_in` items are `{"file": str, "page": int}`; `canonicalize(url: str) -> str`; `classify(canonical: str) -> tuple[str, str, bool]` returning `(cls, role, needs_review)`; `find_doi(text: str) -> str | None`; `extract_links_from_text(text: str, file: str) -> list[Link]` (pages delimited by `\f`, 1-based); `extract_links_from_pdf(pdf: Path) -> list[Link]` (page text + link annotations via pymupdf); `merge_links(links: list[Link]) -> list[Link]` deduped on `canonical`, `found_in` unioned, sorted by canonical.
- Classes: `osf github zenodo figshare dryad openneuro neurovault aspredicted clinicaltrials prospero doi other`. Roles: `prereg code data unknown`.

- [ ] **Step 1: Add fixture `fixture_pdf(tmp_path_factory)`** to conftest: a two-page PDF built with pymupdf. Page 1 text: `"Example Paper Title\ndoi: 10.1126/sciadv.abf4355\nData are at https://osf.io/abcde/.\nPreregistered: 10.17605/OSF.IO/X4C56"` plus a link annotation (`page.insert_link({"kind": fitz.LINK_URI, "from": rect, "uri": "https://github.com/lab/repo"})`) over the words `"our code"`. Page 2 text: `"Data availability\nAll data are available at https://zenodo.org/records/123456\nCode availability\nSee https://github.com/lab/repo\nFunding\nNIH R01."`.

- [ ] **Step 2: Write failing tests** in `tests/test_links.py`:

```python
@pytest.mark.parametrize("raw,expected", [
    ("https://osf.io/abcde/.", "https://osf.io/abcde"),
    ("10.17605/OSF.IO/X4C56", "https://osf.io/x4c56"),
    ("http://osf.io/ABCDE", "https://osf.io/abcde"),
    ("https://doi.org/10.1126/sciadv.abf4355", "https://doi.org/10.1126/sciadv.abf4355"),
    ("https://github.com/lab/repo.git", "https://github.com/lab/repo"),
    ("https://osf.io/x4c56/registrations/", "https://osf.io/x4c56/registrations"),
])
def test_canonicalize(raw, expected): assert canonicalize(raw) == expected

@pytest.mark.parametrize("url,cls,role,review", [
    ("https://osf.io/abcde", "osf", "data", True),
    ("https://osf.io/x4c56/registrations", "osf", "prereg", False),
    ("https://github.com/lab/repo", "github", "code", True),
    ("https://zenodo.org/records/123456", "zenodo", "data", False),
    ("https://openneuro.org/datasets/ds000001/versions/1.0.0", "openneuro", "data", False),
    ("https://neurovault.org/collections/1234", "neurovault", "data", False),
    ("https://aspredicted.org/abc12.pdf", "aspredicted", "prereg", False),
    ("https://clinicaltrials.gov/study/NCT01234567", "clinicaltrials", "prereg", False),
    ("https://doi.org/10.1126/sciadv.abf4355", "doi", "unknown", True),
    ("https://example.org/x", "other", "unknown", True),
])
def test_classify(url, cls, role, review): assert classify(url) == (cls, role, review)

def test_find_doi(): assert find_doi("see doi:10.1126/sciadv.abf4355. Next") == "10.1126/sciadv.abf4355"

def test_extract_from_text_records_pages():
    links = extract_links_from_text("a https://osf.io/abcde/.\fb https://zenodo.org/records/1", "paper.txt")
    assert [(l.canonical, l.found_in[0]["page"]) for l in links] == [
        ("https://osf.io/abcde", 1), ("https://zenodo.org/records/1", 2)]

def test_extract_from_pdf_includes_hidden_annotation(fixture_pdf):
    canon = {l.canonical for l in extract_links_from_pdf(fixture_pdf)}
    assert "https://github.com/lab/repo" in canon
    assert "https://osf.io/x4c56" in canon

def test_merge_unions_found_in():
    a = Link("u", "https://osf.io/abcde", "osf", "data", True, [{"file": "p", "page": 1}])
    b = Link("u", "https://osf.io/abcde", "osf", "data", True, [{"file": "s", "page": 2}])
    merged = merge_links([a, b])
    assert len(merged) == 1 and len(merged[0].found_in) == 2
```

- [ ] **Step 3: Run** `uv run pytest tests/test_links.py -v`. Expected: FAIL, `ModuleNotFoundError: links`.
- [ ] **Step 4: Commit** — `test: link extraction, canonicalization and host classification`.
- [ ] **Step 5: Implement `links.py`.** `canonicalize`: lowercase scheme/host, force https, strip trailing `.,;)` and `/`, drop `.git`, map `doi.org/10.17605/osf.io/<id>` and bare `10.17605/OSF.IO/<id>` to `https://osf.io/<id>`, lowercase OSF ids. Bare DOIs (`10\.\d{4,9}/\S+`) become `https://doi.org/<doi>`. GitHub links are `needs_review=True` (could be a cited tool); OSF non-registration links `needs_review=True` (project vs prereg). Use `fitz` (pymupdf) for page text and `page.get_links()` for annotations.
- [ ] **Step 6: Run** tests. Expected: PASS.
- [ ] **Step 7: Commit** — `feat: extract and classify links from text and PDF annotations`.

---

### Task 3: Document conversions

**Files:**
- Create: `audit-prep/scripts/docs.py`, `tests/test_docs.py`
- Modify: `tests/conftest.py` (fixtures `fixture_docx`, `fixture_xlsx`)

**Interfaces:**
- Produces: `pdf_to_text(pdf: Path, out: Path) -> Path` (`pdftotext -layout`); `pdf_to_pages(pdf: Path, out_dir: Path, dpi: int = 110) -> list[Path]` named `p-001.png`…; `pdf_to_structured(pdf: Path, out_dir: Path, run=subprocess.run) -> dict` with keys `status` (`ok|failed|skipped`), `reason`, `markdown`, `figures`, `tables` (counts), writing `<out_dir>/<stem>.md`, `<out_dir>/figures/fig-NN.png`, `figures/figures.md`, `tables/table-NN.csv`, `tables/tables.md`; `docx_to_md(docx: Path, out: Path, media_dir: Path) -> Path`; `xlsx_to_csv(xlsx: Path, out_dir: Path) -> list[Path]`; `tool_versions() -> dict[str, str | None]` for `pdftotext pdftoppm pandoc zstd docling git`.

- [ ] **Step 1: Add fixtures**: `fixture_docx` (python-docx, one heading "Supplementary Methods" + a paragraph), `fixture_xlsx` (openpyxl, two sheets `Table S1`, `Table S2`, 2×2 values).

- [ ] **Step 2: Write failing tests**:

```python
def test_pdf_to_text_layout_has_form_feeds(fixture_pdf, tmp_path):
    out = pdf_to_text(fixture_pdf, tmp_path / "paper.txt")
    assert out.read_text().count("\f") >= 1 and "Example Paper Title" in out.read_text()

def test_pdf_to_pages_names_and_count(fixture_pdf, tmp_path):
    pages = pdf_to_pages(fixture_pdf, tmp_path / "pages")
    assert [p.name for p in pages] == ["p-001.png", "p-002.png"]

def test_xlsx_to_csv_one_file_per_sheet(fixture_xlsx, tmp_path):
    files = xlsx_to_csv(fixture_xlsx, tmp_path / "s")
    assert sorted(f.name for f in files) == ["Table_S1.csv", "Table_S2.csv"]

def test_docx_to_md(fixture_docx, tmp_path):
    out = docx_to_md(fixture_docx, tmp_path / "s.md", tmp_path / "s_media")
    assert "Supplementary Methods" in out.read_text()

def test_structured_records_failure_when_docling_unavailable(fixture_pdf, tmp_path):
    def failing_run(*a, **k): raise FileNotFoundError("uvx")
    r = pdf_to_structured(fixture_pdf, tmp_path / "out", run=failing_run)
    assert r["status"] == "failed" and "uvx" in r["reason"]

@pytest.mark.slow
def test_structured_smoke(fixture_pdf, tmp_path):
    if not shutil.which("uvx"): pytest.skip("uvx missing")
    r = pdf_to_structured(fixture_pdf, tmp_path / "out")
    assert r["status"] == "ok" and (tmp_path / "out" / "figures" / "figures.md").is_file()

def test_tool_versions_keys():
    assert set(tool_versions()) == {"pdftotext", "pdftoppm", "pandoc", "zstd", "docling", "git"}
```

- [ ] **Step 3: Run** `uv run pytest tests/test_docs.py -v -m "not slow"`. Expected: FAIL (module missing).
- [ ] **Step 4: Commit** — `test: document conversion helpers`.
- [ ] **Step 5: Implement `docs.py`.** Docling runs as `uvx --from docling docling --to md --to json --image-export-mode referenced --output <tmp> <pdf>`; then `_index_docling(json_path, out_dir)` reads the docling JSON: each `pictures[i]` → copy its referenced image to `figures/fig-NN.png` and append `| file | page | caption |` to `figures.md`; each `tables[i]` → write `data.grid` cell text as CSV `tables/table-NN.csv` and a row to `tables.md`; page from `prov[0].page_no`. Any exception → `status: failed` with the exception text. Sheet names sanitized to `[A-Za-z0-9_-]`.
- [ ] **Step 6: Run** non-slow tests → PASS; then `uv run pytest tests/test_docs.py -v -m slow` once to confirm the smoke test passes or skips cleanly.
- [ ] **Step 7: Commit** — `feat: pdf, docx, xlsx conversions and docling structured export`.

---

### Task 4: Verbatim statements

**Files:**
- Create: `audit-prep/scripts/statements.py`, `tests/test_statements.py`

**Interfaces:**
- Produces: `@dataclass Statement(kind: str, heading: str, text: str, page: int)` with kinds `data_availability code_availability preregistration funding open_practices`; `extract_statements(text: str) -> list[Statement]`; `write_statements_md(statements: list[Statement], out: Path) -> Path`.

- [ ] **Step 1: Write failing tests**:

```python
TEXT = "Intro\fData availability\nAll data are available at https://zenodo.org/records/1.\n\nCode availability\nSee GitHub.\n\nFunding\nNIH.\n"
def test_extract_kinds_and_pages():
    s = extract_statements(TEXT)
    assert [(x.kind, x.page) for x in s] == [("data_availability", 2), ("code_availability", 2), ("funding", 2)]
    assert s[0].text.startswith("All data are available")
def test_preregistration_variants():
    assert extract_statements("Pre-registration\nThe study was preregistered.")[0].kind == "preregistration"
def test_write_md_has_page_markers(tmp_path):
    out = write_statements_md(extract_statements(TEXT), tmp_path / "statements.md")
    assert "## Data availability (p. 2)" in out.read_text()
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Commit** — `test: verbatim statement extraction`.
- [ ] **Step 4: Implement.** Heading regex is case-insensitive, line-anchored, matching `data (and code )?availability`, `code availability`, `pre-?registration`, `funding`, `open practices( statement)?`; statement text runs to the next blank line or next heading, max 2000 chars. Page = 1 + count of `\f` before the match.
- [ ] **Step 5: Run** → PASS. **Step 6: Commit** — `feat: extract availability and prereg statements with page numbers`.

---

### Task 5: Crossref metadata

**Files:**
- Create: `audit-prep/scripts/crossref.py`, `tests/test_crossref.py`, `tests/fixtures/crossref_work.json`

**Interfaces:**
- Produces: `fetch_metadata(doi: str, get_json: Callable[[str], dict]) -> dict` with keys `doi title authors journal published type relations url`; `authors` is `[{"family","given"}]`; `published` is `YYYY-MM-DD` (pad missing parts with `01`); `relations` is `[{"type": str, "doi": str}]` from the Crossref `relation` map (e.g. `is-preprint-of`, `has-preprint`, `is-corrected-by`, `has-update`); `default_get_json(url: str) -> dict` (urllib, User-Agent `audit-prep/1.0`).

- [ ] **Step 1: Save fixture** `tests/fixtures/crossref_work.json`: a minimal Crossref `/works/<doi>` response with `message.title`, `author`, `container-title`, `issued.date-parts [[2021,5,12]]`, `type: journal-article`, `relation: {"has-preprint": [{"id": "10.1101/2020.01.01.123456", "id-type": "doi"}]}`.
- [ ] **Step 2: Write failing tests**:

```python
def test_fetch_metadata_parses_fixture(crossref_fixture):
    m = fetch_metadata("10.1126/sciadv.abf4355", lambda url: crossref_fixture)
    assert m["published"] == "2021-05-12" and m["type"] == "journal-article"
    assert m["authors"][0]["family"] and m["journal"]
    assert m["relations"] == [{"type": "has-preprint", "doi": "10.1101/2020.01.01.123456"}]
def test_fetch_metadata_requests_works_endpoint():
    seen = []
    fetch_metadata("10.1/x", lambda url: (seen.append(url), {"message": {}})[1])
    assert seen == ["https://api.crossref.org/works/10.1/x"]
```

- [ ] **Step 3: Run** → FAIL. **Step 4: Commit** — `test: crossref metadata parsing`.
- [ ] **Step 5: Implement.** **Step 6: Run** → PASS. **Step 7: Commit** — `feat: crossref metadata with relations`.

---

### Task 6: Scan: file classification and `prep.yaml` draft

**Files:**
- Create: `audit-prep/scripts/scan.py`, `audit-prep/references/prep-yaml.md`, `tests/test_scan.py`
- Modify: `tests/conftest.py` (fixture `raw_folder` factory)

**Interfaces:**
- Consumes: `links.extract_links_from_pdf/merge_links/find_doi`, `crossref.fetch_metadata`, `docs.pdf_to_text`, `statements.*`.
- Produces: `RESIDUE_NAMES = {".git", ".venv", ".pytest_cache", "__pycache__", ".DS_Store"}`; `SUPPLEMENT_MARKERS = ("supp", "_sm", "som", "mmc", "esm", "moesm", "supplement")`; `classify_files(raw: Path) -> list[dict]` each `{"path": rel, "role": paper|supplement|data|archive|unsorted, "needs_review": bool, "reason": str, "order": int|None}`; `build_plan(raw: Path, get_json) -> dict` (the prep.yaml structure below); `write_plan(plan: dict, path: Path) -> Path`; `load_plan(path: Path) -> dict`; `unresolved(plan: dict) -> list[str]` human-readable reasons the plan cannot run (any `needs_review`, missing `reviewed_by`, no file with role `paper`).
- prep.yaml structure (document it in `references/prep-yaml.md`):

```yaml
schema_version: 1
paper_id: Bissett_2021
reviewed_by: null                  # model name or "human"; required before run
doi: 10.1126/sciadv.abf4355        # null -> needs_review
data_collection: {start: null, end: null, source_quote: null, page: null}
size_policy: {max_file_mb: 500, max_source_mb: 5000, skip_ext: [mp4, mov, avi, wav, mp3, m4a]}
files:
  - {path: sciadv.abf4355.pdf, role: paper, needs_review: false, reason: "DOI resolves to journal-article"}
  - {path: abf4355_sm.pdf, role: supplement, order: 1, needs_review: false, reason: "name marker _sm"}
  - {path: .venv, role: unsorted, needs_review: false, reason: "residue"}
links:
  - {url: ..., canonical: ..., class: osf, role: data, needs_review: true, found_in: [{file: ..., page: 3}], reason: "osf project or registration?"}
```

- [ ] **Step 1: Add conftest factory fixture `raw_folder(tmp_path, fixture_pdf, fixture_docx)`** returning `make(shape: str) -> Path` for shapes `"paper_supp"` (pdf + `_sm.pdf` copy of fixture), `"paper_data_archive"` (pdf + `mydata/` dir with a csv + `mydata.tar.gz` of it), `"paper_residue"` (pdf + `.venv/` + `.git/` + `paper.txt`), `"paper_nodoi"` (a one-page PDF without a DOI).

- [ ] **Step 2: Write failing tests**:

```python
def test_classify_paper_and_supplement(raw_folder):
    roles = {f["path"]: f["role"] for f in classify_files(raw_folder("paper_supp"))}
    assert roles == {"paper.pdf": "paper", "paper_sm.pdf": "supplement"}
def test_classify_data_dir_archive_and_residue(raw_folder):
    roles = {f["path"]: f["role"] for f in classify_files(raw_folder("paper_data_archive"))}
    assert roles["mydata"] == "data" and roles["mydata.tar.gz"] == "archive"
    roles = {f["path"]: f["role"] for f in classify_files(raw_folder("paper_residue"))}
    assert roles[".venv"] == "unsorted" and roles[".git"] == "unsorted" and roles["paper.txt"] == "unsorted"
def test_build_plan_nodoi_marks_paper_needs_review(raw_folder):
    plan = build_plan(raw_folder("paper_nodoi"), get_json=lambda u: {"message": {}})
    paper = [f for f in plan["files"] if f["role"] == "paper"][0]
    assert paper["needs_review"] and plan["doi"] is None
def test_build_plan_links_and_defaults(raw_folder, crossref_fixture):
    plan = build_plan(raw_folder("paper_supp"), get_json=lambda u: crossref_fixture)
    assert plan["doi"] == "10.1126/sciadv.abf4355" and plan["reviewed_by"] is None
    assert plan["size_policy"]["max_file_mb"] == 500
    canon = {l["canonical"]: l for l in plan["links"]}
    assert canon["https://osf.io/abcde"]["needs_review"] is True
    assert canon["https://github.com/lab/repo"]["role"] == "code"
def test_unresolved_lists_blockers(raw_folder, crossref_fixture):
    plan = build_plan(raw_folder("paper_supp"), get_json=lambda u: crossref_fixture)
    msgs = unresolved(plan)
    assert any("reviewed_by" in m for m in msgs) and any("needs_review" in m for m in msgs)
    for l in plan["links"]: l["needs_review"] = False
    plan["reviewed_by"] = "human"
    assert unresolved(plan) == []
def test_write_and_load_roundtrip(tmp_path):
    p = {"schema_version": 1, "files": [], "links": []}
    assert load_plan(write_plan(p, tmp_path / "prep.yaml")) == p
```

- [ ] **Step 3: Run** → FAIL. **Step 4: Commit** — `test: scan classification and prep.yaml draft`.
- [ ] **Step 5: Implement `scan.py`.** Paper pick: among PDFs, those whose first two pages contain a DOI (`links.find_doi` on pymupdf text) and whose Crossref `type` is `journal-article`; longest page count wins; others with supplement markers or the same DOI are supplements (ordered by filename); a PDF without DOI when no paper is found becomes `paper` with `needs_review=True`. A `.txt` next to a same-stem PDF is residue. Directories not in residue are `data`; archive extensions `.zip .tar .tar.gz .tgz .tar.zst .zst .7z` are `archive`. Links come from all PDFs via `extract_links_from_pdf`, merged; `scan` also writes `<raw>/statements.md`? No: scan writes `prep.yaml` only and prints the draft plus the statements to stdout for the reviewer (statements are produced in `run`). Document review guidance in `references/prep-yaml.md`: what each `needs_review` means and how to settle it; never delete lines; use `role: skip` with a reason.
- [ ] **Step 6: Run** → PASS. **Step 7: Commit** — `feat: scan raw folder into prep.yaml draft`.

---

### Task 7: Fetch common + GitHub

**Files:**
- Create: `audit-prep/scripts/fetch_common.py`, `audit-prep/scripts/fetch_github.py`, `tests/test_fetch_common.py`, `tests/test_fetch_github.py`
- Modify: `tests/conftest.py` (fixture `bare_repo`)

**Interfaces:**
- Produces (`fetch_common`): `@dataclass RemoteFile(path: str, size: int, url: str, remote_hash: str | None = None)`; `@dataclass SizePolicy(max_file_mb: int = 500, max_source_mb: int = 5000, skip_ext: frozenset = frozenset({"mp4","mov","avi","wav","mp3","m4a"}))` with `from_plan(d: dict) -> SizePolicy` and `allows(f: RemoteFile) -> bool`; `select_downloads(files: list[RemoteFile], policy: SizePolicy, must_have: tuple[str, ...] = ()) -> tuple[list[RemoteFile], str]` where status is `ok` (all allowed files selected), `partial` (total over `max_source_mb`, only `must_have` substrings selected and non-empty), `listed_only` (nothing selected); `download(url: str, dest: Path, get_bytes) -> Path`; `sha256_file(p: Path) -> str`; `@dataclass FetchResult(source: str, id: str, path: str, status: str, files: list[dict], reason: str = "")` with `files` entries `{"path","size","remote_hash","downloaded","sha256"}`; `default_get_json(url) -> dict`, `default_get_bytes(url) -> bytes`, `default_post_json(url, payload) -> dict`.
- Produces (`fetch_github`): `parse_github_url(url: str) -> tuple[str, str] | None`; `clone_repo(url: str, dest: Path, run=subprocess.run) -> dict` keys `url path commit branch cloned_at status reason zenodo_doi`; `find_zenodo_doi(text: str) -> str | None` (`10.5281/zenodo.\d+`).

- [ ] **Step 1: Add fixture `bare_repo(tmp_path_factory)`**: `git init`, one commit with `README.md` containing `10.5281/zenodo.7654321`, then `git clone --bare` to `repo.git`; returns the bare path.
- [ ] **Step 2: Write failing tests**:

```python
def test_policy_skips_video_and_big_files():
    p = SizePolicy()
    assert not p.allows(RemoteFile("a.mp4", 10, "u")) and not p.allows(RemoteFile("a.nii", 600*10**6, "u"))
    assert p.allows(RemoteFile("a.csv", 10, "u"))
def test_select_all_when_under_cap():
    files = [RemoteFile("a.csv", 10, "u"), RemoteFile("b.mp4", 10, "u")]
    sel, status = select_downloads(files, SizePolicy())
    assert [f.path for f in sel] == ["a.csv"] and status == "ok"
def test_select_listed_only_when_source_too_big():
    files = [RemoteFile(f"s{i}.nii.gz", 400*10**6, "u") for i in range(20)]
    assert select_downloads(files, SizePolicy()) == ([], "listed_only")
def test_select_partial_with_must_have():
    files = [RemoteFile(f"sub-{i}/func.nii.gz", 400*10**6, "u") for i in range(20)] + [RemoteFile("derivatives/group_map.nii.gz", 1000, "u")]
    sel, status = select_downloads(files, SizePolicy(), must_have=("group_map",))
    assert [f.path for f in sel] == ["derivatives/group_map.nii.gz"] and status == "partial"
def test_download_writes_bytes(tmp_path):
    out = download("u", tmp_path / "d" / "f.bin", lambda u: b"xyz")
    assert out.read_bytes() == b"xyz" and sha256_file(out) == hashlib.sha256(b"xyz").hexdigest()
def test_from_plan(): assert SizePolicy.from_plan({"max_file_mb": 1, "max_source_mb": 2, "skip_ext": ["zip"]}).skip_ext == frozenset({"zip"})

# test_fetch_github.py
def test_parse_github_url():
    assert parse_github_url("https://github.com/lab/repo") == ("lab", "repo")
    assert parse_github_url("https://github.com/lab/repo/tree/main/x") == ("lab", "repo")
    assert parse_github_url("https://gitlab.com/x/y") is None
def test_clone_records_commit_and_zenodo(bare_repo, tmp_path):
    r = clone_repo(str(bare_repo), tmp_path / "github" / "lab__repo")
    assert r["status"] == "ok" and len(r["commit"]) == 40 and r["zenodo_doi"] == "10.5281/zenodo.7654321"
    assert (tmp_path / "github/lab__repo/.git").exists()
def test_clone_failure_recorded(tmp_path):
    r = clone_repo("/nonexistent/repo.git", tmp_path / "x")
    assert r["status"] == "failed" and r["reason"]
```

- [ ] **Step 3: Run** both files → FAIL. **Step 4: Commit** — `test: size policy, download helpers and github clone`.
- [ ] **Step 5: Implement.** `clone_repo` runs `git clone --recurse-submodules <url> <dest>`, then `git -C dest rev-parse HEAD` and `git -C dest rev-parse --abbrev-ref HEAD`; reads a README (`README*`, case-insensitive) for a Zenodo DOI. Idempotent: if `dest/.git` exists, record the existing commit with `status: "skipped"`, `reason: "exists"`.
- [ ] **Step 6: Run** → PASS. **Step 7: Commit** — `feat: fetch policy helpers and github cloning`.

---

### Task 8: OSF files and registrations; other prereg sources

**Files:**
- Move: `reproducibility-audit/scripts/osf_fetch.py` → `audit-prep/scripts/fetch_osf.py` (`git mv`, then rewrite)
- Create: `audit-prep/scripts/prereg.py`, `tests/test_fetch_osf.py`, `tests/test_prereg.py`, fixtures `tests/fixtures/osf_node.json`, `osf_files_page1.json`, `osf_files_page2.json`, `osf_registration.json`, `osf_registration_files.json`, `ctgov_study.json`
- Modify: `reproducibility-audit/SKILL.md` (remove the `osf_fetch.py` command lines only; the full rewrite is Task 16)

**Interfaces:**
- Produces (`fetch_osf`): `osf_id(canonical: str) -> str | None` (5-char id from `osf.io/<id>`); `list_osf_files(node_id: str, get_json) -> list[RemoteFile]` (recursive, follows `links.next`, `remote_hash` from `extra.hashes.sha256`); `fetch_osf_files(node_id: str, dest: Path, policy: SizePolicy, get_json, get_bytes) -> FetchResult` (source `osf`); `fetch_osf_registration(reg_id: str, dest: Path, get_json, get_bytes) -> dict` keys `source="osf" id path title date_registered type withdrawn files status reason` where `files` items are `{"name","sha256_expected","sha256_actual","verified"}`; `node_registration_count(node_id, get_json) -> int`.
- Produces (`prereg`): `fetch_aspredicted(url: str, dest: Path, get_bytes) -> dict`; `fetch_clinicaltrials(nct: str, dest: Path, get_json) -> dict` (v2 `https://clinicaltrials.gov/api/v2/studies/<nct>`, `date_registered` from `protocolSection.statusModule.studyFirstSubmitDate`); `fetch_prospero(url: str, dest: Path, get_bytes) -> dict`; `fetch_prereg(link: dict, dest_root: Path, get_json, get_bytes) -> dict` dispatching on `link["class"]`, with OSF links routed to `fetch_osf_registration` when the id is a registration (`/v2/registrations/<id>/` returns 200) else recorded `status: failed, reason: "not a registration"`. All return dicts share keys `source id path date_registered status reason`.

- [ ] **Step 1: `git mv reproducibility-audit/scripts/osf_fetch.py audit-prep/scripts/fetch_osf.py`; commit** — `refactor: move OSF fetch script into audit-prep`.
- [ ] **Step 2: Record fixtures** from the shapes in the existing script's comments (two-page listing with `links.next`, one folder child; registration with `registered_meta` and a files listing whose `extra.hashes.sha256` matches the sha256 of the bytes the test's `get_bytes` returns).
- [ ] **Step 3: Write failing tests**:

```python
def test_osf_id(): assert osf_id("https://osf.io/abcde") == "abcde" and osf_id("https://osf.io/x4c56/registrations") == "x4c56"
def test_list_osf_files_follows_pagination_and_folders(osf_api):
    files = list_osf_files("abcde", osf_api)
    assert sorted(f.path for f in files) == ["data/trials.csv", "readme.txt", "video.mp4"]
def test_fetch_osf_files_applies_policy(osf_api, tmp_path):
    r = fetch_osf_files("abcde", tmp_path / "osf_abcde", SizePolicy(), osf_api, lambda u: b"content")
    assert r.status == "ok" and {f["path"]: f["downloaded"] for f in r.files}["video.mp4"] is False
    assert (tmp_path / "osf_abcde/data/trials.csv").read_bytes() == b"content"
def test_registration_hash_verified(osf_api, tmp_path):
    r = fetch_osf_registration("x4c56", tmp_path / "osf_x4c56", osf_api, lambda u: b"prereg-bytes")
    assert r["date_registered"].startswith("20") and r["files"][0]["verified"] is True and r["status"] == "ok"
def test_registration_hash_mismatch_flagged(osf_api, tmp_path):
    r = fetch_osf_registration("x4c56", tmp_path / "x", osf_api, lambda u: b"tampered")
    assert r["files"][0]["verified"] is False and r["status"] == "hash_mismatch"

# test_prereg.py
def test_clinicaltrials(ctgov_fixture, tmp_path):
    r = fetch_clinicaltrials("NCT01234567", tmp_path / "ct", lambda u: ctgov_fixture)
    assert r["date_registered"] == "2019-03-04" and (tmp_path / "ct/NCT01234567.json").is_file()
def test_aspredicted_saves_pdf(tmp_path):
    r = fetch_aspredicted("https://aspredicted.org/abc12.pdf", tmp_path / "ap", lambda u: b"%PDF-1.4")
    assert r["status"] == "ok" and (tmp_path / "ap/abc12.pdf").read_bytes().startswith(b"%PDF")
def test_aspredicted_failure_recorded(tmp_path):
    def boom(u): raise OSError("403")
    assert fetch_prereg({"class": "aspredicted", "canonical": "https://aspredicted.org/abc12.pdf"}, tmp_path, None, boom)["status"] == "failed"
def test_dispatch_osf_non_registration(osf_api, tmp_path):
    r = fetch_prereg({"class": "osf", "canonical": "https://osf.io/abcde"}, tmp_path, osf_api, lambda u: b"")
    assert r["status"] == "failed" and "not a registration" in r["reason"]
```

The `osf_api` fixture is a function mapping URL → fixture dict (`/nodes/abcde/` → node; `/files/osfstorage/` → page1 whose `links.next` → page2; folder child href → listing; `/registrations/x4c56/` → registration; `/registrations/abcde/` → raises `urllib.error.HTTPError` 404).

- [ ] **Step 4: Run** → FAIL. **Step 5: Commit** — `test: OSF files, registrations and other prereg sources`.
- [ ] **Step 6: Rewrite `fetch_osf.py`** around the Interfaces, keeping the walk/pagination logic; drop its old CLI. **Implement `prereg.py`.** Each result has `path` relative to `dest_root` of the form `preregistration/<source>_<id>`.
- [ ] **Step 7: Run** → PASS. **Step 8: Commit** — `feat: OSF data and registration fetch, AsPredicted, ClinicalTrials.gov, PROSPERO`.

---

### Task 9: Zenodo, figshare, Dryad

**Files:**
- Create: `audit-prep/scripts/fetch_zenodo.py`, `fetch_figshare.py`, `fetch_dryad.py`, tests `tests/test_fetch_repos.py`, fixtures `zenodo_record.json`, `figshare_article.json`, `dryad_dataset.json`, `dryad_files.json`

**Interfaces:**
- Each module exposes `<source>_id(canonical: str) -> str | None` and `fetch_<source>(id: str, dest: Path, policy: SizePolicy, get_json, get_bytes) -> FetchResult` using `fetch_common.select_downloads`. Zenodo: `https://zenodo.org/api/records/<id>`, files at `files[].links.self`, hash `files[].checksum` (`md5:…`), record `metadata.doi` as `version_doi` and `conceptdoi` as `concept_doi` in a new `meta: dict` field on `FetchResult` (default `{}`), added to `fetch_common` in this task. Figshare: `https://api.figshare.com/v2/articles/<id>`, `files[].download_url`, `files[].computed_md5`. Dryad: `https://datadryad.org/api/v2/datasets/doi%3A<doi>` → `_links.stash:version.href` → `/files` listing with `_links.stash:download.href`.

- [ ] **Step 1: Write failing tests** (one per source, same pattern):

```python
def test_zenodo_lists_and_downloads(zenodo_fixture, tmp_path):
    assert zenodo_id("https://zenodo.org/records/123456") == "123456"
    r = fetch_zenodo("123456", tmp_path / "zenodo_123456", SizePolicy(), lambda u: zenodo_fixture, lambda u: b"d")
    assert r.status == "ok" and r.meta["version_doi"] == "10.5281/zenodo.123456"
    assert all(f["remote_hash"].startswith("md5:") for f in r.files)
def test_figshare(...): ...   # id from https://figshare.com/articles/dataset/name/9876543 -> "9876543"
def test_dryad(...): ...      # id from https://doi.org/10.5061/dryad.abc123 -> "10.5061/dryad.abc123"; two API calls
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Commit** — `test: zenodo, figshare and dryad fetchers`.
- [ ] **Step 4: Implement** the three modules and add `meta: dict = field(default_factory=dict)` to `FetchResult`.
- [ ] **Step 5: Run** → PASS. **Step 6: Commit** — `feat: zenodo, figshare and dryad fetchers`.

---

### Task 10: OpenNeuro and NeuroVault

**Files:**
- Create: `audit-prep/scripts/fetch_openneuro.py`, `fetch_neurovault.py`, `tests/test_fetch_imaging.py`, fixtures `openneuro_snapshot_root.json`, `openneuro_snapshot_dir.json`, `neurovault_images_p1.json`, `neurovault_images_p2.json`

**Interfaces:**
- `openneuro_id(canonical) -> tuple[str, str | None] | None` → `(dataset_id, tag)`; `list_openneuro_files(ds: str, tag: str | None, post_json) -> list[RemoteFile]` (GraphQL at `https://openneuro.org/crn/graphql`; when `tag` is None first query `dataset(id){ latestSnapshot { tag } }`; recurse into entries with `directory: true` using the `tree` argument); `fetch_openneuro(ds, tag, dest, policy, post_json, get_bytes, must_have=("derivatives", "group", "parcel")) -> FetchResult` (source `openneuro`, status from `select_downloads`).
- `neurovault_id(canonical) -> str | None`; `fetch_neurovault(collection_id, dest, get_json, get_bytes) -> FetchResult` downloading every image regardless of policy, following `next`, saving `collection.json` and each image's metadata.

- [ ] **Step 1: Write failing tests**: id parsing (`.../datasets/ds000001/versions/1.0.0` → `("ds000001","1.0.0")`; `.../collections/1234/` → `"1234"`); OpenNeuro listing recurses one directory level and marks a 20×400 MB dataset `listed_only` with all files listed and none downloaded; NeuroVault downloads both pages' images into `neurovault_1234/` and writes `collection.json`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Commit** — `test: openneuro and neurovault fetchers`.
- [ ] **Step 4: Implement.** **Step 5: Run** → PASS. **Step 6: Commit** — `feat: openneuro inventory/selective download and neurovault maps`.

---

### Task 11: Manifest

**Files:**
- Create: `audit-prep/scripts/manifest.py`, `audit-prep/references/manifest.md`, `tests/test_manifest.py`

**Interfaces:**
- Produces: `SCHEMA_VERSION = 1`; `new_manifest(paper_id: str, prepared_by: str) -> dict` with every top-level key from the spec (`schema_version paper_id prepared_at prep_versions prepared_by finalized metadata documents links preregistration data_collection code data local_data unsorted files warnings`), lists empty, `finalized False`; `hash_tree(root: Path, exclude: tuple[str, ...] = ("manifest.json", "README.md")) -> list[dict]` sorted by `path`, each `{"path","size","sha256"}`; `.git` contents are hashed too, since they are part of the pinned clone; `write_manifest(prepared: Path, m: dict) -> Path`; `load_manifest(folder: Path) -> dict | None`; `is_prepared(folder: Path) -> bool` (manifest present, schema equal, `finalized` true); `render_readme(m: dict) -> str` (Markdown: title/DOI, prepared_by, documents table, prereg table with dates, code table with commits, data table with status and downloaded/listed counts, unsorted, warnings; every absent component says `none found` or `not searched`).

- [ ] **Step 1: Write failing tests**:

```python
def test_new_manifest_has_all_keys():
    m = new_manifest("X_2020", "human")
    assert set(m) >= {"schema_version","paper_id","prepared_at","prep_versions","prepared_by","finalized","metadata","documents","links","preregistration","data_collection","code","data","local_data","unsorted","files","warnings"}
    assert m["finalized"] is False and m["schema_version"] == 1
def test_hash_tree_excludes_manifest_and_readme(tmp_path):
    (tmp_path / "a.txt").write_text("a"); (tmp_path / "manifest.json").write_text("{}"); (tmp_path / "README.md").write_text("r")
    (tmp_path / "d").mkdir(); (tmp_path / "d/b.txt").write_text("b")
    assert [f["path"] for f in hash_tree(tmp_path)] == ["a.txt", "d/b.txt"]
def test_write_load_is_prepared(tmp_path):
    m = new_manifest("X_2020", "human"); write_manifest(tmp_path, m)
    assert load_manifest(tmp_path)["paper_id"] == "X_2020" and not is_prepared(tmp_path)
    m["finalized"] = True; write_manifest(tmp_path, m); assert is_prepared(tmp_path)
def test_readme_states_absences():
    text = render_readme(new_manifest("X_2020", "human"))
    assert "Preregistration" in text and "none found" in text and "X_2020" in text
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Commit** — `test: manifest schema, hashing and README rendering`.
- [ ] **Step 4: Implement**; write `references/manifest.md` documenting each key and the per-item status vocabulary `ok | skipped | failed | not_applicable | listed_only | partial | hash_mismatch`.
- [ ] **Step 5: Run** → PASS. **Step 6: Commit** — `feat: manifest schema v1 with tree hashing and README`.

---

### Task 12: Orchestration: `prepare.py` and `prep.py` CLI

**Files:**
- Create: `audit-prep/scripts/prepare.py`, `audit-prep/scripts/prep.py`, `tests/test_prepare.py`

**Interfaces:**
- Consumes: everything above.
- Produces (`prepare`): `@dataclass Clients(get_json, get_bytes, post_json, run)` with defaults from `fetch_common` and `subprocess.run`; `locate(target: Path, corpus: Corpus) -> tuple[Path, str]` returning `(folder, "raw"|"prepared")` (if `target` no longer exists but `corpus.prepared_dir(target.name)` does, return the prepared one); `move_into_prepared(raw: Path, corpus: Corpus) -> Path`; `apply_file_plan(prepared: Path, plan: dict, corpus: Corpus, manifest: dict) -> None` (renames paper/supplements into `paper/`, moves `data` dirs to `data/<name>/`, archives beside them, `unsorted` to `corpus.unsorted_dir(paper_id)/<rel>`; records `documents`, `local_data`, `unsorted`; skips anything already moved); `extract_archives(prepared: Path, manifest: dict, run) -> None` (top-level `data/*.{zip,tar*,tgz,zst}`; skip when the sibling dir exists → `extracted: "pre-existing"`; nested archives inside `data/<dir>/` → `nested_archive` entries; `.zst` via `zstd -d`); `process_documents(prepared: Path, manifest: dict, run) -> None` (text, pages, structured, statements, metadata.json, links.json for paper and each supplement; idempotent on existing outputs); `fetch_all(prepared: Path, plan: dict, manifest: dict, clients: Clients) -> None` (dispatch links by role/class: `code` → github into `github/<owner>__<repo>/`; `prereg` → `prereg.fetch_prereg`; `data` → the matching fetcher into `data/<class>_<id>/`; `skip`/`unknown` → recorded with status `skipped`); `run_prep(target: Path, corpus: Corpus, clients: Clients, dry_run: bool = False) -> dict` (loads `prep.yaml`, refuses when `scan.unresolved(plan)` is non-empty by raising `PlanError` with the messages; on `dry_run` prints the planned moves and fetches and returns the manifest unchanged); `finalize(prepared: Path) -> dict` (recompute `hash_tree`, set `files`, `finalized=True`, write manifest + README, `chmod -R a-w`).
- Produces (`prep.py`): argparse CLI `init <dir>`, `scan <folder>`, `run <folder> [--dry-run] [--root R]`, `finalize <folder>`; exit code 2 on `PlanError`/`CorpusError` with the message on stderr.

- [ ] **Step 1: Write failing tests** (use `raw_folder` shapes inside an initialized corpus; `Clients` with fixture-backed getters and a `run` that records commands but really executes only `pdftotext`/`pdftoppm`/`git`/`tar`):

```python
def test_run_refuses_unreviewed_plan(prepped_raw):   # fixture: raw folder + scanned prep.yaml, reviewed_by None
    with pytest.raises(PlanError, match="reviewed_by"): run_prep(prepped_raw.raw, prepped_raw.corpus, prepped_raw.clients)
def test_dry_run_moves_nothing(reviewed_raw, capsys):
    run_prep(reviewed_raw.raw, reviewed_raw.corpus, reviewed_raw.clients, dry_run=True)
    assert reviewed_raw.raw.exists() and "paper/paper.pdf" in capsys.readouterr().out
def test_run_produces_layout(reviewed_raw):
    m = run_prep(reviewed_raw.raw, reviewed_raw.corpus, reviewed_raw.clients)
    p = reviewed_raw.corpus.prepared_dir(reviewed_raw.raw.name)
    assert not reviewed_raw.raw.exists()
    for rel in ["manifest.json", "prep.yaml", "paper/paper.pdf", "paper/paper.txt", "paper/pages/p-001.png",
                "paper/supplement_1.pdf", "paper/supplement_1.txt", "paper/metadata.json", "paper/links.json",
                "paper/statements.md", "github/lab__repo/.git", "data/osf_abcde/data/trials.csv"]:
        assert (p / rel).exists(), rel
    assert m["documents"]["paper"]["original_name"] == "paper.pdf" and m["prepared_by"] == "human"
    assert m["preregistration"][0]["source"] == "osf" and m["preregistration"][0]["status"] == "ok"
def test_residue_moved_to_unsorted(reviewed_residue):
    run_prep(reviewed_residue.raw, reviewed_residue.corpus, reviewed_residue.clients)
    assert (reviewed_residue.corpus.unsorted_dir(reviewed_residue.raw.name) / ".venv").exists()
def test_local_data_and_preexisting_archive(reviewed_data_archive):
    m = run_prep(...)
    p = corpus.prepared_dir(name)
    assert (p / "data/mydata").is_dir() and (p / "data/mydata.tar.gz").is_file()
    assert [a["extracted"] for a in m["local_data"] if a.get("archive")] == ["pre-existing"]
def test_rerun_after_move_resumes(reviewed_raw):
    run_prep(reviewed_raw.raw, reviewed_raw.corpus, reviewed_raw.clients)
    m2 = run_prep(reviewed_raw.raw, reviewed_raw.corpus, reviewed_raw.clients)   # raw path no longer exists
    assert m2["documents"]["paper"]["conversions"]["text"] == "skipped"
def test_finalize_sets_readonly_and_hashes(reviewed_raw):
    run_prep(...); p = corpus.prepared_dir(name); m = finalize(p)
    assert m["finalized"] and is_prepared(p) and (p / "README.md").is_file()
    assert not os.access(p / "paper/paper.pdf", os.W_OK)
    assert {f["path"] for f in m["files"]} >= {"paper/paper.pdf", "prep.yaml"}
def test_cli_init_scan_run_finalize(tmp_path, ...):   # subprocess: uv run audit-prep/scripts/prep.py init/scan; exit code 2 on run before review
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Commit** — `test: prep orchestration and CLI`.
- [ ] **Step 4: Implement `prepare.py` and `prep.py`.** Each sub-step records `status`/`reason` into the manifest and never raises past `run_prep` for a single failed fetch (record `failed` with the exception text, add to `warnings`). `run_prep` writes the manifest after every step so a crash leaves a resumable state. `paper/links.json` is the plan's links list plus a `status`/`fetched_to` per link copied from fetch results.
- [ ] **Step 5: Run** → PASS. **Step 6: Commit** — `feat: prep run pipeline, finalize and CLI`.

---

### Task 13: `new_run.py`

**Files:**
- Create: `audit-prep/scripts/new_run.py`, `tests/test_new_run.py`

**Interfaces:**
- Produces: `make_run_id(rng: random.Random | None = None) -> str` (8 chars from `abcdefghijklmnopqrstuvwxyz234567`); `clone_tree(src: Path, dest: Path, run=subprocess.run) -> str` returning `"clonefile"` after `cp -Rc src dest` succeeds, else `"rsync"` after `rsync -a src/ dest/`; `restore_write(dest: Path) -> None`; `set_dropbox_ignored(dest: Path, run=subprocess.run) -> bool` (`xattr -w com.dropbox.ignored 1 dest`; False on any failure, never raises); `register_run(registry: Path, entry: dict) -> None` (append one JSON line); `new_run(corpus: Corpus, paper_id: str, model: str, runs_root: Path | None = None, run=subprocess.run, rng=None) -> Path` which: requires `is_prepared`, clones to `<runs_root or corpus.runs>/<paper_id>/<run_id>/`, restores write, creates `audit/`, writes `run.json` `{run_id, paper_id, created, manifest_sha256}` (no model), sets the xattr, appends `{run_id, paper_id, model, created, manifest_sha256, run_path}` to the registry, prints and returns the run path. CLI: `new_run.py <paper_id> --model <name> [--root R] [--runs-root D]`.

- [ ] **Step 1: Write failing tests**:

```python
def test_run_id_alphabet(): assert re.fullmatch(r"[a-z2-7]{8}", make_run_id(random.Random(0)))
def test_clone_falls_back_to_rsync(tmp_path):
    calls = []
    def fake_run(cmd, **k):
        calls.append(cmd[0]); 
        if cmd[0] == "cp": return subprocess.CompletedProcess(cmd, 1)
        shutil.copytree(cmd[-2], cmd[-1], dirs_exist_ok=True); return subprocess.CompletedProcess(cmd, 0)
    (tmp_path / "src").mkdir(); (tmp_path / "src/f").write_text("x")
    assert clone_tree(tmp_path / "src", tmp_path / "dst", run=fake_run) == "rsync" and calls == ["cp", "rsync"]
def test_xattr_failure_is_not_fatal(tmp_path):
    def boom(*a, **k): raise FileNotFoundError("xattr")
    assert set_dropbox_ignored(tmp_path, run=boom) is False
def test_new_run_layout_registry_and_blinding(prepared_corpus):   # fixture: corpus with a finalized prepared paper
    run_path = new_run(prepared_corpus, "X_2020", "fable-5.1", rng=random.Random(1))
    assert run_path.parent == prepared_corpus.runs_dir("X_2020") and (run_path / "audit").is_dir()
    assert os.access(run_path / "paper/paper.pdf", os.W_OK)
    rj = json.loads((run_path / "run.json").read_text()); assert "model" not in rj and rj["run_id"] == run_path.name
    assert "fable-5.1" not in "".join(str(p) for p in run_path.rglob("*"))
    assert "fable-5.1" not in "".join(p.read_text(errors="ignore") for p in run_path.rglob("*") if p.is_file())
    line = json.loads(prepared_corpus.registry.read_text().splitlines()[-1])
    assert line["model"] == "fable-5.1" and line["run_id"] == run_path.name
def test_new_run_refuses_unfinalized(corpus_with_unfinalized):
    with pytest.raises(CorpusError, match="finalize"): new_run(corpus_with_unfinalized, "X_2020", "m")
def test_runs_root_override(prepared_corpus, tmp_path):
    assert new_run(prepared_corpus, "X_2020", "m", runs_root=tmp_path / "elsewhere").is_relative_to(tmp_path / "elsewhere")
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Commit** — `test: blinded run creation`.
- [ ] **Step 4: Implement.** **Step 5: Run** → PASS. **Step 6: Commit** — `feat: new_run clones prepared folder under a blinded run id`.

---

### Task 14: `verify_run.py`

**Files:**
- Create: `audit-prep/scripts/verify_run.py`, `tests/test_verify_run.py`

**Interfaces:**
- Produces: `ALLOWED_EXTRA = ("run.json", "audit")`; `verify(folder: Path) -> tuple[str, list[str]]` with statuses `not_prepared | prepared_not_run | run_ok | run_dirty | run_modified` and a list of detail lines (offending paths). Rules: no manifest or not finalized → `not_prepared`; manifest but no `run.json` → `prepared_not_run`; any manifest file missing or hash differing → `run_modified`; any file outside `audit/` and not `run.json`, `manifest.json`, `README.md`, or in the manifest → `run_dirty`; else `run_ok`. CLI prints `STATUS` on the first line then details; exit 0 only for `run_ok`.

- [ ] **Step 1: Write failing tests**:

```python
def test_not_prepared(tmp_path): assert verify(tmp_path)[0] == "not_prepared"
def test_prepared_not_run(prepared_corpus): assert verify(prepared_corpus.prepared_dir("X_2020"))[0] == "prepared_not_run"
def test_run_ok_with_audit_outputs(run_folder):
    (run_folder / "audit/audit.qmd").write_text("x"); (run_folder / "audit/cache").mkdir(); 
    assert verify(run_folder) == ("run_ok", [])
def test_run_dirty_on_stray_file(run_folder):
    (run_folder / "notes.md").write_text("x"); status, details = verify(run_folder)
    assert status == "run_dirty" and details == ["notes.md"]
def test_run_modified_on_changed_or_missing(run_folder):
    (run_folder / "paper/paper.txt").write_text("changed"); assert verify(run_folder)[0] == "run_modified"
    (run_folder / "paper/paper.txt").unlink(); assert verify(run_folder)[0] == "run_modified"
def test_cli_exit_codes(run_folder):   # subprocess uv run verify_run.py <run_folder> -> 0; <tmp_path> -> 1, stdout first line "not_prepared"
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Commit** — `test: run verification statuses`.
- [ ] **Step 4: Implement.** **Step 5: Run** → PASS. **Step 6: Commit** — `feat: verify_run reports prepared/run status`.

---

### Task 15: `audit-prep/SKILL.md`

**Files:**
- Create: `audit-prep/SKILL.md`; Modify: `README.md` (one line listing the skill)
- Test: `tests/test_skill_text.py` (new)

- [ ] **Step 1: Write failing tests**:

```python
SKILLS = Path(__file__).resolve().parents[1]
def test_audit_prep_skill_frontmatter_and_commands():
    text = (SKILLS / "audit-prep/SKILL.md").read_text()
    assert text.startswith("---\nname: audit-prep\n") and "description:" in text
    for cmd in ["prep.py init", "prep.py scan", "prep.py run", "prep.py finalize", "new_run.py", "verify_run.py", "--dry-run"]:
        assert cmd in text, cmd
    assert "reviewed_by" in text and "never delete" in text.lower() and "registry.jsonl" in text
def test_audit_prep_skill_has_no_zsh_path_loop():
    assert "for path in" not in (SKILLS / "audit-prep/SKILL.md").read_text()
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Commit** — `test: audit-prep skill text contract`.
- [ ] **Step 4: Write `SKILL.md`** with frontmatter (`name: audit-prep`, description triggering on "prepare papers for audit", "organize paper folders", "set up audit corpus", and noting both audit skills call it), then sections: Purpose (one paragraph incl. the fairness aim); Layout (the corpus and prepared-folder trees from the spec); Workflow (`init` once; per paper `scan` → review `prep.yaml` per `references/prep-yaml.md` → `run --dry-run` → `run` → `finalize`), exact commands using `uv run ~/.claude/skills/audit-prep/scripts/<script>.py`; Review rules (settle every `needs_review`, fill `reviewed_by` and `data_collection` from the paper text, never delete lines, `skip` with reason, cited tools are `skip`); Runs (`new_run.py`, blinding, never read `registry.jsonl`, all audit output under `audit/`); What prep does not do (spec non-goals); Gotchas (docling first-run download, Dropbox xattr, zsh `path`).
- [ ] **Step 5: Run** → PASS. **Step 6: Commit** — `docs: audit-prep SKILL.md and references`.

---

### Task 16: Rewire `reproducibility-audit`

**Files:**
- Modify: `reproducibility-audit/SKILL.md`, `reproducibility-audit/templates/audit_template.qmd`, `reproducibility-audit/references/report.md` (only if it names file paths); Delete: `reproducibility-audit/scripts/` (now empty)
- Test: extend `tests/test_skill_text.py`

- [ ] **Step 1: Write failing tests**:

```python
def test_reproducibility_audit_has_intake_and_new_layout():
    text = (SKILLS / "reproducibility-audit/SKILL.md").read_text()
    assert "## Intake" in text and "verify_run.py" in text and "new_run.py" in text and "audit-prep" in text
    for old in ["osf_fetch.py", "figs_paper/", "prereg.txt", "~/Projects/<topic>_audits"]: assert old not in text, old
    for new in ["paper/paper.txt", "paper/pages/", "data/osf_", "preregistration/", "audit/audit.qmd", "registry.jsonl"]: assert new in text, new
def test_reproducibility_template_is_blind():
    t = (SKILLS / "reproducibility-audit/templates/audit_template.qmd").read_text()
    assert "MODEL" not in t and "identity recorded in the run registry" in t
def test_no_scripts_dir_left(): assert not (SKILLS / "reproducibility-audit/scripts").exists()
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Commit** — `test: reproducibility-audit uses prepared layout and blind template`.
- [ ] **Step 4: Edit `SKILL.md`.** Add `## Intake` as the first section after the goal paragraph with the five numbered rules from the spec (verify → prep → new run → stop on dirty/modified → read README then manifest; never read `registry.jsonl` or other runs; the warning that prepping during an audit makes prep model-dependent). Replace "Folder organization" with the prepared-folder tree and the rule that all output goes to `audit/` (`audit/audit.qmd`, `audit/audit.html`, caches). Rewrite Stage 1 to: read `manifest.json` for prereg `date_registered` and `data_collection`, note trial-registry presence, use `paper/paper.txt`, `paper/pages/p-NNN.png`, `paper/figures/`, `paper/tables/`, `paper/statements.md`, `preregistration/<source>_<id>/`, `github/`, `data/`. Update every later path mention (`osf/...` → `data/osf_<id>/...`, `paper.txt` → `paper/paper.txt`). Keep all analytic content. Update the privacy line to deliver `audit/audit.html`. In the template replace `(MODEL)` with `(identity recorded in the run registry)` and add a `run_id` line to session info sourced from `run.json`.
- [ ] **Step 5: Run** `uv run pytest tests/ -v -m "not slow"` (includes the existing report-contract test). Expected: PASS.
- [ ] **Step 6: Commit** — `feat: reproducibility-audit intake via audit-prep; blind report template`.

---

### Task 17: Rewire `neuroimaging-validity-audit`

**Files:**
- Modify: `neuroimaging-validity-audit/SKILL.md`, `neuroimaging-validity-audit/templates/audit_template.qmd`
- Test: extend `tests/test_skill_text.py`

- [ ] **Step 1: Write failing tests**:

```python
def test_neuroimaging_audit_has_intake_and_is_blind():
    text = (SKILLS / "neuroimaging-validity-audit/SKILL.md").read_text()
    assert "## Intake" in text and "verify_run.py" in text and "audit-prep" in text
    assert "audit-<llm>" not in text and '"-audit"' not in text and "audit/" in text
    t = (SKILLS / "neuroimaging-validity-audit/templates/audit_template.qmd").read_text()
    assert "MODEL" not in t and "identity recorded in the run registry" in t
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Commit** — `test: neuroimaging audit intake and blind template`.
- [ ] **Step 4: Edit.** Insert the same `## Intake` section before "Intake and scope"; in that section replace "query the paper for relevant URLs and check those" with "use `paper/links.json`, `paper/statements.md` and the manifest's fetch statuses; do not fetch material prep already recorded as absent without saying so"; delete the `-audit` directories sentence; replace the `audit-<llm>` output paragraph with "All persistent output goes under `audit/` in the run folder; nothing in it may name the model." Template: same disclaimer and `run_id` change as Task 16.
- [ ] **Step 5: Run** full non-slow suite → PASS. **Step 6: Commit** — `feat: neuroimaging-validity-audit intake via audit-prep; blind template`.

---

### Task 18: End-to-end check on a fixture corpus and on one real paper

**Files:**
- Create: `tests/test_end_to_end.py`

- [ ] **Step 1: Write failing test** `test_full_cycle(tmp_path, raw_folder, osf_api, crossref_fixture, bare_repo)`: `init_root` → place `paper_supp` raw folder (patched so its GitHub link points at `bare_repo`) → `build_plan` → set `reviewed_by="human"`, resolve all `needs_review` (osf link → `data`, github → `code`) → `write_plan` → `run_prep` → `finalize` → `new_run(..., "model-a")` → `verify(run)[0] == "run_ok"` → write `audit/x.html` → still `run_ok` → second `new_run(..., "model-b")` gives a different id and `"model-a"` appears nowhere under `runs/`.
- [ ] **Step 2: Run** → FAIL (test not yet consistent with wiring, or fixtures missing). **Step 3: Commit** — `test: end-to-end prep, run and verify cycle`.
- [ ] **Step 4: Fix whatever the test exposes** in the modules above (no test edits). **Step 5: Run** → PASS. **Step 6: Commit** — `fix: end-to-end wiring`.
- [ ] **Step 7: Manual smoke on the real corpus (not a test; report results to the user):** `uv run audit-prep/scripts/prep.py init /Users/poldrack/Dropbox/code/autoaudit`, then `scan` and `run --dry-run` on `Wimmer_2022` (small: PDF + DOCX supplement). Do **not** run a real `run` without the user's go-ahead, since it moves the folder.
- [ ] **Step 8: Run `./install.sh`** so `~/.claude/skills/audit-prep` exists; confirm `ls -l ~/.claude/skills/audit-prep`.

---

## Self-review notes

- Spec coverage: layout (T1, T12), scan/review/run/finalize (T6, T12), document processing incl. docling, pandoc, xlsx (T3), statements (T4), Crossref relations (T5), prereg sources incl. hash check and dates (T8), code (T7), data fetchers and size policy incl. OpenNeuro listing and NeuroVault (T7, T9, T10), manifest and README (T11), new_run with clonefile/rsync, xattr, blinding, registry, `--runs-root` (T13), verify statuses and `audit/` rule (T14), SKILL.md and references (T6, T11, T15), audit-skill rewiring and blind templates (T16, T17), deny rule (T1), tests layout (T1). `data_collection` is carried from `prep.yaml` into the manifest in T12 (`run_prep` copies it).
- Names used consistently: `Corpus`, `CorpusError`, `PlanError`, `Link`, `RemoteFile`, `SizePolicy`, `FetchResult(.meta)`, `Clients`, `run_prep`, `finalize`, `new_run`, `verify`.
