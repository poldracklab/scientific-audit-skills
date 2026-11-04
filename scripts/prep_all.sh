#!/usr/bin/env bash
# Run audit-prep on every paper folder in this corpus (skips logs, prepared, runs).
# usage: ./prep_all.sh [model]
set -uo pipefail

MODEL="${1:-deepseek/deepseek-v4.1-flash-1017}"
PREP="$HOME/.claude/skills/audit-prep/scripts/prep_paper.sh"
ROOT="$(cd "$(dirname "$0")" && pwd -P)"

failed=()
for dir in "$ROOT"/*/; do
    paper="$(basename "$dir")"
    case "$paper" in logs|prepared|runs) continue ;; esac
    if grep -q '"finalized": true' "$ROOT/prepared/$paper/manifest.json" 2>/dev/null; then
        echo "=== $paper: already finalized, skipping ==="
        continue
    fi
    echo "=== $paper ==="
    "$PREP" "$ROOT/$paper" "$MODEL" || failed+=("$paper")
done

if [ ${#failed[@]} -gt 0 ]; then
    echo "Failed: ${failed[*]}"
    exit 1
fi
echo "All papers prepped."
