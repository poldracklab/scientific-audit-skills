# audit-prep: design

Date: 2026-11-02. Status: reviewed; awaiting user approval.

## Intent

A new skill, `audit-prep`, turns a loose folder of paper PDFs and whatever else
the user dropped in (supplements, data dumps, legacy analysis trees) into a
standardized, self-describing, read-only **prepared paper folder** that contains
everything an auditing model could need: the paper and supplements as PDF, plain
text, structured Markdown, page images, cropped figures and extracted tables;
the preregistration documents with their registration dates verified; cloned
code repositories pinned to a commit; downloaded or inventoried datasets; and
a manifest recording provenance and status for all of it.

The reason is a model comparison. The user runs the same audit of the same
paper with several different LLMs (via `reproducibility-audit` and
`neuroimaging-validity-audit`) and compares the audits. Any difference in
what material each model could reach, or how well it could read a PDF, is a
confound. Prep removes that confound by doing all retrieval and all document
conversion once, deterministically, before any audit model runs, and by giving
each audit run an identical, isolated copy.

A second reason is hygiene. Audits run in place have left `.git`, `.venv` and
cache directories inside the source folders. Prepared folders are never written
to by an audit.

## Goals

1. One command sequence prepares a paper folder; rerunning is safe and skips
   finished work.
2. Every byte an audit model needs is inside the prepared folder, or, when
   too large to download, is fully inventoried inside the manifest.
3. No audit model ever has to parse a PDF, DOCX or XLSX itself.
4. Every audit run works in a fresh copy of the prepared folder under a
   blinded run ID; the model-to-run mapping lives outside every run, and
   nothing inside a run folder (paths, filenames, report text) names the
   model, so a person or model comparing runs is blind until they consult
   the registry.
5. Both audit skills detect an unprepared folder and run prep first, detect
   a prepared-but-not-run folder and create a run, and verify a run folder is
   pristine before starting.
6. Everything deterministic is a script; the model's judgment is confined to
   classifying files and links in a small YAML plan that the scripts execute.

## Non-goals

- Reading the paper for claims, extracting statistics, or any audit work.
- Installing or running the authors' code, R or Python environments.
- Downloading raw neuroimaging datasets of arbitrary size.
- Blinding a model to its own identity. (Blinding the *comparer* is a goal.)
- Supporting Windows. The user runs macOS with APFS; Linux must work with the
  rsync fallback.

## Anti-goals

- Deleting anything the user put in the folder. Unclassified material is moved
  aside, never removed.
- Producing a prepared folder that differs between two preps of the same
  inputs for reasons other than upstream changes (a repo gained commits, an
  OSF project changed). Prep records what it fetched and when so such
  differences are visible.
- Leaving prep status implicit. If a prereg was searched for and not found,
  the manifest says so. The audit must never have to guess whether something
  is missing because it does not exist or because prep did not look.

## Constraints

- Repository conventions from the user's CLAUDE.md: Python managed with uv and
  run with `uv run`; pytest with TDD; functions over classes in tests;
  fixtures for persistent objects; no code or imports in `__init__.py`; short
  functions.
- Skills in this repo are a directory with `SKILL.md`, optional `references/`,
  `scripts/`, `templates/`, symlinked into `~/.claude/skills` by `install.sh`.
  `audit-prep` follows this layout.
- External tools assumed present: `poppler` (`pdftotext`, `pdftoppm`),
  `pandoc`, `git`, `uv`. Python dependencies are declared per script with
  PEP 723 inline metadata so `uv run script.py` resolves them without a
  project. `docling` (structured PDF conversion) is heavy; it is a dependency
  of the one script that uses it, and that script is skipped with a recorded
  status if docling fails to install.
- The corpus lives in Dropbox at `/Users/poldrack/Dropbox/code/autoaudit`.
  Paths in scripts are arguments, never hard-coded.
- zsh: never use `path` as a loop variable in shell snippets inside SKILL.md.
- Privacy: nothing here is published. No artifacts, no uploads.

## Corpus layout

