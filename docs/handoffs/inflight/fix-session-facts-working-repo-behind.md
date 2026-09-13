# fix/session-facts-working-repo-behind · 2026-09-13

## 状态：✅ 代码完成、门禁全绿、待开 PR / 待用户拍合并

树 `/Users/a77/fwp-wt-session-facts`，基线 `gitea/main@5fb13a8c`，提交 `a098409f`（单提交）。

## 做了什么

`worktree_board.py --this`（SessionStart 唯一调用的路径）此前只报 `cherry+0`，
不报「底落后多少」。两件事正交：cherry 答「我的补丁丢外面没有」，behind 答
「我读到的代码是不是旧的」。

**触发它的实测**：主检出树 `/Users/a77/finance-workspace-private` 落后
`gitea/main` **628 提交**，SessionStart 照报 `cherry+0`。在那棵树上跑
`graph_audit.py`，已随 #734 合入 main 的 `pricing_split.py::parse_pricing_split_intent`、
`judgment_delta.py::counter_evidence_floor_order` 等被报成「在途 / 未进工作树」
（45 条断言标在途）。照 AGENTS.md 断言纪律办事的 agent 会据此写出「我们没有 X」
——正是那条纪律要防的事。

同族前科：夜跑代码根停在落后 548 提交的共用树，吃掉一个交易日（#51 / #739）。
那次修了夜跑的根解析，board 没跟上。

改动三处（`scripts/worktree_board.py` + `tests/test_worktree_board.py`）：
- `behind_count()` / `_count()` —— `rev-list --count` 安全读法。原
  `int(behind_s or 0)` 在 git 把话写到 stdout 时抛 ValueError，喂 SessionStart
  就是 hook 静默不输出。`classify_worktree` 一并换用，消掉那处潜在崩溃。
- `this_tree_lines()` —— 落后量追加在「合入:」**同一行**（2000 字符预算已在
  截断后省略三十余条，多一行就挤掉另一条事实）。数字始终打印，⚠ 只在过阈值加。
- `STALE_BASE_WARN = 50` —— 不取 0。共享仓取 0 是因为那是只读参照仓；工作树按
  构造天天落后（main 约 17 笔合入/天），取 0 会喊到 agent 学会忽略，比不喊更坏。

## 读数

- 变异测试：摘掉 behind 渲染块 → 新增 2 条断言红、其余 13 条绿；装回 → 15 绿
  （清了 `scripts/` 的 `__pycache__`）。
- 端到端：新脚本跑真实那棵落后 628 的树，SessionStart 真实条件（宿主
  python3、无新依赖），落后量与 ⚠ 如实出现。
- 全量 **9544P / 0F / 77S / 2xf**（= main 基线 9540 + 本次 4 条新测试）。
  树在 `/Users` 下——`/tmp` 会让 `test_installed_codex_sandbox_*` 假红（实测两次）。
- `ruff` / `layer_audit` / `check_path_literals` / `build_registry check` 全 exit 0。

## 下一步

1. 开 PR → 待用户确认后合并。合并前重跑一次全量（基线可能已动）。
2. 合并后：主检出树那 628 落后**不归本分支管**——那棵树有 29 个不属于本会话的
   未提交改动，按 AGENTS.md 不能替别人认领。留给动那棵树的 agent 自己 fetch。
3. 家族已查完：`check_agent_workspace_facts.py` 无第二份落后量逻辑，
   `session_facts.sh` 只在 103 行调一次 board，消费这行格式的只有本分支已更新的测试。
