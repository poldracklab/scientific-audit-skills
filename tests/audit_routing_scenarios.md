# Audit routing behavioral checks

Run in a fresh agent context, first without the router and then with
`audit-routing/SKILL.md`. Read both target definitions. Return a route, rationale,
feasibility, and next action. Do not execute audits or change files. Package
 descriptions are supplied facts, not verified filesystem observations.

| Case | Request and materials | Expected behavior |
|---|---|---|
| Missing data | Reproduce fMRI statistics in 30 minutes; paper, plotting code, OpenNeuro metadata only | Preserve reproduction as primary; mark blocked/partial; validity review is a separate option, not an automatic replacement; no large download |
| Imaging claim | Choose for prepared fMRI package focused on regional specificity; participant CSV, runnable R, preregistration | Validity primary with targeted numerical checks; data availability alone does not force reproduction-first |
| Trial | Choose for behavioral trial with CSV, R, preregistration | Reproducibility primary; feasibility provisional pending inspection |
| Unprepared | Choose for unprepared neuroimaging paper-only folder | Provisional validity recommendation now; preparation and isolated run needed before auditing |
| Software | Choose for software library with unit tests, no scientific paper | Neither scientific audit fits |
| Mixed | Both reproduce and assess imaging claims; estimates and code, no priority | One primary with complementary checks and stated assumption, or one focused question if priority changes scope; no duplicate audits |

A recommendation-only request never executes an audit. Record baseline failures
and final outcomes in validation notes. These evaluate behavior, not exact prose.
