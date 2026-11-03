# manifest.json (schema_version 1)

Written by `scripts/manifest.py`. All paths are relative to the prepared folder, POSIX separators. `README.md` is rendered from this file and never hand-edited.

## Top-level keys

| Key | Meaning |
|---|---|
| `schema_version` | Integer, currently 1. `is_prepared` requires equality. |
| `paper_id` | `<Paper>_<Year>` folder identifier. |
| `prepared_at` | UTC ISO timestamp. |
| `prep_versions` | `skill`: the audit-prep git short commit (null when the skill is not a git checkout); tool versions `pdftotext`, `pdftoppm`, `pandoc`, `zstd`, `docling`, `git` from `docs.tool_versions()` (null when a tool is missing). `{}` until filled. |
| `prepared_by` | Model name or `human`; copied from `prep.yaml` `reviewed_by`. |
| `finalized` | `false` until preparation completes; `is_prepared` requires `true`. |
| `metadata` | `{doi, title, authors[], journal, published, relations[]}` or null if not fetched. |
| `documents` | `{paper, supplements[]}`. `paper` is null until set. |
| `links` | `[{url, canonical, found_in:[{file,page}], class, role, needs_review, reason, status, fetched_to}]`: the reviewed `prep.yaml` link plus its fetch `status` and `fetched_to`. |
| `preregistration` | `[{source, id, path, date_registered, status, reason}]`. OSF registrations also carry `title`, `type`, `withdrawn` and `files: [{name, sha256_expected, sha256_actual, verified}]`, where per-file `verified` is `true`, `false` (hash mismatch) or `null` (no frozen hash). |
| `data_collection` | `{start, end, source_quote, page}` or null. |
| `code` | `[{url, path, commit, branch, cloned_at, status, reason, zenodo_doi}]`; a non-GitHub code link is `{source, id, url, path: null, status: unsupported, files: [], reason}`. |
| `data` | FetchResult-shaped items, see below. |
| `local_data` | Author-supplied data, see below. |
| `unsorted` | `[{original_path, moved_to, reason}]`; files moved to `unsorted/<Paper_Year>/`. |
| `files` | `[{path, size, sha256}]` for every regular file under the prepared folder except top-level `manifest.json` and `README.md`. Symlinks and Finder/Dropbox metadata (`.DS_Store`, `Icon\r`, `.dropbox`, `.dropbox.cache`, at any depth) are skipped; `.git` contents and `prep.yaml` are included. Sorted by path. Used by `verify_run.py`. |
| `warnings` | `[str]`. |
| `review` | Null until `run` finishes; then `{status: ok\|failed, problems: [{kind, item, status, detail}], accepted: [{kind, item, status, detail, accepted_reason}], unused: [str]}`, recomputed by `finalize` (a finalized folder has `status: ok`). `kind` is `paper`, `conversion`, `metadata`, `local_data`, `preregistration`, `code` or `data`. `item` grammar: `paper`; `conversion <doc path> <name>`; `metadata crossref`; `local_data <path>`; `preregistration <source> <id>`; `code <url>`; `data <source> <id>`. |

## documents entries

`{original_name, path, pages, conversions}` where `conversions` maps `text`, `pages`, `structured`, `statements` to a step status.

## local_data entries

- Directory: `{original_path, path}`.
- Archive: `{original_path, path, archive: true, extracted}` with `extracted` one of `ok | pre-existing | skipped | failed`.
- Nested archive found inside an extraction: `{path, nested_archive: true}` (not extracted).

## data entries

`{source, id, path, status, files, reason, meta}`; each file is `{path, size, sha256 | remote_hash, downloaded: bool}`.

OpenNeuro (`source: openneuro`, `path` `data/openneuro_<dsid>`) is fetched as metadata only: `files` holds the root-level files (`dataset_description.json`, `participants.tsv`, `README`, `CHANGES`, ...); `meta` is `{scope: "metadata", tag, dataset_doi, name, subjects, modalities, total_files, size}`; the folder holds `dataset.json` (dataset, snapshot, description and summary), `README` and `files.json`, the full snapshot listing `{path, size, directory, annexed, url}`. Imaging files are never downloaded. `status` is `ok` when every root-level file downloaded, else `partial`.

## Status vocabularies

- Per-step statuses (conversions): `ok | skipped | failed | not_applicable`.
- `code` status: `ok | skipped | failed | unsupported`. `skipped`: the clone already exists. `unsupported`: a code link not on GitHub (reason "code links are fetched from GitHub only; fetch manually").
- `links` status: the status of the fetch record it produced (`data`, `preregistration` or `code` vocabulary), or `skipped` for roles that are never fetched (`skip`, `unknown`, Crossref relation DOIs). `fetched_to` is set only when something is on disk.
- `data` status: `ok | partial | listed_only | failed | unsupported`.
  - `ok`: every listed file was selected for download.
  - `partial`: some files selected, others dropped by the size or extension policy (or, for NeuroVault, an image download failed).
  - `listed_only`: files listed but none downloaded; `path` is null.
  - `unsupported`: no fetcher for the source.
- `preregistration` status: `ok | hash_mismatch | unverified | failed`. For OSF, `ok` means every file's `verified` is true; `hash_mismatch` means any is false; `unverified` means none is false but some is null or there are no files, with `reason` `embargoed`, `withdrawn` or `no files in registration` when that is why. Other sources are `ok` once saved, except an AsPredicted link that returns HTML instead of a PDF: it is saved as `<id>.html` with status `unverified`, reason "HTML returned, not a PDF; the link may need its view token".
