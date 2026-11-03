# my-skills

Russ Poldrack's agent skills repository

## Skills

- `adversarial-protocol-review`: adversarial review of an experiment, eval or analysis for what could manufacture its result.
- `audit-prep`: prepare paper folders into standardized, read-only audit inputs and create blinded audit runs.
- `neuroimaging-validity-audit`: self-critical validity audit of published neuroimaging papers.
- `reproducibility-audit`: computational reproducibility audit of a published paper in R and Quarto.

## Audit workflow

Prepare common starting materials once with `audit-prep`: the publication, supplements,
and directly linked data, code and preregistrations. Raw folders remain intact; prep copies
selected inputs into a reviewed, frozen snapshot. The operator creates isolated runs and
keeps the model registry outside the auditor's accessible workspace before evaluation.

Audits start only from a verified run. Models may discover and retrieve additional relevant
evidence, including sources prep could not retrieve. Save it under
`audit/additional-evidence/`, record source URLs, retrieval dates, local files and dependent
findings, and preserve the prepared inputs. This measures auditing from common starting
materials while allowing evidence discovery to contribute to model performance.
