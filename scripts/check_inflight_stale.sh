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
# 判据分两级，按「这个改动能不能归属到本分支」划分：
#
#   一级（强，100% 可归属）：本分支有提交晚于 inflight 文档。
#     提交自带分支归属，`<base>..HEAD` 是精确集合，共树下别人的活混不进来。
#
#   二级（弱，需交集过滤）：未提交改动 ∩ 本分支提交碰过的路径。
#     未提交改动在 git 里**没有分支归属**——它只属于这棵树，不属于任何分支。
#
# 2026-08-11 实测的假阳性（本次修的就是它）：本分支（RejectionKind 门禁分类）被
# 3 个 moneyflow/L2 的脏文件判成「交接过期」，而那 3 个文件本分支 8 个提交一次都
# 没碰过。旧判据只看「代码路径前缀 + mtime」，是**拿文件系统事实推断版本控制事实**
# ——本仓主检出树常年多 agent 共用，这类误报必然发生。误报的代价不是烦人而是失效：
# 一个喊过狼来了的门禁，下次不会有人看。
#
# 接受的假阴性：全新话题的未提交工作（不在本分支提交路径集里）不触发。
# 取舍理由：漏报只是没帮上忙，误报会让整个机制被无视。
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

# 0) 归属基线：topic 分支比 main；main 自己比 origin/main（未推送的提交即在途工作）。
#    基线解析不了（无 main ref / detached HEAD）时**不静默关掉门禁**，退回旧的宽判据，
#    但在标记里声明「本次未做归属过滤」——降级要说出来，否则下一个 agent 无从判断
#    这条告警值多少信任。
if [ "$branch" = "main" ]; then base_ref="origin/main"; else base_ref="main"; fi
git rev-parse --verify --quiet "$base_ref" >/dev/null 2>&1 || base_ref=""

# 1) 未提交的代码改动（路径前缀与 session_facts.sh 共用同一份判据）
code_dirty="$(git status --porcelain 2>/dev/null \
  | sed 's/^...//' | sed 's/^"//;s/"$//' | sed 's/.* -> //' \
  | grep -E '^(intelligence/|evolution/|market_feature_store/|scripts/|tests/|conftest\.py|pytest\.ini|ruff\.toml|test-environment\.json|requirements-consumer\.lock)' \
  | grep -v '^market_feature_store/exports/' || true)"

# 2) 归属过滤：只保留本分支提交碰过的路径（`...` 三点 = 从分叉点比起，即"本分支改了什么"）
degraded=""
if [ -n "$base_ref" ]; then
  branch_paths="$(git diff --name-only "${base_ref}...HEAD" 2>/dev/null || true)"
  if [ -n "$code_dirty" ] && [ -n "$branch_paths" ]; then
    code_dirty="$(printf '%s\n' "$code_dirty" \
      | grep -Fxf <(printf '%s\n' "$branch_paths") || true)"
  else
    code_dirty=""
  fi
else
  degraded="（注意：归属基线不可解析，本次未做归属过滤，可能误报）"
fi
code_n="$(printf '%s' "$code_dirty" | grep -c . || true)"

# 3) 本分支提交里最新的一个（一级判据，强归属）
commit_newest=0
if [ -n "$base_ref" ]; then
  commit_newest="$(git log -1 --format=%ct "${base_ref}..HEAD" 2>/dev/null || echo 0)"
fi
[ -z "$commit_newest" ] && commit_newest=0

# 两级都没信号 = 本分支这轮没干活，不标记
[ "${code_n:-0}" -eq 0 ] && [ "${commit_newest:-0}" -eq 0 ] && exit 0

# 4) inflight 文档是否跟上
inflight="$REPO/docs/handoffs/inflight/${slug}.md"
if [ ! -f "$inflight" ]; then
  reason="本分支有在途工作但没有任何 inflight 交接文档${degraded}"
else
  inflight_mtime="$(stat -f '%m' "$inflight" 2>/dev/null || echo 0)"
  work_newest="${commit_newest:-0}"
  basis="本分支提交"
  if [ "${code_n:-0}" -gt 0 ]; then
    # LC_ALL=C：macOS 的 sort/uniq 在 UTF-8 locale 下按 collation 比较，CJK 主权重
    # 相同会把**不同的中文行判为相等**（2026-08-11 实测：6 个不同小节被 uniq 合成
    # 1 个、计数 5）。这里路径虽多为 ASCII，但本仓有 复盘/ 这类中文路径，按字节比稳。
    dirty_newest="$(printf '%s\n' "$code_dirty" | while IFS= read -r f; do
      stat -f '%m %N' "$REPO/$f" 2>/dev/null
    done | LC_ALL=C sort -rn | head -1 | awk '{print $1}')"
    if [ "${dirty_newest:-0}" -gt "$work_newest" ]; then
      work_newest="$dirty_newest"
      basis="本分支路径上的未提交改动（${code_n} 个）"
    fi
  fi
  if [ "$work_newest" -gt "$inflight_mtime" ]; then
    reason="${basis}晚于 inflight 文档更新（交接可能没跟上）${degraded}"
  else
    exit 0   # 交接文档比本分支最近一次工作新，跟上了
  fi
fi

mkdir -p "$marker_dir"
{
  echo "分支 ${branch}：${reason}"
  echo "干了活但 inflight 交接可能没写/过期。"
  echo "若确认已交接，删除此标记；否则下一个 agent 开工前应跑 handoff skill。"
} > "$marker"

exit 0
