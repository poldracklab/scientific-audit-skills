# prep.yaml: the prep plan

`scan` writes a draft `prep.yaml` into the raw paper folder. The draft is
heuristic. A reviewer (a model or a human) settles every ambiguous item, then
`run` executes the plan. `run` refuses to start while anything is unresolved.

## Example

```yaml
schema_version: 1
paper_id: Bissett_2021
reviewed_by: null                  # model name or "human"; required before run
doi: 10.1126/sciadv.abf4355        # null -> the paper entry needs_review
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
| `reviewed_by` | Who reviewed the plan: the model name, or `human`. `scan` leaves it `null`; the reviewer must fill it. `run` copies it into the manifest as `prepared_by`. It never appears inside a run folder. |
| `doi` | The paper's DOI, found on the first two pages of the paper PDF. `null` when none was found; the paper entry is then `needs_review: true`. Fill it in by hand if the reviewer finds it. |
| `data_collection` | When the data were collected, from the paper text. `start` and `end` are ISO dates (`YYYY-MM-DD`, or `YYYY-MM` when only the month is stated); `source_quote` is the verbatim sentence; `page` is its page number. Leave all four `null` if the paper does not say. |
| `size_policy` | Download caps. `max_file_mb` (default 500) is the largest single file downloaded; `max_source_mb` (default 5000) is the largest total per data source; `skip_ext` (default `mp4 mov avi wav mp3 m4a`) are never downloaded. Sources over a cap are inventoried, not downloaded. Raise a cap only with a reason. |
| `files` | One entry per top-level item in the raw folder. |
| `links` | One entry per distinct URL or DOI found in any PDF, text or link annotation. |

## `files` entries

| Key | Meaning |
|---|---|
| `path` | Path relative to the raw folder. |
| `role` | `paper`, `supplement`, `data`, `archive`, `unsorted`, or `skip`. |
| `order` | Supplements only: 1, 2, ... sets the name `supplement_<order>`. `null` otherwise. |
| `needs_review` | `true` when the scanner could not decide. |
| `reason` | One line saying why the role was proposed (or chosen). |

Roles:

- `paper`: the published article. Exactly one is expected. The scanner picks
  the PDF with a DOI on its first two pages and no supplement marker in its
  name, preferring the longest; Crossref must report `journal-article`.
- `supplement`: supplementary material. Name markers (`supp`, `_sm`, `som`,
  `mmc`, `esm`, `moesm`, `supplement`, case-insensitive) or a PDF with the same
  DOI as the paper. Numbered by filename.
- `data`: a directory or file the authors shared as data or code.
- `archive`: `.zip .tar .tar.gz .tgz .tar.zst .zst .7z`. Confirm it holds the authors' material, not residue.
- `unsorted`: residue (`.git`, `.venv`, `.pytest_cache`, `__pycache__`,
  `.DS_Store`, a `.txt` next to a same-stem PDF). Moved to
  `unsorted/<paper_id>/`, never deleted.
- `skip`: leave in place and do nothing with it. Needs a reason.

## `links` entries

| Key | Meaning |
|---|---|
| `url` | The link as found (trailing punctuation removed). |
| `canonical` | Normalized form used to deduplicate. OSF registry DOIs become `https://osf.io/<id>`. |
| `class` | Host class: `osf`, `github`, `zenodo`, `figshare`, `dryad`, `openneuro`, `neurovault`, `aspredicted`, `clinicaltrials`, `prospero`, `doi`, `other`. |
| `role` | `data`, `code`, `prereg`, `unknown`, or `skip`. Decides which fetcher `run` uses. |
| `needs_review` | `true` for OSF non-registration URLs, GitHub, bare DOIs and unknown hosts. |
| `found_in` | Every `{file, page}` where the link occurs. |
| `reason` | Why the role was proposed, or the reviewer's one-line justification. |

The paper's own DOI is pre-set to `role: skip` with reason "the paper's own doi".

## Review rules

Read the paper text and `statements.md` (the verbatim data, code,
preregistration and funding statements with page numbers) before editing.

1. **Settle every `needs_review`.** Decide the role, set `needs_review: false`,
   and rewrite `reason` as a one-line justification citing the page or
   statement that decided it.
2. **Never delete a line.** A file or link that should not be fetched or moved
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
   is `data`; of a registration is `prereg`; of another article (a citation, a
   preprint) is `skip`. Unknown hosts are `skip` unless the paper names them as
   where its data or code live.
6. **Files.** Confirm the paper; fix `order` so supplements follow the paper's
   own numbering; decide whether an unrecognized file or directory is `data` or
   `unsorted`. A paper without a DOI may still be the paper: set `doi` if the
   reviewer can find it, otherwise leave it `null` and say why in `reason`.
7. **Add missed links.** If the paper names a data, code or prereg location
   the scanner missed, add an entry with `found_in` pointing at the page and
   `reason` saying it was added by review.
8. **Fill `data_collection`** from the methods text (dates of recruitment or
   testing), quoting the sentence verbatim with its page.
9. **Fill `reviewed_by`** last: the model name, or `human`.

`run` checks the plan and refuses to start, listing each blocker, while
`reviewed_by` is empty, any entry has `needs_review: true`, or no file has
`role: paper`.
