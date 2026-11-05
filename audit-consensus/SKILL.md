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
- **Converged** findings: apply the multiplicity rule below even for converged findings.
  For other converged findings, accept them, but spot-check any whose audits disagree on
  magnitude or severity, and report which magnitude holds.
- **Claim verdicts that differ** between audits: decide the consensus verdict from the
  adjudicated findings and state why each audit's verdict was or was not right.
- Cache heavy computations (e.g. `results/*.rds`) and read them in the report. The
  operator re-renders the report after you finish, and every number must come out the
  same.

Scope: adjudicate what the audits raised and the verdicts they disagree on. Do not hunt for
new issues. A new problem you notice while adjudicating goes in *Noticed during
adjudication*, unadjudicated, one line each, but only when it could change a verdict.
Leave out anything smaller. Additional evidence follows the
reproducibility-audit rules: save it under `additional-evidence/` with a provenance row,
with no large downloads, no paid jobs, and no contacting authors.

### Justify the multiple-comparison family

Before alleging missing multiple-comparison correction, establish family membership
from the scientific question, the authors' inferential claims, and the analysis plan,
preregistration, methods, and code where available. List the included tests and explain
why they offer parallel opportunities to support the same inference. Sharing the same
figure, table, dataset, or paper does not establish a family; distinct scientific
questions can legitimately be tested separately.

Focus correction checks primarily on large collections of essentially identical tests
performed in parallel, such as correlations across a set of variables or tests across
many brain voxels. This is a priority, not a minimum family size: smaller families also
need justification from their shared inferential purpose. Check any existing correction,
hierarchical testing, or omnibus procedure before alleging an omission.

Do not apply Holm automatically. Justify both the family and the error criterion
(e.g. family-wise error versus false discovery rate), and assess whether the authors'
method addresses their claim. Report all tests in the justified family, including null
results and effects in the opposite direction.

If family membership is uncertain, describe that uncertainty. An alternative grouping
may be a sensitivity analysis, but do not downgrade a claim solely because it fails
correction under a debatable grouping. A justified correction that changes significance
must be interpreted alongside effect size, uncertainty, and the actual claim; it does
not establish that the effect is absent.

## Stage 5 — Severity and conclusion change

For every confirmed or partly confirmed finding, state its **severity** on the audits'
scale (major / moderate / minor: the effect on the named claim). Then state **whether it
changes a major conclusion**. It does so **only when it moves that claim's consensus
verdict to weak or unsupported**. "Hypothesis-generating" for a claim the paper presents as
established counts. A downgrade such as strong → moderate is reported, but it does not
count as changing the conclusion. Apply this to every claim in the report, explaining any weakening even when it does not
meet this threshold.

## Stage 6 — Report

Write for a reader who has not read the audits. Use plain language and short, connected
paragraphs. Be concise, but give enough context to understand each claim, its evidence,
and what the audit changes. There is no fixed word cap; length should follow the number
and complexity of the main claims. Start from the template and use this order:

1. **Paper summary**: briefly explain the research question, study design, sample or
   data, main analyses, and the paper's central conclusions.
2. **Paper-wide problems**: if confirmed or partly confirmed major problems affect the
   paper as a whole, briefly explain each problem, the evidence establishing it, and
   its impact on the paper's conclusions. Distinguish demonstrated impact from uncertainty
   that prevents verification. If there are no such problems, omit this section.
   A serious problem confined to one claim belongs with that claim.
3. **Main claims**: give each main claim a descriptive subsection heading and these
   four elements, in order:
   - **Claim**: explain what the authors assert, including the population or scope.
   - **Evidence**: describe the evidence the paper offers: relevant design, measurements,
     comparisons, and results. Include deciding estimates and uncertainty when available,
     with a figure, table, or analysis reference. Do this for claims that survive too.
   - **Holds after audit**: explicitly say whether it holds, holds with qualifications,
     is weakened, is unsupported, or cannot be determined with the available evidence.
     Give the consensus strength verdict and explain its meaning for this claim.
     An untested claim is not a verified claim.
   - **If weakened**: explain the audit evidence that weakens it and the scientific
     impact: what narrower conclusion remains defensible, what no longer follows, and
     what is still unresolved. Distinguish reanalysis results from plausible concerns.
     If it is unchanged, say so briefly; do not invent a weakness.

Describe a paper-wide problem once in full, then explain its specific impact on each
affected claim. Readers must not need to decode an issue ID or consult the appendix to
understand a verdict. Brief repetition that makes a claim understandable is appropriate.

Appendix:

- **Minor issues**: changes to a reported number, test, or result label that do not
  change a claim verdict; give the location and effect.
- **Noticed during adjudication**: unadjudicated concerns that could change a verdict,
  clearly labelled as unconfirmed; otherwise "None."
- **Claim verdicts by audit**: per-run claim IDs and verdicts, with reasons for differences
  from the consensus.
- **Finding cross-walk**: every finding ID of every run, consensus item, status, outcome,
  severity, affected claims, and whether it changes a major conclusion.
- **Adjudication notes**: evidence settling disputed or refuted findings, revised
  magnitudes or severities, and why audits differed. Include the family rationale for
  multiplicity findings, even when converged.
- **Cosmetic issues**: typos, labels, rounding or missing details that change no result
  or conclusion, with locations.
- **Adjudication analyses**, provenance, and session info.

Run IDs and finding IDs stay in the appendix. Consensus IDs may be used as optional
links to detailed evidence, but never as substitutes for explanations in the main body.

## Stage 7 — Render and verify

Render `consensus.qmd` to `consensus.html` with embedded resources. Check every number in
the prose against the rendered output. Read the main body as a standalone explanation:
does it summarize the paper, explain any paper-wide problems and their impact, and give
each main claim its evidence, audit verdict, and the evidence and impact of any weakening?
Remove unexplained shorthand and unnecessary detail without losing those elements.
Confirm the cross-walk lists every finding ID of every run in `inputs.json`, and that
multiplicity criticisms justify the family and account for the authors' correction.
Give the operator the file path. Do not publish it.
