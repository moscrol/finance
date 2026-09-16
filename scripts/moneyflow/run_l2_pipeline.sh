#!/bin/zsh
set -uo pipefail

DATA_ROOT="${FINANCE_DATA_ROOT:-${FINANCE_WS:-$(cd "$(dirname "$0")/../.." && pwd)}}"
export FINANCE_DATA_ROOT="$DATA_ROOT"
export FINANCE_WS="$DATA_ROOT"
export MARKET_FEATURE_STORE_DB="${MARKET_FEATURE_STORE_DB:-$DATA_ROOT/db/market_feature_store.duckdb}"
export MONEYFLOW_OUTPUT_DIR="${MONEYFLOW_OUTPUT_DIR:-$DATA_ROOT/scripts/moneyflow/outputs}"
export L2_SOURCE="${L2_SOURCE:-baidu-share:xianyu-l2-7z}"
# 代码根 = 本脚本所在的那棵树：moneyflow 脚本、trading_days 与本文件同源，信任哪份代码可验证
#（工单 #51 夜跑代码根钉死）。状态 / 库 / 输出走 DATA_ROOT：闲鱼分享入口 state/l2-baidu-share.json、
# 日包缓存 state/l2-cache 都在数据根，百度网盘 Cookie 走本机家目录（见 l2_paths.py），与代码根无关。
CODE_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export PATH="/opt/homebrew/bin:/opt/homebrew/opt/node/bin:/usr/local/bin:$PATH"
PY="${FINANCE_PYTHON:-python3}"

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

moneyflow_dir="$CODE_ROOT/scripts/moneyflow"
if [ ! -f "$moneyflow_dir/run_l2_from_share.py" ]; then
  echo "资金流段跳过（缺少 $moneyflow_dir/run_l2_from_share.py）"
  exit 2
fi
if [ ! -f "$DATA_ROOT/state/l2-baidu-share.json" ]; then
  echo "资金流段跳过（缺少 state/l2-baidu-share.json）"
  exit 2
fi

REV=$(git -C "$CODE_ROOT" rev-parse --short=12 HEAD 2>/dev/null || echo unknown)
echo "L2 start date=$D source=$L2_SOURCE code=$CODE_ROOT rev=$REV data=$DATA_ROOT db=$MARKET_FEATURE_STORE_DB"

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
CAL_OUT="$(MARKET_FEATURE_STORE_DB="$MARKET_FEATURE_STORE_DB" "$PY" - "$D" "$CODE_ROOT" 2>&1 <<'PY'
import os
import sys

# 只认 $CODE_ROOT（= 本脚本所在的那棵树）里的那份代码。`python -` 会把**当前工作目录**
# 塞进 sys.path，而本脚本的 cd 在探针之后——不清掉它，夜跑 cwd 恰好是另一棵检出时，
# 判定就用了那棵树的休市表，日志里完全看不出来（2026-09-12 写守卫测试时实测到：把
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
"$PY" "$moneyflow_dir/write_to_duckdb.py" --calendar "$D" "$CAL_VERDICT" "$CAL_SOURCE" "$CAL_REASON" \
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
  # 行情缺口 ≠ L2 故障。本副本走闲鱼日包，L2 自身不依赖当日 fact_stock_daily；
  # 但下游 top100/quant 口径依赖它，缺了会空转。写清楚免得值班误判成 L2 坏了。
  echo "[$(date '+%F %T')] ⚠️ 当日行情 data=$CAL_DATA（非 present）：日包侧可照常，依赖当日 fact_stock_daily 的口径可能空转——这是行情缺口，不是 L2 故障" >&2
fi

cd "$moneyflow_dir" || exit 1
"$PY" run_l2_from_share.py "$D"
rc=$?
if [ "$rc" -eq 0 ]; then
  "$PY" "$CODE_ROOT/scripts/render_moneyflow_html.py" \
    || echo "[$(date '+%F %T')] render_moneyflow_html 失败（不阻断）"
fi
exit "$rc"
