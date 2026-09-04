#!/bin/zsh
# 全量复盘夜间定时入口。
# 链路：preflight（run_review_sync 内置）→ 同步段 → 独立 L2 分支 → 生成段。
# 周末直接跳过；非交易日由质检闸门拦截。preflight 失败（CDP proxy/登录态）会在日志里给出修复提示。
#
# 定时拆分（L2 逐笔数据 ~20:30 才到，18:30 跑必空）：
#   nightly_full_review.sh sync        → 仅同步段（@18:30，不依赖 L2）
#   nightly_full_review.sh finalize    → L2 + 生成段（@20:40，含 sync 守卫）
#   nightly_full_review.sh [date]      → 全量（手动补跑用，phase=all）
# 参数可任意组合：sync 2026-07-22 / finalize / 2026-07-22 /（空）
set -uo pipefail

_HERE="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "${_HERE}/ops_python.sh" ]]; then
  source "${_HERE}/ops_python.sh"
elif [[ -f "${_HERE}/lib/ops_python.sh" ]]; then
  source "${_HERE}/lib/ops_python.sh"
elif [[ -f "${_HERE}/../../../scripts/lib/ops_python.sh" ]]; then
  source "${_HERE}/../../../scripts/lib/ops_python.sh"
elif [[ -f /Users/a77/.local/bin/ops_python.sh ]]; then
  source /Users/a77/.local/bin/ops_python.sh
else
  print -u2 -- "missing ops_python.sh"
  exit 1
fi

CODE_ROOT="${FINANCE_CODE_ROOT:-/Users/a77/finance-workspace-runtime}"
DATA_ROOT="${FINANCE_DATA_ROOT:-/Users/a77/finance-workspace-private}"
WORKSPACE="$DATA_ROOT"
export FINANCE_CODE_ROOT="$CODE_ROOT"
export FINANCE_DATA_ROOT="$DATA_ROOT"
export FINANCE_WS="$DATA_ROOT"
export MARKET_FEATURE_STORE_DB="${MARKET_FEATURE_STORE_DB:-$DATA_ROOT/db/market_feature_store.duckdb}"
export MONEYFLOW_OUTPUT_DIR="${MONEYFLOW_OUTPUT_DIR:-$DATA_ROOT/scripts/moneyflow/outputs}"
export FORESIGHT_USER="linxiaoqi5111"
export FORESIGHT_USERS_DIR="${FORESIGHT_USERS_DIR:-/Users/a77/.local/share/finance-workbench/users}"
export KNOWLEDGE_WIKI="/Users/a77/knowledge-base-private/wiki"
export SUBCONSCIOUS_VAULT="/Users/a77/agent-memory"
export PATH="/opt/homebrew/bin:/opt/homebrew/opt/node/bin:/usr/local/bin:$PATH"
# 复盘会会话卫生：默认不直连 urllib，请求间隔 0.8s。未合入/未切 runtime 前夜跑仍是旧代码，这两项只在新树上生效。
export FUPANHUI_DIRECT="${FUPANHUI_DIRECT:-0}"
export FUPANHUI_MIN_INTERVAL="${FUPANHUI_MIN_INTERVAL:-0.8}"

# 参数：phase (sync|finalize|all) + date。date 缺省今天。
PHASE="all"
D="$(date +%F)"
for arg in "$@"; do
  case "$arg" in
    sync|finalize|all) PHASE="$arg" ;;
    *) D="$arg" ;;
  esac
done

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
    echo "[$(date '+%F %T')] 已有全量复盘/L2 进程在运行，跳过本次 date=$D phase=$PHASE pid=${old_pid:-unknown}"
    exit 75
  fi
fi
echo "$$" > "$LOCK_DIR/pid"
_review_exit() {
  local rc=$?
  rm -rf "$LOCK_DIR"
  ops_health_log "daily-full-review-${PHASE}" "$rc"
}
trap _review_exit EXIT INT TERM

