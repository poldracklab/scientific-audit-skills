---
name: reproducibility-audit
description: >
  Workflow for a computational reproducibility audit of a published paper: work from a folder
  prepared by audit-prep (paper text, authors' data/code, preregistration already fetched),
  reproduce the reported statistics and figures in an R + Quarto notebook, compare the paper
  against its preregistration, and assess the strength of evidence (attrition, clustering,
  multiplicity, specification errors, outcome selection). Use whenever the user asks to
  "reproduce", "audit", "check the stats/figures of", or "see whether the prereg was followed
  in" a published paper, or wants a judgment about how strong a paper's evidence is given its
  data. Covers intake of prepared run folders, the blinded report template with AI-generated
  disclaimers, a checklist of errors that recur in published analyses, and the robustness
  toolkit. Pairs with
  adversarial-protocol-review (the "what could manufacture this result?" mindset) and
  quarto-book (rendering conventions).
---

# Reproducibility audit of a published paper

Goal: a **private, self-contained rendered Quarto report** (R code + prose). It answers three
questions:

1. Do the posted data and code reproduce the reported numbers and figures?
2. Where does the paper depart from its preregistration (or, absent one, which analytic choices were left open)?
3. Given everything, how strong is the evidence for the central claims?

Work through the stages in order. Verify every number you write against rendered output (stage 9).
The report itself follows the contract in `references/report.md`: a verdict-first body of at
most 1500 prose words, with ledgers, full robustness output and session details in the appendix.

## Intake

1. Run `uv run ~/.claude/skills/audit-prep/scripts/verify_run.py <folder>` on the folder you were given.
2. `not_prepared` → invoke the `audit-prep` skill on it (scan, review `prep.yaml`, run, finalize), then continue. Warn the user that prepping from inside an audit makes prep model-dependent; the manifest records `prepared_by`.
3. `prepared_not_run` → run `uv run ~/.claude/skills/audit-prep/scripts/new_run.py <Paper_Year> --model <your model name> --root <corpus root>`, `cd` into the printed path, continue.
4. `run_dirty` or `run_modified` → stop and report the details; do not audit a contaminated folder.
5. `run_ok` → read `README.md`, then `manifest.json`, then proceed. Never read `registry.jsonl` or any other run folder. All persistent output goes under `audit/` in the run folder (`audit/audit.qmd`, `audit/audit.html`, caches, working notes). Nothing inside the run folder may name the auditing model.

## Folder organization

You work in a run folder made by `audit-prep`, a blinded copy of the prepared paper folder:

```
runs/<Paper_Year>/<run_id>/       # your cwd
  manifest.json  README.md  run.json
  paper/
    paper.pdf  paper.txt  paper.md          # pdftotext -layout; docling Markdown
    pages/p-001.png ...                     # every page rendered
    figures/  tables/                       # crops and CSVs, indexed in figures.md / tables.md
    metadata.json  links.json  statements.md
    supplement_1.pdf  supplement_1.txt ...
  preregistration/<source>_<id>/            # e.g. osf_<regid>/, clinicaltrials_<nct>/
  github/<owner>__<repo>/                   # authors' code at the commit in the manifest
  data/
    <name>/                                 # local data directories as supplied
    osf_<id>/  zenodo_<id>/  neurovault_<id>/
  audit/                                    # all your output goes here
```

- All persistent output goes under `audit/`: the report `audit/audit.qmd`, its render `audit/audit.html` (embed-resources: true, a single file), caches and working notes. Never write elsewhere in the run folder; `verify_run.py` treats it as contamination.
- Keep `.qmd` paths relative to `audit/` (`../data/osf_<id>/...`, `../paper/paper.txt`), so the run folder can be moved.
- **Privacy:** these reports critique named colleagues' work. Render locally only. Do **not** publish them as Artifacts, to Quarto Pub, or anywhere else unless the user explicitly asks. Deliver `audit/audit.html` with `SendUserFile`.

## Stage 1: Read the manifest

Prep has already fetched and converted everything; this stage records what it found.

- **Preregistration:** `manifest.json` lists each registration with `date_registered`, `hash_verified` and `status`; `data_collection` gives the start, end, page and a verbatim quote from the methods (or null). The registration files are under `preregistration/<source>_<id>/`. A `hash_mismatch` or `unverified` status means the file may not be the frozen version; say so.
- **Record `date_registered` against the end of data collection.** A "prereg" registered after data collection is not prospective, even if it predates cleaning. Also note whether a self-described clinical trial is in a trial registry (a `clinicaltrials_<nct>/` or other registry folder under `preregistration/`).
- **Materials:** the paper text is `paper/paper.txt` (Markdown: `paper/paper.md`); page renders are `paper/pages/p-NNN.png` (Read them to see figures and CONSORT diagrams); figure crops are in `paper/figures/`, tables in `paper/tables/`; data/code/prereg statements are in `paper/statements.md` and every link in the paper is in `paper/links.json`. The authors' code is under `github/`; downloaded data under `data/<source>_<id>/` (e.g. `data/osf_<id>/`) and local data under `data/<name>/`.
- Before calling material absent, check the manifest's `data` and `code` statuses (`listed_only`, `failed`, `unsupported`) and report what prep could not retrieve.
- If a project has **no registration**, say so explicitly and switch stage 5 to "analytic flexibility".

## Stage 2: Read everything before computing

- **Read the whole paper** (`paper/paper.txt`, supplements beside it). List every inferential statistic in Results and every figure with its caption claims (n's, what the error bands are, which panel is which).
- **Read the prereg in full** (the files under `preregistration/<source>_<id>/`), noting page numbers. Record:
  - the **outcome hierarchy** (primary / secondary / exploratory);
  - the stated hypotheses and analysis models;
  - the mediator and outcome **timepoints**;
  - exclusion rules, ITT vs per-protocol, the planned sample size;
  - any explicit "exploratory / hypothesis-generating" labels;
  - intervention components (e.g. a booster session the paper later omits).
- **Read the authors' scripts** (under `github/` or the data folders, e.g. `data/osf_<id>/`):
  - Which files do they read? Are those files posted?
  - What are the exact model formulas, contrasts and labels?
  - How do the plotting calls handle axis limits?
  - Are analyses present in code but not reported (e.g. continuous-time models, extra outcomes)?
- **Inventory the posted data** against the codebook and scripts:
  - Is it the full randomized sample or only completers?
  - Are cluster IDs present (provider, site, session)?
  - Are there renamed variables (e.g. `_t5…_t8` → `_t1…_t4`)?
  - Are there measured outcomes that are never reported?
  - Can missing variables be reconstructed from the code (ID ranges that encode branch; hard-coded ID lists for covariates)? Document every reconstruction.

## Stage 3: Reproduce the reported statistics

- **Refit the authors' exact specification first.** Copy their formula, contrasts, reference levels and covariates, even where you think they are wrong. Then tabulate `claim | paper | reproduced` with a bold **Status:** line: *exact reproduction*, *minor discrepancy* (quantify it and give the likely cause, e.g. one missing observation), or *major discrepancy*.
- **Match the p-value method** (sjPlot/Wald vs lmerTest Satterthwaite). Report which you used.
- **Sign conventions.** These often differ because of reference levels; say so rather than calling it an error.
- **PDF extraction drops minus signs.** Before flagging a CI like "[0.04, 0.42]" around a negative estimate as an error, look at the rendered page image in `paper/pages/`.

## Stage 4: Reproduce the figures

Run the authors' plotting code as written, then show a corrected or fuller version beside it. Recurring problems:

- **Data silently dropped.** `scale_y_continuous(limits=)` (or `ylim()`) *deletes* out-of-range rows before `geom_smooth`/stat layers are computed; `coord_cartesian()` only zooms. Count the rows dropped and compare with the n in the caption.
- **Figure lines that are not the model.** `geom_smooth(method = "lm")` through `timepoint` treated as a number shows pooled OLS lines through equally spaced points, not the categorical mixed model.
- **Jitter that adds fake variation.** `position_jitter`/`jitterdodge` with a nonzero `height` adds vertical noise to measured values. Flag it when the noise is comparable to the effect.
- **Captions that don't match the plot.** Check swapped panel letters, wrong scale names (e.g. "PHQ-9" for a PHQ-2 subscale), n's, and text references to the wrong panel.
- **Hidden structure.** Show the clustering structure the analysis ignores: cell or cluster means ± SE, not just pooled groups.

## Stage 5: Preregistration deviations (or analytic flexibility)

Table: `# | Preregistration (page) | Paper | Disclosed? | Severity (Major/Moderate/Minor)`. Look for:

- **Outcome switching.** A null primary outcome, with secondary or exploratory outcomes promoted to the abstract and described "as hypothesized". Prereg language like "hypothesis generating, not confirming" is decisive.
- **Selective reporting** of a planned panel (e.g. 1 of 49 biomarkers reported).
- **Changed mediator timepoint**, mediation run despite a prereg gate ("only for outcomes showing an effect"), and dropped serial or qualitative analyses.
- **Analysis-set changes:** per-protocol instead of the planned exclusions; changed medical exclusions (note when these *are* disclosed).
- **Intervention components** in the prereg but missing from the paper's Methods.
- **Model form:** prereg "slope" vs reported categorical contrasts. Run the prereg-faithful version; if it gives the same answer, say so.

**Judgment convention:** when a secondary outcome's prereg prediction is non-directional, assume the implied direction is the intervention's intended benefit. The problem worth flagging is promotion up the outcome hierarchy, not directionality.

**No prereg:** use a table `Choice | Used | Alternatives in the data | Consequence`. Cover outcome (including unreported measures in the data), baseline adjustment, summary statistic (slope vs endpoint), which contrast is highlighted vs the one implied by the stated hypothesis, and clustering. Credit constraints such as copying a previously published paradigm and analysis.

## Stage 6: Error-hunting checklist (each has caught a real error)

- **Arithmetic identities.** In mediation, total = direct + indirect (c = c′ + ab). Check them on the *printed* figure and table values: it catches swapped labels without any code. Also check that CONSORT boxes add up (allocated ≥ completed in each arm).
- **lavaan labels.** Reusing one label (e.g. `cv*x1 + cv*x2`) **constrains those coefficients to be equal**. Refit with the coefficients free and run an LRT on the constraint. A quick symptom: rescale one covariate (e.g. 1–7 → 0–1). If standardized results change, the model is misspecified.
- **Methods vs code.** "Controlling for baseline X": is X actually in *every* equation the text implies (e.g. the mediator equation)?
- **Claims vs output.** Check every "significant" claim in Discussion and Abstract against the code's own output; Discussion lists drift.
- **Baseline covariate in slope models.** A baseline main effect adjusts level, not slope. Refit with `baseline × time` when groups differ at baseline.
- **Copy-paste formula slips** in scripts (a covariate listed twice and another dropped).
- **Recode bugs** (e.g. `'Woman' -> 'Women'` creating a stray factor level).

Present specification errors as "before / after" code plus a decomposition table (fix A only, fix B only, both), so it's clear which fix does the work. Also compute the downstream effect on *every* claim that used the model; corrections are often not one-directional, and saying so matters. The decomposition table and per-claim effects go in the appendix; the finding record in the body carries only the numbers that decide it.

## Stage 7: Robustness and threats toolkit

- **Differential attrition** (per-protocol analyses, unequal arm burden):
  - χ² test of retention by arm, using CONSORT counts.
  - Baseline balance among completers; this is reassuring only about the measured variables.
  - **Lee bounds** on change scores. These are the worst case and usually very wide.
  - **One-factor selection-model tipping point.** With retention q, E[Z | top q] = φ(Φ⁻¹(1−q))/q. Compute the gap between arms, then the ρ (completion propensity ↔ improvement) needed to produce the observed effect. Compare with the ρ implied for baseline *levels*.
  - **Benchmark against a low-attrition subsample** (branch, site) if one exists.
  - Note where the posted data exclude dropouts, which makes ITT impossible. The authors' ITT file is the obvious thing to request.
- **Unit of manipulation:** when a treatment varies only between a few providers, sites or classrooms:
  - count the units per cell;
  - give the design-effect table SE × √(1 + (m − 1)ρ) with df = units − unit-level parameters;
  - compute cell-level ICCs (pre-treatment measures are especially telling);
  - run **leave-one-cell/cluster-out** refits, and report all rows in the appendix, not just the damning one; the body's robustness table gets one row summarising the result.
- **Multiplicity** within prereg families (Holm/BH). List *all* nominal hits, including those in the unfavourable direction and those that survive.
- **Subgroup or branch splits** where the design differs. Treat the three-way interaction as post hoc, and list the confounded differences between branches.
- **Fragility:** leave-one-participant-out p-value range; ANCOVA on the endpoint as a cross-check.
- **Timing:** is the effect at one follow-up only? Does the mediator's time course fit the proposed mechanism? Does the prereg designate a key timepoint (usually not)?

## Stage 8: Outcome × finding matrix

For trials with many outcomes, build a matrix:

- **Rows:** every prereg primary and secondary outcome, plus the headline exploratory ones.
- **Columns:** prereg role, how the paper treats it (headline / null mentioned / not mentioned), the effect at each timepoint, the effect per subsample, and mediation under the authors' and the corrected specification.
- **Units:** effects in **baseline-SD units, sign-aligned so + = benefit**.
- **Composite row:** add an equal-weight composite of the self-report family as an omnibus row, labelled post hoc.
- **Mediation caveat:** when the *a* path is shared across outcomes, consistent "significant mediation" mostly reflects observational mindset–outcome associations, not treatment effects. Say this explicitly.

Use the matrix to answer the user's likely question: *is this a real effect that was oversold, or something weaker?* The matrix goes in the appendix; the answer goes in the bottom line and the claims table.

## Stage 9: Write, render, and **verify prose against output**

- Follow `references/report.md` and copy `templates/audit_template.qmd` to `audit/audit.qmd`. The body is
  bottom line → claims table → findings that change a conclusion → minor findings table →
  robustness table → assessment, at most 1500 prose words; materials, prereg table, full
  reproduction and robustness output, finding detail, clean checks, verification and session
  info are appendix sections tagged `{.appendix}`.
- Keep the two disclaimer callouts (`callout-important` "AI-generated — not for publication";
  `callout-warning` "Preliminary & unvetted analysis").
- Put computed numbers in inline `r` expressions wherever feasible. Static markdown tables only for the paper's own numbers.
- Render with `quarto render audit/audit.qmd` (output `audit/audit.html`) and grep for `Output created`. Expensive bootstraps (2000 draws × several lavaan models) take a few minutes.
- **After every render, extract the text and check each claim.** Strip tags with a short Python script and read the tables. Drafted prose has repeatedly asserted things the tables contradicted ("only one hit", "dropping any other cell leaves it intact", mislabelled bounds). Also extract the embedded PNGs (base64 in the HTML) and look at them, e.g. to catch empty labels.
- Things that cut in the authors' favour (e.g. the tipping point needing an implausible ρ; a more consistent pattern for one factor) belong in the report too.

## Stage 10: Assessment and follow-up conversation

- Rate each central claim (strong / moderate / weak / hypothesis-generating) with the one or two reasons that decide it, in the claims table and the assessment. Distinguish **computational reproducibility** (often fine) from **inferential strength** (often not).
- When asked about errors, separate those **visible from the paper alone** (arithmetic, label swaps) from those **visible only in the code**.
- If asked whether something warrants a correction: a corrigendum fits errors that change specific stated conclusions without overturning the main results; a retraction is for broader failure. The usual route is to contact the authors first. Have the key models rerun independently before anything leaves the user's hands. Don't draft letters to journals unless asked.

## Gotchas

- **zsh:** never use `path` as a shell loop variable. It is tied to `$PATH` and silently breaks every later command (`curl: command not found`). Use Python for download loops.
- **OSF API:** folder children are at `relationships.files.links.related.href`, and listings paginate (`links.next`). The download URL is `links.download`.
- **Folder renames mid-session** reset the shell cwd. Use absolute paths, or cd at the start of each command.
- **Name clashes inside `mutate()`:** a tibble column named like an outer object (e.g. a result column `spec` vs a lookup table `spec`) masks it. Look values up outside `mutate()`.
- **Authors' misspecified models are not scale-invariant.** When reproducing their specification on transformed data (e.g. sign-aligned z-scores for a matrix), run it on the raw data and transform the output instead.
- Missing R packages (e.g. `effects`): substitute (`emmeans`) and note the small numeric difference against the authors' hard-coded values.
