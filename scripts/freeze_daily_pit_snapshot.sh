#!/bin/zsh
set -euo pipefail

ROOT="${FINANCE_WS:-$(cd "$(dirname "$0")/.." && pwd)}"
DB="${PIT_SNAPSHOT_DB:-${ROOT}/db/market_feature_store.duckdb}"
KB="${PIT_KNOWLEDGE_ROOT:-${KNOWLEDGE_WIKI:-${HOME}/knowledge-base-private}}"
OUT="${PIT_SNAPSHOT_DIR:-${HOME}/fidelity-replay/pit-snapshots}"
DAILY_AGENT_DIR="${PIT_DAILY_AGENT_DIR:-${ROOT}/market_feature_store/exports}"

exec /usr/bin/python3 "${ROOT}/scripts/pit_snapshot_inventory.py" freeze \
  --db "${DB}" \
  --finance-root "${ROOT}" \
  --kb-root "${KB}" \
  --out-dir "${OUT}" \
  --daily-agent-dir "${DAILY_AGENT_DIR}"
