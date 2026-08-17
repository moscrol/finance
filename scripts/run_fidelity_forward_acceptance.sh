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
SNAPSHOT_DIR="${PIT_SNAPSHOT_DIR:-/Users/a77/fidelity-replay/pit-snapshots}"
STATE_ROOT="${FIDELITY_RUNTIME_ROOT:-/Users/a77/fidelity-runtime}"
DB="${MARKET_FEATURE_STORE_DB:-${DATA_ROOT}/db/market_feature_store.duckdb}"
D="${1:-$(date +%F)}"

_ops_exit() {
  local rc=$?
  ops_health_log "fidelity-forward-acceptance" "$rc"
}
trap _ops_exit EXIT

test -f "${DB}"
export FINANCE_CODE_ROOT="${CODE_ROOT}"
export FINANCE_WS="${DATA_ROOT}"

HAS_TRADE_DATE=$(
  "$OPS_PYTHON" - "${DB}" "${D}" <<'PY'
import sys

import duckdb

with duckdb.connect(sys.argv[1], read_only=True) as connection:
    row = connection.execute(
        "SELECT COUNT(*) FROM fact_market_daily WHERE trade_date = ?",
        [sys.argv[2]],
    ).fetchone()
print(1 if row and row[0] else 0)
PY
)
if [ "${HAS_TRADE_DATE}" != "1" ]; then
  echo "skip fidelity forward acceptance: no fact_market_daily row for ${D}"
  exit 0
fi

"$OPS_PYTHON" "${CODE_ROOT}/scripts/fidelity_forward_acceptance.py" \
  record \
  --code-root "${CODE_ROOT}" \
  --data-root "${DATA_ROOT}" \
  --snapshot-dir "${SNAPSHOT_DIR}" \
  --output-root "${STATE_ROOT}/forward-acceptance" \
  --date "${D}"
