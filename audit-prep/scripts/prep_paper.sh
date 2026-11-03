#!/usr/bin/env bash
# Launch Claude Code to run the audit-prep skill on one raw paper folder.
#
# usage: prep_paper.sh <raw_paper_dir> [model]
#
# <raw_paper_dir> must sit directly inside a corpus initialized with
# `prep.py init` (i.e. its parent contains .autoaudit-root). Claude Code is
# started in the corpus root. The model defaults to claude-opus-5-5 and is
# also recorded as the plan's reviewed_by.
set -euo pipefail

DEFAULT_MODEL="claude-opus-5-5"

usage() {
    echo "usage: $(basename "$0") <raw_paper_dir> [model]   (default model: $DEFAULT_MODEL)" >&2
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

main() {
    [ $# -ge 1 ] && [ $# -le 2 ] || usage
    [ -d "$1" ] || die "not a directory: $1" 2
    local paper_dir root model
    paper_dir="$(cd "$1" && pwd -P)"
    model="${2:-$DEFAULT_MODEL}"
    root="$(find_root "$(dirname "$paper_dir")")" ||
        die "no .autoaudit-root above $paper_dir; run prep.py init <corpus> first"
    check_layout "$paper_dir" "$root"
    cd "$root"
    exec claude --model "$model" "$(build_prompt "$(basename "$paper_dir")" "$root" "$model")"
}

main "$@"
