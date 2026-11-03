# Audit Consensus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A new `audit-consensus` skill and a `consensus.sh` launcher. The launcher reconciles all completed blinded audits of one paper into a consensus report. Before it does, it redacts model identities from the source runs.

**Architecture:** Python helpers (`audit-consensus/scripts/`, stdlib only, run with `uv run`) do the deterministic work. They discover runs, check completion, check manifests, redact model names, create the consensus folder, and attach the model mapping. A bash launcher, modeled on `reproducibility-audit/scripts/new_run.sh`, calls the helpers and starts the agent headless. It then attaches the run→model mapping and re-renders the report. The agent's behaviour lives in `SKILL.md` and `templates/consensus_template.qmd`.

**Tech Stack:** bash, Python ≥3.11 (stdlib), pytest, uv, Quarto/R (agent side only).

**Spec:** `docs/superpowers/specs/2026-11-03-audit-consensus-design.md`

## Global Constraints

- Default model: `claude-opus-5-5`.
- Launcher usage: `consensus.sh [--interactive] <paper_id> [<model>]`, run from the corpus root (the directory holding `.autoaudit-root`).
- Harness selection, by lowercased model name: `*claude*` → Claude Code, `*gpt*` → Codex, else opencode with `openrouter/<model>`. The flags match `new_run.sh` exactly.
- Runs are discovered from disk under `runs/<paper_id>/`, never from `registry.jsonl`. The registry is used only to look up models.
- Completed run: `audit/audit.qmd` and `audit/audit.html` both exist. If `audit/agent_log.jsonl` exists, its last JSON event must also be a completion event.
- Fewer than 2 completed runs, or completed runs that disagree on `manifest_sha256`, stops the launcher with a non-zero exit and no agent.
- Redaction: case-insensitive. Each run's own model aliases become its `run_id`. Any other paper-run model alias becomes `[redacted-model]`. Only files under `audit/` are ever modified. A match outside `audit/` stops the launcher before anything is modified.
- Output folder: `runs/<paper_id>/consensus/<consensus_id>/`. It is new on every invocation and never overwritten.
- Only the launcher modifies source runs (redaction). The agent writes only inside its consensus folder.
- Per user CLAUDE.md: `uv run` for every command. No code in `__init__.py`. Pytest functions, not classes. Commit tests before implementation. Short functions.

## Review Focus

1. **A run whose audit is still in progress**, for example `gvisp3bd` today. It is skipped with a warning naming it, and its log is never redacted. Pinned in Task 1 and Task 3.
2. **A discovered run with no registry entry**, so its own model is unknown. Blinding can't be guaranteed, so prepare stops and names the run. Pinned in Task 3.
3. **Running consensus twice on the same paper**, including twice in the same second. The second redaction finds nothing and changes nothing. The two consensus folders are distinct, and the first is untouched. Pinned in Task 3.
4. **A read-only file under `audit/` that needs redaction.** It gets redacted and its original mode is restored. Pinned in Task 2.
5. **A corpus root path containing spaces.** Everything works. Pinned in Task 4: the fixture root is `my corpus`.

---

### Task 0: Branch and commit the spec

- [ ] **Step 1:** `git checkout -b audit-consensus`
- [ ] **Step 2:** Commit the spec:

```bash
git add docs/superpowers/specs/2026-11-03-audit-consensus-design.md docs/superpowers/plans/2026-11-03-audit-consensus.md
git commit -m "Add audit-consensus design and plan"
```

### Task 1: Run discovery and validation

**Files:**
- Create: `audit-consensus/scripts/discover.py`
- Modify: `tests/conftest.py`. Add `audit-consensus/scripts` to `sys.path` next to the existing audit-prep entry.
- Test: `tests/test_consensus_discover.py`

**Interfaces:**
- Produces:
  - `class ConsensusError(Exception)`
  - `find_runs(paper_runs: Path) -> list[Path]`: subdirectories containing `run.json`, sorted by name. `consensus/` has no `run.json`, so it is excluded.
  - `log_finished(log: Path) -> bool`
  - `is_completed(run: Path) -> bool`
  - `completed_runs(paper_runs: Path) -> tuple[list[Path], list[Path]]`: returns `(completed, skipped)`.
  - `check_same_manifest(runs: list[Path]) -> None`: raises `ConsensusError`.
  - `COMPLETION_EVENTS`, a module constant.

