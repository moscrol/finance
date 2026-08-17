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
KB_WIKI="${KNOWLEDGE_WIKI:-/Users/a77/knowledge-base-private/wiki}"
DB="${MARKET_FEATURE_STORE_DB:-${DATA_ROOT}/db/market_feature_store.duckdb}"
STATE_ROOT="${FIDELITY_RUNTIME_ROOT:-/Users/a77/fidelity-runtime}"
D="${1:-$(date +%F)}"
EXPORTS="${DATA_ROOT}/market_feature_store/exports"
TMP_JSON="${EXPORTS}/.${D}-theme-candidates.fidelity.$$.json"
TMP_MD="${EXPORTS}/.${D}-theme-candidates.fidelity.$$.md"

_ops_exit() {
  local rc=$?
  rm -f "${TMP_JSON}" "${TMP_MD}"
  ops_health_log "fidelity-daily-agent" "$rc"
}
trap _ops_exit EXIT

test -d "${CODE_ROOT}/intelligence"
test -d "${EXPORTS}"
test -f "${DB}"

export MARKET_FEATURE_STORE_DB="${DB}"
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
  echo "skip fidelity daily agent: no fact_market_daily row for ${D}"
  exit 0
fi

cd "${CODE_ROOT}"

"$OPS_PYTHON" -m intelligence.cli theme \
  --date "${D}" \
  --market-triggered \
  --out-json "${TMP_JSON}" \
  --out-md "${TMP_MD}"

"$OPS_PYTHON" - "${TMP_JSON}" "${D}" <<'PY'
import json
import sys

from intelligence.services.fidelity_contract import contract_errors

with open(sys.argv[1], encoding="utf-8") as handle:
    body = json.load(handle)
if body.get("lineage_schema_version") != "claim-lineage-v1":
    raise SystemExit("theme candidates missing claim-lineage-v1")
if body.get("candidate_count", 0) and not body.get("evidence_catalog"):
    raise SystemExit("theme candidates missing evidence catalog")
if body.get("trade_date") != sys.argv[2]:
    raise SystemExit("theme candidate trade_date mismatch")
manifest_payload = {
    "lineage_schema_version": body.get("lineage_schema_version"),
    "evidence_catalog": body.get("evidence_catalog"),
    "candidate_evidence_refs": [
        candidate.get("evidence_refs")
        for candidate in body.get("candidates", [])
        if isinstance(candidate, dict)
    ],
}
errors = contract_errors(body, manifest_payload=manifest_payload)
if errors:
    raise SystemExit(
        "theme candidates invalid fidelity contract 1.2: "
        + "; ".join(errors)
    )
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

agent_rc=0
"$OPS_PYTHON" -m intelligence.cli agent-daily \
  --date "${D}" \
  --finance-root "${DATA_ROOT}" \
  --kb-wiki "${KB_WIKI}" \
  --out-json "${DATA_ROOT}/market_feature_store/exports/${D}-daily-agent.json" \
  --out-md "${DATA_ROOT}/market_feature_store/exports/${D}-daily-agent.md" \
  --out-html "${DATA_ROOT}/复盘/daily/${D}/${D}-daily-agent.html" \
  --summary-json "${DATA_ROOT}/market_feature_store/exports/${D}-daily-agent-summary.json" \
  --semantic-rag-top-n 0 \
  || agent_rc=$?

# 研究队列分桶不依赖 wiki RAG；归档缺口任务包到 wiki/raw，永不 apply。
RECEIVE_SH="${CODE_ROOT}/skills/daily-full-review/scripts/receive_kb_ingest_queue.sh"
if [ -x "${RECEIVE_SH}" ] || [ -f "${RECEIVE_SH}" ]; then
  /bin/zsh "${RECEIVE_SH}" "${D}" "${DATA_ROOT}" "${KB_WIKI}" \
    || echo "kb ingest receive 失败（不阻断）"
else
  RECV="$(dirname "${KB_WIKI}")/scripts/kb_ingest_queue.py"
  QUEUE="${DATA_ROOT}/market_feature_store/exports/${D}-kb-ingest-queue.json"
  if [ -f "${QUEUE}" ] && [ -f "${RECV}" ]; then
    "$OPS_PYTHON" "${RECV}" receive "${QUEUE}" --wiki-root "${KB_WIKI}" \
      || echo "kb ingest receive 失败（不阻断）"
  fi
fi

exit "${agent_rc}"
