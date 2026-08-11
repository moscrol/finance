#!/usr/bin/env bash
# SessionStart hook：把「你在哪棵树、用哪个解释器、上次读数是什么」在会话开头
# 投递给 agent。**一份逻辑供所有 harness**（Devin / Claude Code / 其他）。
#
# ## 为什么必须是 hook 而不是文档
#
# AGENTS.md 与 CLAUDE.md 都写了「用 .venv-workbench/bin/python」。2026-08-10 我
# （一个读过 CLAUDE.md 的 agent）连续二十多次用宿主 python3 跑 pytest，得到
# 71 failed，而正确解释器下是 14 failed —— 差 57 条全是环境噪声。更糟的是我拿
# 那个数字做完了一整套归属分析，推理无懈可击、输入是垃圾。
#
# 本仓 check_agent_workspace_facts.py 的 docstring 记着同一件事：2026-08-05 一晚
# 两个 agent 在这两件事上出错 7 次，**没有一次被文档拦住**。
# 结论已被写进 pre-commit 注释：提醒的到达率不可靠，门禁是 100%。
#
# 分工（三层，按「这条信息失效会怎样」划分，不按「哪个位置显眼」）：
#   门禁（pre-commit / conftest.py）  违反有后果 → 唯一 100% 到达
#   本 hook                          必须知道、否则走弯路 → 无条件注入
#   skill / AGENTS.md                需要时才查 → 按需加��
#
# ## 为什么走 additionalContext 而不是裸 echo
#
# 实测两边文档，协议一致：
#   Devin        docs/extensibility/hooks/overview.mdx:145-174
#   Claude Code  马书 ch18 §18.8 示例2（restored-src 的 SessionStart 实例）
# 都要求 `{"hookSpecificOutput":{"hookEventName":"SessionStart",
# "additionalContext":"..."}}`。裸 echo 到 stdout 依赖 harness 恰好把 stdout 当
# context 收 —— 那是实现细节，不是协议。走 JSON 才跨 harness 通用。
#
# ## 为什么有字节预算
#
# 族 B（马书 ch19 §19.6，claudemd.ts:93）：`MAX_MEMORY_CHARACTER_COUNT = 40000`
# **是警告阈值而非硬拦截**——「系统会提示用户，但不会阻止加载。实际上限受制于
# 整个系统提示词的 token 预算，过大的 CLAUDE.md 会挤压其他上下文空间。」
# 同章对 AutoMem/TeamMem（会随使用膨胀的内容）的处置是**主动截断**行数与字节。
#
# 本 hook 输出的正是这类会膨胀的内容（脏文件列表、收据），所以自带预算并在
# 超限时**声明砍了什么**——静默截断会让 agent 以为看到了全部。
#
# 预算取 2000 字符，是本仓自己的取舍而非抄那个 40000：hook 事实是「开工必读」，
# 与 preferences.md 那种长期规约争同一份注意力，短才有人读完。
# INDEX 已把 40000 标为「不可搬运量纲」——用它的机制，不抄它的数字。
#
# ## 为什么全部现场探测
#
# 写死的事实和 AGENTS.md 里写死的事实一样会过期，且过期时无人知晓。本轮已三次
# 撞见这个形状：依赖清单写两份当天就漂、门禁 LOCAL_ROOTS 手写漏了 evolution/、
# 能力图谱「数数别用固定行号」。所以这里一个事实都不写死。
#
# 退出码恒为 0：观测设施故障不该阻断会话。

set -uo pipefail

# 仓根：候选逐个试，**必须通过哨兵文件校验**才采信（`-d` 不够）。
# 不写死家目录（scripts/check_path_literals.py 会拦）。
#
# 2026-08-11 实测：多根工作区下 DEVIN_PROJECT_DIR=/Users/a77（父目录，不是仓根）。
# 旧逻辑只判 `-d`，该目录恰好存在于是被无条件采信，脚本对着错的树输出
# 「树: a77 @ ?、解释器不存在、代码改动 0」——四项全错，退出码却是 0。
# **静默失真比静默不输出更坏**：不输出只是没帮上忙，假事实会被下一个 agent 当真。
# 所以判据从「目录存在」升级为「这棵树里有本脚本」。
#
# 逐个候选用 for + break，不写成 `$(A || B)` 串联：`||` 与 `&&` 的优先级会让
# git 成功时后半段仍然执行，REPO 变成两行拼接，随后 cd 失败静默 exit 0
# ——一个静默不输出的 hook 等于没装，且没有任何报错提示。实测踩过。
SENTINEL="scripts/session_facts.sh"
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

BUDGET=2000
LINES=()