Test helper: a `make_run(paper_runs, run_id, manifest="m1", html=True, log_lines=None)` fixture-factory in the test file. It writes `run.json` (`{"run_id":…, "manifest_sha256": manifest}`), `audit/audit.qmd`, optionally `audit/audit.html`, and optionally `audit/agent_log.jsonl`.

- [ ] **Step 1: Write the failing tests**
  - `test_find_runs_ignores_dirs_without_run_json`: `a1`, `b2`, a `consensus/` dir, and a stray dir with no `run.json` → `[a1, b2]`.
  - `test_run_without_html_is_not_completed`
  - `test_run_without_log_is_completed`: html plus qmd and no log → True. These are interactive runs.
  - `test_claude_result_event_finishes_log`: last line `{"type":"result","subtype":"success"}` → True.
  - `test_codex_turn_completed_finishes_log`: last line `{"type":"turn.completed"}` → True.
  - `test_opencode_stop_finishes_log`: last line `{"type":"step_finish","part":{"reason":"stop"}}` → True. With `"reason":"tool-calls"` → False.
  - `test_unfinished_log_means_in_progress`: a log ending in `{"type":"step_start"}`, with html present → not completed. `completed_runs` returns it in `skipped`.
  - `test_trailing_garbage_line_is_ignored`: the last *parseable* JSON line decides.
  - `test_mismatched_manifests_raise`: `ConsensusError` whose message names both run IDs.

- [ ] **Step 2:** `uv run pytest tests/test_consensus_discover.py -v`. Expected: FAIL (ImportError).
- [ ] **Step 3: Commit the tests.** `git add tests/ && git commit -m "Test consensus run discovery"`
- [ ] **Step 4: Implement `discover.py`.** `COMPLETION_EVENTS` is a predicate over the parsed event. It returns True for type `result`, type `turn.completed`, or type `step_finish` with `part.reason == "stop"`. Before relying on the Codex and opencode markers, check them against a real log if one is available.
- [ ] **Step 5:** `uv run pytest tests/test_consensus_discover.py -v`. Expected: PASS.
- [ ] **Step 6: Commit.** `git commit -am "Discover completed audit runs for consensus"` (stage the new file first)

### Task 2: Registry lookup and redaction

**Files:**
- Create: `audit-consensus/scripts/redact.py`
- Test: `tests/test_consensus_redact.py`

**Interfaces:**
- Consumes: `ConsensusError` from `discover.py`.
- Produces:
  - `load_models(registry: Path, paper_id: str) -> dict[str, str]`: run_id → model, with duplicate lines collapsed (the last entry wins).
  - `aliases(model: str) -> list[str]`: the full model string plus its part after the last `/`, deduplicated and sorted longest first.
  - `plan_redaction(run: Path, own: str, others: list[str]) -> dict[str, list[str]]`. Keys are `own_aliases` and `other_aliases`, each sorted longest first. Every alias of `own` is removed from `other_aliases`.
  - `outside_audit_leaks(run: Path, strings: list[str]) -> list[str]`: relative paths outside `audit/` whose bytes contain any string, case-insensitive.
  - `redact_run(run: Path, run_id: str, plan: dict) -> dict[str, int]`: relative path → number of replacements, for changed files only.
  - `remaining_leaks(run: Path, strings: list[str]) -> list[str]`: relative paths anywhere in the run.
  - `OTHER_PLACEHOLDER = "[redacted-model]"`.

