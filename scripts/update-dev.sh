#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MESSAGE="${1:-dev update}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: git repository not initialized."
  exit 1
fi

if ! git show-ref --verify --quiet refs/heads/dev; then
  git branch dev main
fi
git checkout dev
"$ROOT_DIR/scripts/backup-before-change.sh" "dev: ${MESSAGE} (${STAMP})"

if git remote get-url origin >/dev/null 2>&1; then
  git push -u origin dev
  echo "Pushed dev changes to origin/dev."
else
  echo "No GitHub remote configured yet. Commit kept locally on dev."
  echo "Set remote later with:"
  echo "  git remote add origin <GITHUB_REPO_URL>"
fi
