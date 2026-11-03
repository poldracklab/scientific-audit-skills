# Audit consensus — design

Date: 2026-11-03
Status: draft, awaiting approval

## Intent

Each paper in the autoaudit corpus is audited several times by independent, blinded
reproducibility-audit runs (different models, same prepared inputs). The operator needs to
know, per paper: **which major issues are confirmed across audits, how severe they are, and
whether they change the paper's major conclusions.** Reading N reports side by side and
reconciling them by hand is slow and error-prone, especially because the reports number their
claims and findings independently and differ in which analyses they ran.

The consensus tool reads all completed audits of one paper, reconciles them, and — where the
audits disagree or only one of them tested something — runs whatever additional analysis is
needed against the paper's data and code to settle the question. It produces one consensus
report per invocation.

### Worked example (Bissett_2021, two runs)

- Converged: Fig. 3A SSRT drop does not by itself evidence violations (both rate moderate,
  reached via estimator arithmetic vs independent-race simulation); n = 651 not 672 (minor);
  F(1,23)=7.51 reported p<.001 (is .012); "Auditory 1" duplicated.
- Agree in substance, different depth: moderator effects are hypothesis-generating (one
  ran Holm/BH, the other argued from Bayes factors).
- Single-audit, untested by the other: equal-dataset weighting (7/14 positive) only in
  `gcqq6n2r`; baseline dependence at 100 ms, Fig. 3B trial-excision reversal, omission
  coding only in `35r6ybjk`. These are what the consensus agent must check itself.
- Verdict disagreement on the central claim: "strong at 0–50 ms" vs "moderate pooled, weak
  generality". The consensus report must say which is right, and why, after checking.

## Goals

