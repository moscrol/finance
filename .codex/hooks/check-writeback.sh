#!/bin/sh
# Delegate Stop hook decisions to the shared agent-memory policy.
set -u

repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
V="$repo_root/.agent-memory"
[ -d "$V" ] || V="/Users/a77/agent-memory"

shared="$V/40_playbooks/check-writeback.sh"
if [ -x "$shared" ]; then
  exec "$shared"
fi

exit 0
