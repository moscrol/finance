#!/usr/bin/env bash
# ============================================================
# 一键进化流水线：复盘完成后只敲这一行
#   用法:  scripts/evolve_daily.sh [YYYY-MM-DD] [--force]
#   省略日期 -> 用今天；--force -> 复盘数据有缺口也强行继续
# 流程: 查漏补缺 -> generate(1/3/4) -> validate(1/3/4) -> log
#        -> 盘面×知识库(题材候选+简报) -> 知识库补全队列 -> 补全复核队列
#        -> audit -> suggest
# 不改任何规则；suggest 只给建议；题材/补全均为“只读报告”(产物落 exports/，不写知识库)。
# 记录/验证/题材产物已 .gitignore。
# ============================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT"

DATE="${1:-$(date +%F)}"
FORCE="no"
for a in "$@"; do [ "$a" = "--force" ] && FORCE="yes"; done

EXPORTS="market_feature_store/exports"

# 预检：DuckDB 是否被占用。全量复盘/同步运行时会持有写锁，此时本流水线无法打开库。
if ! python3 -c "import sys; sys.path.insert(0,'.'); from market_feature_store.db import connect; connect(read_only=True).close()" 2>/dev/null; then
  echo "[STOP] 数据库被占用：全量复盘/同步可能还在运行（DuckDB 持有写锁）。"
  echo "       请等复盘/同步完全结束、数据库释放后再运行本脚本。"
  echo "       当前占用数据库的进程："
  ps ax -o pid,etime,command | grep "market_feature_store" | grep -v grep || true
  exit 3
fi

echo "============================================================"
echo "[0/8] 复盘数据查漏补缺  check_daily_review_data.py $DATE"
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
echo "[1/8] 生成名单  generate --date $DATE"
python3 scripts/evolve.py generate --date "$DATE"

echo
echo "[2/8] 前瞻验证  validate --strategy 1/3/4"
for s in 1 3 4; do
  echo "  -- 策略 $s --"
  python3 scripts/evolve.py validate --strategy "$s"
done

echo
echo "[3/8] 回写 进化.md  log"
python3 scripts/evolve.py log

# ---------- 盘面 × 知识库：对齐 + 看要不要补全（全为只读报告，落 exports/，不改知识库） ----------
SKIP_GATE=""
[ "$FORCE" = "yes" ] && SKIP_GATE="--skip-gate"   # 仅 --force(数据有缺口)时跳过题材脚本内部的完整性闸门

echo
echo "[4/8] 盘面→检索知识库：题材候选 + 简报"
# 4a 题材候选(新 ThemeRadarService；是补全队列的输入)：读盘面 fact + 检索知识库 wiki
if python3 -m intelligence.cli theme --date "$DATE" --market-triggered \
     --out-json "$EXPORTS/$DATE-theme-candidates.json" \
     --out-md   "$EXPORTS/$DATE-theme-candidates.md"; then
  echo "[OK] 题材候选已生成：$EXPORTS/$DATE-theme-candidates.json"
else
  echo "[WARN] 题材候选生成失败（可能复盘未跑该步/数据不足）；后续补全队列会自动跳过。"
fi
# 4b 人读简报：把市场信号与知识库 Evidence Graph 对齐（triggered-themes.json + brief.md）
python3 scripts/build_market_triggered_theme_brief.py "$DATE" $SKIP_GATE \
  || echo "[WARN] 题材简报生成失败（已跳过，不影响策略名单）。"

echo
echo "[5/8] 知识库补全队列  build_theme_backfill_queue.py $DATE"
if [ -f "$EXPORTS/$DATE-theme-candidates.json" ]; then
  python3 scripts/build_theme_backfill_queue.py "$DATE" \
    || echo "[WARN] 补全队列生成失败（已跳过）。"
else
  echo "[SKIP] 未找到 $EXPORTS/$DATE-theme-candidates.json（由复盘的 theme-candidates 步产出），跳过。"
fi

echo
echo "[6/8] 补全复核队列(看要不要补全知识库)  build_theme_backfill_review_queue.py $DATE"
if [ -f "$EXPORTS/$DATE-theme-backfill-queue.json" ]; then
  python3 scripts/build_theme_backfill_review_queue.py "$DATE" \
    || echo "[WARN] 复核队列生成失败（已跳过）。"
else
  echo "[SKIP] 未找到 $EXPORTS/$DATE-theme-backfill-queue.json（上一步未产出），跳过。"
fi

echo
echo "[7/8] 体检  audit"
python3 scripts/evolve.py audit || true

echo
echo "[8/8] 调参建议(仅建议)  suggest"
python3 scripts/evolve.py suggest || true

echo
echo "============================================================"
echo "完成 ✅  $DATE"
echo "  记录:  evolution/records/$DATE.json"
echo "  验证:  evolution/validation/cumulative-s*.json"
echo "  日志:  进化.md 的 AUTO 区块已更新"
echo "  题材:  $EXPORTS/$DATE-theme-candidates.{json,md}、$DATE-market-triggered-theme-brief.md"
echo "  补全:  $EXPORTS/$DATE-theme-backfill-queue.json、$DATE-theme-backfill-review-queue.{json,md}"
echo "         (补全复核队列 = 人工决定要不要回知识库补 概念/实体暴露/证据)"
echo "============================================================"