# 按目标日期 $D 判周末（不能用 `date +%u`，那是「今天」的星期——
# 手动跨日补跑时今天可能是周末而 $D 是工作日，会被误跳过）
dow=$(date -j -f "%Y-%m-%d" "$D" +%u)
if [ "$dow" -gt 5 ]; then
  echo "[$(date '+%F %T')] $D 周末，跳过全量复盘"
  exit 0
fi

cd "$WORKSPACE" || exit 1
REV=$(git -C "$CODE_ROOT" rev-parse --short=12 HEAD 2>/dev/null || echo unknown)
WORKSPACE_REV=$(git -C "$WORKSPACE" rev-parse --short=12 HEAD 2>/dev/null || echo unknown)
echo "[$(date '+%F %T')] === 全量复盘开始 phase=$PHASE date=$D l2_code=$CODE_ROOT l2_rev=$REV workspace=$WORKSPACE workspace_rev=$WORKSPACE_REV db=$MARKET_FEATURE_STORE_DB moneyflow_out=$MONEYFLOW_OUTPUT_DIR ==="

# 失败告警：Mac 系统通知（零配置必达本机）+ 飞书（可选，凭证/权限就绪才发）；告警自身失败不影响退出码
notify() {
  osascript -e "display notification \"$1\" with title \"全量复盘告警\" sound name \"Basso\"" 2>/dev/null || true
  "$OPS_PYTHON" "$WORKSPACE/scripts/notify_feishu.py" "$1" 2>/dev/null || true
}

run_moneyflow() {
  L2_LOCK_HELD=1 "$CODE_ROOT/scripts/moneyflow/run_l2_pipeline.sh" "$D"
}

run_sync() {
  "$OPS_PYTHON" skills/daily-full-review/scripts/run_review_sync.py --date "$D"
}

# L2 是独立 DAG 分支：同步段即使失败也会尝试，避免 SW-L1/复盘会故障截断资金流。
# 返回 moneyflow_rc / l2_rc 两个全局变量。
# L2 挂账暂停：state/l2-paused.flag 存在 → 不抓取、L2 门放行（check 脚本读 L2_PAUSED=1
# 会跳过并留痕）。删除 flag 文件即恢复；欠账日期用 run_l2_pipeline.sh 按日回补。
L2_PAUSED_FLAG="$WORKSPACE/state/l2-paused.flag"
run_l2_branch() {
  if [ -f "$L2_PAUSED_FLAG" ]; then
    export L2_PAUSED=1
    echo "[$(date '+%F %T')] L2 已挂账暂停（存在 $L2_PAUSED_FLAG），跳过资金流段与 L2 质量门"
    moneyflow_rc=0
    l2_rc=0
    return 0
  fi
  run_moneyflow
  moneyflow_rc=$?
  if [ "$moneyflow_rc" -ne 0 ]; then
    echo "[$(date '+%F %T')] 资金流段失败 rc=$moneyflow_rc"
    # --fail 仅在实际交易日落 failed；非交易日由 write_to_duckdb.py 内部保护跳过，
    # 避免把历史 complete 或空跑降级成失败（8.6 覆写事故根因）。
    "$OPS_PYTHON" "$CODE_ROOT/scripts/moneyflow/write_to_duckdb.py" --fail "$D" "nightly moneyflow rc=$moneyflow_rc" \
      || echo "[$(date '+%F %T')] L2 失败状态回写未成功"
    notify "❌ 全量复盘 $D 资金流段失败 rc=$moneyflow_rc；日志 logs/daily-full-review.out.log"
  fi
  "$OPS_PYTHON" scripts/check_daily_review_data.py "$D" --phase l2
  l2_rc=$?
  # rc=3：闸门被 duckdb 写锁挡住没跑成，结果未知——与「质量门未通过」是两回事
  if [ "$l2_rc" -eq 3 ]; then
    echo "[$(date '+%F %T')] L2 质量门未能执行：duckdb 写锁占用超重试窗 rc=3，结果未知"
    notify "⚠️ 全量复盘 $D L2 质量门没跑成（duckdb 写锁占用，非质量问题）；等写进程收工后重跑 finalize；日志 logs/daily-full-review.out.log"
  elif [ "$l2_rc" -ne 0 ]; then
    echo "[$(date '+%F %T')] L2 质量门未通过 rc=$l2_rc"
    notify "❌ 全量复盘 $D L2 质量门未通过；日志 logs/daily-full-review.out.log"
  fi
}

