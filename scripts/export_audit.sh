#!/usr/bin/env bash
# Publish the bot's journal/state (no secrets) to the git branch `audit-logs`
# so it can be audited remotely. Run it from cron after the daily run, e.g.:
#   15 0 * * * cd /path/to/trading-bot && scripts/export_audit.sh >> logs/export_audit.log 2>&1
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
BRANCH="audit-logs"
WT="$REPO/../trading-bot-audit"
SRC="$REPO/data/live"

cd "$REPO"
git fetch -q origin "$BRANCH" 2>/dev/null || true
if [ ! -d "$WT" ]; then
  if git show-ref -q "refs/remotes/origin/$BRANCH"; then
    git worktree add -q "$WT" "$BRANCH" 2>/dev/null || git worktree add -q -B "$BRANCH" "$WT" "origin/$BRANCH"
  else
    git worktree add -q --detach "$WT"
    (cd "$WT" && git checkout -q --orphan "$BRANCH" && git rm -rqf . && echo "# Audit logs" > README.md)
  fi
fi

mkdir -p "$WT/live"
cp "$SRC"/*.json "$SRC"/*.jsonl "$WT/live/" 2>/dev/null || true
python3 "$REPO/scripts/audit_report.py" --journal "$WT/live/executor_journal.jsonl" > "$WT/REPORT.md" || true

cd "$WT"
# Refuse to publish anything that looks like an API key/secret (64 alphanumeric chars)
if grep -rEq '[A-Za-z0-9]{64}' --include='*.json' --include='*.jsonl' --include='*.md' .; then
  echo "export_audit: possible secret found, aborting" >&2
  exit 1
fi
git add -A
git diff --cached --quiet || git commit -q -m "audit: $(date -u +%Y-%m-%dT%H:%MZ)"
git push -q origin "$BRANCH"
echo "export_audit: published to $BRANCH"
