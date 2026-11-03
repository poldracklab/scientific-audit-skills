#!/usr/bin/env bash
# Launch Claude Code to run the audit-prep skill on one raw paper folder.
#
# usage: prep_paper.sh [--interactive] <raw_paper_dir> [model]
#
# <raw_paper_dir> must sit directly inside a corpus initialized with
# `prep.py init` (i.e. its parent contains .autoaudit-root). Claude Code runs
# in the corpus root. The model defaults to claude-opus-5-5 and is also
# recorded as the plan's reviewed_by.
#
# By default the session is headless: it runs with --permission-mode auto,
# exits when done, writes its transcript to <corpus>/logs/prep/, and exits
# with the agent's status. --interactive opens a normal session instead.
set -euo pipefail

DEFAULT_MODEL="claude-opus-5-5"

usage() {
    echo "usage: $(basename "$0") [--interactive] <raw_paper_dir> [model]   (default model: $DEFAULT_MODEL)" >&2
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

run_headless() {
    local model="$1" prompt="$2" log="$3" status=0
    mkdir -p "$(dirname "$log")"
    echo "Transcript: $log"
    claude -p --model "$model" --permission-mode auto \
        --output-format stream-json --verbose "$prompt" > "$log" || status=$?
    print_result "$log"
    return "$status"
}

main() {
    local interactive=0
    [ "${1:-}" = "--interactive" ] && { interactive=1; shift; }
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
    cd "$root"
    if [ "$interactive" = 1 ]; then
        exec claude --model "$model" "$prompt"
    fi
    run_headless "$model" "$prompt" "$root/logs/prep/$paper-$(date -u +%Y%m%dT%H%M%SZ).jsonl"
}

main "$@"
