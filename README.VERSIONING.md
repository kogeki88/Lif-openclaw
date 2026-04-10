# OpenClaw VPS Safe Versioning & Rollback

This repo uses a **safe two-branch workflow**:
- `main` = stable, known-good state
- `dev` = testing and changes in progress

Design goals:
- Always create a backup before risky changes
- Keep rollback fast
- Never commit secrets/tokens/runtime state

## One-Time Setup

Run from your OpenClaw root folder (for VPS: `/root/.openclaw` or `/home/lifadmin/.openclaw`):

```bash
git init -b main
git config core.hooksPath .githooks
chmod +x scripts/*.sh .githooks/pre-commit
git add -A
git commit -m "chore: initialize safe versioning + rollback workflow"
git branch dev
```

If using GitHub:

```bash
git remote add origin <GITHUB_REPO_URL>
git push -u origin main
git push -u origin dev
```

## Daily Safe Workflow

1. Work in `dev`.
2. Use backup script before any risky change.
3. Validate/test.
4. Merge `dev` into `main` only when known-good.
5. Tag stable versions on `main`.

## Scripts

- `scripts/backup-before-change.sh`
  - Creates timestamped tar backup in `backups/` (auto-detects existing project folders)
  - Commits a pre-change snapshot (if changes exist)
- `scripts/update-dev.sh "message"`
  - Ensures `dev` branch exists, switches to it
  - Runs backup script with your message as commit text
  - Pushes to GitHub if `origin` exists
- `scripts/tag-stable.sh [stable-YYYYMMDD-HHMMSS]`
  - Creates annotated stable tag from `main`
  - Pushes tag if `origin` exists
- `scripts/rollback-last-stable.sh [tag] [--push]`
  - Creates safety branch from current state
  - Hard-resets `main` to latest `stable-*` tag (or specified tag)
  - Optional `--push` force-updates remote `main` safely with lease

## Exact Command Recipes

### Save current stable version

```bash
git checkout main
./scripts/backup-before-change.sh
./scripts/tag-stable.sh
```

### Push test changes

```bash
git checkout dev
./scripts/update-dev.sh "describe your test change"
```

### Tag a stable release

```bash
git checkout main
git merge --ff-only dev
./scripts/tag-stable.sh stable-$(date -u +%Y%m%d-%H%M%S)
```

### Roll back to last stable version

```bash
git checkout main
./scripts/rollback-last-stable.sh
```

If you need to push rollback to GitHub immediately:

```bash
./scripts/rollback-last-stable.sh "" --push
```

## Safety Rules (Important)

- Never commit `.env`, tokens, auth files, `openclaw.json`, runtime DB/log/session files.
- Pre-commit secret scan runs automatically through `.githooks/pre-commit`.
- Every rollback creates a `rollback-safety-*` branch first.
- Prefer `--ff-only` merges from `dev` to `main` to keep history clean and auditable.
