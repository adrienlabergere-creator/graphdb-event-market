#!/usr/bin/env bash
# Usage: check_commit_messages.sh <base-ref> [head-ref]
# Fails if a commit subject does not follow "type(scope): message" or if the message
# carries trailer lines other than "Pair:". Merge commits are ignored.
set -euo pipefail

base="${1:?usage: check_commit_messages.sh <base-ref> [head-ref]}"
head="${2:-HEAD}"
pattern='^(feat|fix|test|docs|refactor|chore)(\([a-z0-9_-]+\))?: .{5,}'
status=0

for sha in $(git rev-list --no-merges "${base}..${head}"); do
  message="$(git log -1 --format=%B "$sha")"
  subject="$(printf '%s\n' "$message" | head -n1)"
  if ! printf '%s' "$subject" | grep -Eq "$pattern"; then
    echo "Bad subject in ${sha:0:8}: $subject"
    echo "  expected: feat|fix|test|docs|refactor|chore(scope): message"
    status=1
  fi
  extra="$(printf '%s\n' "$message" | git interpret-trailers --parse | grep -vi '^Pair:' || true)"
  if [ -n "$extra" ]; then
    echo "Unexpected trailer in ${sha:0:8}: $extra"
    echo "  only a 'Pair: <name>' trailer is allowed (git commit --amend to fix)."
    status=1
  fi
done

exit "$status"
