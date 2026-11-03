# audit-consensus

Reconciles several blinded reproducibility audits of one paper into a consensus report:
which issues are confirmed, how severe they are, and whether they change a major conclusion
(only when a claim's consensus verdict falls to weak or unsupported).

- `scripts/consensus.sh [--interactive] <paper_id> [<model>]` is the operator's launcher.
  Run it from the corpus root; the default model is `claude-opus-5-5`.
- `scripts/consensus.py prepare|attach-models` handles discovery, completeness and manifest
  checks, model-name redaction, the consensus folder and `inputs.json`, and the
  post-run `run_models.json`.
- `scripts/discover.py` and `scripts/redact.py` are the helpers behind it.
- `SKILL.md` tells the consensus agent what to do; `templates/consensus_template.qmd` is
  the report shape.

See the top-level README, section "Reconcile the audits into a consensus report".
