#!/usr/bin/env bash
# Reconcile all completed audits of one paper into a consensus report.
#
# usage: consensus.sh [--interactive] <paper_id> [<model>]
#
# Run from the corpus root (the directory holding .autoaudit-root). The
# default model is claude-opus-5-5; the harness is chosen from the model
# name as in new_run.sh: *claude* -> Claude Code, *gpt* -> Codex, anything
# else -> opencode via OpenRouter.
#
# Before the agent starts, model names in the completed source runs are
# replaced with run IDs (consensus.py prepare). After it finishes, the
# run-ID -> model mapping is written to run_models.json and the report is
# re-rendered so it appears in the appendix.
set -euo pipefail

DEFAULT_MODEL="claude-opus-5-5"

usage() {
    echo "usage: $(basename "$0") [--interactive] <paper_id> [<model>]" >&2
    exit 2
}

die() {
    echo "$(basename "$0"): $1" >&2
    exit 1
}

scripts_dir() {
    cd "$(dirname "$0")" && pwd
}

build_prompt() {
    cat <<EOF
Use the audit-consensus skill to reconcile the audits of $1.

The current directory is a new consensus folder; inputs.json lists the completed runs, which are in ../../<run_id>/. Read the source runs but never modify them. Never read other folders under ../ (earlier consensus runs) or runs not listed in inputs.json. Never read registry.jsonl.

Write all output in the current directory. Render consensus.html locally and give me the file path when done. Do not publish it anywhere.
EOF
}

prepare_folder() {
    local scripts="$1" paper="$2" root="$3"
    uv run --quiet "$scripts/consensus.py" prepare "$paper" --root "$root" \
        || die "could not prepare a consensus folder for $paper; no agent launched."
}

run_dirs() {
    uv run --no-project --quiet python -I -c '
import json, sys
for run in json.load(open("inputs.json", encoding="utf-8"))["runs"]:
    print(sys.argv[1] + "/" + run["run_id"])
' "$1"
}

add_dir_flags() {
    local dir
    while IFS= read -r dir; do printf -- "--add-dir\0%s\0" "$dir"; done
}

HIDDEN=()

file_mode() {
    stat -f %Lp "$1" 2>/dev/null || stat -c %a "$1"
}

# Earlier consensus folders hold run_models.json and earlier verdicts; make them
# unreadable while the agent runs. HIDDEN entries are "<mode>:<dir>".
hide_earlier() {
    local dir
    for dir in ../*/; do
        dir="${dir%/}"
        [ "$dir" = "../$(basename "$PWD")" ] && continue
        HIDDEN+=("$(file_mode "$dir"):$dir")
        chmod 000 "$dir"
    done
}

restore_hidden() {
    local entry
    for entry in "${HIDDEN[@]+"${HIDDEN[@]}"}"; do chmod "${entry%%:*}" "${entry#*:}"; done
    HIDDEN=()
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
    shift 2
    case "$(harness "$model")" in
        claude)   claude --model "$model" "$@" -- "$prompt" ;;
        codex)    codex --model "$model" "$prompt" ;;
        opencode) opencode run --model "openrouter/$model" "$prompt" ;;
    esac
}

launch_headless() {
    local model="$1" prompt="$2"
    shift 2
    case "$(harness "$model")" in
        claude)   claude -p --model "$model" --permission-mode auto \
                      --output-format stream-json --verbose "$@" -- "$prompt" ;;
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
    local log="agent_log.jsonl" status=0
    echo "Transcript: $PWD/$log"
    launch_headless "$@" > "$log" || status=$?
    print_result "$log"
    return "$status"
}

finish_report() {
    local scripts="$1" root="$2"
    uv run --quiet "$scripts/consensus.py" attach-models "$PWD" --root "$root" > /dev/null
    if [ -f consensus.qmd ]; then
        quarto render consensus.qmd || echo "warning: re-render with model mapping failed" >&2
    fi
}

main() {
    local interactive=0 status=0
    [ "${1:-}" = "--interactive" ] && { interactive=1; shift; }
    [ $# -ge 1 ] && [ $# -le 2 ] || usage
    local paper="$1" model="${2:-$DEFAULT_MODEL}" root scripts outdir prompt
    root="$(pwd -P)"
    [ -e "$root/.autoaudit-root" ] || die "run from the corpus root (no .autoaudit-root in $root)"
    scripts="$(scripts_dir)"
    outdir="$(prepare_folder "$scripts" "$paper" "$root")"
    echo "Consensus folder: $outdir" >&2
    prompt="$(build_prompt "$paper")"
    cd "$outdir"
    local -a dirs=()
    while IFS= read -r -d "" flag; do dirs+=("$flag"); done < <(run_dirs "$root/runs/$paper" | add_dir_flags)
    trap restore_hidden EXIT
    hide_earlier
    if [ "$interactive" = 1 ]; then
        launch_interactive "$model" "$prompt" "${dirs[@]}" || status=$?
    else
        run_headless "$model" "$prompt" "${dirs[@]}" || status=$?
    fi
    restore_hidden
    finish_report "$scripts" "$root"
    return "$status"
}

main "$@"