# ── 1. 哪棵树 ──────────────────────────────────────────────────────────
# 本仓主检出树下另有 4 个附属 worktree 各在不同分支。只报分支不报树是不够的：
# 在错误的树上切分支/stash 会毁掉别人正在进行的工作（2026-08-05 真实发生过）。
branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
rev="$(git rev-parse --short HEAD 2>/dev/null || echo '?')"
common="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
main_tree=""
[ -n "$common" ] && main_tree="$(dirname "$common")"
wt_count="$(git worktree list 2>/dev/null | wc -l | tr -d ' ')"
here="$(pwd)"
if [ -n "$main_tree" ] && [ "$here" = "$main_tree" ]; then
  kind="主检出树"
else
  kind="附属 worktree"
fi
LINES+=("树: ${here##*/} @ ${branch} (${rev}) — ${kind}，全仓共 ${wt_count} 棵")

# ── 2. 用哪个解释器 ────────────────────────────────────────────────────
# 从 test-environment.json 读（与 conftest.py / check_agent_workspace_facts.py
# 同一份真本源），不在这里写第二份路径。
spec="$REPO/test-environment.json"
py=""
if [ -f "$spec" ]; then
  py="$(sed -n 's/.*"interpreter"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$spec" | head -1)"
fi
[ -z "$py" ] && py="$REPO/.venv-workbench/bin/python"
if [ -x "$py" ]; then
  LINES+=("解释器: ${py}  ← 用它跑 pytest/ruff。宿主 python3 缺依赖，用错会得到偏高的失败数（实测 71 vs 14），那个数字看起来完全合理")
else
  LINES+=("解释器: ⚠ ${py} 不存在或不可执行 —— 环境本身需要修")
fi

# ── 3. 代码是否有未提交改动 ────────────────────────────────────────────
# 只列**影响被测行为**的路径。本仓工作区长期有 40+ 个脏文件（复盘台账、
# market_feature_store/exports、复盘/ 下 HTML），全是每日 ingest 的正常产物；
# 整块塞进来会把真信号埋掉。判据前缀与 test-environment.json 共用同一份。
dirty_total="$(git status --porcelain 2>/dev/null | grep -c . || true)"
code_dirty="$(git status --porcelain 2>/dev/null \
  | sed 's/^...//' | sed 's/^"//;s/"$//' | sed 's/.* -> //' \
  | grep -E '^(intelligence/|evolution/|market_feature_store/|scripts/|tests/|conftest\.py|pytest\.ini|ruff\.toml|test-environment\.json|requirements-consumer\.lock)' \
  | grep -v '^market_feature_store/exports/' || true)"
code_n="$(printf '%s' "$code_dirty" | grep -c . || true)"
if [ "${code_n:-0}" -gt 0 ]; then
  first="$(printf '%s' "$code_dirty" | head -3 | tr '\n' ' ')"
  LINES+=("代码改动: ${code_n} 个未提交（${first}…）；全树另有 $((dirty_total - code_n)) 个 ingest 数据产物，与被测行为无关")
else
  LINES+=("代码改动: 无（全树 ${dirty_total} 个脏文件均为 ingest 数据产物）")
fi

# ── 4. 上次读数能不能直接采信 ──────────────────────────────────────────
# 存在的理由：多 agent 协作里，下一个 agent 通常不信前人的「3943 passed」而重跑
# 一遍。那是理性反应——脱离条件的数字不是证据。收据带齐条件后，几秒即可判定。
receipt="$HOME/.finance-runtime/test-receipts/latest.json"
if [ -f "$receipt" ]; then
  r_rev="$(sed -n 's/.*"revision"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$receipt" | head -1)"
  r_pass="$(sed -n 's/.*"passed"[[:space:]]*:[[:space:]]*\([0-9]*\).*/\1/p' "$receipt" | head -1)"
  r_fail="$(sed -n 's/.*"failed"[[:space:]]*:[[:space:]]*\([0-9]*\).*/\1/p' "$receipt" | head -1)"
  r_dirty="$(sed -n 's/.*"dirty"[[:space:]]*:[[:space:]]*\([a-z]*\).*/\1/p' "$receipt" | head -1)"
  head_full="$(git rev-parse HEAD 2>/dev/null || echo '')"
  if [ "$r_rev" = "$head_full" ] && [ "$r_dirty" = "false" ]; then
    verdict="条件与当前一致，可直接采信，不必重跑"
  else
    verdict="条件与当前不符，需重跑（跑 scripts/check_test_receipt.py 看差哪条）"
  fi
  LINES+=("上次读数: passed=${r_pass:-?} failed=${r_fail:-?} @ ${r_rev:0:8} — ${verdict}")
else
  LINES+=("上次读数: 无收据（跑一次 pytest 即自动生成）")
fi

# ── 5. 门禁 ────────────────────────────────────────────────────────────
if [ -f "$REPO/.pre-commit-config.yaml" ]; then
  gates="$(grep -c '^      - id:' "$REPO/.pre-commit-config.yaml" 2>/dev/null || echo '?')"
  LINES+=("门禁: pre-commit ${gates} 道（解释器用错 / 层级违规 / 新增硬编码路径 会被拦下）")
