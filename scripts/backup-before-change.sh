#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: git repository not initialized."
  exit 1
fi

STAMP="$(date -u +%Y%m%d-%H%M%S)"
BACKUP_DIR="$ROOT_DIR/backups"
BACKUP_FILE="$BACKUP_DIR/prechange-${STAMP}.tar.gz"
COMMIT_MESSAGE="${1:-backup: pre-change snapshot ${STAMP}}"

mkdir -p "$BACKUP_DIR"

# Backup only paths that exist in this installation.
candidate_paths=(
  "scripts"
  ".githooks"
  ".gitignore"
  ".gitattributes"
  "README.VERSIONING.md"
  "workspace"
  "trading-stack"
  "workspace-shelter"
  "workspace-vanilmirth"
  "workspace-filir"
  "workspace-amistr"
)

existing_paths=()
for path in "${candidate_paths[@]}"; do
  if [[ -e "$path" ]]; then
    existing_paths+=("$path")
  fi
done

if [[ "${#existing_paths[@]}" -eq 0 ]]; then
  echo "ERROR: nothing to back up. Expected project paths were not found."
  exit 1
fi

tar \
  --exclude-vcs \
  --exclude='*.env' \
  --exclude='.env*' \
  --exclude='*.sqlite*' \
  --exclude='*.log' \
  --exclude='*.jsonl' \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='.openclaw' \
  -czf "$BACKUP_FILE" \
  "${existing_paths[@]}"

echo "Backup created: $BACKUP_FILE"

git add -A
if git diff --cached --quiet; then
  echo "No git changes to commit."
  exit 0
fi

"$ROOT_DIR/scripts/secret-scan-staged.sh"
git commit -m "$COMMIT_MESSAGE"
echo "Committed pre-change snapshot on branch: $(git branch --show-current)"