```
autoaudit/
  <Paper_Year>/               # raw input folders as they are today (prep consumes these)
  prepared/<Paper_Year>/      # prep output; made read-only when finalized
  runs/<Paper_Year>/<run_id>/ # one APFS clone per audit run; the audit model's cwd
  unsorted/<Paper_Year>/      # material prep could not classify, moved out of the way
  registry.jsonl              # run_id -> model mapping; never inside prepared/ or runs/
  .autoaudit-root             # marker written by `prep.py init`; scripts refuse to write without it
  .claude/settings.json       # deny rule: no reads of registry.jsonl (Claude Code only)
```

The corpus root is `--root` if given, else the nearest ancestor of the target
folder containing `.autoaudit-root`. `prep.py init <dir>` creates the marker
and the four directories. Without a marker every script stops with a message
naming `init`, so pointing a skill at a stray folder never scatters
`prepared/` and `runs/` into, say, `~/Downloads`. A single ad hoc paper is
handled by running `init` on a fresh directory and dropping the paper in it;
the old free-form `~/Projects/<topic>_audits/` layout in
`reproducibility-audit` is retired.

`new_run.py` sets the `com.dropbox.ignored` extended attribute on each run
folder so Dropbox does not upload a full copy per model. `prepared/` is
synced; it is the valuable artifact. Both behaviours are overridable with
`--runs-root <dir>` for a location outside Dropbox.

The raw input folder is **moved**, not copied, to `prepared/<Paper_Year>/`
during the run step, so the 1.2 GB Demidenko data is not duplicated. Prep
records the original relative path of every renamed file in the manifest.

Paper folder names stay as they are (`Lastname_Year`, with a letter suffix
for a second paper in the same year). Prep does not rename folders.

## Prepared paper folder layout

```
prepared/<Paper_Year>/
  manifest.json
  README.md                       # generated from the manifest; the first thing an audit reads
  prep.yaml                       # the plan that was executed (kept for provenance)
  paper/
    paper.pdf
    paper.txt                     # pdftotext -layout
    paper.md                      # docling Markdown, figure and table placeholders resolved to files below
    pages/p-001.png ...           # every page, 110 dpi
    figures/fig-01.png ...        # docling crops; figures.md lists file, page, caption
    figures/figures.md
    tables/table-01.csv ...       # docling tables; tables.md lists file, page, caption
    tables/tables.md
    metadata.json                 # Crossref record: DOI, title, authors, journal, dates, relations (corrections, retractions, preprint)
    links.json                    # every URL and DOI found, with source location, classification, fetch status
    statements.md                 # verbatim data availability, code availability, preregistration and funding statements, with page numbers
    supplement_1.pdf              # supplements numbered in prep.yaml order
    supplement_1.txt
    supplement_1.md
    supplement_1/pages/ figures/ tables/
    supplement_2.docx             # non-PDF supplements: original plus conversions
    supplement_2.md               # pandoc, with media extracted to supplement_2/media/
    supplement_3.xlsx
    supplement_3/<sheet>.csv
  preregistration/
    osf_<regid>/                  # registration files + registration.json (title, dates, type, frozen SHA-256 and verification result)
    aspredicted_<id>/             # saved PDF + page text
    clinicaltrials_<nct>/         # record JSON and history
    prospero_<id>/
  github/
    <owner>__<repo>/              # full clone, default branch, submodules; .git kept; commit SHA in manifest
  data/
    <original_dir_name>/          # pre-existing local data directories, one per original directory
    osf_<nodeid>/                 # original OSF folder structure
    zenodo_<recordid>/
    figshare_<id>/
    dryad_<doi-suffix>/
    openneuro_<dsid>/             # files under the cap; always a full file listing in manifest
    neurovault_<collectionid>/    # collection metadata and all statistical maps
```

