#!/bin/zsh
set -euo pipefail

_HERE="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "${_HERE}/ops_python.sh" ]]; then
  source "${_HERE}/ops_python.sh"
elif [[ -f "${_HERE}/lib/ops_python.sh" ]]; then
  source "${_HERE}/lib/ops_python.sh"
elif [[ -f /Users/a77/.local/bin/ops_python.sh ]]; then
  source /Users/a77/.local/bin/ops_python.sh
else
  print -u2 -- "missing ops_python.sh"
  exit 1
fi

CODE_ROOT="${FINANCE_CODE_ROOT:-/Users/a77/finance-workspace-runtime}"
DATA_ROOT="${FINANCE_WS:-/Users/a77/finance-workspace-private}"
DB="${PIT_SNAPSHOT_DB:-${DATA_ROOT}/db/market_feature_store.duckdb}"
KB="${PIT_KNOWLEDGE_ROOT:-${KNOWLEDGE_WIKI:-${HOME}/knowledge-base-private}}"
OUT="${PIT_SNAPSHOT_DIR:-${HOME}/fidelity-replay/pit-snapshots}"
DAILY_AGENT_DIR="${PIT_DAILY_AGENT_DIR:-${DATA_ROOT}/market_feature_store/exports}"

_ops_exit() {
  local rc=$?
  ops_health_log "pit-snapshot" "$rc"
}
trap _ops_exit EXIT

export FINANCE_CODE_ROOT="${CODE_ROOT}"
export FINANCE_WS="${DATA_ROOT}"

"$OPS_PYTHON" "${CODE_ROOT}/scripts/pit_snapshot_inventory.py" freeze \
  --db "${DB}" \
  --finance-root "${CODE_ROOT}" \
  --kb-root "${KB}" \
  --out-dir "${OUT}" \
  --daily-agent-dir "${DAILY_AGENT_DIR}"