fi

# ── 6. 在途交接：当前分支的活文档 ──────────────────────────────────────
# 为什么注入而不是靠 agent 记得去读：`docs/handoffs/` 有 63 份日期快照、无索引，
# 接手者既不知该读哪份、也没有机制迫使他读。本轮已证明「提醒的到达率不可靠」
# ——CLAUDE.md 写着用哪个解释器，我照样连续二十多次用错。
#
# 只注入**当前分支那一份**（分片键 = 分支名，`/` 换 `-`）：
#  · 一个共享的 CURRENT.md 在本仓是错的设计——多棵 worktree 共享同一个 .git、
#    同树可并发两个 agent，单个可变文件就是争用点（2026-08-07 一次 commit 吞掉
#    另一 agent 的 4 个在途文件）。按写者分片让并发天然无冲突。
#  · 顺带白送索引：`ls inflight/` 即「当前几件事在飞」。
#
# 这一段放在最后：预算耗尽时先被截断的是它，而不是解释器那条硬事实。
# 排序即优先级——预算不够时保住哪条，是设计决定，不能靠碰巧。
inflight_dir="$REPO/docs/handoffs/inflight"
slug="$(printf '%s' "$branch" | tr '/' '-')"
inflight="$inflight_dir/${slug}.md"

# stale 标记先算好，**排在正文之前**注入（2026-08-11 实测调序）：
# 它是对下面那份文档的信任度限定。放在正文之后时，正文一变长就把它挤出预算——
# 结果是「限定语没了、正文还在」，接手者会全额相信一份已经过期的交接。
# 这是最坏的组合，比两者都不注入更坏。限定语必须先于被限定的内容到达。
marker="$REPO/.git/agent-memory/stale-inflight-${slug}.marker"
stale_line=""
if [ -f "$marker" ]; then
  # 只取第 1 行（判据/理由）。marker 后两行是通用行动建议，与本行末尾的
  # 「跑 handoff skill 补写」重复——重复文案在 2000 字符预算里是实打实的挤占，
  # 实测多花 ~110 字符、多砍掉 4 行正文。
  stale_txt="$(head -1 "$marker" 2>/dev/null | tr '\n' ' ')"
  stale_line="⚠ 交接可能过期: ${stale_txt}。若已交接请删标记；否则跑 handoff skill 补写（见 docs/handoffs/inflight/）"
fi

if [ -f "$inflight" ]; then
  # 用 awk 按行处理而非 head -c：后者按字节切会把中文劈成半个字符，产出非法
  # UTF-8，下游 grep/cut/rg 全部把输出当二进制——本轮在 load-memory.sh 上实测踩过，
  # 且因此连续误判了五次根因（量具被自己污染的输出骗了）。
  #
  # 为什么不再用 `NR<=12` 取前 12 行（2026-08-11 实测改）：
  #   交接文档的自然结构是「身份 → 已做 → 未验/边界 → 下一步 → 踩过的坑」，
  #   前 12 行只覆盖到「已做」。也就是说**截断恰好砍掉了风险面**：接手者拿到了
  #   「这分支在干嘛」，没拿到「哪里会咬人」。实测本分支那份 46 行文档，
  #   「本轮没跑 pytest」「别在这棵树跑全量对账」「6 条静默失真的坑」全在 12 行之外。
  #
  # 为什么是「重排」而不是「按小节名挑」：
  #   写死中文小节名会踩本仓记过的坑——`## 任**务**看**板**` 夹粗体就匹配不上，
  #   且失败方式是**静默出空**。这里只做一件弱耦合的事：把「已验证」这类
  #   *回顾性* 小节挪到末尾，其余保持原序。预算够就全都注入，不够时由下面的
  #   组装循环从尾部砍——砍掉的是「我做完了什么」，保住的是「什么还没验」。
  #   小节名没匹配上只会退化成原序，匹配不到 `^## ` 则整篇按原序注入，都不会出空。
  #
  # 不在这里做字数截断：awk 在 LC_ALL=C 下 length() 数的是字节，而预算是字符，
  # 两个量纲混用必然算错。截断统一交给下面按字符计数、且会**声明**砍了多少的循环。
  brief="$(LC_ALL=C awk '
    # BEGIN 里必须显式 sec=0。awk 用**未初始化变量**做数组下标时，下标是空串 ""
    # 而不是数字 0——于是首个 `## ` 之前的正文（标题、更新日期）写进 body[""]，
    # 而 END 的 `for (i=0; ...)` 读的是 body["0"]，两个不同的格子。
    # 后果：整篇没有 `## ` 的交接文档会**注入全空**，且退出码 0、无任何报错。
    # 2026-08-11 实测踩到，正是本段注释声称要避开的那种「静默出空」。
    BEGIN { sec = 0 }
    /^## / { sec++; late[sec] = ($0 ~ /已验证|验证通过|已完成|已交付|[Vv]erified|[Dd]one/) ? 1 : 0 }
    !/^$/  { body[sec] = body[sec] $0 "\n" }
    END {
      for (i = 0; i <= sec; i++) if (!late[i]) printf "%s", body[i]
      for (i = 0; i <= sec; i++) if ( late[i]) printf "%s", body[i]
    }
  ' "$inflight" 2>/dev/null)"
  if [ -n "$brief" ]; then
    # 超出 ≤3K 约定时在指针行标注实际字节数：预算总量固定（工作区事实约占 790 字符，
    # 留给正文约 1140 ≈ 3K 中文），文档一超标，被截断的就不再是末尾的「已验证」，
    # 而是「下一步」和「踩过的坑」——机制的价值恰好丢在这里。
    # 标注救不回被砍的内容，但它让「这份交接超标了」对读者和下一个写者都可见，
    # 而不是让人以为自己看到的就是全部（静默截断正是本仓反复吃亏的形状）。
    doc_bytes="$(wc -c < "$inflight" 2>/dev/null | tr -d ' ')"
    if [ "${doc_bytes:-0}" -gt 3072 ]; then
      LINES+=("在途交接: docs/handoffs/inflight/${slug}.md（⚠ ${doc_bytes} 字节，超 ≤3K 约定，下面正文已被截断，接手请读原文件）")
    else
      LINES+=("在途交接: docs/handoffs/inflight/${slug}.md（本分支活文档，接手先读）")
    fi
    [ -n "$stale_line" ] && LINES+=("$stale_line") && stale_line=""
    while IFS= read -r l; do LINES+=("  ${l}"); done <<< "$brief"
  fi
