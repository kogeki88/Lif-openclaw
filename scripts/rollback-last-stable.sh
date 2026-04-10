#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TARGET_TAG="${1:-}"
PUSH_AFTER="${2:-}"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: git repository not initialized."
  exit 1
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "ERROR: working tree is not clean. Commit or stash changes before rollback."
  exit 1
fi

if [[ -z "$TARGET_TAG" ]]; then
  TARGET_TAG="$(git tag --list 'stable-*' --sort=-creatordate | head -n 1)"
fi

if [[ -z "$TARGET_TAG" ]]; then
  echo "ERROR: no stable tags found. Tag a stable release first."
  exit 1
fi

if ! git rev-parse "$TARGET_TAG" >/dev/null 2>&1; then
  echo "ERROR: tag not found: $TARGET_TAG"
  exit 1
fi

STAMP="$(date -u +%Y%m%d-%H%M%S)"
SAFETY_BRANCH="rollback-safety-${STAMP}"
CURRENT_BRANCH="$(git branch --show-current)"

git checkout -b "$SAFETY_BRANCH"
git checkout main
git reset --hard "$TARGET_TAG"

echo "Rollback complete."
echo "  Restored main to tag: $TARGET_TAG"
echo "  Safety branch saved: $SAFETY_BRANCH (from prior state on $CURRENT_BRANCH)"

if [[ "$PUSH_AFTER" == "--push" ]]; then
  if git remote get-url origin >/dev/null 2>&1; then
    git push origin "$SAFETY_BRANCH"
    git push --force-with-lease origin main
    echo "Pushed rollback to GitHub (main force-updated safely with lease)."
  else
    echo "No GitHub remote configured; skip push."
  fi
fi
