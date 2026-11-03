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

## Installation

Clone this repository, then run `bash install.sh` to install the skills.

## Example

Prepare a directory that miminally contains a PDF of the publication to be audited, along with any supplementary materials, code, or other data; note that code/data that are linked from the paper will be downloaded if they aren't in the folder.  I would place these paper folders within a folder (I'll call it `autoaudit`) containing all of the papers to be audited; these should be outside of this skill folder.  

Let's say that the paper folder is titled `Poldrack_2026`.  The following prompt will run the audit-prep workflow:

```
Use the audit-prep skill to prepare Poldrack_2026 (corpus root: /path/to/autoaudit).

Corpus-wide settings: 
structured_conversion: true; reviewed_by: the model name you are running as.

Finalize if review is clean.
```

For several papers, list them and add:

`apply the same ettings to each; report a one-line summary per paper.`

Once that's done, then you first need to create a run directory for the particular model; this happens outside of the coding agent, since we need to hide the identity of the model from later review.  First you need to create the run directory for a specific model; we will choose `claude-opus-5-5`. This assumes that your skills are being installed to ~/.agents:

```
uv run ~/.agents/skills/audit-prep/scripts/new_run.py Poldrack_2026 --model claude-opus-5-5 --root /path/to/autoaudit
```

This will return a run ID, and you can then verify it:

```
uv run /Users/poldrack/.claude/skills/audit-prep/scripts/verify_run.py /path/to/autoaudit/runs/Poldrack_2026/<run_id>
```
It should return `run_ok` in which case you are ready to proceed.


You are now ready to run the audit. Open the relevant coding agent within the run directory; note that you are responsible for making sure that the model being used matches the model entered for the run key, so be sure to check that before prompting.  You can run the audit using something like the following prompt:

```
Use the reproducibility-audit skill to audit the paper in this run folder.

The current directory is an audit-prep run for Poldrack_2026. Start with the skill's intake step (verify_run.py on this folder); proceed only if it reports run_ok.

Write all output under audit/ and leave every other file in the run folder unchanged.

Render audit/audit.html locally and give me the file path when done. Do not publish it anywhere.
```