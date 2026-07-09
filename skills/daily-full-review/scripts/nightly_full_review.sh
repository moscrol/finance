#!/bin/zsh
# 全量复盘夜间定时入口（launchd 18:30 调用）。
# 链路：preflight（run_review_sync 内置）→ 同步段 → 生成段（intelligence.cli daily）→ agent-daily。
# 周末直接跳过；非交易日由质检闸门拦截。preflight 失败（CDP proxy/登录态）会在日志里给出修复提示。
set -uo pipefail

WORKSPACE="/Users/a77/finance-workspace-private"
export FINANCE_WS="$WORKSPACE"
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

# 失败告警：阻断性失败时经飞书主动通知用户（告警自身失败不影响退出码）
notify() {
  python3 "$WORKSPACE/scripts/notify_feishu.py" "$1" || true
}

python3 skills/daily-full-review/scripts/run_review_sync.py --date "$D"
rc=$?
if [ $rc -ne 0 ]; then
  echo "[$(date '+%F %T')] 同步段失败 rc=$rc（常见原因：CDP proxy 未启动 / fupanhui 未登录 / 非交易日），停止后续生成段"
  notify "⚠️ 全量复盘 $D 同步段失败 rc=$rc（常见：CDP proxy 未启动 / fupanhui 未登录 / 非交易日），后续生成段未跑；日志 logs/daily-full-review.out.log"
  exit $rc
fi

python3 -m intelligence.cli daily --date "$D" --skip-sync --from-step daily-review \
  --summary-json "market_feature_store/exports/$D-daily-workflow-summary.json"
rc=$?
if [ $rc -ne 0 ]; then
  echo "[$(date '+%F %T')] 生成段失败 rc=$rc"
  notify "⚠️ 全量复盘 $D 生成段失败 rc=$rc（同步已完成，可手动重跑 intelligence.cli daily --skip-sync）；日志 logs/daily-full-review.out.log"
  exit $rc
fi

python3 -m intelligence.cli agent-daily --date "$D"

# 双盲答卷 T+1/T+3 数值回检（幂等，只回填脚本可算指标；人工字段不覆盖）
LEDGER="docs/learning/forecast-review-ledger"
answers=$(ls "$LEDGER"/*.answer.*.json 2>/dev/null | tail -12)
if [ -n "$answers" ]; then
  /usr/bin/python3 scripts/dual_blind_forecast.py recheck ${=answers} \
    && /usr/bin/python3 scripts/dual_blind_auto_verdict.py --all-pending \
    && /usr/bin/python3 scripts/dual_blind_forecast.py index --html \
    && /usr/bin/python3 scripts/dual_blind_answers_to_md.py \
    && /usr/bin/python3 scripts/render_dual_blind_pair_html.py \
    && /usr/bin/python3 scripts/render_dual_blind_qa.py \
    || echo "[$(date '+%F %T')] 双盲答卷 recheck 失败（不阻断复盘收尾）"
fi

# 资金流段：L2 大单资金流三榜（串行于复盘之后，避免 DuckDB 写锁冲突；失败不阻断收尾）
MONEYFLOW_DIR="$WORKSPACE/scripts/moneyflow"
[ -f "$HOME/.secrets/clickhouse.env" ] && source "$HOME/.secrets/clickhouse.env"
if [ -d "$MONEYFLOW_DIR" ] && [ -n "${CH_PASSWORD:-}" ]; then
  (cd "$MONEYFLOW_DIR" \
    && python3 scan_limitup.py "$D" \
    && python3 scan_top100.py "$D" \
    && python3 scan_quant.py "$D" \
    && python3 "$WORKSPACE/scripts/render_moneyflow_html.py") \
    || echo "[$(date '+%F %T')] 资金流段失败（不阻断复盘收尾）"
else
  echo "[$(date '+%F %T')] 资金流段跳过（scripts/moneyflow 未合并或缺 CH_PASSWORD）"
fi

# 知识库证据断更监控（超 7 天未 ingest 新批次则飞书告警；不阻断收尾）
python3 "$WORKSPACE/scripts/check_kb_freshness.py" --max-age 7 --alert || true

echo "[$(date '+%F %T')] === 全量复盘完成 date=$D ==="

