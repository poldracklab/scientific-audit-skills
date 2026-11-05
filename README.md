# scientific-audit-skills

Poldracklab agent skills repository

Released under an MIT license.

Adapted from Mike Frank's [claude-skills](https://github.com/mcfrank/claude-skills/tree/main).


## Skills

- `adversarial-protocol-review`: adversarial review of an experiment, eval or analysis for what could manufacture its result.
- `audit-consensus`: reconcile several blinded audits of one paper into a consensus report of confirmed issues, their severity, and whether they change the paper's conclusions.
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

Once several models have audited the same paper, `audit-consensus` reconciles their
reports. It matches claims and findings across audits by meaning. For each finding it
records whether the audits agree, disagree, or only one of them looked. Where they disagree
or only one looked, it runs the check itself against the paper's data and code. The result
answers one question: which issues are confirmed, how severe are they, and does any of them
change a major conclusion?

## Installation

Clone this repository, then run `bash install.sh`. It symlinks each skill into
`~/.claude/skills` and `~/.agents/skills`, so edits in the clone take effect immediately.
The launcher scripts below are installed with their skills.

### Requirements

Core:

- [uv](https://docs.astral.sh/uv/) — runs every Python script (dependencies are declared
  inline, so there is nothing else to install).
- Node.js / `npx` — `install.sh` first updates any `npx skills`-installed skills.
- At least one coding agent CLI:
  [Claude Code](https://docs.claude.com/en/docs/claude-code) (`claude`), and optionally
  [Codex](https://github.com/openai/codex) (`codex`) or
  [opencode](https://opencode.ai) (`opencode`, with an OpenRouter key) for preparing and
  auditing with other models.

Used by `audit-prep`:

| Tool | Needed for |
|---|---|
| Poppler (`pdftotext`, `pdftoppm`) | paper text and page images (always) |
| `git` | cloning linked GitHub code |
| Docling (fetched automatically via `uvx`) | structured PDF conversion (`structured_conversion: true`, the default); first use downloads models |
| `pandoc` | DOCX supplements |
| `zstd` | `.zst` archives |
| `rsync` | run creation when an APFS clone is unavailable |

Used by the audits: [R](https://www.r-project.org) and [Quarto](https://quarto.org) to
render `audit/audit.qmd` (and the consensus report, `consensus.qmd`). Agents install any R
packages an audit needs under `audit/`.

On macOS: `brew install uv node poppler pandoc zstd` and `brew install --cask r quarto`.

## Example

Prepare a directory that minimally contains a PDF of the publication to be audited, along
with any supplementary materials, code, or other data; note that code/data that are linked
from the paper will be downloaded if they aren't in the folder. Place these paper folders
within a corpus folder (here called `autoaudit`) containing all of the papers to be
audited; it should be outside of this skill folder.

Let's say that the paper folder is titled `Poldrack_2026`:

```
autoaudit/
  Poldrack_2026/
    paper.pdf
    supplement.docx
    corrigendum.pdf      # optional: a published correction (also erratum, correction)
```

A correction to the paper is prepared beside it as `paper/corrigendum_<n>.pdf`, and the
auditors are told to audit the paper as corrected.

### 1. Initialize the corpus (once)

```sh
uv run ~/.claude/skills/audit-prep/scripts/prep.py init /path/to/autoaudit
```

### 2. Prepare the paper

```sh
~/.claude/skills/audit-prep/scripts/prep_paper.sh /path/to/autoaudit/Poldrack_2026
```

This starts a coding agent (`claude-opus-5-5` by default; pass another model as a second
argument) in the corpus root with the audit-prep skill. The harness is chosen from the
model name as in step 3: `*claude*` → Claude Code, `*gpt*` → Codex, anything else →
opencode via OpenRouter (e.g. `prep_paper.sh <paper_dir> qwen/qwen3-coder` runs
`openrouter/qwen/qwen3-coder`). The model scans the folder, reviews
`prep.yaml`, fetches linked materials, and finalizes `prepared/Poldrack_2026/` if review is
clean. `reviewed_by` is set to the model name.

The session is headless (the same commands as the table in step 3), exits when done, prints
the model's final message, saves the full transcript to
`autoaudit/logs/prep/Poldrack_2026-<timestamp>.jsonl`, and returns the agent's exit status.

Then confirm the result:

```sh
uv run ~/.claude/skills/audit-prep/scripts/prep.py review /path/to/autoaudit/prepared/Poldrack_2026
```

Exit 0 means the folder is ready. If the model stopped with open problems (an ambiguous
role, an unretrievable dataset), fix them interactively:

```sh
~/.claude/skills/audit-prep/scripts/prep_paper.sh --interactive /path/to/autoaudit/Poldrack_2026
```

To start over, add `--overwrite`. It first removes the earlier prep of that paper:
`prepared/Poldrack_2026/` (even when finalized), the generated `prep.yaml` and
`statements.md` in the raw folder, and its transcripts in `logs/prep/`. The supplied files
are kept, and so are any audit runs in `runs/Poldrack_2026/`, which still reflect the old
snapshot (the launcher prints a note when there are any).

### 3. Create a blinded run and audit it

Run from the corpus root:

```sh
cd /path/to/autoaudit
~/.claude/skills/reproducibility-audit/scripts/new_run.sh Poldrack_2026 claude-opus-5-5
```

This creates `runs/Poldrack_2026/<run_id>/` with `new_run.py` (recording the model only in
the operator's `registry.jsonl`), checks it with `verify_run.py`, and launches the auditor
in the run folder only if it reports `run_ok`. The harness is chosen from the model name:

| Model name contains | Harness | Headless command |
|---|---|---|
| `claude` | Claude Code | `claude -p --permission-mode auto` |
| `gpt` | Codex | `codex exec --sandbox workspace-write` (network enabled) |
| anything else | opencode via OpenRouter | `opencode run --auto --model openrouter/<model>` |

The transcript is saved to `<run>/audit/agent_log.jsonl` and the report is rendered to
`<run>/audit/audit.html`. Add `--interactive` before the paper ID to open a normal session
instead. Each call creates a fresh run, so repeat it once per model being compared:

```sh
for model in claude-opus-5-5 gpt-5.5 qwen/qwen3-coder; do
  ~/.claude/skills/reproducibility-audit/scripts/new_run.sh Poldrack_2026 "$model"
done
```

### 4. Reconcile the audits into a consensus report

Once two or more runs of a paper have finished, run from the corpus root:

```sh
cd /path/to/autoaudit
~/.claude/skills/audit-consensus/scripts/consensus.sh Poldrack_2026            # default model claude-opus-5-5
~/.claude/skills/audit-consensus/scripts/consensus.sh Poldrack_2026 gpt-5.5    # or choose one
```

The launcher uses only completed runs. A completed run has a rendered `audit.html`, and a
finished transcript if there is one. Unfinished runs are skipped with a warning.

Before the agent starts, the launcher **rewrites model names in each completed run's
`audit/` files**:

- the run's own model becomes its run ID;
- any other model used on the paper becomes `[redacted-model]`;
- the registry keeps the mapping.

It stops without launching in two cases:

- a model name appears outside `audit/` in a file that differs between runs (an identical
  file, such as the README's "Prepared by" line, cannot identify an auditor);
- a model name survives redaction, for example inside a binary cache.

The agent runs in a new `runs/Poldrack_2026/consensus/<consensus_id>/` folder:

- Earlier consensus folders are made unreadable while it runs, then restored.
- It classifies every finding as converged, disputed or untested.
- It runs whatever extra analyses are needed to settle disputed and untested findings, and
  writes `consensus.html`.

Afterwards the launcher writes `run_models.json` and re-renders the report, so the
run-to-model mapping appears in its appendix. It then writes `consensus_unblinded.html`,
a copy of the report with every run ID replaced by its model name (a model that audited
more than once is shown as `model (run_id)`). The consensus agent never sees the names;
`consensus.html` stays blinded. Harness selection and `--interactive` work as
they do for `new_run.sh`.

**The redaction is permanent.** It rewrites the original transcripts and notes in each
run's `audit/`. The registry still maps run IDs to models, so the mapping can be restored.
The prepared inputs (`paper/`, `data/`, `manifest.json`, `README.md`, `run.json`) are never
modified, so `verify_run.py` still reports the runs as unmodified. Redacting a run twice
changes nothing.

#### Output

```
runs/Poldrack_2026/consensus/<consensus_id>/   # <consensus_id> = UTC timestamp + 4 random characters
  inputs.json       # runs reconciled (with audit.qmd hashes), runs skipped, redaction counts
  consensus.qmd     consensus.html
  consensus_unblinded.html   # the report with run IDs replaced by model names
  R/  results/      # the consensus agent's own adjudication analyses and their output
  run_models.json   # run ID -> model, written by the launcher after the agent finishes
  agent_log.jsonl   # headless transcript
```

Each invocation makes a new folder; earlier consensus reports are never overwritten. Run it
again after more audits finish to get a consensus over the larger set.

#### Reading the report

The report explains the paper and its evidence in this order:

- **Paper summary**: the question, design, data, analyses, and central conclusions.
- **Paper-wide problems**: major problems affecting the whole paper, with the evidence
  and impact explained. Omitted when there are none.
- **Main claims**: for each claim, explain what it says, the paper's supporting evidence,
  whether it holds after the audit, and the evidence and scientific impact of any weakening.
  Claims that survive receive explanations too.

The main body uses plain language and enough context to stand alone, without a fixed word
cap or cryptic issue-ID tables. A finding counts as changing a major conclusion when it
moves the consensus verdict to weak or unsupported; smaller downgrades are also explained.

The appendix holds minor issues, unconfirmed concerns noticed during adjudication,
per-audit verdicts, the complete **finding cross-walk**, **Adjudication notes**,
**Cosmetic issues**, analyses, and provenance, including the run-to-model mapping.

Multiplicity criticisms require a justified family based on the scientific inference,
even when all audits agree. Tests in one figure are not automatically a family.
Debatable groupings are sensitivity analyses, not automatic grounds for a downgrade.

Each finding gets one status:

| Status | Meaning | What the consensus agent does |
|---|---|---|
| Converged | Two or more audits raised it; none tested it and found it clean | Checks multiplicity family rationale; otherwise accepts, with spot-checks for disagreements on size or severity |
| Disputed | Raised by at least one audit, and **any** audit tested the same point and found no problem | Re-runs the check and finds out why they differ |
| Single-audit, untested | Raised by one audit; no other audit looked | Runs the check itself |

Disputed and untested findings end up **confirmed**, **partly confirmed**, or **refuted**.
Status is never decided by counting audits.

The appendix includes **Relative audit accuracy and usefulness**: separate judgments for
every included audit, supported by adjudicated findings and allowing ties when the
evidence does not clearly distinguish them. Accuracy concerns correctness and calibration;
usefulness concerns consequential findings, reproducible evidence, and clear explanations
of what holds or changes. The comparison accounts for scope and access to materials,
weights scientific consequence rather than finding counts, and applies to these audits
of this paper, not to the models generally. The consensus does not hunt for new issues
beyond what the audits raised.

### Batch processing

All three launchers exit with the agent's status, so they can be looped. In zsh, use `dir`,
not `path`, as the loop variable:

```sh
cd /path/to/autoaudit
for dir in /path/to/autoaudit/*_20*/; do
  ~/.claude/skills/audit-prep/scripts/prep_paper.sh "$dir" || echo "prep failed: $dir"
done
```

To build consensus reports for every audited paper (papers with fewer than two finished
runs are refused without launching an agent):

```sh
cd /path/to/autoaudit
for dir in runs/*/; do
  ~/.claude/skills/audit-consensus/scripts/consensus.sh "$(basename "$dir")" || echo "no consensus: $dir"
done
```
