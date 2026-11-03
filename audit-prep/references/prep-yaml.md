# prep.yaml: the prep plan

`scan` writes a draft `prep.yaml` into the raw paper folder. The draft is
heuristic. A reviewer (a model or a human) settles every ambiguous item, then
`run` executes the plan. `run` refuses to start while anything is unresolved.
After the draft starts, new retrieval links can be added and existing sources retried.
Changing or removing a previously requested source requires a fresh draft, so stale
downloaded files cannot remain in the prepared snapshot.
Raw inputs stay in place; selected items are copied into a draft under `prepared/`.
After draft creation, its `prep.yaml` is authoritative, including when `run` is called
with the raw path. Edit links and acceptance reasons there. Changes to local file
selection or raw contents require moving the draft aside and starting a fresh draft.
The prep process does not delete existing drafts.

## Example

```yaml
schema_version: 1
paper_id: Bissett_2021
reviewed_by: null                  # model name or "human"; required before run
doi: 10.1126/sciadv.abf4355        # null -> the paper entry needs_review
structured_conversion: true        # choose consistently across the corpus
data_collection: {start: null, end: null, source_quote: null, page: null}
size_policy: {max_file_mb: 500, max_source_mb: 5000, skip_ext: [mp4, mov, avi, wav, mp3, m4a]}
files:
  - {path: sciadv.abf4355.pdf, role: paper, needs_review: false, reason: "DOI resolves to journal-article", order: null}
  - {path: abf4355_sm.pdf, role: supplement, order: 1, needs_review: false, reason: "name marker _sm"}
  - {path: .venv, role: unsorted, needs_review: false, reason: "residue", order: null}
links:
  - {url: "https://osf.io/abcde/", canonical: "https://osf.io/abcde", class: osf, role: data,
     needs_review: true, found_in: [{file: sciadv.abf4355.pdf, page: 3}], reason: "osf project or registration?"}
```

## Top-level fields

| Field | Meaning |
|---|---|
| `schema_version` | Plan format version. Currently `1`. Do not edit. |
| `paper_id` | The raw folder name, `<FirstAuthor>_<Year>`. Becomes `prepared/<paper_id>/`. |
| `reviewed_by` | Who reviewed the plan: the model name, or `human`. `scan` leaves it `null`; the reviewer must fill it. `run` copies it into the manifest as `prepared_by`. Nothing inside a run folder may name the *auditing* model. `prepared_by` (the model or person who reviewed `prep.yaml`) is present in every run of a paper alike and does not identify the auditor; the audit's model identity lives only in `registry.jsonl`. |
| `doi` | The paper's DOI: the first DOI on the first two pages of the paper PDF that Crossref reports as `journal-article`. Deposit DOIs (`10.5281/zenodo`, `10.17605/osf.io`, `10.6084/m9.figshare`, `10.5061/dryad`, `10.18112/openneuro`) are never candidates. `null` when no candidate is a journal-article; the paper entry is then `needs_review: true`. When Crossref could not be reached, the first candidate is kept unconfirmed and the paper entry needs review. Fill it in by hand if the reviewer finds it. |
| `data_collection` | When the data were collected, from the paper text. `start` and `end` are ISO dates (`YYYY-MM-DD`, or `YYYY-MM` when only the month is stated); `source_quote` is the verbatim sentence; `page` is its page number. Leave all four `null` if the paper does not say. |
| `structured_conversion` | Boolean, default `true`: request PDF Markdown, figure and table extraction. `false`: omit it, recorded as `not_requested`, while retaining text and page images. Choose consistently across the corpus before preparing model inputs. Changing it after a draft starts requires a fresh draft. Disabled conversion does not launch Docling, including for its version probe. |
| `size_policy` | Download caps. `max_file_mb` (default 500) is the largest single file downloaded; `max_source_mb` (default 5000) is the largest total per data source; `skip_ext` (default `mp4 mov avi wav mp3 m4a`) are never downloaded. Sources over a cap are inventoried, not downloaded. Raise a cap only with a reason. |
| `files` | One entry per top-level item in the raw folder. |
| `links` | One entry per distinct URL or DOI found in any PDF, text or link annotation. |
| `accept_failures` | Optional; add it after `run` only. A mapping of problem item → reason that acknowledges a prep problem which cannot be fixed. Keys are the item strings `prep.py review` prints (for example `data osf abcde`, `conversion paper/paper.pdf structured`, `preregistration osf x4c56`); each reason must be a non-empty string saying what the auditor will be missing. Accepted problems are listed under "Prep review" in `README.md`; a key matching no problem is reported as unused. Never accept a failure just to make the run pass. The keys `run` (an incomplete run) and `plan` (files, links or roles edited after `run`; `review` compares the plan with the hash `run` recorded, ignoring `accept_failures`) cannot be accepted: `run` refuses the plan; rerun `prep.py run` instead. The placeholder `<why this is acceptable>` that `review` prints is not a reason and is refused. A data link that failed before its id was parsed is keyed by its canonical URL (`data osf https://osf.io/`), while a parsed one is keyed by its id (`data osf abcde`); if a key stops matching after a rerun, `review` lists it as unused. `link <canonical>` problems can be accepted like any other key, but the right response is to rerun `prep.py run`. |

