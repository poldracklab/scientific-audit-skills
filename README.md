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

Clone this repository, then run `bash install.sh`. It symlinks each skill into
`~/.claude/skills` and `~/.agents/skills`, so edits in the clone take effect immediately.
The launcher scripts below are installed with their skills.

### Requirements

Core:

- [uv](https://docs.astral.sh/uv/) — runs every Python script (dependencies are declared
  inline, so there is nothing else to install).
- Node.js / `npx` — `install.sh` first updates any `npx skills`-installed skills.
- At least one coding agent CLI:
  [Claude Code](https://docs.claude.com/en/docs/claude-code) (`claude`; required for
  `prep_paper.sh`), and optionally [Codex](https://github.com/openai/codex) (`codex`) or
  [opencode](https://opencode.ai) (`opencode`, with an OpenRouter key) for auditing other
  models.

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
render `audit/audit.qmd`. Agents install any R packages an audit needs under `audit/`.

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
```

### 1. Initialize the corpus (once)

```sh
uv run ~/.claude/skills/audit-prep/scripts/prep.py init /path/to/autoaudit
```

### 2. Prepare the paper

```sh
~/.claude/skills/audit-prep/scripts/prep_paper.sh /path/to/autoaudit/Poldrack_2026
```

This starts Claude Code (`claude-opus-5-5` by default; pass another model as a second
argument) in the corpus root with the audit-prep skill. The model scans the folder, reviews
`prep.yaml`, fetches linked materials, and finalizes `prepared/Poldrack_2026/` if review is
clean. `reviewed_by` is set to the model name.

The session is headless: it runs with `--permission-mode auto`, exits when done, prints the
model's final message, saves the full transcript to
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

### Batch processing

Both scripts exit with the agent's status, so they can be looped. In zsh, use `dir`, not
`path`, as the loop variable:

```sh
cd /path/to/autoaudit
for dir in /path/to/autoaudit/*_20*/; do
  ~/.claude/skills/audit-prep/scripts/prep_paper.sh "$dir" || echo "prep failed: $dir"
done
```

### Isolation

Blinding only holds if the auditor cannot see anything outside its run folder. In
particular, it must not read:

- `registry.jsonl`, which maps run IDs to models;
- other runs of the same paper (another model's audit);
- `prepared/` and the raw folders (harmless for blinding, but outside the common
  starting materials).

`new_run.sh` only sets the working directory. By default every agent CLI can **read any
file your user account can read**, so a curious or thorough auditor could `ls ../..` and
find the registry. The options below are listed from most to least reliable. Whatever you
choose, test it with a probe before a real audit (see the end of this section).

#### Any harness: container or separate user (most reliable)

Run the agent where the rest of the corpus does not exist. With Docker, mount only the
run folder plus the agent's credentials:

```sh
run=/path/to/autoaudit/runs/Poldrack_2026/<run_id>
docker run --rm -it -v "$run":/work -w /work \
  -e ANTHROPIC_API_KEY \
  my-audit-image claude -p --model claude-opus-5-5 --permission-mode auto "<prompt>"
```

The image needs the agent CLI, uv, R, Quarto and the skills installed. Pass credentials
as an environment variable (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`) or
mount the CLI's auth file read-only (for Codex, `~/.codex/auth.json`). Network access stays
on.

Without containers, run the agent as a separate account (e.g. `auditbot`) that can read
only the current run. `chmod 700` the corpus and every run folder, `chown -R auditbot` the
active run, give `auditbot` traverse (`x`) permission on the parent directories, and launch
with `sudo -u auditbot -H ...`. That account needs its own agent login.

#### Claude Code: settings plus sandbox

Claude Code can enforce this itself, with one session-only settings override passed via
`--settings` (your `~/.claude/settings.json` is not changed). It needs two layers:

- `blockReadsOutsideWorkingDirectories` / `blockWritesOutsideWorkingDirectories` confine
  the Read/Edit/Write file tools in every permission mode.
- The OS sandbox (Seatbelt on macOS, bubblewrap on Linux) confines Bash. Without it,
  `python -c "open('../../../registry.jsonl')"` slips past the file-tool rules.

```sh
claude -p --model claude-opus-5-5 --permission-mode auto --settings '{
  "permissions": {
    "blockReadsOutsideWorkingDirectories": true,
    "blockWritesOutsideWorkingDirectories": true
  },
  "sandbox": {
    "enabled": true,
    "failIfUnavailable": true,
    "allowUnsandboxedCommands": false,
    "filesystem": {
      "denyRead": ["/path/to/autoaudit"],
      "allowRead": ["/path/to/autoaudit/runs/Poldrack_2026/<run_id>"]
    },
    "network": {
      "allowedDomains": ["cloud.r-project.org", "github.com", "objects.githubusercontent.com",
                         "osf.io", "api.osf.io", "files.osf.io", "zenodo.org", "doi.org"]
    }
  }
}' "<prompt>"
```

Notes:

- `failIfUnavailable` makes the run fail instead of silently running unsandboxed.
  `allowUnsandboxedCommands: false` stops a blocked command from being retried outside the
  sandbox.
- The sandbox blocks all network traffic except `allowedDomains`. Extend the list for any
  journal, data host or package mirror an audit needs, and look in the transcript for
  blocked fetches. This limits evidence discovery, so it trades breadth for isolation.
- Version-dependent: these settings require a recent Claude Code (checked against 2.1.317).

#### Codex: a permission profile

`--sandbox workspace-write` (what `new_run.sh` uses) confines **writes only**; Codex can
still read the whole disk. Reads are confined by a permission profile (beta). Keep it in a
dedicated `CODEX_HOME` so your normal Codex config is unaffected:

```toml
# ~/.codex-audit/config.toml
default_permissions = "workspace-only"

[permissions.workspace-only]
extends = ":workspace"

[permissions.workspace-only.filesystem]
":root" = "deny"
":minimal" = "read"
":tmpdir" = "deny"
":slash_tmp" = "deny"

[permissions.workspace-only.network]
enabled = true
```

```sh
cp ~/.codex/auth.json ~/.codex-audit/
CODEX_HOME=~/.codex-audit codex exec -m gpt-5.5 --skip-git-repo-check --json "<prompt>"
```

Profiles are **ignored** if `--sandbox` is passed or `sandbox_mode` is set in the config,
so this command omits `--sandbox`. To use it with `new_run.sh`, the script's Codex line has
to change accordingly. Because the feature is beta, the probe test matters here.

#### opencode: container or separate user only

opencode has no OS-level sandbox. Its permission rules can deny paths outside the project,
for one session:

```sh
OPENCODE_CONFIG_CONTENT='{"permission": {"external_directory": "deny"}}' \
  opencode run --auto --model openrouter/qwen/qwen3-coder "<prompt>"
```

(`external_directory` must be `deny`, since `--auto` approves anything set to `ask`.) The
check is a best-effort parse of tool paths and shell commands. A Python one-liner or a
generated script bypasses it, so use a container or a separate user for real blinding.

#### Probe test

From a fresh run folder, launch the agent with your isolation setup and ask it to try:

```
Run each of these and report the output verbatim:
cat ../../../registry.jsonl
ls ../..
python3 -c "print(open('../../../registry.jsonl').read())"
```

All three should fail. Then delete the probe run and create a fresh one for the real
audit.

`new_run.sh` creates runs under the corpus. To place them elsewhere (e.g. outside
Dropbox), call `new_run.py --runs-root` directly. That alone does not provide isolation,
since the registry stays readable.
