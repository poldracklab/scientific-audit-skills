---
name: audit-prep
description: >
  Prepare paper folders for a reproducibility or neuroimaging validity audit: turn a loose
  folder of PDFs, supplements, data dumps and residue into a standardized, read-only prepared
  folder (paper and supplements converted to text, Markdown, page images, figures and tables;
  preregistrations fetched with dates; code cloned at a pinned commit; data downloaded or
  inventoried; everything recorded in manifest.json), then set up blinded, isolated audit runs
  for model comparisons. Use whenever the user asks to "prepare papers for audit", "organize
  paper folders", "set up an audit corpus", prep one or many papers, or create or verify an
  audit run. reproducibility-audit and neuroimaging-validity-audit invoke it when they meet an
  unprepared folder.
---

# Audit prep

Purpose: every audit model gets exactly the same material, already retrieved and already
converted, in its own pristine copy, under a run ID that does not name the model. Differences
between audits by different models then reflect the models, not what each could fetch or how
well it parsed a PDF. Your judgment is confined to reviewing one YAML plan per paper.

**Prep once, up front.** Prep is meant to be done once, by the user with a model of their
choosing, before any comparison runs. An audit skill that preps a folder on the fly makes prep
model-dependent; the manifest records who did it as `prepared_by`. Tell the user if you do.

## Layout

Corpus root (created by `init`):

```
<corpus>/
  <Paper_Year>/               # raw input folders; run moves them into prepared/
  prepared/<Paper_Year>/      # prep output; read-only once finalized
  runs/<Paper_Year>/<run_id>/ # one clone per audit run; the audit model's cwd
  unsorted/<Paper_Year>/      # material prep could not classify, moved aside, never deleted
  registry.jsonl              # run_id -> model mapping; never read it
  .autoaudit-root             # marker; scripts refuse to write without it
  .claude/settings.json       # deny rule on reading registry.jsonl
```

Prepared paper folder:

```
prepared/<Paper_Year>/
  manifest.json  README.md  prep.yaml
  paper/
    paper.pdf  paper.txt  paper.md          # pdftotext -layout; docling Markdown
    pages/p-001.png ...                     # every page
    figures/fig-01.png ... figures.md       # crops plus caption index
    tables/table-01.csv ... tables.md
    metadata.json  links.json  statements.md
    supplement_1.pdf  supplement_1.txt  supplement_1.md  supplement_1/
    supplement_2.docx supplement_2.md       # pandoc; media in supplement_2/media/
    supplement_3.xlsx supplement_3/<sheet>.csv
  preregistration/
    osf_<regid>/  aspredicted_<id>/  clinicaltrials_<nct>/  prospero_<id>/
  github/<owner>__<repo>/                   # full clone, .git kept, commit in manifest
  data/
    <original_dir_name>/                    # local data directories as supplied
    osf_<nodeid>/  zenodo_<recordid>/  neurovault_<collectionid>/
    openneuro_<dsid>/   # metadata only: dataset.json, README, files.json, root-level BIDS files
```

Data fetchers exist for OSF, Zenodo, NeuroVault and OpenNeuro (metadata and root-level files
only; imaging files are listed in `files.json`, never downloaded); code is cloned from GitHub.
Any other data host (figshare, Dryad, bare DOIs, other) is recorded in the manifest as
`status: unsupported` with its URL, so the auditor sees it. Field-level detail:
`references/manifest.md`.

## Workflow

Use absolute paths throughout (see Gotchas). Set up the corpus once:

```zsh
uv run ~/.claude/skills/audit-prep/scripts/prep.py init /abs/corpus
```

Put each raw paper folder (`Lastname_Year`, as is; prep does not rename) directly under the
corpus root. Then, per paper:

1. **Scan.** Writes `<raw>/prep.yaml` and `<raw>/statements.md` and prints both. If it finds
   no paper candidate, `statements.md` is not written: set a `paper` role by hand in
   `prep.yaml`; `run` generates `paper/statements.md` later.

   ```zsh
   uv run ~/.claude/skills/audit-prep/scripts/prep.py scan /abs/corpus/Smith_2021
   ```