elif [ -d "$inflight_dir" ]; then
  others="$(ls "$inflight_dir" 2>/dev/null | grep -c '\.md$' || true)"
  if [ "${others:-0}" -gt 0 ]; then
    LINES+=("在途交接: 本分支无（inflight/ 下另有 ${others} 份属其他分支）。完工请按 devin-writeback.md 覆写 inflight/${slug}.md")
  fi
fi

# 没有 inflight 正文可挂（文档缺失 / brief 为空）时，stale 仍需独立发出——
# 「该有交接却没有」正是最该被看见的那种情况。
[ -n "$stale_line" ] && LINES+=("$stale_line")

# ── 组装：预算内输出，超限则截断并**声明**砍了什么 ─────────────────────
#
# 标题与尾部声明都要**先生成、再量实际长度**做预留，不写死常量。
# 这是本仓 load-memory.sh 已经踩过并改掉的同一个坑（dd77c316：手写 RESERVED=1000
# 实际是 986，且会随内容漂移——预留太小则总量超预算，太大则白扔额度）。
#
# 2026-08-11 实测：本脚本原先两样都没算，标题（约 30 字符）和声明（约 40 字符）
# 都在 BUDGET 之外，实际输出 2069 字符 / 预算 2000，**声明「已达 2000 预算」的那句话
# 本身就是超出预算的一部分**。量具报的数和它自己的规矩对不上，虽然只溢出 3%，
# 但一个自己都不守的预算，下次没人会拿它当约束。
#
# 省略条数取 ${#LINES[@]}（全被砍时的可达上界），所以量出的是长度上界，不是估值。
HEADER="## 工作区事实（SessionStart 自动探测，非文档摘抄）"
decl_max="（已达 ${BUDGET} 字符预算，省略后 ${#LINES[@]} 条；完整事实跑 scripts/check_agent_workspace_facts.py）"
avail=$(( BUDGET - ${#HEADER} - 1 - ${#decl_max} - 1 ))   # 两个 -1 是各自的尾部换行

body=""
kept=0
for line in "${LINES[@]}"; do
  candidate="${body}${line}"$'\n'
  if [ "${#candidate}" -gt "$avail" ]; then
    body="${body}（已达 ${BUDGET} 字符预算，省略后 $(( ${#LINES[@]} - kept )) 条；完整事实跑 scripts/check_agent_workspace_facts.py）"$'\n'
    break
  fi
  body="$candidate"
  kept=$((kept + 1))
done

# JSON 转义：只需处理反斜杠、双引号与换行。用 python3 更稳，但 hook 要在
# 「解释器可能不对」的环境里工作，故不依赖任何 venv，纯 shell 完成。
esc="$(printf '%s' "$body" | sed 's/\\/\\\\/g; s/"/\\"/g' | awk '{printf "%s\\n", $0}')"

printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"## 工作区事实（SessionStart 自动探测，非文档摘抄）\\n%s"}}\n' "$esc"
exit 0
