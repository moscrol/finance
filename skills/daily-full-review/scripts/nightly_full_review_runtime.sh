#!/bin/zsh
# Stable launchd wrapper: run clean runtime code against private persistent data.
set -uo pipefail

export FINANCE_CODE_ROOT="${FINANCE_CODE_ROOT:-/Users/a77/finance-workspace-runtime}"
export FINANCE_DATA_ROOT="${FINANCE_DATA_ROOT:-/Users/a77/finance-workspace-private}"

exec /bin/zsh "$FINANCE_CODE_ROOT/skills/daily-full-review/scripts/nightly_full_review.sh" "$@"
