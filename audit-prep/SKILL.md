---
name: audit-prep
description: >
  Use when preparing paper folders for reproducibility or neuroimaging validity audits,
  organizing an audit corpus, reviewing a prep plan, or creating and verifying isolated
  audit runs before model evaluation.
---

# Audit prep

Prepare common starting materials once: the publication, any published correction, supplements, and its directly
linked data, code and preregistrations. Convert documents, record provenance and retrieval
gaps, then freeze a snapshot for every model. Discovery of additional relevant evidence
belongs to auditing and is part of the evaluated capability.

The operator completes preparation and run creation before the evaluated session. The
preparer may be a model or a human; record that identity as `prepared_by`. Auditors do not
prepare their own inputs or register their own model identity.

## Layout

```
<corpus>/
  .autoaudit-root
  <Paper_Year>/               # raw inputs and initial prep.yaml; retained in place
  prepared/<Paper_Year>/      # working draft; read-only snapshot after finalize
  runs/<Paper_Year>/<run_id>/  # isolated copy with audit/ for all audit output
  registry.jsonl              # operator-only run ID -> model mapping
```

Raw folders stay in place. Only selected paper, supplement, corrigendum, data and archive entries are
copied into the draft. Files marked `skip` and `unsorted` remain in the raw folder and are
excluded from prepared inputs and audit runs. Never delete supplied material.

A prepared folder contains `manifest.json`, generated `README.md`, the reviewed `prep.yaml`,
and these source directories:

- `paper/`: `paper.pdf`, `paper.txt`, page images in `pages/`, metadata, links and statements;
  supplements named `supplement_<order>`. Structured conversion adds Markdown, `figures/`
  and `tables/`. DOCX supplements become Markdown; XLSX sheets become CSVs. A published
  correction (corrigendum, erratum, correction notice) is `corrigendum_<order>`, converted
  like a supplement; the README tells auditors to audit the paper as corrected.
- `preregistration/<source>_<id>/`: registration files, metadata and dates.
- `github/<owner>__<repo>/`: code with its `.git` history and recorded commit.
- `data/<original_name>/`: supplied data and archives; fetched sources use
  `osf_<id>/`, `zenodo_<id>/`, `neurovault_<id>/`, or `openneuro_<dsid>/`.
  OpenNeuro supplies metadata and root-level BIDS files, with imaging files inventoried
  in `files.json`, not downloaded.

Data fetchers cover OSF, Zenodo, NeuroVault and OpenNeuro; code is cloned from GitHub.
Downloaded data archives are unpacked beside the retained originals using the local-data
extractor (ZIP, tar variants and Zstandard; `.7z` is recorded as unsupported).
Unchanged archives reuse their extraction; changed archives replace only their own prior
output after successful unpacking. Nested archives are listed for review, not recursively
unpacked. Extraction failures and nested archives require resolution or explicit acceptance.
Any other data host is recorded as `status: unsupported` with its URL. Retrieve directly
linked material manually when practical and record where it was saved; otherwise explain
what is missing. See [manifest.md](references/manifest.md) for field details.

## Workflow

Use absolute paths. In the commands below, replace `<audit-prep>` with this skill's installed
directory; the commands do not assume Claude Code or any particular installation path.

```sh
uv run <audit-prep>/scripts/prep.py init /abs/corpus
uv run <audit-prep>/scripts/prep.py scan /abs/corpus/Smith_2021
```

`scan` writes `prep.yaml` and `statements.md` in the raw folder. If it finds no paper, set the
paper role manually. `run` derives its own statements from the selected paper; it never copies
the raw statements file. Do not re-scan a reviewed plan: scan
overwrites it. Review the plan using the rules below, then:

Scan rejects symbolic links before reading inputs or writing its outputs. Generated files
replace the previous files atomically; a scan cannot write through an existing output link.

```sh
uv run <audit-prep>/scripts/prep.py run /abs/corpus/Smith_2021 --dry-run
uv run <audit-prep>/scripts/prep.py run /abs/corpus/Smith_2021
```

Dry run prints copies, conversions and fetches without changing files. Exit 2 lists plan
blockers. `run` copies selected inputs into `prepared/Smith_2021/`, converts documents,
fetches the reviewed links and metadata, and records progress in `manifest.json`.

Once the draft exists, its `prepared/Smith_2021/prep.yaml` is authoritative. Rerun using either
the raw or prepared path to resume; add missed links or edit `accept_failures` in the draft plan.
Previously requested retrieval sources cannot be removed or changed in that draft, because
their downloaded files would otherwise remain as stale evidence. Such changes require a
fresh draft. Retrying the same sources and adding new ones remain supported.
Local file selection, raw contents and the structured-conversion choice are fixed for that draft. To change them, the operator
moves the draft aside, updates the raw plan and starts a fresh draft; prep never silently
deletes old work. Selected inputs containing symbolic links are rejected, as are symbolic
links found before finalization. Materialize needed targets as ordinary files first.

`run` exits 1 while prep products are missing or failed. Fix and rerun first. If a gap cannot
be fixed, acknowledge the printed item under `accept_failures`, with a reason explaining
what the auditor will lack. This records an evidence limitation, not permission to waive an
incomplete run or a changed plan. Crossref metadata and requested conversions are checked,
as are data, code, registrations, archive extraction and links added after a run.