- [ ] **Step 1: Write the failing tests**
  - `test_load_models_dedupes_and_filters_paper`: a registry with a duplicated `a1` line and another paper's run → `{"a1": "claude-opus-5-5", "b2": "google/gemini-4-argon"}`.
  - `test_aliases_strip_provider_prefix`: `aliases("google/gemini-4-argon") == ["google/gemini-4-argon", "gemini-4-argon"]`, and `aliases("claude-opus-5-5") == ["claude-opus-5-5"]`.
  - `test_redacts_own_and_other_models_in_log`: `audit/agent_log.jsonl` contains `"model":"Claude-Opus-5-5"` and `see gemini-4-argon`. Run `a1` (own model claude) → the text contains `"model":"a1"` and `see [redacted-model]`, and the counts are `{"audit/agent_log.jsonl": 2}`.
  - `test_redacts_every_text_file_under_audit`: a hit in `audit/notes/x.md` is redacted too.
  - `test_full_alias_replaced_before_bare`: `openrouter/google/gemini-4-argon` becomes `openrouter/[redacted-model]`, not `openrouter/google/[redacted-model]`.
  - `test_outside_audit_leak_is_reported_not_changed`: a model string in `paper/paper.txt` → `outside_audit_leaks` returns `["paper/paper.txt"]`, and the file's bytes are unchanged after `redact_run`.
  - `test_binary_file_hit_is_left_and_reported`: an `audit/cache/x.rds` holding invalid UTF-8 plus the model bytes is unchanged, and `remaining_leaks` lists it.
  - `test_redaction_is_idempotent`: a second `redact_run` returns `{}`.
  - `test_read_only_file_is_redacted_and_mode_restored` (Review Focus 4): the file mode is `0o444` before and after, and the content is redacted.
  - `test_mtime_untouched_for_files_without_hits`.

- [ ] **Step 2:** `uv run pytest tests/test_consensus_redact.py -v`. Expected: FAIL.
- [ ] **Step 3: Commit the tests.**
- [ ] **Step 4: Implement `redact.py`.**
  - Read each file as bytes. If it doesn't decode as UTF-8, skip it during redaction; the rescan still sees it.
  - Replace with `re.sub` using `re.escape(alias)` and `re.IGNORECASE`, applying all of `own_aliases` before `other_aliases`, longest first.
  - Write only when the text changed. To write, temporarily add `0o200`, write, then restore the original mode.
  - Skip symlinks.
- [ ] **Step 5:** Run the tests. Expected: PASS.
- [ ] **Step 6: Commit.**

### Task 3: `consensus.py` CLI (`prepare`, `attach-models`)

**Files:**
- Create: `audit-consensus/scripts/consensus.py`, with the PEP 723 header like `new_run.py`.
- Test: `tests/test_consensus_cli.py`

**Interfaces:**
- Consumes: Tasks 1 and 2.
- Produces:
  - `prepare(root: Path, paper_id: str, now: datetime | None = None, rng: random.Random | None = None) -> Path`
  - `make_consensus_id(now: datetime, rng: random.Random) -> str`: `YYYYMMDDTHHMMSSZ-xxxx`, where `xxxx` is 4 characters from new_run's `ALPHABET`. It sorts chronologically.
  - `attach_models(root: Path, consensus_dir: Path) -> Path`: writes `run_models.json` as `{run_id: model}` for the runs listed in `inputs.json`, and returns its path.
  - CLI:
    - `consensus.py prepare <paper_id> [--root R]` prints the consensus directory on stdout and warnings on stderr. Exit 0 on success, 2 on `ConsensusError`, with `error: …` on stderr.
    - `consensus.py attach-models <consensus_dir> [--root R]`.
    - The root defaults to cwd and must contain `.autoaudit-root`.
  - `inputs.json` schema: `{"consensus_id", "paper_id", "created", "runs": [{"run_id", "audit_qmd_sha256"}], "skipped": [run_id…], "redactions": {run_id: {path: count}}}`. It must never contain model names.

`prepare` runs in this order, and nothing is modified before step 5:
1. Discover runs and split them into completed and skipped. Warn about each skipped run on stderr.
2. Require at least 2 completed runs.
3. Check that the manifests match.
4. Load models. Every completed run must have one. Collect all aliases, then check `outside_audit_leaks` for every run.
5. Redact every completed run.
6. Rescan with `remaining_leaks` and stop if anything remains.
7. Create `consensus/<id>/`.
8. Write `inputs.json`.

