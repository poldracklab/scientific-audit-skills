#!/usr/bin/env bash
# Create a blinded neuroimaging validity audit run for a finalized paper and launch an auditor in it.
#
# usage: new_run.sh [--interactive] <paper_id> <model>
#
# Run from the corpus root (the directory holding .autoaudit-root). The
# harness is chosen from the model name: *claude* -> Claude Code,
# *gpt* -> Codex, anything else -> opencode via OpenRouter.
#
# By default the auditor runs headless: it exits when done, writes its
# transcript to <run>/audit/agent_log.jsonl, and this script exits with the
# agent's status. --interactive opens a normal session instead.
set -euo pipefail

usage() {
    echo "usage: $(basename "$0") [--interactive] <paper_id> <model>" >&2
    exit 2
}

die() {
    echo "$(basename "$0"): $1" >&2
    exit 1
}

prep_scripts() {
    local skills_dir
    skills_dir="$(cd "$(dirname "$0")/../.." && pwd)"
    echo "$skills_dir/audit-prep/scripts"
}

build_prompt() {
    cat <<EOF
Use the neuroimaging-validity-audit skill to audit the paper in this run folder.

The current directory is an audit-prep run for $1. Start with the skill's intake step (verify_run.py on this folder); proceed only if it reports run_ok.

Write all output under audit/ and leave every other file in the run folder unchanged.

Render audit/audit.html locally and give me the file path when done. Do not publish it anywhere.
EOF
}

create_run() {
    local paperdir="$1" model="$2" root="$3" prep rundir status
    prep="$(prep_scripts)"
    rundir="$(uv run "$prep/new_run.py" "$paperdir" --model "$model" --root "$root")"
    echo "New run dir for $model: $rundir" >&2
    status="$(uv run "$prep/verify_run.py" "$rundir" | head -1)"
    echo "verify_run: $status" >&2
    [ "$status" = "run_ok" ] || die "run folder did not verify ($status); not launching an agent."
    echo "$rundir"
}

harness() {
    case "$(echo "$1" | tr '[:upper:]' '[:lower:]')" in
        *claude*) echo claude ;;
        *gpt*)    echo codex ;;
        *)        echo opencode ;;
    esac
}

launch_interactive() {
    local model="$1" prompt="$2"
    case "$(harness "$model")" in
        claude)   exec claude --model "$model" "$prompt" ;;
        codex)    exec codex --model "$model" "$prompt" ;;
        opencode) exec opencode run --model "openrouter/$model" "$prompt" ;;
    esac
}

launch_headless() {
    local model="$1" prompt="$2"
    case "$(harness "$model")" in
        claude)   claude -p --model "$model" --permission-mode auto \
                      --output-format stream-json --verbose "$prompt" ;;
        codex)    codex exec -m "$model" --sandbox workspace-write \
                      -c sandbox_workspace_write.network_access=true \
                      --skip-git-repo-check --json "$prompt" ;;
        opencode) opencode run --auto --model "openrouter/$model" --format json "$prompt" ;;
    esac
}

print_result() {
    uv run --no-project --quiet python -I -c '
import json, sys
for line in open(sys.argv[1], encoding="utf-8"):
    try:
        event = json.loads(line)
    except ValueError:
        continue
    if isinstance(event, dict) and event.get("type") == "result":
        print(event.get("result", ""))
' "$1" || true
}

run_headless() {
    local model="$1" prompt="$2" log="audit/agent_log.jsonl" status=0
    echo "Transcript: $PWD/$log"
    launch_headless "$model" "$prompt" > "$log" || status=$?
    print_result "$log"
    return "$status"
}

main() {
    local interactive=0
    [ "${1:-}" = "--interactive" ] && { interactive=1; shift; }
    [ $# -eq 2 ] || usage
    local paperdir="$1" model="$2" root rundir prompt
    root="$(pwd -P)"
    [ -e "$root/.autoaudit-root" ] || die "run from the corpus root (no .autoaudit-root in $root)"
    rundir="$(create_run "$paperdir" "$model" "$root")"
    prompt="$(build_prompt "$paperdir")"
    cd "$rundir"
    if [ "$interactive" = 1 ]; then
        launch_interactive "$model" "$prompt"
    fi
    run_headless "$model" "$prompt"
}

main "$@"