Archives found at the top level of the raw folder or downloaded from a source
(`.zip`, `.tar.*`, `.tgz`, `.zst`) are extracted into a sibling directory named
after the archive; the archive is kept. If that sibling already exists (as in
Demidenko_2024) extraction is skipped and the manifest records
`extracted: pre-existing`. Archives nested inside a local data directory are
not extracted; they are listed in the manifest as `nested_archive` so the
auditor knows they exist. `zstd` joins the assumed external tools.

## Workflow

Three script commands with the model's judgment between the first two.

### 1. `prep.py scan <raw_folder>` → `prep.yaml` draft

Pure heuristics, no network except Crossref:

- Candidate paper: the PDF with a DOI in its first two pages that resolves
  via Crossref to a journal article, preferring the longest if several.
  Supplements: files whose names contain `supp`, `_sm`, `som`, `mmc`, `ESM`,
  `MOESM`, or that are PDFs with no DOI or a DOI equal to the paper's.
- Existing directories are listed as `data` candidates. Known residue
  (`.git`, `.venv`, `.pytest_cache`, `__pycache__`, `.DS_Store`, `*.txt`
  siblings of a same-named PDF) is proposed as `unsorted`.
- Every URL and DOI is extracted from the paper and supplement text **and
  from PDF link annotations** (many links are hyperlinks behind text). Each
  gets a provisional class from its host: `osf`, `github`, `zenodo`,
  `figshare`, `dryad`, `openneuro`, `neurovault`, `aspredicted`,
  `clinicaltrials`, `prospero`, `other`; and a provisional role: `prereg`
  for registration hosts and OSF registration URLs, `code` for GitHub,
  `data` for the rest, `unknown` for `other`.
- The draft lists every file and link with its proposed class and marks
  anything ambiguous `needs_review: true`.

### 2. The model reviews `prep.yaml`

The SKILL.md tells the model to read the scan report and the paper text
(`statements.md` is produced at scan time for this purpose) and settle every
`needs_review` item: which OSF link is a prereg versus a data project, which
supplement is which, whether a directory is data or residue, whether a
`github` link is the paper's code or a cited tool (the latter is `skip`).
It may add links the scanner missed. It must not delete lines; it marks
things `skip` with a one-line reason. `prep.py run` refuses to start while
any `needs_review` remains.

`prep.yaml` carries a `reviewed_by` field (model name, or `human`) that the
reviewer fills in; `run` refuses to start without it and copies it into the
manifest as `prepared_by`. The user's decision: prep is meant to be done once
up front, by the user with a model of their choosing, before any comparison
runs. The audit skills still prep an unprepared folder when they meet one, but
the SKILL.md for both warns that doing so makes prep model-dependent and the
manifest shows who did it.

### 3. `prep.py run <raw_folder> [--dry-run]`

Executes the plan. `--dry-run` prints every rename, fetch and conversion and
stops. Steps, each idempotent and recorded in the manifest with status
`ok | skipped | failed | not_applicable` and a reason:

1. Move the folder to `prepared/<Paper_Year>/`, create the layout, move
   unsorted items to `unsorted/<Paper_Year>/` preserving relative paths.
2. Rename paper and supplements; record original names.
3. Document processing for every PDF: `pdftotext -layout`, `pdftoppm` pages,
   docling Markdown with figure crops and tables, caption index files.
   DOCX via pandoc with media extraction; XLSX sheets to CSV.
4. Crossref metadata, including `relation` entries (is-preprint-of,
   has-correction, is-retracted-by). Each related DOI is added to `links.json`.
5. Preregistrations: OSF via the API with frozen-hash verification (existing
   `osf_fetch.py registration`, moved into this skill); AsPredicted PDF
   download; ClinicalTrials.gov v2 API record; PROSPERO record page. Each
   records `date_registered`. The manifest also carries `data_collection`
   dates if the model filled them in `prep.yaml` from the paper, so the audit
   can compare without re-reading.
6. Code: `git clone --recurse-submodules`, record HEAD SHA, default branch,
   remote URL, and whether the repo has a release or Zenodo DOI mentioned in
   its README.
7. Data: per-source fetchers with a size policy (below). Always write a
   complete remote file listing (path, size, remote checksum when the API
   provides one) into the manifest before deciding what to download.