2. **Review `prep.yaml`** by the rules below and `references/prep-yaml.md`.
3. **Dry run.** Prints every move, conversion and fetch, changes nothing. Exit 2 with a list of
   blockers means the review is unfinished: fix each listed item in `<raw>/prep.yaml`, then
   repeat the dry run.

   ```zsh
   uv run ~/.claude/skills/audit-prep/scripts/prep.py run /abs/corpus/Smith_2021 --dry-run
   ```

4. **Run.** Moves the folder to `prepared/Smith_2021/`, lays out `paper/`, `data/`, `github/`,
   `preregistration/`, moves unclassified items to `unsorted/Smith_2021/`, converts documents,
   fetches Crossref metadata, preregistrations, code and data, and writes `manifest.json` after
   each step. It is resumable: if interrupted or a fetch fails, rerun the same command (the raw
   path is fine; it finds the moved folder).

   ```zsh
   uv run ~/.claude/skills/audit-prep/scripts/prep.py run /abs/corpus/Smith_2021
   ```

   After the last step `run` reviews the manifest. A *problem* is anything prep was supposed
   to produce and did not: no paper document; a document conversion `failed`; Crossref
   metadata missing; a local archive whose extraction `failed` or was `skipped`; a
   preregistration not `ok`; a code record `failed` or `unsupported`; a data record not `ok`
   (`partial`, `listed_only`, `failed`, `unsupported`). While any problem is open, `run`
   exits 1 and prints each one with the exact key to paste. Fix and rerun first (a missed
   link: edit `prepared/Smith_2021/prep.yaml`, rerun). Only a problem that cannot be fixed
   goes under `accept_failures` in `prepared/Smith_2021/prep.yaml`, with a reason saying what
   the auditor will be missing. Never accept a failure to make the run pass: the aim is
   identical material for every model.
5. **Finalize.** Hashes the tree, writes `README.md`, marks `finalized`, makes the tree
   read-only. After this the folder is "prepared". Finalize refuses (exit 1) while a problem
   is open; the review is written into `manifest.json` and `README.md`.

   ```zsh
   uv run ~/.claude/skills/audit-prep/scripts/prep.py finalize /abs/corpus/prepared/Smith_2021
   ```

   To print the open and accepted problems without changing anything:

   ```zsh
   uv run ~/.claude/skills/audit-prep/scripts/prep.py review /abs/corpus/prepared/Smith_2021
   ```

For many papers, scan them all, review each plan, then run and finalize each. In zsh loops use
a variable such as `dir`, never `path`:

```zsh
for dir in /abs/corpus/*_<->*(/); do
  uv run ~/.claude/skills/audit-prep/scripts/prep.py scan "$dir"
done
```

`prep.py scan`, `run`, `review`, `finalize` and `new_run.py` accept `--root /abs/corpus`;
`verify_run.py` and `prep.py init` take only their positional argument. Without `--root` they use the nearest ancestor holding
`.autoaudit-root` and stop with a message naming `init` if there is none.

## Review rules for `prep.yaml`

Read `statements.md` and the paper text before editing. Then:

- Settle every `needs_review: true`: choose the role, set it `false`, and rewrite `reason` as a
  one-line justification citing the page or statement.
- **Never delete a line.** Anything that should not be moved or fetched gets `role: skip` with
  a one-line reason.
- OSF links: "preregistered at" means `prereg`; "data/materials/code available at" means `data`.
- GitHub links: the authors' analysis code is `code`; a cited tool or someone else's package
  is `skip`, reason "cited tool". Article DOIs (citations, preprints) are `skip`.
- Confirm the `paper` file, and confirm `doi` is the article's own DOI, not a deposit DOI
  (Zenodo, OSF, figshare, Dryad, OpenNeuro); set it to the article DOI or `null`.
- Fix supplement `order` to match the paper's numbering; decide `data` versus `unsorted` for
  unrecognized items. Add links the scanner missed, with `found_in` and a reason.
- Fill `data_collection` (start, end, verbatim `source_quote`, `page`) from the methods, or
  leave it null if the paper does not say.