- [ ] **Step 1: Write the failing tests.** They use a tmp corpus fixture with `.autoaudit-root`, `registry.jsonl`, and runs built with the Task 1 factory.
  - `test_prepare_creates_folder_and_inputs`: the dir is under `runs/P/consensus/`, `inputs.json` lists both runs with sha256 values for their `audit.qmd`, and `"claude" not in inputs.json text`.
  - `test_prepare_skips_in_progress_run_with_warning` (Review Focus 1): three runs, one with an unfinished log. That run's ID appears in the stderr warning and in `skipped`, and its log bytes are unchanged.
  - `test_prepare_needs_two_completed_runs`: exit 2, a message containing "at least 2", and no `consensus/` dir.
  - `test_prepare_stops_on_run_missing_from_registry` (Review Focus 2): exit 2, the message names the run, and no files are redacted in either run.
  - `test_prepare_stops_on_leak_outside_audit`: exit 2, the message names the path, and nothing is redacted.
  - `test_prepare_stops_if_leak_survives_redaction`: binary hit → exit 2, and no consensus dir.
  - `test_prepare_twice_gives_distinct_folders` (Review Focus 3): pass the same `now` with different `rng` seeds. The folders are distinct, the first `inputs.json` is unchanged, and the second records empty redactions.
  - `test_consensus_ids_sort_chronologically`
  - `test_attach_models_writes_mapping`: `run_models.json == {"a1": "claude-opus-5-5", "b2": "gpt-5.6-sol"}`.
  - `test_cli_requires_corpus_root`: exit 2, and the message mentions `.autoaudit-root`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3: Commit the tests.**
- [ ] **Step 4: Implement `consensus.py`.** Keep each pipeline step its own function.
- [ ] **Step 5:** Run. Expected: PASS.
- [ ] **Step 6: Commit.**

### Task 4: `consensus.sh` launcher

**Files:**
- Create: `audit-consensus/scripts/consensus.sh` (executable)
- Test: `tests/test_consensus_sh.py`, using the same fake-agent/PATH-stub pattern as `tests/test_new_run_sh.py`.

**Interfaces:**
- Consumes: the `consensus.py prepare` and `attach-models` CLIs, called with `uv run "$scripts/consensus.py" …`, where `$scripts` is the launcher's own directory.
- Harness functions (`harness`, `launch_headless`, `launch_interactive`, `print_result`) are copied from `new_run.sh`, not shared. This is the designer's call: factoring them out would mean changing `new_run.sh` and the existing test that `reproducibility-audit/scripts` holds only `new_run.sh`.
- Claude gets one extra flag in both modes: `--add-dir <corpus>/runs/<paper_id>`. Without it, auto mode can't read the sibling run folders.

Behaviour:
1. Parse the arguments. Usage errors exit 2.
2. Require `.autoaudit-root` in the cwd.
3. Run `prepare`. On failure, exit 1 with its stderr and no agent.
4. `cd` to the consensus dir.
5. Run the agent. Headless, the transcript goes to `agent_log.jsonl` in the consensus dir and the result is printed. Interactive does *not* `exec`, so the post-steps still run.
6. Then always run `attach-models`. If `consensus.qmd` exists, run `quarto render consensus.qmd`.
7. Exit with the agent's status.

The prompt (exact copy):

```
Use the audit-consensus skill to reconcile the audits of <paper_id>.

The current directory is a new consensus folder; inputs.json lists the completed runs, which are in ../../<run_id>/. Read the source runs but never modify them. Never read registry.jsonl.

Write all output in the current directory. Render consensus.html locally and give me the file path when done. Do not publish it anywhere.
```

- [ ] **Step 1: Write the failing tests.** Use a fixture corpus at `tmp_path / "my corpus"` (Review Focus 5) with two completed runs and a registry. Stub `claude`/`codex`/`opencode`/`quarto` on PATH, and use the real `consensus.py` copied alongside the script along with `discover.py`/`redact.py`.
  - `test_script_is_executable`
  - `test_wrong_arguments_print_usage`, parametrized over `()` and `("a","b","c")`.
  - `test_must_run_from_corpus_root`
  - `test_default_model_is_claude_opus_5_5`: with only `<paper_id>`, the claude stub gets `--model claude-opus-5-5`.
  - `test_claude_headless_flags`: `-p`, `--permission-mode auto`, `--output-format stream-json`, `--verbose`, and `--add-dir` equal to the paper's runs dir. The cwd is the consensus dir, and the prompt contains "Use the audit-consensus skill" and "Never read registry.jsonl".
  - `test_codex_and_opencode_harness_selection`: the flags match the `new_run.sh` tests.
  - `test_runs_redacted_before_agent_starts`: the fake agent writes `grep -ril claude-opus-5-5 <runs dir>` output to a file, and that file is empty.
  - `test_headless_log_in_consensus_dir_and_result_printed`
  - `test_models_attached_and_report_rendered_after_agent`: the fake agent creates `consensus.qmd`. Afterwards `run_models.json` exists, and the quarto stub recorded `render consensus.qmd` with the consensus dir as its cwd.
  - `test_no_render_when_agent_wrote_no_report`
  - `test_prepare_failure_launches_no_agent`: with only one run → exit 1 and the agent log is absent.
  - `test_agent_failure_status_propagates`: `FAKE_STATUS=4` → exit 4, and the models are still attached.
  - `test_interactive_runs_post_steps`
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3: Commit the tests.**
- [ ] **Step 4: Implement `consensus.sh`.** Use `set -euo pipefail`, short functions, and the same style as `new_run.sh`.
- [ ] **Step 5:** Run. Expected: PASS.
- [ ] **Step 6: Commit.**