# 生成段 + 收尾（KB 时效 / 最终硬门）。前置：sync 与 L2 均已通过。
run_generation_and_finalize() {
  "$OPS_PYTHON" -m intelligence.cli daily --date "$D" --skip-sync --from-step daily-review \
    --summary-json "market_feature_store/exports/$D-daily-workflow-summary.json"
  local rc=$?

  # 幂等兜底：20:05 fidelity 或 daily 步已写出的 kb-ingest-queue 归档进 wiki/raw。
  # 只 receive，不 apply。daily 计划里也有同一步；重复跑按 payload hash 去重。
  local RECEIVE_SH="$WORKSPACE/skills/daily-full-review/scripts/receive_kb_ingest_queue.sh"
  if [ -f "$RECEIVE_SH" ]; then
    /bin/zsh "$RECEIVE_SH" "$D" "$WORKSPACE" "$KNOWLEDGE_WIKI" \
      || echo "[$(date '+%F %T')] kb ingest receive 失败（不阻断）"
  fi

  if [ "$rc" -ne 0 ]; then
    echo "[$(date '+%F %T')] 生成段失败 rc=$rc"
    notify "⚠️ 全量复盘 $D 生成段失败 rc=$rc（同步已完成，可手动重跑 intelligence.cli daily --skip-sync）；日志 logs/daily-full-review.out.log"
    return "$rc"
  fi

  # 双盲答卷回检已退役（2026-08-20）：不再随 finalize 跑 recheck / auto_verdict。
  # 脚本仍留在 scripts/，可手动调用；不要接回夜跑。

  # 知识库证据断更监控（超 7 天未 ingest 新批次则告警；不阻断收尾）
  local kb_msg
  kb_msg=$("$OPS_PYTHON" "$WORKSPACE/scripts/check_kb_freshness.py" --max-age 7)
  if [ $? -eq 2 ]; then
    notify "$kb_msg——研报证据需要补 ingest（PDF 批次）"
  fi

  # 最终硬门：数据/报告/L2 全部通过才允许宣布完成
  "$OPS_PYTHON" scripts/check_daily_review_data.py "$D" --phase all
  local all_rc=$?
  if [ "$all_rc" -eq 3 ]; then
    echo "[$(date '+%F %T')] === 最终硬门未能执行 date=$D（duckdb 写锁占用 rc=3，完整性未知）==="
    notify "⚠️ 全量复盘 $D 最终质量门没跑成（duckdb 写锁占用，非缺数）；等写进程收工后重跑 finalize；日志 logs/daily-full-review.out.log"
    return "$all_rc"
  elif [ "$all_rc" -ne 0 ]; then
    echo "[$(date '+%F %T')] === 全量复盘失败 date=$D all gate rc=$all_rc ==="
    notify "❌ 全量复盘 $D 未通过最终质量门；日志 logs/daily-full-review.out.log"
    return "$all_rc"
  fi

  echo "[$(date '+%F %T')] === 全量复盘完成 date=$D phase=$PHASE l2_code=$CODE_ROOT l2_rev=$REV workspace=$WORKSPACE workspace_rev=$WORKSPACE_REV ==="
  return 0
}

