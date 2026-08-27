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
USER_ID="${FORESIGHT_USER:-linxiaoqi5111}"
DB="${MARKET_FEATURE_STORE_DB:-${DATA_ROOT}/db/market_feature_store.duckdb}"

_ops_exit() {
  local rc=$?
  ops_health_log "checkpoint-recheck" "$rc"
}
trap _ops_exit EXIT

export FINANCE_CODE_ROOT="${CODE_ROOT}"
export FINANCE_WS="${DATA_ROOT}"
cd "${CODE_ROOT}"

"$OPS_PYTHON" -m intelligence.cli checkpoint recheck \
  --user "${USER_ID}" \
  --apply \
  --db-path "${DB}"