### Task 5: Skill text, report template, and docs

**Files:**
- Create:
  - `audit-consensus/SKILL.md`
  - `audit-consensus/README.md`
  - `audit-consensus/templates/consensus_template.qmd`
- Modify:
  - `tests/test_skill_text.py`: append the tests.
  - The top-level `README.md`: a launcher section next to `new_run.sh`.

**SKILL.md must cover these stages**, and its text must use the spec's wording for the definitions:

1. **Intake.** Read `inputs.json`. Never read `registry.jsonl`, and never guess at authorship. Refer to audits by run ID only.
2. **Extract.** For each run, list its claims, its findings, and what it checked and found clean, from the findings, robustness table, clean-checks and verification appendices.
3. **Cross-walk.** Match claims and findings across runs by meaning, not by ID.
4. **Classify**, using the spec's three statuses and its rule for three or more runs. Any explicit clean result → **Disputed**. **Converged** needs ≥ 2 raising the finding and none finding it clean. Never decide by majority or by confidence.
5. **Adjudicate.** For disputed and untested findings, use new analyses in `R/` with output in `results/`. Source code is copied into the folder before it is re-run, and the outcome is **confirmed**, **partly confirmed**, or **refuted**. Spot-check converged findings whose magnitudes or severities differ. Cache heavy results so that a re-render reproduces the same numbers.
6. **Severity and conclusion change.** Use the major / moderate / minor scale. A finding changes a conclusion **only when the claim's consensus verdict falls to weak or unsupported**; a downgrade such as strong → moderate is reported but does not count.
7. **Report.** Follow the template order.
8. **Render and verify** every number against the rendered output.

Scope limits: no new hunting for issues (incidental issues go in "Noticed during adjudication", unadjudicated). No ratings of audits. The rules on additional evidence are the same as in reproducibility-audit.

**The template's sections, in order:**
- The disclaimers: the AI-generated callout and the preliminary-and-unvetted callout, worded like `audit_template.qmd`.
- Bottom line
- Claims (columns: consensus claim, consensus verdict, then one verdict column per run ID, then why verdicts differ)
- Confirmed issues
- Disputed and refuted findings
- Agreed minor issues
- Noticed during adjudication
- Appendix: Finding cross-walk, Adjudication analyses, Provenance, Session info

Provenance includes a chunk that reads `run_models.json` if it exists. Otherwise it prints "Model mapping attached after the consensus run." It also carries the known-limitation sentence: the consensus model may also be one of the auditing models.

- [ ] **Step 1: Write the failing tests** in `test_skill_text.py`.
  - `test_consensus_skill_frontmatter_and_rules`: the text starts with `---\nname: audit-consensus\n` and contains `inputs.json`, `registry.jsonl`, `Disputed`, `Converged`, `partly confirmed`, `weak or unsupported`, and `strong → moderate`. It does not contain `letter grade`.
  - `test_consensus_template_sections_in_order`: assert the index order of the section headings listed above.
  - `test_consensus_template_is_blind`: it contains `run_models.json` and `"MODEL" not in t`.
  - `test_consensus_scripts_dir_contents`: the scripts are `consensus.py`, `consensus.sh`, `discover.py` and `redact.py`, ignoring `__pycache__`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3: Commit the tests.**
- [ ] **Step 4: Write `SKILL.md`, the template, and both READMEs.**
- [ ] **Step 5:** Run the full suite with `uv run pytest`. Expected: everything passes, except existing slow-marked tests that need external tools; those are unchanged.
- [ ] **Step 6: Commit.**