case "$PHASE" in
  sync)
    # 仅同步段（定时 @18:30）。失败则告警退出；finalize 守卫会拦住残缺数据。
    run_sync
    rc=$?
    if [ "$rc" -ne 0 ]; then
      echo "[$(date '+%F %T')] 同步段失败 rc=$rc（常见原因：CDP proxy 未启动 / fupanhui 未登录 / 非交易日）"
      notify "⚠️ 全量复盘 $D 同步段失败 rc=$rc（常见：CDP proxy 未启动 / fupanhui 未登录 / 非交易日）；20:40 finalize 将被守卫拦下；日志 logs/daily-full-review.out.log"
      echo "[$(date '+%F %T')] === sync 段失败 date=$D rc=$rc ==="
      exit "$rc"
    fi
    echo "[$(date '+%F %T')] === sync 段完成 date=$D（等待 20:40 finalize 跑 L2+生成段）==="
    exit 0
    ;;

  finalize)
    # 定时 @20:40。守卫：18:30 sync 必须已通过 same-day-gate，否则不生成报告。
    "$OPS_PYTHON" scripts/check_daily_review_data.py "$D" --phase data
    guard_rc=$?
    if [ "$guard_rc" -eq 3 ]; then
      # 闸门被写锁挡住没跑成 ≠ 数据不完整；如实播报，别引导人去补数
      echo "[$(date '+%F %T')] finalize 守卫未能执行：duckdb 写锁占用超重试窗（rc=3），完整性未知，中止生成段"
      notify "⚠️ 全量复盘 $D finalize 中止：质检闸门被 duckdb 写锁挡住没跑成（非缺数）；等写进程收工后重跑 finalize；日志 logs/daily-full-review.out.log"
      echo "[$(date '+%F %T')] === finalize 中止 date=$D sync 守卫 rc=$guard_rc ==="
      exit "$guard_rc"
    elif [ "$guard_rc" -ne 0 ]; then
      echo "[$(date '+%F %T')] finalize 守卫未通过：$D 同步段数据不完整（same-day-gate rc=$guard_rc），中止生成段"
      notify "⚠️ 全量复盘 $D finalize 中止：18:30 sync 段未成功（same-day-gate fail），未生成报告；需先补跑 sync；日志 logs/daily-full-review.out.log"
      echo "[$(date '+%F %T')] === finalize 中止 date=$D sync 守卫 rc=$guard_rc ==="
      exit "$guard_rc"
    fi
    run_l2_branch
    if [ "$moneyflow_rc" -ne 0 ] || [ "$l2_rc" -ne 0 ]; then
      echo "[$(date '+%F %T')] === 全量复盘失败 date=$D 资金流 rc=$moneyflow_rc L2门 rc=$l2_rc ==="
      exit 1
    fi
    run_generation_and_finalize
    exit $?
    ;;

  all)
    # 全量（手动补跑）。保留原行为：sync → L2（独立分支，sync 失败也跑）→ 生成段。
    run_sync
    rc=$?
    run_l2_branch
    if [ "$rc" -ne 0 ]; then
      echo "[$(date '+%F %T')] 同步段失败 rc=$rc（常见原因：CDP proxy 未启动 / fupanhui 未登录 / 非交易日），停止后续生成段"
      notify "⚠️ 全量复盘 $D 同步段失败 rc=$rc（常见：CDP proxy 未启动 / fupanhui 未登录 / 非交易日），后续生成段未跑；日志 logs/daily-full-review.out.log"
      echo "[$(date '+%F %T')] === 全量复盘失败 date=$D 同步段 rc=$rc ==="
      exit "$rc"
    fi
    if [ "$moneyflow_rc" -ne 0 ] || [ "$l2_rc" -ne 0 ]; then
      echo "[$(date '+%F %T')] === 全量复盘失败 date=$D 资金流 rc=$moneyflow_rc L2门 rc=$l2_rc ==="
      exit 1
    fi
    run_generation_and_finalize
    exit $?
    ;;
esac
