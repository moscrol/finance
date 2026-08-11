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
#
# ⏱ **SessionEnd hook 的超时只有 1.5 秒**（马书 ch18:284，`hooks.ts:174-182`，
#   env `CLAUDE_CODE_SESSIONEND_HOOKS_TIMEOUT_MS` 可覆盖；且 1.5s 同时是单 hook
#   超时和整体 AbortSignal 上限，因为所有 hook 并行跑）。本仓这条 hook 没配
#   `timeout` 字段，吃的就是默认值。
#   2026-08-11 实测本脚本 110~143 ms，约 10 倍余量。**往下加任何 git 操作前先重测**
#   ——超时被杀是静默的，门禁会无声失效而不是报错。
#   顺带：本仓 SessionEnd 没配 matcher，所以 clear / logout / prompt_input_exit /
#   other 四种 reason 都会触发（`/clear` 也算），这是有意的。

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

# 走 git 的 **common dir**，不能写死 "$REPO/.git"（2026-08-12 实测修）：
# 附属 worktree 里 `.git` 是一个**文件**（73 字节，内容形如 `gitdir: .../worktrees/xxx`），
# 不是目录——`mkdir -p "$REPO/.git/agent-memory"` 直接 `Not a directory`，
# 标记永远写不下去，而门禁照样 exit 0。
# 后果比看上去大：**本门禁在所有附属 worktree 里完全失效**，而本仓常态是 5 棵 worktree
# 并行。此前只在主检出树验过，所以一直没暴露。
# common dir 在主树和 worktree 里都解析到同一个真实 .git；标记按分支名分片，
# 而一个分支同时只可能被一棵树检出，共享一份不会串。
marker_dir="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null || echo "$REPO/.git")/agent-memory"
marker="$marker_dir/stale-inflight-${slug}.marker"

# 标记的增删**推迟到判定完成之后**，本段只定义动作、不执行。
#
# 依据 10_knowledge/gate-covers-only-its-return-value.md：给一段逻辑加闸门时，
# 先问「它除了返回值还写了什么」——写在别处的副作用不受判定路径管辖。
# 旧写法开头就 `rm -f "$marker"`，之后才做几次 git 查询。脚本一旦在中间被杀
# （SessionEnd 只有 1.5 秒预算；用户 Ctrl+C 同理），**上一轮留下的合法 stale 标记
# 就被无声销毁了**，而门禁自己不会报任何错——下一个 agent 少看见一条告警，
# 且没有任何迹象表明它曾经存在。
# 「先清空再重算」在**可被中断**的执行体里不是幂等操作，是有损操作。
not_stale() { rm -f "$marker"; exit 0; }

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
#
# **必须排除交接文档自己那条路径**，否则门禁自噬：写完交接去提交，这个提交的时间
# 必然晚于文档 mtime（git commit 不改文件 mtime），下一轮立刻又判「过期」——
# 写了也没用，永远报警。2026-08-11 实测撞到：本分支交接文档提交完当场复发。
# 这是本仓已记过的「提交动作让文档当场失效」在门禁侧的重现。
#
# 只动交接文档的提交 = 交接行为本身，不是「新干的活」，必须不计入。
commit_newest=0
if [ -n "$base_ref" ]; then
  commit_newest="$(git log -1 --format=%ct "${base_ref}..HEAD" \
    -- ":(exclude)docs/handoffs/inflight/${slug}.md" 2>/dev/null || echo 0)"
fi
[ -z "$commit_newest" ] && commit_newest=0

# 两级都没信号 = 本分支这轮没干活，不标记
[ "${code_n:-0}" -eq 0 ] && [ "${commit_newest:-0}" -eq 0 ] && not_stale

# 4) inflight 文档是否跟上
inflight="$REPO/docs/handoffs/inflight/${slug}.md"
if [ ! -f "$inflight" ]; then
  reason="本分支有在途工作但没有任何 inflight 交接文档${degraded}"
else
  # 文档时间取 max(工作区 mtime, 最后一次改动它的提交时间)。
  # 只取 mtime 会漏一种情况：交接文档与代码写在**同一个提交**里——此时该提交
  # 计入上面的 commit_newest（它也动了代码），而文档 mtime 停在写入那一刻、
  # 恒早于提交时刻，于是又误判过期。取两者较大值，两种写法都成立。
  inflight_mtime="$(stat -f '%m' "$inflight" 2>/dev/null || echo 0)"
  doc_commit="$(git log -1 --format=%ct -- "docs/handoffs/inflight/${slug}.md" 2>/dev/null || echo 0)"
  [ "${doc_commit:-0}" -gt "${inflight_mtime:-0}" ] && inflight_mtime="$doc_commit"
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
    not_stale   # 交接文档比本分支最近一次工作新，跟上了
  fi
fi

mkdir -p "$marker_dir"
{
  echo "分支 ${branch}：${reason}"
  echo "干了活但 inflight 交接可能没写/过期。"
  echo "若确认已交接，删除此标记；否则下一个 agent 开工前应跑 handoff skill。"
} > "$marker"

exit 0
