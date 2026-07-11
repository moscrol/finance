#!/bin/zsh
set -euo pipefail

CODE_ROOT="${FINANCE_CODE_ROOT:-/Users/a77/finance-workspace-runtime}"
DATA_ROOT="${FINANCE_WS:-/Users/a77/finance-workspace-private}"
SNAPSHOT_DIR="${PIT_SNAPSHOT_DIR:-/Users/a77/fidelity-replay/pit-snapshots}"
STATE_ROOT="${FIDELITY_RUNTIME_ROOT:-/Users/a77/fidelity-runtime}"
DB="${MARKET_FEATURE_STORE_DB:-${DATA_ROOT}/db/market_feature_store.duckdb}"
D="${1:-$(date +%F)}"

test -f "${DB}"

HAS_TRADE_DATE=$(
  /usr/bin/python3 - "${DB}" "${D}" <<'PY'
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

exec /usr/bin/python3 "${CODE_ROOT}/scripts/fidelity_forward_acceptance.py" \
  record \
  --code-root "${CODE_ROOT}" \
  --data-root "${DATA_ROOT}" \
  --snapshot-dir "${SNAPSHOT_DIR}" \
  --output-root "${STATE_ROOT}/forward-acceptance" \
  --date "${D}"
