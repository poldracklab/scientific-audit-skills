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

## Validation record (2026-11-06)

Before implementation, an independent agent handled cases 1–5 using only the
two target skills. It identified blocked reproduction but recommended a validity
audit as the next alternative, rather than retaining reproduction as the primary
route in a structured recommendation. Other baseline choices were appropriate.
The packaging pytest failed because no discoverable routing skill existed; the
tests were committed before implementation.

With the router, a fresh agent evaluated all six cases. It retained reproduction
as primary when inputs were missing, selected validity for regional specificity,
selected reproduction for the behavioral trial, gave a provisional route before
preparation, rejected the software-library case, and proposed one primary audit
plus complementary checks for mixed objectives. It distinguished supplied facts
from verified readiness and did not execute audits. Review clarified that run
verification uses audit-prep's script. These synthetic checks do not establish
performance on arbitrary real packages.

Automated validation: skill quick-validator passed; routing packaging and existing
skill-text tests: 37 passed. Full suite: 586 passed, 7 failed, 2 errors. Failures
were outside changed implementation files:

- `test_consensus_sh.py::test_default_model_is_claude_opus_5_5`,
  `test_interactive_runs_post_steps`, and
  `test_prompt_not_absorbed_by_variadic_add_dir[extra0/extra1]`: default launcher
  selected Codex while tests expected Claude.
- `test_docs.py::test_structured_smoke`: structured conversion returned failed;
  underlying cause not established in this run.
- `test_prepare.py::test_cli_init_scan_run_finalize` and
  `test_cli_refuses_without_root`: dependency retrieval failed with DNS errors.
- `test_audit_report.py::test_report_embeds_figure_bytes` and
  `test_report_has_no_external_display_resources`: Quarto architecture detection
  failed because sandbox restrictions blocked sysctl.

These full-suite failures were not repaired as part of routing-skill creation.
