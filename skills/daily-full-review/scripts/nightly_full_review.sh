#!/bin/zsh
# 全量复盘夜间定时入口（launchd 18:30 调用）。
# 链路：preflight（run_review_sync 内置）→ 同步段 → 独立 L2 分支 → 生成段。
# 周末直接跳过；非交易日由质检闸门拦截。preflight 失败（CDP proxy/登录态）会在日志里给出修复提示。
set -uo pipefail

CODE_ROOT="${FINANCE_CODE_ROOT:-/Users/a77/finance-workspace-runtime}"
DATA_ROOT="${FINANCE_DATA_ROOT:-/Users/a77/finance-workspace-private}"
WORKSPACE="$DATA_ROOT"
export FINANCE_CODE_ROOT="$CODE_ROOT"
export FINANCE_DATA_ROOT="$DATA_ROOT"
export FINANCE_WS="$DATA_ROOT"
export MARKET_FEATURE_STORE_DB="${MARKET_FEATURE_STORE_DB:-$DATA_ROOT/db/market_feature_store.duckdb}"
export MONEYFLOW_OUTPUT_DIR="${MONEYFLOW_OUTPUT_DIR:-$DATA_ROOT/scripts/moneyflow/outputs}"
export FORESIGHT_USER="linxiaoqi5111"
export FORESIGHT_USERS_DIR="/Users/a77/agent-memory/.foresight"
export KNOWLEDGE_WIKI="/Users/a77/knowledge-base-private/wiki"
export SUBCONSCIOUS_VAULT="/Users/a77/agent-memory"
export PATH="/opt/homebrew/bin:/opt/homebrew/opt/node/bin:/usr/local/bin:$PATH"

D="${1:-$(date +%F)}"
LOG_DIR="$DATA_ROOT/logs"
LOCK_PARENT="${FINANCE_LOCK_DIR:-$DATA_ROOT/state/locks}"
LOCK_DIR="$LOCK_PARENT/daily-full-review.lock"
mkdir -p "$LOG_DIR" "$LOCK_PARENT"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  old_pid="$(cat "$LOCK_DIR/pid" 2>/dev/null || true)"
  if [ -z "$old_pid" ] || ! kill -0 "$old_pid" 2>/dev/null; then
    echo "[$(date '+%F %T')] 清理 stale lock pid=$old_pid"
    rm -rf "$LOCK_DIR"
    mkdir "$LOCK_DIR" || exit 75
  else
    echo "[$(date '+%F %T')] 已有全量复盘/L2 进程在运行，跳过本次 date=$D pid=${old_pid:-unknown}"
    exit 75
  fi
fi
echo "$$" > "$LOCK_DIR/pid"
trap 'rm -rf "$LOCK_DIR"' EXIT INT TERM

dow=$(date +%u)
if [ "$dow" -gt 5 ]; then
  echo "[$(date '+%F %T')] $D 周末，跳过全量复盘"
  exit 0
fi

cd "$WORKSPACE" || exit 1
REV=$(git -C "$CODE_ROOT" rev-parse --short=12 HEAD 2>/dev/null || echo unknown)
WORKSPACE_REV=$(git -C "$WORKSPACE" rev-parse --short=12 HEAD 2>/dev/null || echo unknown)
echo "[$(date '+%F %T')] === 全量复盘开始 date=$D l2_code=$CODE_ROOT l2_rev=$REV workspace=$WORKSPACE workspace_rev=$WORKSPACE_REV db=$MARKET_FEATURE_STORE_DB moneyflow_out=$MONEYFLOW_OUTPUT_DIR ==="

# 失败告警：Mac 系统通知（零配置必达本机）+ 飞书（可选，凭证/权限就绪才发）；告警自身失败不影响退出码
notify() {
  osascript -e "display notification \"$1\" with title \"全量复盘告警\" sound name \"Basso\"" 2>/dev/null || true
  python3 "$WORKSPACE/scripts/notify_feishu.py" "$1" 2>/dev/null || true
}

