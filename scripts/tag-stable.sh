#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: git repository not initialized."
  exit 1
fi

current_branch="$(git branch --show-current)"
if [[ "$current_branch" != "main" ]]; then
  echo "ERROR: stable tagging is only allowed from main. Current branch: $current_branch"
  exit 1
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "ERROR: working tree is not clean. Commit or stash changes before tagging."
  exit 1
fi

TAG_INPUT="${1:-}"
if [[ -n "$TAG_INPUT" ]]; then
  TAG_NAME="$TAG_INPUT"
else
  TAG_NAME="stable-$(date -u +%Y%m%d-%H%M%S)"
fi

git tag -a "$TAG_NAME" -m "Stable release $TAG_NAME"
echo "Created stable tag: $TAG_NAME"

if git remote get-url origin >/dev/null 2>&1; then
  git push origin main
  git push origin "$TAG_NAME"
  echo "Pushed main and tag to origin."
else
  echo "No GitHub remote configured. Tag exists locally only."
fi
