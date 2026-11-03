# Analysis recipes

Use the sections relevant to the study design and available data. These are targeted
checks, not a requirement to run every analysis for every paper. Retain all attempted
specifications and report limitations.

## Error-hunting checklist

- **Arithmetic identities.** In mediation, total = direct + indirect (c = c′ + ab). Check them on the *printed* figure and table values: it catches swapped labels without any code. Also check that CONSORT boxes add up (allocated ≥ completed in each arm).
- **lavaan labels.** Reusing one label (e.g. `cv*x1 + cv*x2`) **constrains those coefficients to be equal**. Refit with the coefficients free and run an LRT on the constraint. A quick symptom: rescale one covariate (e.g. 1–7 → 0–1). If standardized results change, the model is misspecified.
- **Methods vs code.** "Controlling for baseline X": is X actually in *every* equation the text implies (e.g. the mediator equation)?
- **Claims vs output.** Check every "significant" claim in Discussion and Abstract against the code's own output; Discussion lists drift.
- **Baseline covariate in slope models.** A baseline main effect adjusts level, not slope. Refit with `baseline × time` when groups differ at baseline.
- **Copy-paste formula slips** in scripts (a covariate listed twice and another dropped).
- **Recode bugs** (e.g. `'Woman' -> 'Women'` creating a stray factor level).

Present specification errors as "before / after" code plus a decomposition table (fix A only, fix B only, both), so it's clear which fix does the work. Also compute the downstream effect on *every* claim that used the model; corrections are often not one-directional, and saying so matters. The decomposition table and per-claim effects go in the appendix; the finding record in the body carries only the numbers that decide it.

## Robustness and threats toolkit

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

## Outcome × finding matrix

For trials with many outcomes, build a matrix:

- **Rows:** every prereg primary and secondary outcome, plus the headline exploratory ones.
- **Columns:** prereg role, how the paper treats it (headline / null mentioned / not mentioned), the effect at each timepoint, the effect per subsample, and mediation under the authors' and the corrected specification.
- **Units:** effects in **baseline-SD units, sign-aligned so + = benefit**.
- **Composite row:** add an equal-weight composite of the self-report family as an omnibus row, labelled post hoc.
- **Mediation caveat:** when the *a* path is shared across outcomes, consistent "significant mediation" mostly reflects observational mindset–outcome associations, not treatment effects. Say this explicitly.

Use the matrix to answer the user's likely question: *is this a real effect that was oversold, or something weaker?* The matrix goes in the appendix; the answer goes in the bottom line and the claims table.

