#!/bin/zsh
set -euo pipefail

CODE_ROOT="${FINANCE_CODE_ROOT:-/Users/a77/finance-workspace-runtime}"
DATA_ROOT="${FINANCE_WS:-/Users/a77/finance-workspace-private}"
KB_WIKI="${KNOWLEDGE_WIKI:-/Users/a77/knowledge-base-private/wiki}"
DB="${MARKET_FEATURE_STORE_DB:-${DATA_ROOT}/db/market_feature_store.duckdb}"
D="${1:-$(date +%F)}"

test -d "${CODE_ROOT}/intelligence"
test -d "${DATA_ROOT}/market_feature_store/exports"
test -f "${DB}"

export MARKET_FEATURE_STORE_DB="${DB}"
cd "${CODE_ROOT}"

exec /usr/bin/python3 -m intelligence.cli agent-daily \
  --date "${D}" \
  --finance-root "${DATA_ROOT}" \
  --kb-wiki "${KB_WIKI}" \
  --out-json "${DATA_ROOT}/market_feature_store/exports/${D}-daily-agent.json" \
  --out-md "${DATA_ROOT}/market_feature_store/exports/${D}-daily-agent.md" \
  --out-html "${DATA_ROOT}/复盘/daily/${D}/${D}-daily-agent.html" \
  --summary-json "${DATA_ROOT}/market_feature_store/exports/${D}-daily-agent-summary.json"
