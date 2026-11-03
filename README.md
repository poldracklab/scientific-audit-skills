# scientific-audit-skills

Poldracklab agent skills repository

Released under an MIT license.

Adapted from Mike Frank's [claude-skills](https://github.com/mcfrank/claude-skills/tree/main).


## Skills

- `adversarial-protocol-review`: adversarial review of an experiment, eval or analysis for what could manufacture its result.
- `audit-prep`: prepare paper folders into standardized, read-only audit inputs and create blinded audit runs.
- `neuroimaging-validity-audit`: self-critical validity audit of published neuroimaging papers.
- `reproducibility-audit`: computational reproducibility audit of a published paper in R and Quarto.

## Audit workflow

Prepare common starting materials once with `audit-prep`: the publication, supplements,
and directly linked data, code and preregistrations. Raw folders remain intact; prep copies
selected inputs into a reviewed, frozen snapshot. The operator creates isolated runs and
keeps the model registry outside the auditor's accessible workspace before evaluation. This allows for testing of multiple models on the same extracted data.

Audits start only from a verified run. Models may discover and retrieve additional relevant
evidence, including sources prep could not retrieve. Save it under
`audit/additional-evidence/`, record source URLs, retrieval dates, local files and dependent
findings, and preserve the prepared inputs. This measures auditing from common starting
materials while allowing evidence discovery to contribute to model performance. Model outputs are saved with a coded name so that other models can't identify the model that generated the output; this allows unbiased comparison of different model outputs by a separate model.