8. Hash every file in the prepared folder, write `manifest.json` and
   `README.md`.

### Size policy

Defaults (my call; overridable in `prep.yaml`): download any file up to
500 MB and any single source up to 5 GB; skip video and audio. Above the caps,
the source is `listed_only` with its full inventory in the manifest. OpenNeuro
datasets are inventoried via the OpenNeuro GraphQL API; derivatives named in the
paper (group maps, parcellated time series) are downloaded individually when
under the per-file cap. NeuroVault statistical maps are always downloaded;
they are small.

### 4. `prep.py finalize <prepared_folder>`

Verifies the manifest against the tree, writes `README.md`, and makes the
tree read-only (`chmod -R a-w`). A folder is "prepared" when `manifest.json`
exists with `schema_version` matching the current one and `finalized: true`.

### 5. `new_run.py <Paper_Year> --model <name>`

Makes `runs/<Paper_Year>/<run_id>/` with `cp -Rc` (APFS clone), falling back
to `rsync -a` when the clone fails; restores write permission inside the run
copy; generates `run_id` as 8 random base32 characters; appends
`{run_id, paper, model, created, manifest_sha256}` to `registry.jsonl`;
prints the run path and nothing else. The skills tell the model never to read
`registry.jsonl`, and `autoaudit/.claude/settings.json` denies `Read` on it.

### 6. `verify_run.py <folder>`

Returns one of `not_prepared`, `prepared_not_run`, `run_ok`, `run_dirty`,
`run_modified`. Rules: every manifest file must be present with its recorded
hash, else `run_modified`; all audit output lives under `audit/` in the run
folder, and any file outside `audit/` that is not in the manifest makes the
run `run_dirty`. Files under `audit/` are never inspected, so an interrupted
audit resumes in its own run folder and shows `run_ok`. One registry line is
therefore one audit attempt, resumed or not. Prints a short report. Audit
skills call this first and act on the result.

## Manifest (`manifest.json`, schema_version 1)

```
schema_version, paper_id, prepared_at, prep_versions {skill, docling, poppler, pandoc}
finalized: bool
metadata: {doi, title, authors[], journal, published, relations[]}
documents: {paper: {...}, supplements: [...]}   # each with original_name, pages, conversion statuses
links: [{url, canonical, found_in: [{file, page}], class, role, decision, fetched_to, status, reason}]
preregistration: [{source, id, path, date_registered, hash_verified, status}]
data_collection: {start, end, source_quote, page} | null
code: [{url, path, commit, branch, cloned_at, status}]
data: [{source, id, path, status: ok|listed_only|failed, files: [{path, size, sha256|remote_hash, downloaded: bool}]}]
local_data: [{original_path, path}]
unsorted: [{original_path, moved_to, reason}]
files: [{path, size, sha256}]                    # everything under the prepared folder, for verify_run
warnings: [str]
```

`README.md` is a human-readable rendering: what the paper is, what is present,
what is absent and why, what was listed but not downloaded, prereg dates,
code commits, and the warnings. It is regenerated from the manifest and never
hand-edited.

## Changes to the audit skills

Both `reproducibility-audit/SKILL.md` and `neuroimaging-validity-audit/SKILL.md`
get a short **Intake** section at the top, replacing their current gathering
instructions:

1. Run `verify_run.py` on the folder you were given.
2. `not_prepared` → invoke the `audit-prep` skill on it, then continue.
3. `prepared_not_run` → run `new_run.py` with your model name, `cd` into the
   printed path, continue.
4. `run_dirty` or `run_modified` → stop and report; do not audit a
   contaminated folder.
5. `run_ok` → read `README.md`, then `manifest.json`, then proceed. Never
   read `../../../registry.jsonl` or any other run folder.

Specific edits:

