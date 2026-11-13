#!/usr/bin/env bash
# Push the commit at HEAD to the branch, rebasing over concurrent writers.
# Usage: .github/scripts/p2u_push.sh [branch]   (default: $GITHUB_REF_NAME or main)
# Up to 5 attempts: fetch, rebase --autostash -X theirs (keep this run's files on
# a conflict), then a plain rebase, then push. After the rebase, home-picks.json
# is re-merged key by key (p2u_merge_live.py) so this run's stale copy cannot
# wipe sections other jobs published meanwhile (favourites by league, codes).
set -uo pipefail
BR="${1:-${GITHUB_REF_NAME:-main}}"
HERE="$(cd "$(dirname "$0")" && pwd)"
for i in 1 2 3 4 5; do
  if git fetch -q origin "$BR"; then
    PRE=$(git rev-parse HEAD); THEIRS=$(git rev-parse FETCH_HEAD)
    BASE=$(git merge-base "$PRE" "$THEIRS" 2>/dev/null || true)
    if git rebase -q --autostash -X theirs "$THEIRS" || { git rebase --abort 2>/dev/null; git rebase -q --autostash "$THEIRS"; }; then
      python3 "$HERE/p2u_merge_live.py" "$BASE" "$PRE" "$THEIRS" || true
      if git push origin "HEAD:$BR"; then echo "pushed to $BR (attempt $i)"; exit 0; fi
    else
      git rebase --abort 2>/dev/null || true
    fi
  fi
  echo "push attempt $i failed; retrying"
  sleep $((i * 8))
done
echo "::error::could not push to $BR after 5 attempts"
exit 1
