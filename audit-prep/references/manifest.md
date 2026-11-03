# manifest.json (schema_version 1)

Written by `scripts/manifest.py`. All paths are relative to the prepared folder, POSIX separators. `README.md` is rendered from this file and never hand-edited.

## Top-level keys

| Key | Meaning |
|---|---|
| `schema_version` | Integer, currently 1. `is_prepared` requires equality. |
| `paper_id` | `<Paper>_<Year>` folder identifier. |
| `prepared_at` | UTC ISO timestamp. |
| `prep_versions` | Tool versions (`skill`, `docling`, `poppler`, `pandoc`), from `docs.tool_versions()`. `{}` until filled. |
| `prepared_by` | Model name or `human`; copied from `prep.yaml` `reviewed_by`. |
| `finalized` | `false` until preparation completes; `is_prepared` requires `true`. |
| `metadata` | `{doi, title, authors[], journal, published, relations[]}` or null if not fetched. |
| `documents` | `{paper, supplements[]}`. `paper` is null until set. |
| `links` | `[{url, canonical, found_in:[{file,page}], class, role, decision, fetched_to, status, reason}]`. |
| `preregistration` | `[{source, id, path, date_registered, hash_verified, status}]`. |
| `data_collection` | `{start, end, source_quote, page}` or null. |
| `code` | `[{url, path, commit, branch, cloned_at, status}]`. |
| `data` | FetchResult-shaped items, see below. |
| `local_data` | Author-supplied data, see below. |
| `unsorted` | `[{original_path, moved_to, reason}]`; files moved to `unsorted/<Paper_Year>/`. |
| `files` | `[{path, size, sha256}]` for every regular file under the prepared folder except top-level `manifest.json` and `README.md`. Symlinks are skipped; `.git` contents and `prep.yaml` are included. Sorted by path. Used by `verify_run.py`. |
| `warnings` | `[str]`. |

## documents entries

`{original_name, path, pages, conversions}` where `conversions` maps `text`, `pages`, `structured`, `statements` to a step status.

## local_data entries

- Directory: `{original_path, path}`.
- Archive: `{original_path, path, archive: true, extracted}` with `extracted` one of `ok | pre-existing | skipped | failed`.
- Nested archive found inside an extraction: `{path, nested_archive: true}` (not extracted).

## data entries

`{source, id, path, status, files, reason, meta}`; each file is `{path, size, sha256 | remote_hash, downloaded: bool}`.

## Status vocabularies

- Per-step statuses (conversions, code): `ok | skipped | failed | not_applicable`.
- `links` status: the status of the fetch record it produced (`data`, `preregistration` or `code` vocabulary), or `skipped` for roles that are never fetched (`skip`, `unknown`, Crossref relation DOIs). `fetched_to` is set only when something is on disk.
- `data` status: `ok | partial | listed_only | failed | unsupported`.
  - `partial`: some files downloaded, others skipped by size policy.
  - `listed_only`: files listed but none downloaded.
  - `unsupported`: no fetcher for the source.
- `preregistration` status: `ok | hash_mismatch | unverified | failed`.
