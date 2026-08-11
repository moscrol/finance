#!/usr/bin/env bash
# SessionEnd hook：检测本分支是否「干了活但没写 inflight 交接」，是则落 stale 标记。
#
# 为什么是「检测 + 标记」而不是「自动补写」：
#   SessionEnd 触发时 agent 已经结束，无法让它补充上下文（卡在哪、为什么这么改、
#   踩了什么坑）。脚本生成的状态快照没有这些，写了也是空壳。所以这里只做检测，
#   把「可能没交接」这个事实落成一个标记文件，由 session_facts.sh 在下次
#   SessionStart 时注入给下一个 agent——「忘写交接」从静默变成 100% 可见。
#
# 为什么用 .git/agent-memory/ 而不是仓库目录：
#   这是本仓既有约定（devin-writeback.md 的 writeback-ok 状态戳就用这里），
#   .git/ 不入版本库、不污染 git status，天然是「agent 间传递状态」的地方。
#
# 判据（保守，只抓最明确的过期，避免多 agent 共树下误报）：
#   1. 当前分支有未提交的**代码**改动（复用 session_facts.sh 的 code 路径前缀，
#      排除 ingest 产物）→ 说明干了活
#   2. inflight 文档不存在，或存在但 mtime 早于最近一次代码改动 → 交接没跟上
#   满足则写 stale 标记。
#
# 退出码恒 0：观测设施故障不该阻断会话结束。

set -uo pipefail

# 仓根：候选逐个试，必须通过哨兵文件校验才采信（`-d` 不够——多根工作区下
# DEVIN_PROJECT_DIR 可能是父目录 /Users/a77，它存在但不是本仓。
# 详见 scripts/session_facts.sh 同段注释，2026-08-11 实测）。
SENTINEL="scripts/check_inflight_stale.sh"
REPO=""
for cand in \
  "${DEVIN_PROJECT_DIR:-}" \
  "$(git rev-parse --show-toplevel 2>/dev/null)" \
  "$(cd "$(dirname "$0")/.." 2>/dev/null && pwd)"
do
  if [ -n "$cand" ] && [ -f "$cand/$SENTINEL" ]; then REPO="$cand"; break; fi
done
[ -n "$REPO" ] || exit 0
cd "$REPO" 2>/dev/null || exit 0

branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
[ "$branch" = "?" ] && exit 0
slug="$(printf '%s' "$branch" | tr '/' '-')"

marker_dir="$REPO/.git/agent-memory"
marker="$marker_dir/stale-inflight-${slug}.marker"

# 清理旧标记：每次 SessionEnd 都重算，避免上一轮的 stale 一直挂着
rm -f "$marker"

# 1) 是否有未提交的代码改动
code_dirty="$(git status --porcelain 2>/dev/null \
  | sed 's/^...//' | sed 's/^"//;s/"$//' | sed 's/.* -> //' \
  | grep -E '^(intelligence/|evolution/|market_feature_store/|scripts/|tests/|conftest\.py|pytest\.ini|ruff\.toml|test-environment\.json|requirements-consumer\.lock)' \
  | grep -v '^market_feature_store/exports/' || true)"
code_n="$(printf '%s' "$code_dirty" | grep -c . || true)"
[ "${code_n:-0}" -eq 0 ] && exit 0   # 没干活，不标记

# 2) inflight 文档是否跟上
inflight="$REPO/docs/handoffs/inflight/${slug}.md"
if [ ! -f "$inflight" ]; then
  reason="本分支没有任何 inflight 交接文档"
else
  inflight_mtime="$(stat -f '%m' "$inflight" 2>/dev/null || echo 0)"
  code_newest="$(printf '%s\n' "$code_dirty" | while IFS= read -r f; do
    stat -f '%m %N' "$REPO/$f" 2>/dev/null
  done | sort -rn | head -1 | awk '{print $1}')"
  if [ "${code_newest:-0}" -gt "$inflight_mtime" ]; then
    reason="最近一次代码改动晚于 inflight 文档更新（交接可能没跟上）"
  else
    exit 0   # 交接文档比代码改动新，跟上
  fi
fi

mkdir -p "$marker_dir"
{
  echo "分支 ${branch}：${reason}"
  echo "干了活但 inflight 交接可能没写/过期。"
  echo "若确认已交接，删除此标记；否则下一个 agent 开工前应跑 handoff skill。"
} > "$marker"

exit 0
