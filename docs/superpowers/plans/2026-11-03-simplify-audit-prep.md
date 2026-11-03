# Simplify audit preparation and intake

> **For agentic workers:** Use superpowers:executing-plans for implementation.

**Goal:** Preserve a common prepared starting point while allowing each auditor to discover additional evidence.

**Architecture:** Raw inputs stay in place. Copy selected material into the existing unfinalized prepared directory; finalization freezes it. Run creation remains an operator tool, outside evaluated audit sessions. Auditors consume runs and record additional evidence under audit/.

**Tech Stack:** Existing Python scripts, uv, pytest, YAML, Markdown and Quarto.

**Spec:** Approved review and follow-up discussion in this session. Implementation choices: reuse the existing draft/finalized distinction rather than add another directory or workflow engine; preserve existing fetchers and conversion retry support.

## Constraints

- Use uv for commands and pytest for tests. Commit failing tests before implementation.
- Keep functions small; no code or imports in __init__.py.
- Preserve raw inputs and finalized snapshots. Never modify the autoaudit example corpus.
- Allow audit-time retrieval, including retrying failed prep sources, within resource limits.

## Review focus

- Skipped files and nested symlinks must not enter benchmark inputs.
- Changed file selections must not reuse stale copied inputs or conversions.
- Failed preparation must be resumable without moving or losing raw inputs.
- Operator registry must not be required in the auditor's workspace.
- Additional evidence must remain distinguishable from supplied evidence.

## Tasks

- [x] Tests first: raw preservation, excluded files, local selection changes, symlinks, integrity waivers, operator setup and audit retrieval contracts. Update old tests only where the approved requirements change. Run RED and commit tests.
- [x] Simplify layout to explicit copies from raw sources; remove collision parking and moved-folder recovery. Keep conversions/download retries. Reject symlinks. Make review structural failures non-waivable. Run focused tests.
- [x] Separate operator run setup from audit intake. Remove Claude-specific startup assumptions. Document supplemental retrieval and add provenance slots to reports. Make structured conversion a plan option; keep default enabled for compatibility. Move specialized reproducibility recipes to a reference. Run focused tests.
- [x] Run the full suite, perform a fresh review and fix consequential findings with RED/GREEN tests. Report changes and limitations.

## Execution notes

- Existing review CLI already rejects run/plan acceptance keys; harden the review function itself rather than introducing another gate.
- Working in the clean current checkout; no separate worktree needed for this maintenance task.
- Tests committed before their implementations: c90f7bd (13 code failures and 7 documentation failures), 6cf2b0e (7 boundary/conversion failures), 9530e44 (8 review regressions).
- Skill scenarios confirmed raw/prepared-without-run inputs stop for operator setup, while verified runs permit additional retrieval and retries with provenance.
- Fresh review identified stale remote sources, untracked raw statements, and symlinked roots. Fixed with the final RED/GREEN pass, along with checking symlinks before finalization writes.
- Ruling: require a fresh draft for local selection/content or conversion-choice changes and for changing/removing requested retrieval sources. This avoids deletion/invalidation machinery; rebuilding may repeat downloads. Additions and retries remain supported.
- Ruling: retain the existing draft/finalized directory distinction and operator new_run tool; no workflow engine or additional staging directory introduced.
- Final validation: `uv run --no-sync pytest -q` — 357 passed, 5 existing PyMuPDF/SWIG deprecation warnings. Real Quarto and Docling checks passed outside the sandbox, which otherwise blocks their OS/tool-cache access. `git diff --check` clean.
