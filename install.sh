#!/usr/bin/env bash
# install symlinks in harness dirs

# start by updating any npx-installed skills
npx skills@latest update -g

set -euo pipefail
repo="$(cd "$(dirname "$0")" && pwd)"
for target in ~/.agents/skills ~/.claude/skills; do
  mkdir -p "$target"
  for skill in "$repo"/*/; do
    name="$(basename "$skill")"
    [ -f "$skill/SKILL.md" ] || continue
    echo "linking $skill to $target"
    ln -sfn "$skill" "$target/$name"
  done
done
