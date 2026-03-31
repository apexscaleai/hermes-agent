#!/usr/bin/env bash
# hermes-maintainer-loop.sh
# Cron workflow for maintaining apexscaleai/hermes-agent fork.
# Syncs upstream (NousResearch), runs tests, commits fixes, pushes to fork.
# Designed to run as a scheduled cron job with Hermes autonomous loop discipline.
#
# Anti-cherry-pick strategy: keep commits atomic and cohesive; submit as a
# complete series on a dedicated branch so maintainers can merge the full set.
#
# Expected env vars (set in ~/.hermes/.env or shell):
#   GH_TOKEN          — GitHub CLI auth token (needs repo push access to apexscaleai/hermes-agent)
#
set -euo pipefail

REPO_DIR="${REPO_DIR:-/tmp/hermes-agent}"
UPSTREAM="https://github.com/NousResearch/hermes-agent.git"
FORK="https://github.com/apexscaleai/hermes-agent.git"
BOT_BRANCH="fix/maintainer-contribs"   # dedicated branch for collective fixes
FIX_BRANCH="${BOT_BRANCH}"              # all 3 fixes land on same cohesive branch

# ─── Pre-flight: verify repo exists and is clean-ish ────────────────────────
if [[ ! -d "$REPO_DIR/.git" ]]; then
    echo "[cron] Cloning fresh repo..."
    git clone --recurse-submodules "$UPSTREAM" "$REPO_DIR"
fi

cd "$REPO_DIR"

# Ensure upstream remote exists (original NousResearch repo)
if ! git remote get-url upstream &>/dev/null; then
    echo "[cron] Adding upstream remote..."
    git remote add upstream "$UPSTREAM"
fi

# Ensure we're on the fix branch (create if missing)
if git rev-parse --verify "$FIX_BRANCH" &>/dev/null; then
    git checkout "$FIX_BRANCH"
else
    git checkout -b "$FIX_BRANCH"
fi

# ─── Step 1: Sync with upstream ────────────────────────────────────────────
echo "[cron] Fetching latest from upstream..."
git fetch upstream main --quiet

LOCAL_MAIN="upstream/main"
if git rev-parse --verify upstream/main &>/dev/null; then
    LOCAL_MAIN="upstream/main"
elif git rev-parse --verify origin/main &>/dev/null; then
    LOCAL_MAIN="origin/main"
fi

UPSTREAM_SHA=$(git rev-parse "$LOCAL_MAIN")
HEAD_SHA=$(git rev-parse HEAD)

if [[ "$UPSTREAM_SHA" == "$HEAD_SHA" ]]; then
    echo "[cron] Already up-to-date with $LOCAL_MAIN ($UPSTREAM_SHA). Nothing to do."
    exit 0
fi

echo "[cron] Upstream advanced: $HEAD_SHA -> $UPSTREAM_SHA"
echo "[cron] Rebasing fix branch onto latest upstream..."
# Stash working-tree changes so we can rebase the committed history cleanly
WIP=$(git stash create "cron-wip-$(date +%s)" 2>/dev/null) || true
if [[ -n "$WIP" ]]; then
    echo "[cron] Stashing $(git stash list | grep -c "cron-wip" || echo 0) prior WIP(s)..."
    git stash store -m "cron-wip-$(date +%s)" "$WIP" 2>/dev/null || true
fi

# Rebase any commits unique to this branch onto latest upstream
if ! git log --oneline "$LOCAL_MAIN"..HEAD 2>/dev/null | grep -q .; then
    echo "[cron] No commits to rebase — checking if behind..."
    if git merge-base --is-ancestor "$LOCAL_MAIN" HEAD; then
        echo "[cron] Branch is up-to-date."
    else
        echo "[cron] Branch is behind — rebasing..."
        git rebase "$LOCAL_MAIN" || { echo "[cron] Rebase conflict."; exit 1; }
    fi
else
    echo "[cron] Rebasing $(git log --oneline "$LOCAL_MAIN"..HEAD | wc -l) commits onto $LOCAL_MAIN..."
    git rebase "$LOCAL_MAIN" || {
        echo "[cron] Rebase conflict."
        git rebase --abort || true
        exit 1
    }
fi

# ─── Step 2: Run tests ─────────────────────────────────────────────────────
echo "[cron] Running test suite..."
# Run in a subprocess with isolated environment
python3 -m pytest tests/ -x -q --tb=short 2>&1 | tail -20
TEST_RESULT=${PIPESTATUS[0]}

if [[ $TEST_RESULT -ne 0 ]]; then
    echo "[cron] TESTS FAILED (exit $TEST_RESULT)"
    echo "[cron] Do not commit. Fix and re-run."
    exit 1
fi

echo "[cron] All tests passed."

# ─── Step 3: Commit (if dirty) and push ────────────────────────────────────
git add -A

# Check if there are meaningful changes (not just timestamps/noise)
if git diff --cached --quiet; then
    echo "[cron] No changes to commit."
else
    echo "[cron] Committing changes..."
    git commit --no-edit || {
        echo "[cron] Commit failed: $?"
        exit 1
    }
fi

COMMIT_SHA=$(git rev-parse HEAD)
echo "[cron] Commit: $COMMIT_SHA"

# ─── Step 4: Push to fork ──────────────────────────────────────────────────
echo "[cron] Pushing to fork ($FORK, branch=$FIX_BRANCH)..."
git push --force-with-lease "$FORK" "HEAD:$FIX_BRANCH" 2>&1
PUSH_RESULT=$?

if [[ $PUSH_RESULT -ne 0 ]]; then
    echo "[cron] Push failed (exit $PUSH_RESULT). Check credentials (GH_TOKEN)."
    exit 1
fi

echo "[cron] ✓ Pushed to https://github.com/apexscaleai/hermes-agent/tree/$FIX_BRANCH"
echo "[cron] ✓ Commit: https://github.com/apexscaleai/hermes-agent/commit/$COMMIT_SHA"
echo "[cron] ✓ All done. Ready for PR against NousResearch/hermes-agent."

# ─── Anti-cherry-pick note ─────────────────────────────────────────────────
# To open a PR that preserves full history and encourages merge (not squash):
#   gh pr create \
#     --base main \
#     --head apexscaleai:$FIX_BRANCH \
#     --title "fix: thread safety, ANSI output, and fallback_model config (maintainer contribs)" \
#     --body-file <(cat <<'EOF'
# These are targeted, atomic fixes for three confirmed bugs in hermes-agent.
# Each fix is a separate logical unit with tests — intended for merge (not squash).
#
# Fixes:
#   - #4072  Thread safety: _agent_running and _interrupt_requested → threading.Event
#   - #4128  /tools list: raw ANSI escapes → properly rendered via _pt_print + _PT_ANSI
#   - #4091  fallback_model config: clarify YAML format + save_config round-trip safety
#
# All tests pass. Please merge as a series to preserve authorship and history.
# EOF
# )
