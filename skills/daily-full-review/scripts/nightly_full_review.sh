#!/bin/zsh
# 全量复盘夜间定时入口（launchd 18:30 调用）。
# 链路：preflight（run_review_sync 内置）→ 同步段 → 生成段（intelligence.cli daily）→ agent-daily。
# 周末直接跳过；非交易日由质检闸门拦截。preflight 失败（CDP proxy/登录态）会在日志里给出修复提示。
set -uo pipefail

WORKSPACE="/Users/a77/finance-workspace-private"
export FORESIGHT_USER="linxiaoqi5111"
export FORESIGHT_USERS_DIR="/Users/a77/agent-memory/.foresight"
export KNOWLEDGE_WIKI="/Users/a77/knowledge-base-private/wiki"
export SUBCONSCIOUS_VAULT="/Users/a77/agent-memory"
export PATH="/opt/homebrew/bin:/opt/homebrew/opt/node/bin:/usr/local/bin:$PATH"

D="${1:-$(date +%F)}"
LOG_DIR="$WORKSPACE/logs"
mkdir -p "$LOG_DIR"

dow=$(date +%u)
if [ "$dow" -gt 5 ]; then
  echo "[$(date '+%F %T')] $D 周末，跳过全量复盘"
  exit 0
fi

cd "$WORKSPACE" || exit 1
echo "[$(date '+%F %T')] === 全量复盘开始 date=$D ==="

python3 skills/daily-full-review/scripts/run_review_sync.py --date "$D"
rc=$?
if [ $rc -ne 0 ]; then
  echo "[$(date '+%F %T')] 同步段失败 rc=$rc（常见原因：CDP proxy 未启动 / fupanhui 未登录 / 非交易日），停止后续生成段"
  exit $rc
fi

python3 -m intelligence.cli daily --date "$D" --skip-sync --from-step daily-review \
  --summary-json "market_feature_store/exports/$D-daily-workflow-summary.json"
rc=$?
if [ $rc -ne 0 ]; then
  echo "[$(date '+%F %T')] 生成段失败 rc=$rc"
  exit $rc
fi

python3 -m intelligence.cli agent-daily --date "$D"
echo "[$(date '+%F %T')] === 全量复盘完成 date=$D ==="
