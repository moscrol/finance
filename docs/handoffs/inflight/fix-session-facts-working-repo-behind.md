# fix/session-facts-working-repo-behind · 2026-09-13

## 状态：✅ 完成、门禁全绿、PR #743 待用户拍合并

树 `/Users/a77/fwp-wt-session-facts`，基线 `gitea/main@5fb13a8c`，3 提交。
全量 **9547P / 0F**；四道门禁 exit 0；merge-tree 实探干净、落后基线 0。

## 两件事，都在 `worktree_board.py`

### ① 底旧探测（本分支起因）
`--this`（SessionStart 唯一调的路径）只报 `cherry+0`，不报落后量。两者正交：
cherry 答「补丁丢外面没有」，behind 答「读到的代码旧不旧」。

实测：主检出树落后 `gitea/main` **628 提交**却照报 `cherry+0`；在那棵树跑
`graph_audit`，已随 #734 进 main 的 `pricing_split` / `judgment_delta` 等被报成
「在途 / 未进工作树」（45 条）。照断言纪律办事的 agent 会据此写「我们没有 X」。
同族前科：夜跑代码根落后 548 提交，吃掉一个交易日（#739）。

`TreeRow.behind` 本来就有、`classify_worktree` 一直在算，只是全量看板渲染、
`--this` 不渲染——字段填了没在决策点被读。

- `behind_count()` / `_count()`：`rev-list --count` 安全读法（原 `int(x or 0)`
  遇 git 写 stdout 会抛 → hook 静默不输出）。
- 落后量追加在「合入:」**同一行**（2000 字符预算已在截断后省略三十余条）。
- `STALE_BASE_WARN = 50`：不取 0，工作树天天落后，取 0 会喊到被忽略。

### ② 吸收 #572（顺手减掉一张冲突 PR）
#572 改的正是这两个文件，留着必打架；自身 1 提交 vs main 前进 759，且
`last_switch_for_port` 在 main 与其基线**逐字节相同** → 重做比 rebase 便宜。

治的是：切换漏 `--port` → 账本落无归属行 → 旧读取侧回落到上一条带 port 的行 →
**每个会话把上一版 rev 报成 8792 现状**（09-03 f4c03b9a 被报成 c88c81da，已 16 行）。
现在报「判不出」并指向 `audit_deploy_ledger.py check`。不替它猜：8796 末次 switch
后面同样有未归属行，按「取最新」会把 8792 报成 8796。

- 规程补 `--port` 治源头那半条**已在 main**，不重复。移植其 3 条测试（逐字）。
- 补 #572 漏的第三处调用方 `tests/test_deploy_ledger_homes.py:87`（该文件 09-09
  随 #688 才有，晚于 #572，直接 rebase 会红）。
- main 规程注释原写「理由见 PR #572」，关闭后会悬空 → 改指代码契约与测试名。

## 纪律

- 两次变异测试都做了：摘掉修复 → 对应断言红、其余绿；装回全绿。
- 验收树必须在 `/Users`，`/tmp` 会让沙箱测试假红。
- 家族已查：`check_agent_workspace_facts.py` 无第二份逻辑；`session_facts.sh`
  只 103 行调一次 board；`last_switch_for_port` 三处调用方全改到。

## 下一步

1. #743 合并前重跑全量（基线可能已动）；合后关 #572 留指向 #743 的指针。
2. 主检出树那 628 落后**不归本分支**：该树有 29 个非本会话的改动，不能
   替别人认领。本分支只让它被看见。
