#!/usr/bin/env bash
# Usage: uv run bash audit_status.sh [project-directory]
# Processed = finalized manifest; completed audit = nonempty rendered report.
# Preparation models come from the manifest; audit models from registry.jsonl.
set -euo pipefail

ROOT="${1:-$(cd "$(dirname "$0")" && pwd -P)}"
command -v jq >/dev/null || { echo 'jq is required' >&2; exit 1; }
[[ -d "$ROOT" ]] || { echo "Not a directory: $ROOT" >&2; exit 1; }
registry="$ROOT/registry.jsonl"
[[ -f "$registry" ]] || registry=/dev/null
# Parse once, and fail visibly if the registry is malformed.
records=$(jq -s '.' "$registry")

for dir in "$ROOT"/*/; do
    [[ -d "$dir" ]] || continue
    paper="${dir%/}"
    paper="${paper##*/}"
    case "$paper" in logs|prepared|runs) continue ;; esac

    processed=no
    manifest="$ROOT/prepared/$paper/manifest.json"
    if [[ -f "$manifest" ]]; then
        processed=$(jq -r 'if .finalized == true then
            "yes (\(.prepared_by // "unknown"))" else "no" end' "$manifest")
    fi

    audits=""
    while IFS=$'\t' read -r run_id model; do
        [[ -n "$run_id" ]] || continue
        if [[ -s "$ROOT/runs/$paper/$run_id/audit/audit.html" ]]; then
            audits="${audits:+$audits, }$run_id ($model)"
        fi
    done < <(jq -r --arg paper "$paper" '.[] | select(.paper_id == $paper)
        | [.run_id, (.model // "unknown")] | @tsv' <<< "$records")
    printf '%s:\nprocessed=%s\naudits=%s\n\n' "$paper" "$processed" "${audits:-none}"
done
