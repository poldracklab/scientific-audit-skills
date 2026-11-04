#!/usr/bin/env bash
# Launch a coding agent to run the audit-prep skill on one raw paper folder.
#
# usage: prep_paper.sh [--interactive] [--overwrite] <raw_paper_dir> [model]
#
# <raw_paper_dir> must sit directly inside a corpus initialized with
# `prep.py init` (i.e. its parent contains .autoaudit-root). The agent runs
# in the corpus root. The model defaults to claude-opus-5-5 and is also
# recorded as the plan's reviewed_by. The harness is chosen from the model
# name: *claude* -> Claude Code, *gpt* -> Codex, anything else -> opencode
# via OpenRouter (e.g. qwen/qwen3-coder runs as openrouter/qwen/qwen3-coder).
#
# By default the session is headless: it runs with --permission-mode auto,
# exits when done, writes its transcript to <corpus>/logs/prep/, and exits
# with the agent's status. --interactive opens a normal session instead.
#
# --overwrite first removes the earlier prep of this paper: the draft or
# finalized prepared/<paper>/, the scan outputs prep.yaml and statements.md in
# the raw folder, and its transcripts in logs/prep/. Supplied raw files and
# audit runs under runs/<paper>/ are kept.
set -euo pipefail

DEFAULT_MODEL="claude-opus-5-5"

usage() {
    echo "usage: $(basename "$0") [--interactive] [--overwrite] <raw_paper_dir> [model]   (default model: $DEFAULT_MODEL)" >&2
    exit 2
}

die() {
    echo "$(basename "$0"): $1" >&2
    exit "${2:-1}"
}

find_root() {
    local dir="$1"
    while [ "$dir" != "/" ]; do
        [ -e "$dir/.autoaudit-root" ] && { echo "$dir"; return 0; }
        dir="$(dirname "$dir")"
    done
    return 1
}

check_layout() {
    local paper_dir="$1" root="$2"
    [ "$(dirname "$paper_dir")" = "$root" ] ||
        die "$paper_dir must be directly inside the corpus root $root"
}

build_prompt() {
    local paper="$1" root="$2" model="$3"
    cat <<EOF
Use the audit-prep skill to prepare $paper (corpus root: $root).

Corpus-wide settings:
structured_conversion: true; reviewed_by: $model.

Finalize if review is clean.
EOF
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

run_headless() {
    local model="$1" prompt="$2" log="$3" status=0
    mkdir -p "$(dirname "$log")"
    echo "Transcript: $log"
    launch_headless "$model" "$prompt" > "$log" || status=$?
    print_result "$log"
    return "$status"
}

remove_tree() {
    [ -e "$1" ] || return 0
    chmod -R u+w "$1"
    rm -rf "$1"
}

remove_earlier_prep() {
    local root="$1" paper="$2" log
    remove_tree "$root/prepared/$paper"
    rm -f "$root/$paper/prep.yaml" "$root/$paper/statements.md"
    for log in "$root/logs/prep/$paper"-[0-9]*T[0-9]*Z.jsonl; do
        [ -f "$log" ] && rm -f "$log"
    done
    if [ -d "$root/runs/$paper" ]; then
        echo "$(basename "$0"): note: audit runs in $root/runs/$paper were made from the removed snapshot; they are kept" >&2
    fi
    return 0
}

main() {
    local interactive=0 overwrite=0
    while [ $# -gt 0 ]; do
        case "$1" in
            --interactive) interactive=1 ;;
            --overwrite)   overwrite=1 ;;
            --*)           usage ;;
            *)             break ;;
        esac
        shift
    done
    [ $# -ge 1 ] && [ $# -le 2 ] || usage
    [ -d "$1" ] || die "not a directory: $1" 2
    local paper_dir root model paper prompt
    paper_dir="$(cd "$1" && pwd -P)"
    model="${2:-$DEFAULT_MODEL}"
    root="$(find_root "$(dirname "$paper_dir")")" ||
        die "no .autoaudit-root above $paper_dir; run prep.py init <corpus> first"
    check_layout "$paper_dir" "$root"
    paper="$(basename "$paper_dir")"
    prompt="$(build_prompt "$paper" "$root" "$model")"
    [ "$overwrite" = 1 ] && remove_earlier_prep "$root" "$paper"
    cd "$root"
    if [ "$interactive" = 1 ]; then
        launch_interactive "$model" "$prompt"
    fi
    run_headless "$model" "$prompt" "$root/logs/prep/$paper-$(date -u +%Y%m%dT%H%M%SZ).jsonl"
}

main "$@"
