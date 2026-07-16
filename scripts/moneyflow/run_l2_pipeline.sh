#!/bin/zsh
set -uo pipefail

CODE_ROOT="${FINANCE_CODE_ROOT:-/Users/a77/finance-workspace-runtime}"
DATA_ROOT="${FINANCE_DATA_ROOT:-/Users/a77/finance-workspace-private}"
export FINANCE_DATA_ROOT="$DATA_ROOT"
export MARKET_FEATURE_STORE_DB="${MARKET_FEATURE_STORE_DB:-$DATA_ROOT/db/market_feature_store.duckdb}"
export MONEYFLOW_OUTPUT_DIR="${MONEYFLOW_OUTPUT_DIR:-$DATA_ROOT/scripts/moneyflow/outputs}"
export PATH="/opt/homebrew/bin:/opt/homebrew/opt/node/bin:/usr/local/bin:$PATH"

if [ "${1:-}" = "--force-rescan" ]; then
  export L2_FORCE_RESCAN=1
  shift
fi
D="${1:-$(date +%F)}"

if [ "${L2_LOCK_HELD:-0}" != "1" ]; then
  lock_parent="${FINANCE_LOCK_DIR:-$DATA_ROOT/state/locks}"
  lock_dir="$lock_parent/daily-full-review.lock"
  mkdir -p "$lock_parent"
  if ! mkdir "$lock_dir" 2>/dev/null; then
    old_pid="$(cat "$lock_dir/pid" 2>/dev/null || true)"
    if [ -n "$old_pid" ] && ! kill -0 "$old_pid" 2>/dev/null; then
      rm -rf "$lock_dir"
      mkdir "$lock_dir" || exit 75
    else
      echo "已有全量复盘/L2 进程在运行，跳过 date=$D pid=${old_pid:-unknown}"
      exit 75
    fi
  fi
  echo "$$" > "$lock_dir/pid"
  trap 'rm -rf "$lock_dir"' EXIT INT TERM
fi

[ -f "$HOME/.secrets/clickhouse.env" ] && source "$HOME/.secrets/clickhouse.env"
moneyflow_dir="$CODE_ROOT/scripts/moneyflow"
if [ ! -d "$moneyflow_dir" ] || [ -z "${CH_PASSWORD:-}" ]; then
  echo "资金流段跳过（缺少代码或 CH_PASSWORD）"
  exit 2
fi

REV=$(git -C "$CODE_ROOT" rev-parse --short=12 HEAD 2>/dev/null || echo unknown)
echo "L2 start date=$D code=$CODE_ROOT rev=$REV db=$MARKET_FEATURE_STORE_DB"
echo "L2 shared cache=$MONEYFLOW_OUTPUT_DIR/l2_query_cache_${D}.json force_rescan=${L2_FORCE_RESCAN:-0}"

cd "$moneyflow_dir" || exit 1
python3 write_to_duckdb.py --begin "$D" \
  && python3 scan_limitup.py "$D" \
  && python3 scan_top100.py "$D" \
  && python3 scan_quant.py "$D" \
  && python3 "$CODE_ROOT/scripts/render_moneyflow_html.py"