```sh
uv run <audit-prep>/scripts/prep.py review /abs/corpus/prepared/Smith_2021
uv run <audit-prep>/scripts/prep.py finalize /abs/corpus/prepared/Smith_2021
```

`review` is read-only: exit 0 ok, 1 open problems, 2 plan or corpus error. An interrupted `run`
leaves `review: null`; review and finalize report `run: incomplete` until run completes.
Finalize refuses open problems, hashes the tree, generates the README, marks `finalized`
and removes write permission. A finalized folder cannot be resumed with `run`.

`scan`, `run`, `review`, `finalize` and `new_run.py` accept `--root /abs/corpus`; otherwise
scripts find the nearest `.autoaudit-root`. `verify_run.py` takes only the folder argument.

## Review rules for `prep.yaml`

Read the paper text and `statements.md`; the scanner's decisions are suggestions.
See [prep-yaml.md](references/prep-yaml.md) for the schema and detailed examples.

- Resolve every `needs_review: true`, set it to `false`, and cite the page or statement
  supporting the role in `reason`. **Never delete a line**; exclude an item with `role: skip`.
- Confirm the `paper` file, and confirm `doi` is the article's own DOI, not a deposit DOI.
  Set the article DOI or `null`; number supplements in the paper's order.
- A published correction to the paper is `role: corrigendum` (numbered by publication date),
  never `paper` or `supplement`, even when its file name has no marker. Its DOI is not the
  paper's `doi`. Correction notices for other articles are `skip`.
- Fetch directly linked study data, code and preregistrations. Distinguish an OSF project
  from a registration using the surrounding statement. For linked OSF files and a derived
  parent-project link, choose either the needed files or the whole project, skipping the
  redundant links with a reason.
- GitHub analysis code is `code`; a cited package is `skip`. Other articles and cited tools
  are not prep inputs. Add missed study-artifact links with `found_in` and a reason.
- Choose `structured_conversion` once for the corpus: `true` (default) produces PDF
  Markdown, figure crops and tables with Docling; `false` omits that optional conversion
  with status `not_requested`. Text and page images remain available. Use the same choice
  for all models' starting materials, rather than accepting repeated conversion failures.
- Fill data-collection dates and their verbatim source quote/page when available, and set
  `reviewed_by` last to the preparer's model name or `human`.
- `accept_failures` requires a non-empty reason, not the printed placeholder. The keys
  `run` and `plan` cannot be accepted. Accepted evidence gaps appear in the README's
  "Prep review" section for every auditor.

## Operator: create audit runs

After finalizing, create each run outside the evaluated audit session:

```sh
uv run <audit-prep>/scripts/new_run.py Smith_2021 --model <model-name> --root /abs/corpus
uv run <audit-prep>/scripts/verify_run.py /abs/corpus/runs/Smith_2021/<run_id>
```

Run creation copies the snapshot under a random ID, restores write permission, creates
`audit/`, pins the manifest and README in `run.json`, and records the model mapping in
`registry.jsonl` outside the run. APFS clone is attempted first, then rsync. `--runs-root`
can place runs outside the corpus or Dropbox; the Dropbox-ignore attribute is best-effort.
Run creation reserves a new destination before copying. Existing files, directories and
symbolic links are refused without alteration; a failed copy cleans up only its own new run.

The operator launches the auditor with only its run folder as the accessible workspace.
Keep `registry.jsonl` and other runs inaccessible using the execution environment's access
controls; a working directory alone is not isolation. The auditing model never supplies or
writes its own identity. Graders unblind using the operator's registry after scoring.

Only `run_ok` permits auditing. `not_prepared` and `prepared_not_run` require operator setup;
`run_dirty` or `run_modified` require a fresh run. Verification checks snapshot files and
allows changes only under `audit/` (Finder and Dropbox metadata are ignored).

Auditors may retrieve additional evidence, including retrying failed prep sources, under
`audit/additional-evidence/`. Reports distinguish supplied and discovered evidence and
record source URLs, retrieval dates, local files and dependent findings. Keep prepared
inputs unchanged. All audit reports, caches, working copies and environments go in `audit/`;
verification therefore allows an interrupted audit to resume in the same run.

## Boundaries and practical notes

- Retrieval permits HTTP(S) on ports 80/443 only, with no URL credentials. Every connection
  resolves to public addresses and connects to those validated addresses; redirects obey
  the same policy. Local-file URLs, internal services and implicit environment proxies are
  blocked. Proxy-only environments need operator-managed retrieval outside this tool.
- Git retrieval accepts HTTPS `github.com` repository-root URLs only. It pins a validated
  address using Git's `http.curloptResolve`, disables redirects and automatic submodule
  retrieval, and ignores global/system Git configuration and inherited Git/proxy settings.
  Review submodule dependencies separately rather than bypassing these restrictions.
- Prep does not extract scientific claims, assess findings, or execute authors' analyses.
- Default data caps are 500 MB per file and 5000 MB per source; video/audio are skipped.
  Larger sources are inventoried. Raw imaging downloads are not part of routine prep.
- Docling may download models on first use. A requested conversion failure is recorded
  for review; an intentionally disabled conversion is not a failure.
- Legacy snapshots remain readable by their manifest schema. If the raw folder was moved
  by an older prep version, recover a separate raw source before rebuilding; do not
  reconstruct it by treating a prepared tree as raw input.
- In zsh, use `dir`, not `path`, for loop variables (`path` is tied to `PATH`).