## `files` entries

| Key | Meaning |
|---|---|
| `path` | A top-level name in the raw folder; absolute paths, parent traversal and nested paths are rejected. A selected directory includes its contents. |
| `role` | `paper`, `supplement`, `data`, `archive`, `unsorted`, or `skip`. |
| `order` | Supplements only: 1, 2, ... sets the name `supplement_<order>`. `null` otherwise. |
| `needs_review` | `true` when the scanner could not decide. |
| `reason` | One line saying why the role was proposed (or chosen). |

Roles:

- `paper`: the published article. Exactly one is expected. The scanner picks
  the PDF with a DOI on its first two pages and no supplement marker in its
  name (deposit DOIs do not count), preferring the longest; Crossref must report
  `journal-article`.
- `supplement`: supplementary material, any file type. A filename stem token
  (split on `-`, `_`, `.`, whitespace; case-insensitive) that is a marker
  (`sm`, `som`, `mmc`, `esm`, `moesm`, `supp`, `supplement`), a marker plus
  digits (`mmc1`, `MOESM1`), or a word starting with `supp` (`supplementary`);
  or a PDF with the same DOI as the paper. Author names such as `Somerville`
  do not match. Numbered by filename.
- `data`: a directory or file the authors shared as data or code. A directory
  holding only data-like files (`.csv .tsv .json .mat .rds .rda .sav .nii
  .nii.gz .hdr .img .parquet .xlsx .txt .dat .h5 .npy .zip .tar*`) is `data`
  without review; any other directory is `data` with `needs_review: true`,
  reason "directory: data or residue?".
- `archive`: `.zip .tar .tar.gz .tgz .tar.zst .zst .7z`. Confirm it holds the authors' material, not residue.
- `unsorted`: residue, matched on the basename: environments and caches
  (`.git`, `.venv`, `venv`, `renv`, `.pytest_cache`, `__pycache__`,
  `node_modules`, `.ipynb_checkpoints`, `.Rproj.user`, `.Rhistory`, `.quarto`,
  `.DS_Store`), earlier audit output (`audit-*`, `*_files`, `figs_paper`,
  `*_audit.qmd`, `*_audit.html`, `osf_prereg`), and a `.txt` next to a
  same-stem PDF. Retained in the raw folder and excluded from prepared inputs; never deleted.
- `skip`: retain in the raw folder and exclude from prepared inputs. Needs a reason.

## `links` entries

| Key | Meaning |
|---|---|
| `url` | The link as found (trailing punctuation removed). |
| `canonical` | Normalized form used to deduplicate. OSF registry DOIs become `https://osf.io/<id>`. |
| `class` | Host class: `osf`, `github`, `zenodo`, `figshare`, `dryad`, `openneuro`, `neurovault`, `aspredicted`, `clinicaltrials`, `prospero`, `doi`, `other`. Deposit DOIs take their repository's class (`10.5281/zenodo` -> `zenodo`, `10.6084` -> `figshare`, `10.5061/dryad` -> `dryad`, `10.18112/openneuro` -> `openneuro`; role `data`). `run` picks the fetcher by `class`, so the reviewer may change it too (for example a `doi` link that is a Zenodo record becomes `zenodo`). Only `osf`, `zenodo`, `neurovault` and `openneuro` (metadata only) data and `github` code are fetched; other classes end `unsupported` with their URL. |
| `role` | `data`, `code`, `prereg`, `unknown`, or `skip`. Decides which fetcher `run` uses. |
| `needs_review` | `true` for OSF links the scan could not resolve, derived OSF parent-project links, GitHub, bare DOIs and unknown hosts. |
| `found_in` | Every `{file, page}` where the link occurs. |
| `reason` | Why the role was proposed, or the reviewer's one-line justification. |

