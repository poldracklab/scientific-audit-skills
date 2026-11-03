---
name: audit-consensus
description: >
  Reconcile several independent, blinded reproducibility audits of the same paper into one
  consensus report. Use when a consensus folder made by consensus.sh (inputs.json present)
  needs reconciling, or when the user asks which audit findings are confirmed across runs,
  how severe they are, and whether they change the paper's major conclusions. Matches claims
  and findings across audits by meaning. Distinguishes converged, disputed and untested
  findings, and runs whatever additional analysis against the paper's data and code is
  needed to settle disagreements. Not a fresh audit and not a rating of the audits.
---

# Consensus of independent audits

Goal: a **private, self-contained rendered Quarto report** (`consensus.html`) that answers,
for one paper: which issues raised by the audits are confirmed, how severe each is, and
whether any changes a major conclusion. Settle every disagreement with evidence, never by
counting audits or by trusting the more confident report.

Work through the stages in order. Start from `templates/consensus_template.qmd`.

## Intake

1. Your working directory is a consensus folder `runs/<paper_id>/consensus/<consensus_id>/`
   created by `consensus.sh`. Read `inputs.json`: it lists the completed runs to reconcile
   (`runs[].run_id`) and any runs skipped because their audit was unfinished. Each source
   run is at `../../<run_id>/`. Skipped runs are not inputs; do not read them. Never read
   other folders under `consensus/`: earlier consensus runs hold the model mapping and
   earlier verdicts, and would break blinding and anchor your adjudication.
2. Refer to audits by run ID only. Never read `registry.jsonl`, never guess which model
   wrote an audit, and never write a model name into any file. Model names in the source
   runs have been replaced with run IDs or `[redacted-model]`. The operator attaches
   the run-ID → model mapping after you finish.
3. Treat the source runs as read-only. You may read anything in them: `paper/`, `data/`,
   `manifest.json`, `README.md`, and each run's `audit/` (report, code, caches, results).
   To re-run a source audit's code, copy it into your folder first and run the copy.
4. Write everything under the consensus folder: `consensus.qmd`, `R/` for adjudication
   code, `results/` for its outputs, `additional-evidence/` for retrieved material.

## Stage 1 — Extract

For each run, read `audit/audit.qmd` (and `audit.html` where inline values matter) and list:

- its **claims** with their verdicts;
- its **findings** (ID, status line, severity, affected claim, key numbers);
- what it **checked and found clean**: rows of its robustness table marked as not changing
  the verdict, its *Clean checks* and *Verification performed* appendices, and robustness
  output it reports.

The third list decides whether silence means "checked, no problem" or "never looked".

## Stage 2 — Cross-walk

Match claims across runs by meaning, not by ID. The runs number claims and findings
independently, and one run's claim may split or merge another's. Produce one consensus
claim list. Then match every finding from every run to a consensus item. Two findings
match when they identify the same problem in the same analysis, even when they reach it
by different routes (for example estimator arithmetic versus simulation). Every finding ID
from every run appears in the cross-walk table; nothing is dropped silently.

## Stage 3 — Classify

Each consensus finding gets exactly one status:

- **Converged**: two or more audits raised it independently and none tested the same
  point and found it clean.
- **Disputed**: at least one audit raised it, and **any** audit explicitly tested the same
  point and found no problem. This holds however many audits raised it: one explicit clean
  result makes it disputed.
- **Single-audit, untested**: one audit raised it and no other audit looked.

Audits that never looked are recorded in the cross-walk but do not change the status.
Never classify by majority, and never by which report sounds more certain.

## Stage 4 — Adjudicate

- **Disputed** and **untested** findings: run the check yourself against the paper's data
  and code, in `R/` with output in `results/`. Find out *why* the audits differ (different
  baseline, different replication unit, a code error in one run, a different reading of the
  paper). Give an outcome: **confirmed**, **partly confirmed**, or **refuted**. If an
  existing output in a source run already settles the question, cite that exact output
  instead of recomputing it, and say why it suffices.
- **Converged** findings: accept them, but spot-check any whose audits disagree on
  magnitude or severity, and report which magnitude holds.
- **Claim verdicts that differ** between audits: decide the consensus verdict from the
  adjudicated findings and state why each audit's verdict was or was not right.
- Cache heavy computations (e.g. `results/*.rds`) and read them in the report. The
  operator re-renders the report after you finish, and every number must come out the
  same.

Scope: adjudicate what the audits raised and the verdicts they disagree on. Do not hunt for
new issues. A new problem you notice while adjudicating goes in *Noticed during
adjudication*, unadjudicated, one line each. Additional evidence follows the
reproducibility-audit rules: save it under `additional-evidence/` with a provenance row,
with no large downloads, no paid jobs, and no contacting authors.

## Stage 5 — Severity and conclusion change

For every confirmed or partly confirmed finding, state its **severity** on the audits'
scale (major / moderate / minor: the effect on the named claim). Then state **whether it
changes a major conclusion**. It does so **only when it moves that claim's consensus
verdict to weak or unsupported**. "Hypothesis-generating" for a claim the paper presents as
established counts. A downgrade such as strong → moderate is reported, but it does not
count as changing the conclusion. Apply this to every claim in the consensus claims table.

## Stage 6 — Report

Fill the template in its order:

1. **Bottom line** (at most 150 words). The first sentence says which major conclusions
   change, or that none do. Then: the confirmed major issues and their severity, and what
   remains unresolved.
2. **Claims**: one row per consensus claim, with the consensus verdict, one column per run
   ID (that run's claim ID and verdict, or "not assessed"), and a one-line reason wherever
   verdicts differ.
3. **Confirmed issues**: ranked by severity, then by consequence. Each record gives its
   status (converged / adjudicated: confirmed or partly confirmed), the runs and finding
   IDs that raised it, severity, affected claim, whether it changes the conclusion, and
   the evidence.
4. **Disputed and refuted findings**: the evidence that settled each one, and why the
   audits differed.
5. **Agreed minor issues**: one compact table.
6. **Noticed during adjudication** ("None." if empty).
7. **Appendix**: finding cross-walk, adjudication analyses (code and output), provenance,
   session info.

Write in the reproducibility-audit report style: every section opens with its conclusion,
and numbers appear inline only when they decide a verdict.

## Stage 7 — Render and verify

Render `consensus.qmd` to `consensus.html` with embedded resources. Check every number in
the prose against the rendered output. Confirm the cross-walk lists every finding ID of
every run in `inputs.json`. Give the operator the file path. Do not publish it.