- Fill `reviewed_by` last: your model name, or `human` if the user reviewed it.
- `accept_failures` (top level, after `run`): only for a problem `review` prints that cannot
  be fixed (embargoed registration, a dataset far over the size policy, a host with no fetcher
  whose files you placed by hand under `data/<name>/`). The key is the printed item string;
  the reason must be non-empty and say what the auditor will be missing. Accepted gaps appear
  under "Prep review" in `README.md` for every auditor.

`run` refuses while `reviewed_by` is empty, any `needs_review` remains, there is not exactly one
`paper`, a role or class is not a known value, supplement `order`s are not distinct integers,
a listed path does not exist, or an `accept_failures` entry has no reason;
fix each listed item in `<raw>/prep.yaml`, then repeat the dry run.

## Runs

An audit never works in `prepared/`. Each audit attempt gets its own blinded copy:

```zsh
cd /abs/corpus
uv run ~/.claude/skills/audit-prep/scripts/new_run.py Smith_2021 --model <model-name>
```

(or pass `--root /abs/corpus` from elsewhere; `--runs-root /abs/dir` puts runs outside
Dropbox). It clones the prepared folder to `runs/Smith_2021/<run_id>/` (APFS clone, rsync
fallback), restores write permission, creates `audit/`, writes `run.json` (no model name), sets
the Dropbox-ignore attribute, appends the model mapping to `registry.jsonl`, and prints the run
path. `cd` into that printed path. Check a folder before auditing it:

```zsh
uv run ~/.claude/skills/audit-prep/scripts/verify_run.py /abs/corpus/runs/Smith_2021/<run_id>
```

It prints one of `not_prepared`, `prepared_not_run`, `run_ok`, `run_dirty`, `run_modified`,
then details; exit 0 only for `run_ok`. `run_modified`: a manifest-listed file, or `manifest.json`/`README.md` themselves, changed or is
missing.
`run_dirty`: a file outside `audit/` that is not in the manifest (Finder and Dropbox metadata such as `.DS_Store` are ignored). Either way, do not audit it;
make a new run.

Blinding rules:

- Start the audit session with the corpus root as the working directory so `.claude/settings.json` applies; then `cd` into the run folder. `prep.py init` writes the deny rule `Read(/registry.jsonl)` into the corpus root's
  `.claude/settings.json`; Claude Code loads project settings only from the session's starting
  directory, and the leading `/` anchors the rule there, so it still applies after the `cd`.
- Never read `registry.jsonl`, and never look in another run folder.
- Nothing inside a run folder may name the *auditing* model: not file names, not paths, not
  report text. `prepared_by` (the model or person who reviewed `prep.yaml`) is present in every
  run of a paper alike and does not identify the auditor; the audit's model identity lives only
  in `registry.jsonl`.
- All audit output goes under `audit/` in the run. `verify_run.py` ignores `audit/`, so an
  interrupted audit resumes in the same run and still shows `run_ok`.
- Graders compare runs blind and unblind only by consulting the registry.

## What prep does not do

- Read the paper for claims, extract statistics, or any other audit work.
- Install or run the authors' code or their R or Python environments.
- Download raw neuroimaging datasets of arbitrary size: sources above the size caps (500 MB per
  file, 5 GB per source; video and audio skipped) are inventoried as `listed_only`.
- Fetch from hosts without a fetcher; those are `unsupported` in the manifest.
- Delete anything the user supplied, rename paper folders, or blind a model to its own identity.

## Gotchas

- docling runs via `uvx`; its first run downloads models and is slow. If it fails, the
  structured conversion is recorded as `failed` and the rest of prep continues.
- Run folders carry the `com.dropbox.ignored` attribute so Dropbox does not upload a copy per
  model; `prepared/` syncs. Use `--runs-root` if the corpus is not in Dropbox.
- `scan` overwrites `prep.yaml` without asking. Never re-scan a folder whose `prep.yaml` has
  been reviewed; back it up first if you must.
- In zsh, `path` is tied to `PATH`: never use it as a loop variable.
- `run` moves the raw folder, which resets a shell whose cwd was inside it. Always pass absolute
  paths, and never `cd` into a raw folder before running prep.
- A finalized prepared folder is read-only and `run` refuses it ("already finalized"). Check
  `prep.py review` and the warnings before finalizing.
