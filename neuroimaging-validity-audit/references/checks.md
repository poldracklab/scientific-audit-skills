# Targeted audit checks

Select checks relevant to the claim; this is not a mandatory checklist for every
paper. Evidence of a risk factor alone does not establish its effect on results.

## Documents and numerical consistency

- Reconcile enrollment, exclusions, analysis samples, missingness, denominators,
  degrees of freedom, and repeated observations.
- Check test statistic/p-value/interval/effect-size compatibility only when test
  type, tails, corrections, and degrees of freedom are sufficiently specified.
  Allow rounding; confirm PDF extraction before calling a discrepancy an error.
- Compare abstract, text, figures, tables, supplement, preregistration, and code.
  Identify exploratory versus confirmatory claims and documented deviations.
- Distinguish a significant/nonsignificant pair from a tested interaction, and
  non-rejection from equivalence. Avoid observed post-hoc power as evidence.
- Assess multiplicity using the justified-family guidance below;
  an unknown analysis history is not proof of selective reporting.

## Task activation and cognitive interpretation

- Inspect contrast weights and task demands: inhibition, attention, rarity,
  difficulty, time-on-task, errors, motor output, and baseline content.
- Check independent ROI definitions versus selection on the tested effect.
  Distinguish circular effect-size estimation from legitimate selected displays.
- Match spatial claims to voxel/cluster inference and correction scope; cluster
  significance does not make every voxel a separately established finding.
- Ask whether reverse inference, causal necessity, or regional specificity needs
  evidence beyond the reported activation contrast.
- For nulls, examine precision, measurement quality, and whether subtraction or
  nuisance adjustment could remove the intended signal.

## Prediction and decoding

- Establish the target generalization unit: trials, runs, participants, families,
  sites, or time. Inspect overlap and dependence across training/test partitions.
- Trace feature selection, imputation, scaling, harmonization, nuisance regression,
  hyperparameter selection, and model selection relative to those partitions.
  Judge leakage against the intended deployment setting, not a blanket rule.
- Check label confounds, temporal autocorrelation, repeated test-set use,
  appropriate baselines, and exchangeability of permutation schemes.
- Successful decoding establishes information available to a model; identifying
  a particular represented construct requires excluding pertinent alternatives.
- Saved predictions permit metric checks but cannot prove training was clean.

## Brain–behavior and individual differences

- Check ROI/feature selection independence, influential units, confounding,
  restriction of range, exclusions, and effective sample size.
- Assess reliability of the actual contrast or score, not only its components.
  Robust mean activation does not establish reliable participant rankings.
- Quantify uncertainty where possible; an imprecise null cannot establish absence.
  Do not blindly disattenuate correlations using uncertain reliability estimates.
- A group-effect sample-size recommendation does not automatically transfer to
  between-person associations, or vice versa.

## Longitudinal and dense sampling

- Separate sessions from independent participants and within-person from
  between-person estimands. Check trends, autocorrelation, seasonality, and
  time-varying confounds.
- Inspect blocked/temporal splits and resampling exchangeability. Many observations
  from one participant do not by themselves establish population generalization.

## Meta-analysis, ontology, and methods papers

- Trace sample overlap, multiple effects per study, inclusion decisions, and
  dependence. Inspect whether labels operationalize the construct claimed.
- For benchmarks, inspect ground truth, tuning/test separation, baseline fairness,
  and whether the metric actually measures the advertised benefit.
- Treat corpus coverage and publication selection as limitations to evaluate,
  not automatically demonstrated bias.

## Cheap checks by available artifact

| Artifact | Useful checks | Important boundary |
|---|---|---|
| Participant ROI/behavior tables | Refit associations and direct contrasts; intervals; influence; justified covariates | Cannot validate upstream ROI independence from values alone |
| Out-of-fold predictions and IDs | Metrics; uncertainty at correct unit; subgroup/site differences; duplicate IDs | Cannot exclude all training leakage |
| First-level contrast/variance images | Selected group models; participant influence | Holds preprocessing and first-level modeling fixed |
| Events and design matrices | Contrast estimability; collinearity; behavioral confounds | Does not verify image alignment or actual execution |
| Unthresholded group maps | Signs, reported coordinates, map/table agreement | Does not recover participant variability |
| Repeated measurements | Reliability and temporal dependence | Requires a model suited to the intended estimand |

For permutations/bootstrap, verify that resampling respects dependence and the
null statistic actually varies. For simulations, include known-positive and
known-negative conditions and record assumptions. For sensitivity analyses,
report all attempted defensible alternatives, including ones strengthening the
claim, without selecting a preferred result by significance.

### Justify the multiple-comparison family

Require multiple-comparison correction only for a clear family of parallel, related
tests. Establish family membership from the scientific question, analysis plan,
preregistration, methods, and code where available. List the included tests, describe
what is held constant and what varies across the tests, and explain how they test
related hypotheses in parallel. A broad narrative or headline conclusion is not
sufficient to combine otherwise distinct scientific questions into one family.
Sharing the same figure, table, dataset, participants, or paper does not establish
a family. Reporting results together is not evidence that the tests are parallel.

Examples of clear families include essentially identical tests of the same contrast
across many brain voxels, the same brain–behavior association across a set of ROIs,
or parallel correlations screening related variables for the same association.
Family size alone is not decisive: a small set can qualify when its tests are clearly
parallel and related. Conversely, separate prespecified hypotheses about task
performance, acceptability, and a mechanistic association do not become a family
merely because they appear in one table or contribute to an intervention narrative.
Prespecification alone does not exempt a genuinely parallel family from correction.

Only after establishing this family, check any existing correction, hierarchical
testing, or omnibus procedure before alleging an omission. Do not apply Holm
automatically. Justify the error criterion (e.g. family-wise error versus false
discovery rate) and assess whether the authors' method addresses their claim.
Report all tests in the justified family, including null results and effects in
the opposite direction.

If family membership is unclear, do not classify missing correction as an error
and do not downgrade a claim for uncorrected significance. State what evidence
would be needed to establish a parallel family. An alternative grouping may be
an explicitly optional sensitivity analysis; failure under that grouping is not
a demonstrated defect and must not drive the verdict. For a clear family, interpret
a justified correction that changes significance alongside effect size, uncertainty,
and the actual claim; it does not establish that the effect is absent.
