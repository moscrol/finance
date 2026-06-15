#!/usr/bin/env bash
# ============================================================
# 一键进化流水线：复盘完成后只敲这一行
#   用法:  scripts/evolve_daily.sh [YYYY-MM-DD] [--force]
#   省略日期 -> 用今天；--force -> 复盘数据有缺口也强行继续
# 流程: 查漏补缺 -> generate(1/3/4) -> validate(1/3/4) -> log -> audit/suggest
# 不改任何规则；suggest 只给建议。记录/验证产物已 .gitignore。
# ============================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT"

DATE="${1:-$(date +%F)}"
FORCE="no"
for a in "$@"; do [ "$a" = "--force" ] && FORCE="yes"; done

# 预检：DuckDB 是否被占用。全量复盘/同步运行时会持有写锁，此时本流水线无法打开库。
if ! python3 -c "import sys; sys.path.insert(0,'.'); from market_feature_store.db import connect; connect(read_only=True).close()" 2>/dev/null; then
  echo "[STOP] 数据库被占用：全量复盘/同步可能还在运行（DuckDB 持有写锁）。"
  echo "       请等复盘/同步完全结束、数据库释放后再运行本脚本。"
  echo "       当前占用数据库的进程："
  ps ax -o pid,etime,command | grep "market_feature_store" | grep -v grep || true
  exit 3
fi

echo "============================================================"
echo "[0/5] 复盘数据查漏补缺  check_daily_review_data.py $DATE"
echo "============================================================"
if python3 scripts/check_daily_review_data.py "$DATE"; then
  echo "[OK] 当日复盘数据完整。"
else
  echo "[WARN] 当日复盘数据 INCOMPLETE（见上方 “-” 列表，请补齐）。"
  if [ "$FORCE" != "yes" ]; then
    echo "已停止。补齐后重跑，或强制继续："
    echo "    scripts/evolve_daily.sh $DATE --force"
    exit 1
  fi
  echo "[--force] 忽略缺口，继续。"
fi

echo
echo "[1/5] 生成名单  generate --date $DATE"
python3 scripts/evolve.py generate --date "$DATE"

echo
echo "[2/5] 前瞻验证  validate --strategy 1/3/4"
for s in 1 3 4; do
  echo "  -- 策略 $s --"
  python3 scripts/evolve.py validate --strategy "$s"
done

echo
echo "[3/5] 回写 进化.md  log"
python3 scripts/evolve.py log

echo
echo "[4/5] 体检  audit"
python3 scripts/evolve.py audit || true

echo
echo "[5/5] 调参建议(仅建议)  suggest"
python3 scripts/evolve.py suggest || true

echo
echo "============================================================"
echo "完成 ✅  $DATE"
echo "  记录:  evolution/records/$DATE.json"
echo "  验证:  evolution/validation/cumulative-s*.json"
echo "  日志:  进化.md 的 AUTO 区块已更新"
echo "============================================================"
