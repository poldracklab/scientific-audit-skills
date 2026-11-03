
### Isolation

Blinding only holds if the auditor cannot see anything outside its run folder. In
particular, it must not read:

- `registry.jsonl`, which maps run IDs to models;
- other runs of the same paper (another model's audit);
- `prepared/` and the raw folders (harmless for blinding, but outside the common
  starting materials).

The consensus agent is different: it must read the other runs of its paper. Blinding there
works by rewriting the model names in those runs (see step 4), not by hiding them. The launcher enforces two things:

- Claude Code is given read access only to the completed runs listed in `inputs.json`;
- earlier consensus folders, which hold `run_models.json`, are unreadable while the agent runs.

Two rules are instructions only: never read `registry.jsonl`, and never read runs that are
still in progress. The isolation options below apply to the consensus agent too, as long as
the paper's run folders stay readable.

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
