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
    if [ -z "$old_pid" ] || ! kill -0 "$old_pid" 2>/dev/null; then
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

# 交易日预检查（工单 #52）。判据是**日历**，与「行情到没到」彻底分开：
#   旧实现拿当日 fact_stock_daily 行数代理交易日。2026-09-11（周五、真交易日、
#   同步失败 0 行）被判成休市 → 这里 exit 0 → 静默报成功，L2 整天没跑。
# 三值处置。注意「安全方向」对调度守卫来说是**跑**，不是跳过：
#   closed  → 跳过（真休市，跑也没数据）
#   trading → 正常跑
#   unknown → 照样跑 + 吼一声。判不出来时宁可跑到上游真实失败（上游日包会失败得
#             很响），也不要 exit 0 装作没事——后者就是本工单要消灭的形状。
# 探针自身异常（import 失败/无 python/输出对不上格式）一律归 unknown，不再 2>/dev/null
# 吞掉 stderr：那会让「判定挂了」和「判定说休市」在日志里长得一模一样。
CAL_OUT="$(MARKET_FEATURE_STORE_DB="$MARKET_FEATURE_STORE_DB" python3 - "$D" "$CODE_ROOT" 2>&1 <<'PY'
import os
import sys

# 只认 $CODE_ROOT 里的那份代码。`python3 -` 会把**当前工作目录**塞进 sys.path，
# 而本脚本的 cd 在探针之后——不清掉它，夜跑 cwd 恰好是另一棵检出时，判定就用了
# 那棵树的休市表，日志里完全看不出来（2026-09-12 写守卫测试时实测到：把
# CODE_ROOT 里的包拆掉，探针照样答 trading，因为它从 cwd 兜到了别处）。
# 与工单 #51「夜跑代码根钉死」同一条纪律：信任哪份代码必须可验证。
root = os.path.normpath(sys.argv[2])
sys.path = [root] + [p for p in sys.path if p not in ("", ".", os.getcwd())]

from market_feature_store import trading_days

origin = os.path.normpath(trading_days.__file__)
if not origin.startswith(root + os.sep):
    # 认不出来就归 unknown（→ 照跑 + 告警），不冒充判定成功。
    print(
        "unknown\tprobe_wrong_code_root\tunknown\t"
        f"trading_days 来自 {origin}，不在 CODE_ROOT={root} 内"
    )
    raise SystemExit(0)

market_data_state = trading_days.market_data_state
v = trading_days.trading_day_verdict(sys.argv[1])
# 制表符分隔：reason 是中文长句，别用空格分隔。
print(f"{v.verdict}\t{v.source}\t{market_data_state(sys.argv[1])}\t{v.reason}")
PY
)"
CAL_RC=$?  # 必须紧跟其后取：后面任何一条命令都会覆盖 $?

CAL_LINE="$(printf '%s\n' "$CAL_OUT" | tail -1)"
CAL_VERDICT="$(printf '%s\n' "$CAL_LINE" | cut -f1)"
CAL_SOURCE="$(printf '%s\n' "$CAL_LINE" | cut -f2)"
CAL_DATA="$(printf '%s\n' "$CAL_LINE" | cut -f3)"
CAL_REASON="$(printf '%s\n' "$CAL_LINE" | cut -f4)"

if [ "$CAL_RC" -ne 0 ]; then
  CAL_VERDICT="unknown"
  CAL_SOURCE="probe_failed_rc=$CAL_RC"
  CAL_DATA="unknown"
  CAL_REASON="$CAL_OUT"
fi
case "$CAL_VERDICT" in
  trading | closed | unknown) ;;
  *)
    CAL_SOURCE="probe_unparseable"
    CAL_REASON="$CAL_OUT"
    CAL_VERDICT="unknown"
    CAL_DATA="unknown"
    ;;
esac

echo "L2 calendar date=$D verdict=$CAL_VERDICT source=$CAL_SOURCE data=$CAL_DATA"

# 日历判定落台账（2026-09-13 QC S2）：unknown 不再只在 stderr 吼一声——
# 调度守卫/值班查的是 ops_pipeline_run_daily，不是日志。trading/closed 也记，
# 于是「无 calendar 行」唯一地意味着「本副本还没带这版修复」。台账失败不阻断。
python3 "$moneyflow_dir/write_to_duckdb.py" --calendar "$D" "$CAL_VERDICT" "$CAL_SOURCE" "$CAL_REASON" \
  || echo "[$(date '+%F %T')] ⚠️ 日历台账写入失败 date=$D（不阻断）" >&2

if [ "$CAL_VERDICT" = "closed" ]; then
  echo "[$(date '+%F %T')] 休市 date=$D（$CAL_SOURCE）：$CAL_REASON —— 跳过 L2 流水线"
  exit 0
fi
if [ "$CAL_VERDICT" = "unknown" ]; then
  echo "[$(date '+%F %T')] ⚠️ 交易日判不定 date=$D（$CAL_SOURCE）：$CAL_REASON" >&2
  echo "[$(date '+%F %T')] ⚠️ 按「要干活」处理继续跑 L2；失败由上游真实报错暴露，不静默 exit 0" >&2
fi
if [ "$CAL_DATA" != "present" ]; then
  # 行情缺口 ≠ L2 故障。L2 四步对当日行情的依赖是不对称的（见工单 #52 §1）：
  # limitup 读**前一交易日**涨停池，行情缺当天也能跑完；top100 读**当日**
  # fact_stock_daily 取成交额前 100，当天 0 行就必然空转。写清楚，免得值班的人
  # 把「上游行情没到」误判成「L2 坏了」。
  echo "[$(date '+%F %T')] ⚠️ 当日行情 data=$CAL_DATA（非 present）：limitup 用前一交易日涨停池可照常；top100/quant 依赖当日 fact_stock_daily，可能空转——这是行情缺口，不是 L2 故障" >&2
fi

cd "$moneyflow_dir" || exit 1
python3 write_to_duckdb.py --begin "$D" \
  && python3 scan_limitup.py "$D" \
  && python3 scan_top100.py "$D" \
  && python3 scan_quant.py "$D" \
  && python3 "$CODE_ROOT/scripts/render_moneyflow_html.py"
