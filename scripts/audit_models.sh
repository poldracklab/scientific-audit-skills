#!/usr/bin/env bash
# Usage: uv run bash audit_models.sh <paper-directory> [model ...]
# Requires a finalized paper from audit-prep.
set -euo pipefail

if [[ $# -eq 0 || "${1:-}" == --help ]]; then
    echo "Usage: uv run bash audit_models.sh <paper-directory> [model ...]"
    [[ $# -gt 0 ]] && exit 0
    exit 2
fi

ROOT="$(cd "$(dirname "$0")" && pwd -P)"
RUNNER="$HOME/.agents/skills/reproducibility-audit/scripts/new_run.sh"
[[ -d "$1" ]] || { echo "Not a directory: $1" >&2; exit 1; }
PAPER="$(cd "$1" && pwd -P)"
shift

if [[ $# -eq 0 ]]; then
    set -- claude-opus-5-5 gpt-5.6-sol deepseek/deepseek-v4.1-flash
fi
[[ -f "$RUNNER" ]] || { echo "Audit launcher not found: $RUNNER" >&2; exit 1; }
cd "$ROOT"

failed=()
for model in "$@"; do
    echo "=== $(basename "$PAPER"): $model ==="
    uv run bash "$RUNNER" "$PAPER" "$model" || failed+=("$model")
done

if [[ ${#failed[@]} -gt 0 ]]; then
    echo "Failed models: ${failed[*]}" >&2
    exit 1
fi
echo "All audits completed."