1. Classify every finding raised by any audit into exactly one status:
   - **Converged** — two or more audits raised it independently (matched by meaning, not ID).
   - **Disputed** — one audit raised it; another explicitly tested the same thing and found
     no problem. The consensus agent investigates why and resolves it.
   - **Single-audit, untested** — one audit raised it; no other audit looked. The consensus
     agent runs the check itself.
   Converged findings are also spot-checked when the audits disagree on magnitude or
   severity.
   With three or more runs, status is decided by the strongest contrary evidence, never by
   count *(designer's call)*: if **any** audit explicitly tested the point and found no
   problem, the finding is **Disputed** and must be adjudicated, however many audits raised
   it. **Converged** requires ≥ 2 raising it and none finding it clean. Audits that never
   looked are recorded in the cross-walk but do not change the status.
2. For disputed and untested findings, give an adjudication outcome: **confirmed**,
   **partly confirmed**, or **refuted**, backed by an analysis in the consensus folder (or,
   where no new analysis is needed, a pointer to the exact output in a source run that
   settles it).
3. For every confirmed or partly confirmed finding, state **severity** (using the
   reproducibility-audit report's major / moderate / minor scale) and **whether it changes
   a major conclusion**, naming the claim. **Definition (operator decided):** a finding
   changes a conclusion only when it moves that claim's consensus verdict to **weak** or
   **unsupported** (or equivalent wording such as "hypothesis-generating" for a claim the
   paper presents as established). A downgrade such as strong → moderate is reported but
   does *not* count as changing the conclusion. This applies to every claim in the merged
   claims table *(designer's call; the operator did not restrict it to claims the paper
   presents as central)*. The Bottom line lists every claim that crosses the threshold.
4. Merge the audits' claim lists into one consensus claim list (matched by meaning), with a
   consensus verdict per claim and each audit's original verdict shown beside it; explain
   every verdict disagreement.
5. Work with any number of completed runs ≥ 2.

## Non-goals

- No letter grades or other ratings of the individual audits (explicitly dropped by the
  user for now).
- Not a fresh full audit. The consensus agent checks findings the audits raised and claim
  verdicts they disagree on; it does not go hunting for new issues. If it stumbles on a
  new problem while adjudicating, it may list it in a clearly separated "noticed during
  adjudication" note, unadjudicated.
- No publishing; the report is private, like the audits.
- No containerization (deferred project-wide).

## Anti-goals (failure even if it runs)

- Treating "the other audit didn't mention it" as "the other audit found no problem".
  Disputed vs untested must be distinguished from what each report actually checked
  (findings, robustness tables, clean-checks and verification appendices).
- Settling a disagreement by majority vote or by trusting the more confident report
  instead of by evidence.
- Modifying any source run folder (the launcher's model-name redaction, under Blinding, is
  the sole exception).
- Letting model identity leak into the adjudication (see Blinding).
- A bottom line that buries whether major conclusions change.

## Packaging and invocation (operator decided)

- New skill directory `audit-consensus/` in `scientific-audit-skills`, alongside
  `reproducibility-audit/`, containing `SKILL.md`, `README.md`, `templates/consensus_template.qmd`,
  `references/` as needed, and `scripts/consensus.sh`.
- `consensus.sh [--interactive] <paper_id> [<model>]`, run from the corpus root (directory
  holding `.autoaudit-root`, as for `new_run.sh`). **Default model: `claude-opus-5-5`.**
- Headless by default, `--interactive` opts out, harness chosen from model name exactly as
  in `new_run.sh` (`*claude*` → Claude Code, `*gpt*` → Codex, else opencode/OpenRouter).
  Headless transcript to `agent_log.jsonl` in the consensus folder; script exits with the
  agent's status and prints the agent's final result, as `new_run.sh` does. Shared launcher
  logic should be reused rather than copied where practical (builder's call how).
- Built test-first with pytest, following the existing `tests/test_new_run_sh.py` style.
- **Definition of done (operator decided):** the pytest suite passes. It covers discovery,
  the completeness and manifest checks, redaction and its rescan, the consensus folder
  layout, harness selection, the default model, attaching the model mapping, and the
  SKILL.md/template text checks, in the style of `test_skill_text.py`. Agent harnesses are
  stubbed. A live run on Bissett_2021 comes later, after the current audit job finishes,
  and is not part of this build. The worked example above is the reference for judging it.

## Inputs and validation

- Runs are discovered **from disk**: subdirectories of `runs/<paper_id>/` that contain
  `run.json` (excluding the `consensus/` directory). `registry.jsonl` is not used for
  discovery (it contains duplicates and entries for runs no longer on disk).
- A run is **completed** if it has `audit/audit.qmd` and a rendered `audit/audit.html`,
  and, when `audit/agent_log.jsonl` exists, the log ends with that harness's completion event. For Claude Code that is a `result`
  event; the builder should check what Codex and opencode emit. That
  rules out headless jobs still running. Without this check the launcher could redact a
  log that is still being written *(designer's call)*.
  Incomplete runs are skipped with a warning naming them.
- Fewer than two completed runs → exit non-zero with a clear message; no agent launched.
- All completed runs of a paper should share the same `manifest_sha256` in `run.json`; if
  they don't, stop and report (they were not audits of the same inputs).

## Output layout

```
runs/<paper_id>/consensus/<consensus_id>/
  consensus.qmd   consensus.html
  R/  results/          # adjudication analyses and their outputs
  inputs.json           # run IDs (and hashes of their audit.qmd) that were reconciled
  agent_log.jsonl       # headless transcript
```

- A new `<consensus_id>` each invocation; earlier consensus runs are never overwritten.
  ID scheme is the builder's call (must sort chronologically or record a timestamp).
- The agent's working directory is the consensus folder. It may **read** everything in
  the source run folders (paper/, data/, audit/ including their code and caches) and
  re-execute source-run code, but writes only inside its consensus folder. Re-running a
  source audit's code means copying it into the consensus folder first. Same rules on
  additional evidence retrieval as the reproducibility-audit skill (save under the
  consensus folder, provenance table, no paid jobs/large downloads).
- Analyses follow reproducibility-audit conventions: R + Quarto, numbers inline from
  computed results, AI-generated / preliminary-and-unvetted disclaimers at the top.

## Blinding

- Throughout the agent session, audits are referred to by run ID only. The agent must not
  read `registry.jsonl` and must not try to infer which model wrote which audit.
- Blinding is **enforced by the launcher, not just instructed** (operator decided). The
  headless transcripts (`audit/agent_log.jsonl`) name the model in plain text, and other
  files in a run folder may too. Before launching the agent, the launcher **redacts in
  place**: in every completed source run it replaces each model string from that run's
  `registry.jsonl` entry with the run's registry key (`run_id`). It checks all files in the
  run folder, not only the log. Model strings to match: the registry `model` value, plus
  its bare form without a provider prefix (`google/gemini-4-argon` → `gemini-4-argon`). It
  also matches the bare model names of every other run of the same paper, so no audit can
  name another. Matching is case-insensitive. After redaction the launcher rescans and
  stops without launching if any match remains, e.g. in a binary file.
- Redaction is the **one permitted modification of source runs**, performed by the
  launcher, never by the agent. It permanently rewrites the original transcripts; the
  registry keeps the mapping, so it can be reversed. Redaction is idempotent and logged
  (file, count) to the consensus folder's `inputs.json`.
- Redaction must not touch the prepared inputs that `verify_run.py` checks (`paper/`,
  `data/`, `manifest.json`, `README.md`, `run.json`). If a model string turns up there,
  stop and report it instead of redacting.
- After the agent finishes, the launcher attaches the run-ID → model mapping from
  `registry.jsonl` (deduplicated) to the final report, so the rendered `consensus.html`
  shows it in an appendix. Mechanism is the builder's call; one option: the template reads
  an optional `run_models.json` at render time and the launcher writes that file then
  re-renders. The agent-produced analysis must not change between the two renders.
- Known limitation: the default consensus model is also one of the auditing models and
  may recognize its own style. Recorded in the report's provenance appendix; not mitigated.

## Report contract (consensus.qmd)

Verdict-first, in this order:

1. **Bottom line** — the confirmed major issues, their severity, and which major
   conclusions they change (or that none do). Short.
2. **Claims** — merged claim table: consensus claim, consensus verdict, each run's
   original claim ID and verdict, and a one-line reason wherever verdicts differ.
3. **Confirmed issues** — ranked by severity; each with status (converged / adjudicated),
   which runs raised it (with their finding IDs), severity, affected claim, whether it
   changes the conclusion, and evidence.
4. **Disputed and refuted findings** — each with the evidence that settled it and why the
   audits differed (e.g. different baseline, different replication unit, error in one run).
5. **Agreed minor issues** — compact table.
6. **Appendix** — finding cross-walk (every finding ID from every run → consensus item and
   status, so nothing is silently dropped); adjudication analyses and output; provenance
   (inputs.json contents, additional evidence, run-ID → model mapping, known limitation);
   session info.

Every finding from every source run must appear in the cross-walk.

## Left to the builder

- Exact SKILL.md wording and stage breakdown for the consensus agent.
- consensus_id scheme; how shared launcher code is factored.
- Mechanism for attaching the model mapping after the agent run.
- Which helper checks (discovery, completeness, manifest match) live in Python vs bash;
  Python under `audit-consensus/scripts/` run via `uv run` is the default expectation.
