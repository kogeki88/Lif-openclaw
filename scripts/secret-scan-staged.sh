#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: not inside a git repository."
  exit 1
fi

staged_files="$(git diff --cached --name-only)"
if [[ -z "${staged_files}" ]]; then
  exit 0
fi

blocked_file_regex='(^|/)\.env($|\.|/)|(^|/)openclaw\.json($|\.|/)|(^|/)exec-approvals\.json$|(^|/)auth-profiles\.json$|(^|/)vps_access_credentials\.json$|(^|/)lifadmin_key$|(^|/)credentials(/|$)|(^|/)identity(/|$)|(^|/)agents(/|$)|(^|/)memory(/|$)|(^|/)logs(/|$)|(^|/)tasks(/|$)|(^|/)\.openclaw(/|$)|(^|/)\.venv(/|$)|\.sqlite($|\.|/)'

if echo "$staged_files" | grep -E "$blocked_file_regex" >/dev/null; then
  echo "ERROR: blocked sensitive/runtime file detected in staged changes."
  echo "$staged_files" | grep -E "$blocked_file_regex" || true
  exit 1
fi

added_lines="$(git diff --cached -U0 --no-color | grep -E '^\+' | grep -vE '^\+\+\+' || true)"
if [[ -z "$added_lines" ]]; then
  echo "Secret scan passed."
  exit 0
fi

# Direct token signatures.
direct_secret_regex='(sk-or-v1-[A-Za-z0-9]{24,}|xai-[A-Za-z0-9_-]{24,}|AIza[0-9A-Za-z_-]{20,}|[A-Za-z0-9_-]{24}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{20,})'
if echo "$added_lines" | grep -E "$direct_secret_regex" >/dev/null; then
  echo "ERROR: direct secret-like token detected in staged diff. Commit blocked."
  echo "$added_lines" | grep -E "$direct_secret_regex" | sed -n '1,20p' || true
  exit 1
fi

# Key assignments with literal values.
named_key_regex='(OPENROUTER_API_KEY|DISCORD_BOT_TOKEN|ELEVENLABS_API_KEY|BRAVE_API_KEY|GOOGLE_API_KEY|GEMINI_API_KEY|VYDRA_API_KEY|XAI_API_KEY)'
shell_assignment_regex="(export[[:space:]]+)?${named_key_regex}[[:space:]]*=[[:space:]]*['\\\"][^'\\\"]{8,}['\\\"]"
json_assignment_regex="\\\"${named_key_regex}\\\"[[:space:]]*:[[:space:]]*\\\"[^\\\"]{8,}\\\""
placeholder_regex='(\$\{?[A-Z_][A-Z0-9_]*\}?|your[-_]?|example|changeme|<[^>]+>)'

suspect_assignments="$(echo "$added_lines" | grep -E "$shell_assignment_regex|$json_assignment_regex" || true)"
real_assignments="$(echo "$suspect_assignments" | grep -Ev "$placeholder_regex" || true)"
if [[ -n "$real_assignments" ]]; then
  echo "ERROR: API key/token assignment with literal value detected. Commit blocked."
  echo "$real_assignments" | sed -n '1,20p' || true
  exit 1
fi

echo "Secret scan passed."
