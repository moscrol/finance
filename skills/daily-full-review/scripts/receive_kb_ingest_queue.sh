#!/bin/zsh
# 把当日 kb-ingest-queue.json 归档进知识库 wiki/raw/cross-repo-ingest-queue。
# 只 receive，不 apply、不 mark、不改 relations。缺文件或失败都 exit 0，不阻断夜跑。
set -uo pipefail

D="${1:?usage: receive_kb_ingest_queue.sh YYYY-MM-DD [finance-root] [kb-wiki]}"
DATA_ROOT="${2:-${FINANCE_DATA_ROOT:-${FINANCE_WS:-/Users/a77/finance-workspace-private}}}"
KB_WIKI="${3:-${KNOWLEDGE_WIKI:-/Users/a77/knowledge-base-private/wiki}}"
QUEUE="${DATA_ROOT}/market_feature_store/exports/${D}-kb-ingest-queue.json"
RECV="$(dirname "${KB_WIKI}")/scripts/kb_ingest_queue.py"

if [ ! -f "${QUEUE}" ]; then
  echo "[$(date '+%F %T')] kb-ingest-queue 不存在，跳过 receive: ${QUEUE}"
  exit 0
fi
if [ ! -f "${RECV}" ]; then
  echo "[$(date '+%F %T')] kb_ingest_queue.py 不存在，跳过 receive: ${RECV}"
  exit 0
fi

python3 "${RECV}" receive "${QUEUE}" --wiki-root "${KB_WIKI}"
rc=$?
if [ "${rc}" -ne 0 ]; then
  echo "[$(date '+%F %T')] kb ingest receive 失败 rc=${rc}（不阻断复盘）"
fi
exit 0