The paper's own DOI is pre-set to `role: skip` with reason "the paper's own doi" only
when Crossref confirmed it as a `journal-article`; an unconfirmed `doi` keeps its link's
normal class and role with `needs_review: true`.
A known data or code host with no identifier (for example `https://osf.io/`, left
when a URL wraps across lines) is pre-set to `role: skip` with reason "bare host,
no identifier (likely a line-wrapped URL)"; check that the full link is listed too.

OSF ids are resolved at scan time (`GET /v2/guids/<id>/`), so an `osf` link
says what it names, with `needs_review: false`: a project gets `role: data`,
reason `osf project "<title>"`; a registration gets `role: prereg`, reason
`osf registration "<title>"`; a single file gets `role: data`, reason
`osf file <name> in project <node id>`, and `run` downloads just that file to
`data/osf_<file id>/<path in project>`. For every project that holds linked
files and is not itself listed, the scan adds a derived link
`https://osf.io/<node id>` (`class: osf`, `role: data`, `needs_review: true`,
`found_in` the union of its files' pages, reason "parent project of osf file
links <ids>; fetch the whole project?"). Decide whether the auditor needs the
whole project. When the parent project is fetched, set the individual file
links to `role: skip` with reason `contained in osf_<node id>` to avoid
duplicate copies (keeping both is harmless but noisy); otherwise set the
parent to `role: skip`. A project already linked in any URL form (for example
`https://osf.io/<node id>/files/osfstorage`) gets no derived link. If
resolution failed (offline, private or unknown id), the link keeps what the
scanner set from its URL: a plain `https://osf.io/<id>` link keeps "osf
project or registration?" with `needs_review: true`, and a
`.../registrations/<id>` URL stays pre-set to `role: prereg` with
`needs_review: false`. A guid of another kind (preprint, user) is left
unchanged the same way. A registration left at `role: data` ends `failed` at
`run` with reason "https://osf.io/<id> is a registration; set role: prereg".

## Review rules

Read the paper text and `statements.md` before editing. It holds the verbatim
statements found under data availability, code availability, preregistration,
open practices, funding and acknowledgements headings (funding often sits in
the acknowledgements), with page numbers. If none was found it says so; then
read the paper text for them directly, because run-in headings in two-column
layouts are often missed.

1. **Settle every `needs_review`.** Decide the role, set `needs_review: false`,
   and rewrite `reason` as a one-line justification citing the page or
   statement that decided it.
2. **Never delete a line.** A file or link that should not be fetched or copied
   gets `role: skip` with a reason. Deleting lines hides what the scanner saw.
3. **OSF: prereg or data?** An `osf.io/<id>` link (or OSF registry DOI
   `10.17605/OSF.IO/<ID>`) can be a project or a registration. Use the
   sentence around it: "preregistered at", "registration", "prereg" means
   `role: prereg`; "data are available at", "materials", "code" means
   `role: data`. If one id is the registration of another, keep both with
   their own roles.
4. **GitHub: the paper's code or a cited tool?** A repository the authors say
   holds their analysis code (code availability statement, "our code") is
   `role: code`. A tool, package or someone else's repository that the paper
   only cites or used is `role: skip`, reason "cited tool".
5. **Bare DOIs and other hosts.** A DOI of a dataset (Zenodo, Dryad, Figshare)
   is `data`, with `class` set to its repository when the scanner left it `doi`; of a registration is `prereg`; of another article (a citation, a
   preprint) is `skip`. Unknown hosts are `skip` unless the paper names them as
   where its data or code live.
6. **Files.** Confirm the paper, and confirm `doi` is the article's own DOI, not a deposit DOI
   (a Zenodo, OSF, figshare, Dryad or OpenNeuro DOI is where the data live, not
   the paper); fix `order` so supplements follow the paper's own numbering; decide whether an unrecognized file or directory is `data` or
   `unsorted`. A paper without a DOI may still be the paper: set `doi` if the
   reviewer can find it, otherwise leave it `null` and say why in `reason`.
7. **Add missed links.** If the paper names a data, code or prereg location
   the scanner missed, add an entry with `found_in` pointing at the page and
   `reason` saying it was added by review.
8. **Fill `data_collection`** from the methods text (dates of recruitment or
   testing), quoting the sentence verbatim with its page.
9. **Fill `reviewed_by`** last: the model name, or `human`.

`run` checks the plan and refuses to start, listing each blocker, while
`reviewed_by` is empty, any entry has `needs_review: true`, no file or more
than one file has `role: paper`, a file or link `role` or a link `class` is not
one of the values listed above, a supplement `order` is missing, not an integer
or used twice, or a selected `files[].path` does not exist. Selected inputs must
contain only ordinary files/directories: symbolic links, including nested or broken
links, are rejected. Materialize needed targets before creating the draft.
