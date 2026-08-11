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

# 仓根：优先 Devin 提供的 DEVIN_PROJECT_DIR，其次 git，最后脚本位置。
# 不写死家目录（scripts/check_path_literals.py 会拦）。
REPO="${DEVIN_PROJECT_DIR:-}"
if [ -z "$REPO" ] || [ ! -d "$REPO" ]; then
  # 分两步，不写成 `$(A || cd .. && pwd)`：那个写法里 `||` 与 `&&` 的优先级会让
  # git 成功时 `pwd` 仍然执行，REPO 变成两行拼接，随后 cd 失败静默 exit 0
  # ——一个静默不输出的 hook 等于没装，且没有任何报错提示。实测踩过。
  REPO="$(git rev-parse --show-toplevel 2>/dev/null)"
  if [ -z "$REPO" ]; then
    REPO="$(cd "$(dirname "$0")/.." && pwd)"
  fi
fi
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
if [ -f "$inflight" ]; then
  # 只取正文前若干行喂进注入；全文让 agent 自己 Read（路径已给出）。
  # 用 awk 按行截断而非 head -c：后者按字节切会把中文劈成半个字符，产出非法
  # UTF-8，下游 grep/cut/rg 全部把输出当二进制——本轮在 load-memory.sh 上实测踩过，
  # 且因此连续误判了五次根因（量具被自己污染的输出骗了）。
  brief="$(LC_ALL=C awk 'NR<=12 && !/^$/ { print }' "$inflight" 2>/dev/null)"
  if [ -n "$brief" ]; then
    LINES+=("在途交接: docs/handoffs/inflight/${slug}.md（本分支活文档，接手先读）")
    while IFS= read -r l; do LINES+=("  ${l}"); done <<< "$brief"
  fi
elif [ -d "$inflight_dir" ]; then
  others="$(ls "$inflight_dir" 2>/dev/null | grep -c '\.md$' || true)"
  if [ "${others:-0}" -gt 0 ]; then
    LINES+=("在途交接: 本分支无（inflight/ 下另有 ${others} 份属其他分支）。完工请按 devin-writeback.md 覆写 inflight/${slug}.md")
  fi
fi

# ── 组装：预算内输出，超限则截断并**声明**砍了什么 ─────────────────────
body=""
kept=0
for line in "${LINES[@]}"; do
  candidate="${body}${line}"$'\n'
  if [ "${#candidate}" -gt "$BUDGET" ]; then
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
