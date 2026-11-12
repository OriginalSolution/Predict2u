#!/usr/bin/env bash
# Push the commit at HEAD to the branch, rebasing over concurrent writers.
# Usage: .github/scripts/p2u_push.sh [branch]   (default: $GITHUB_REF_NAME or main)
# Up to 5 attempts: pull --rebase --autostash -X theirs (keep this run's files on
# a conflict), then a plain rebase, then push. Fails the step if nothing pushed.
set -uo pipefail
BR="${1:-${GITHUB_REF_NAME:-main}}"
for i in 1 2 3 4 5; do
  if git pull --rebase --autostash -X theirs origin "$BR" || { git rebase --abort 2>/dev/null; git pull --rebase --autostash origin "$BR"; }; then
    if git push origin "HEAD:$BR"; then echo "pushed to $BR (attempt $i)"; exit 0; fi
  else
    git rebase --abort 2>/dev/null || true
  fi
  echo "push attempt $i failed; retrying"
  sleep $((i * 8))
done
echo "::error::could not push to $BR after 5 attempts"
exit 1
