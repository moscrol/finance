#!/bin/zsh
# 18:30 sync 入口：周末跳过、复用夜跑锁，同步走 S7 staging 包装。
# 仓内源；install_eval_launchd.sh 同步到 ~/.local/bin/nightly-full-review-s7.sh。
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

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
DATA_ROOT="${FINANCE_DATA_ROOT:-/Users/a77/finance-workspace-private}"
export FINANCE_DATA_ROOT="$DATA_ROOT"
export FINANCE_WS="$DATA_ROOT"
export MARKET_FEATURE_STORE_DB="${MARKET_FEATURE_STORE_DB:-$DATA_ROOT/db/market_feature_store.duckdb}"
export FINANCE_S7_ROOT="${FINANCE_S7_ROOT:-/Users/a77/.finance-runtime/finance-s7-sync}"
PY="${FINANCE_SYNC_PYTHON:-${OPS_PYTHON}}"
WRAPPER="${FINANCE_S7_WRAPPER:-/Users/a77/.local/bin/nightly-review-sync-staged.py}"

PHASE="sync"
D="$(date +%F)"
for arg in "$@"; do
  case "$arg" in
    sync) PHASE="sync" ;;
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
_s7_exit() {
  local rc=$?
  rm -rf "$LOCK_DIR"
  ops_health_log "daily-full-review-sync" "$rc"
}
trap _s7_exit EXIT INT TERM

dow=$(date -j -f "%Y-%m-%d" "$D" +%u)
if [ "$dow" -gt 5 ]; then
  echo "[$(date '+%F %T')] $D 周末，跳过全量复盘"
  exit 0
fi

ops_wait_duckdb_unlocked || exit 75

echo "[$(date '+%F %T')] === S7 staging sync 开始 date=$D s7=$(git -C "$FINANCE_S7_ROOT" rev-parse --short=12 HEAD 2>/dev/null || echo missing) db=$MARKET_FEATURE_STORE_DB python=$PY ==="
"$PY" -u "$WRAPPER" --date "$D"
rc=$?
if [ "$rc" -ne 0 ]; then
  echo "[$(date '+%F %T')] S7 staging sync 失败 rc=$rc"
  osascript -e "display notification \"S7 staging sync $D rc=$rc\" with title \"全量复盘告警\" sound name \"Basso\"" 2>/dev/null || true
  "$OPS_PYTHON" "$DATA_ROOT/scripts/notify_feishu.py" "⚠️ S7 staging sync $D 失败 rc=$rc；生产库未换名" 2>/dev/null || true
  echo "[$(date '+%F %T')] === sync 段失败 date=$D rc=$rc ==="
  exit "$rc"
fi
echo "[$(date '+%F %T')] === S7 staging sync 完成 date=$D（等待 20:40 finalize）==="
exit 0