run_moneyflow() {
  L2_LOCK_HELD=1 "$CODE_ROOT/scripts/moneyflow/run_l2_pipeline.sh" "$D"
}

python3 skills/daily-full-review/scripts/run_review_sync.py --date "$D"
rc=$?

# L2 是独立 DAG 分支：同步段即使失败也会尝试，避免 SW-L1/复盘会故障截断资金流。
run_moneyflow
moneyflow_rc=$?
if [ $moneyflow_rc -ne 0 ]; then
  echo "[$(date '+%F %T')] 资金流段失败 rc=${moneyflow_rc}"
  python3 "$CODE_ROOT/scripts/moneyflow/write_to_duckdb.py" --fail "$D" "nightly moneyflow rc=${moneyflow_rc}" \
    || echo "[$(date '+%F %T')] L2 失败状态回写未成功"
  notify "❌ 全量复盘 $D 资金流段失败 rc=${moneyflow_rc}；日志 logs/daily-full-review.out.log"
fi
python3 scripts/check_daily_review_data.py "$D" --phase l2
l2_rc=$?
if [ $l2_rc -ne 0 ]; then
  echo "[$(date '+%F %T')] L2 质量门未通过 rc=${l2_rc}"
  notify "❌ 全量复盘 $D L2 质量门未通过；日志 logs/daily-full-review.out.log"
fi

if [ $rc -ne 0 ]; then
  echo "[$(date '+%F %T')] 同步段失败 rc=${rc}（常见原因：CDP proxy 未启动 / fupanhui 未登录 / 非交易日），停止后续生成段"
  notify "⚠️ 全量复盘 $D 同步段失败 rc=${rc}（常见：CDP proxy 未启动 / fupanhui 未登录 / 非交易日），后续生成段未跑；日志 logs/daily-full-review.out.log"
  echo "[$(date '+%F %T')] === 全量复盘失败 date=$D 同步段 rc=${rc} ==="
  exit $rc
fi

if [ $moneyflow_rc -ne 0 ] || [ $l2_rc -ne 0 ]; then
  echo "[$(date '+%F %T')] === 全量复盘失败 date=$D 资金流 rc=${moneyflow_rc} L2门 rc=${l2_rc} ==="
  exit 1
fi

python3 -m intelligence.cli daily --date "$D" --skip-sync --from-step daily-review \
  --summary-json "market_feature_store/exports/$D-daily-workflow-summary.json"
rc=$?
if [ $rc -ne 0 ]; then
  echo "[$(date '+%F %T')] 生成段失败 rc=$rc"
  notify "⚠️ 全量复盘 $D 生成段失败 rc=${rc}（同步已完成，可手动重跑 intelligence.cli daily --skip-sync）；日志 logs/daily-full-review.out.log"
  exit $rc
fi

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

# 知识库证据断更监控（超 7 天未 ingest 新批次则告警；不阻断收尾）
kb_msg=$(python3 "$WORKSPACE/scripts/check_kb_freshness.py" --max-age 7)
if [ $? -eq 2 ]; then
  notify "$kb_msg——研报证据需要补 ingest（PDF 批次）"
fi

# 最终硬门：数据/报告/L2 全部通过才允许宣布完成
python3 scripts/check_daily_review_data.py "$D" --phase all
all_rc=$?
if [ $all_rc -ne 0 ]; then
  echo "[$(date '+%F %T')] === 全量复盘失败 date=$D all gate rc=${all_rc} ==="
  notify "❌ 全量复盘 $D 未通过最终质量门；日志 logs/daily-full-review.out.log"
  exit $all_rc
fi

echo "[$(date '+%F %T')] === 全量复盘完成 date=$D l2_code=$CODE_ROOT l2_rev=$REV workspace=$WORKSPACE workspace_rev=$WORKSPACE_REV ==="
