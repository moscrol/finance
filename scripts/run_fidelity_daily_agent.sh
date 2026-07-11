#!/bin/zsh
set -euo pipefail

CODE_ROOT="${FINANCE_CODE_ROOT:-/Users/a77/finance-workspace-runtime}"
DATA_ROOT="${FINANCE_WS:-/Users/a77/finance-workspace-private}"
KB_WIKI="${KNOWLEDGE_WIKI:-/Users/a77/knowledge-base-private/wiki}"
DB="${MARKET_FEATURE_STORE_DB:-${DATA_ROOT}/db/market_feature_store.duckdb}"
STATE_ROOT="${FIDELITY_RUNTIME_ROOT:-/Users/a77/fidelity-runtime}"
D="${1:-$(date +%F)}"
EXPORTS="${DATA_ROOT}/market_feature_store/exports"
TMP_JSON="${EXPORTS}/.${D}-theme-candidates.fidelity.$$.json"
TMP_MD="${EXPORTS}/.${D}-theme-candidates.fidelity.$$.md"

test -d "${CODE_ROOT}/intelligence"
test -d "${EXPORTS}"
test -f "${DB}"

export MARKET_FEATURE_STORE_DB="${DB}"

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
  echo "skip fidelity daily agent: no fact_market_daily row for ${D}"
  exit 0
fi

cd "${CODE_ROOT}"

cleanup() {
  rm -f "${TMP_JSON}" "${TMP_MD}"
}
trap cleanup EXIT

/usr/bin/python3 -m intelligence.cli theme \
  --date "${D}" \
  --market-triggered \
  --out-json "${TMP_JSON}" \
  --out-md "${TMP_MD}"

/usr/bin/python3 - "${TMP_JSON}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    body = json.load(handle)
if body.get("lineage_schema_version") != "claim-lineage-v1":
    raise SystemExit("theme candidates missing claim-lineage-v1")
if body.get("candidate_count", 0) and not body.get("evidence_catalog"):
    raise SystemExit("theme candidates missing evidence catalog")
PY

BACKUP="${STATE_ROOT}/backups/${D}"
mkdir -p "${BACKUP}"
for name in "${D}-theme-candidates.json" "${D}-theme-candidates.md"; do
  if [ -f "${EXPORTS}/${name}" ] && [ ! -f "${BACKUP}/${name}" ]; then
    cp -p "${EXPORTS}/${name}" "${BACKUP}/${name}"
  fi
done
mv "${TMP_JSON}" "${EXPORTS}/${D}-theme-candidates.json"
mv "${TMP_MD}" "${EXPORTS}/${D}-theme-candidates.md"

exec /usr/bin/python3 -m intelligence.cli agent-daily \
  --date "${D}" \
  --finance-root "${DATA_ROOT}" \
  --kb-wiki "${KB_WIKI}" \
  --out-json "${DATA_ROOT}/market_feature_store/exports/${D}-daily-agent.json" \
  --out-md "${DATA_ROOT}/market_feature_store/exports/${D}-daily-agent.md" \
  --out-html "${DATA_ROOT}/复盘/daily/${D}/${D}-daily-agent.html" \
  --summary-json "${DATA_ROOT}/market_feature_store/exports/${D}-daily-agent-summary.json"
