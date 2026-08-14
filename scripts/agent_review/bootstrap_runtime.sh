#!/bin/zsh
set -euo pipefail

REPO="${AGENT_REVIEW_REPO:-/Users/a77/.finance-runtime/agent-runtime-backends-c4673667}"
STATE_ROOT="${AGENT_REVIEW_ROOT:-/Users/a77/.finance-runtime/agent-review-loop}"
PYTHON="${AGENT_REVIEW_PYTHON:-/Users/a77/finance-workspace-private/.venv-workbench/bin/python}"

cd "$REPO"
exec "$PYTHON" -m scripts.agent_review.bootstrap \
  --repo "$REPO" \
  --state-root "$STATE_ROOT"