- `reproducibility-audit`: Stage 1 shrinks to intake plus the two judgment
  notes that remain the auditor's (registration date versus data collection;
  trial registry presence), reading them from the manifest. Folder layout
  section, `osf/`, `paper.txt`, `prereg.txt`, `figs_paper/` references and
  the `qmd` template paths change to the prepared layout. `scripts/osf_fetch.py`
  moves to `audit-prep/scripts/` and the skill no longer references it.
  Report outputs are written in the run folder root.
- `neuroimaging-validity-audit`: intake section replaces the "query the paper
  for URLs" instruction and the "do not look in other -audit directories"
  rule, which structure now enforces. Template paths updated.
- Both: all persistent output goes to `audit/` inside the run folder;
  nothing is written to `prepared/`. The neuroimaging skill's `audit-<llm>/`
  convention is removed. Report files are named `audit.qmd` and `audit.html`.
  Both templates drop the model name from the disclaimer, which becomes
  "written by an AI agent (identity recorded in the run registry)". Session
  info in the appendix records tool versions and the run ID, not the model.
  Nothing inside the run folder may name the model.

## Testing

A root `pyproject.toml` (no package, dev dependency group: pytest, pymupdf,
openpyxl, pyyaml, python-docx) so `uv run pytest` works from the repo root;
the scripts keep their PEP 723 headers for standalone `uv run script.py` use.
Tests live in the root `tests/` beside the existing report-contract test, and
`tests/conftest.py` adds `audit-prep/scripts` to `sys.path` so script
functions import directly. pytest under `tests/`, functions and fixtures only. Network is never touched in
tests; fetchers take an injectable `get` function and tests supply recorded
JSON. Fixtures: a generated two-page PDF with text, a DOI, a visible URL and a
hidden link annotation (built with pymupdf); a tiny DOCX and XLSX; a local bare
git repository to clone from; a raw folder fixture that mirrors the shapes in
the corpus (paper plus supplement, paper plus data dir and archive, paper plus
residue). Docling and pandoc integration tests are marked `slow` and skipped
when the tool is unavailable, with one smoke test that does run them on the
fixture PDF. `new_run.py` is tested for clone-or-fallback, registry append,
and that the run copy contains no registry. `verify_run.py` is tested on each
status. The existing report-contract test for the two audit skills keeps
passing after the template path changes.

## Left to the builder

- Exact filename heuristics and the format of the scan report.
- CLI flag names; whether `prep.py` is one script with subcommands or three.
- How docling output is mapped onto `figures/` and `tables/` numbering.
- Handling of AsPredicted pages that require a view token (record the URL and
  `status: failed` with the reason if the PDF cannot be fetched).
- Whether `README.md` generation uses a template file or inline formatting.
- Parallelism of downloads.

## Calls I made (for the user to check)

- Input folders are moved into `prepared/`, not copied.
- Unclassifiable material goes to `autoaudit/unsorted/<Paper_Year>/`, outside
  the prepared tree.
- Size caps: 500 MB per file, 5 GB per source, video and audio skipped.
- docling for structured conversion; pandoc for DOCX; openpyxl for XLSX.
- Run IDs are 8 random base32 characters; the registry is JSON Lines.
- Prepared trees are made read-only at finalize.
- The audit skill creates a run itself when handed a prepared folder, passing
  its own model name.
- Claude Code deny rule on the registry as an extra guard.
- Corpus root is found by a `.autoaudit-root` marker; scripts refuse to write
  without one. The old free-form `reproducibility-audit` folder layout is
  retired in favour of `init` on any directory.
- Run folders get the Dropbox-ignore attribute; `prepared/` syncs.
- Audit output is confined to `audit/` inside the run; `verify_run` ignores
  that directory, so runs are resumable and one registry line is one attempt.
- Pre-extracted archives are left alone; archives nested in local data
  directories are listed, not extracted.
- Tests and dev dependencies live in a root `pyproject.toml` and root `tests/`.

## Decisions the user made after review

- Prep is normally done once, up front, by the user. Audit skills may still
  prep but warn, and the manifest records `prepared_by`.
- Nothing inside a run folder names the model: not paths, not filenames, not
  the report disclaimer. Only `registry.jsonl` does.
