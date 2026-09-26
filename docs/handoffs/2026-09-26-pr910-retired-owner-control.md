# #910 前向后 6F：退役 owner 树让封存负控失效

## 背景

2026-09-26 协调者会话接手 #910（Pi `01a0d35f` 停止推进）。#868 已于 09-25 合 main，本 PR 改为对 main 的独立 PR。本轮把 `gitea/main@9c3e61bfa` 普通合并进 PR 头（`1bfc00979`）后，定向四目标读成 194P/6F。六项全是 `tests/test_pi_review_repair.py::test_sandbox_preflight_collects_real_author_tests[*]`。Pi 09-25 23:18 在 `2da72eef4` 上报过同一文件 74P。

## 按发现顺序

1. 失败栈统一停在封存预检 `sandbox_preflight.mjs` 第 55 行：`sandbox_check.py` 第 6 行读 `/Users/a77/finance-worktrees/adaptive-research-loop/intelligence/services/llm_refine.py`，抛 `FileNotFoundError`。
2. 这条读取是封存模板（`docs/verification/2026-09-23-adaptive-qc-glm-roundtrip/*/sandbox_preflight.mjs.txt`）里的负控：候选外、`$HOME` 下的文件必须 `PermissionError`。被读的是 #868 owner 当时的活 worktree。
3. 该 worktree 在 09-26 02:16 的收尾清理中被删除（`~/.finance-runtime/reviews/unclosed-inventory-20260926/remove-apply-20260926T021618.json`，`action=removed`）。路径缺失给 ENOENT 而不是 EPERM，`except PermissionError` 接不住，预检中止。`[metadata-*]`、`[keychain-*]` 要验的步骤在后面，于是一起失败。
4. 排除 main：在临时 detached 树里重跑合并前的 `2da72eef4`，同样 6F、同样 ENOENT；`git diff 2da72eef4 1bfc00979` 对这些测试读取的全部文件为空。
5. 修法落在测试（`d36a916ef`）：`repoint_retired_read_control()` 只在一次性测试输入里把这条负控改指候选内受保护的 `.claude/settings.json`。锚点按退役路径正则匹配，且断言恰好 1 处。第一版把完整家目录路径写成常量，被「路径字面量」提交钩子拦下，改成只匹配 `/finance-worktrees/adaptive-research-loop/` 片段。
6. 之后又两次合入 main（`c9f8062ed`、`346be5d8b`，前者只改文档和 `material_claim_review.py`，后者纯文档），定向 200P。

## 方案对比

| 方案 | 评价 | 结果 |
|---|---|---|
| 改封存模板里的路径 | 模板有 SHA-256 封存，`prepare()` 遇改动直接拒绝；改它就破坏封存合同 | 否 |
| 让生成器在产出时改写这条负控 | 真批次必须在新证据根重新绑定候选、基座和输入，届时本来就要重写；现在改只是扩大本 PR 范围 | 否 |
| 恢复被删的 worktree | 把测试钉在一台机器的历史状态上，下次清理还会坏 | 否 |
| 测试夹具改指一个必然存在、必须被拒的文件 | 保留负控本意（受保护内容读不到）；`$HOME` 下候选外路径仍由 `~/.pi/agent/models.json` 那条原负控覆盖 | 采用 |

产品行为本身是 fail-closed：路径缺失只会让预检失败、不出 PASS 收据，不存在放行风险。

## 验证

- 撤保护：把替身换成可读的 `AGENTS.md`，两轴都以 `forbidden read: …/AGENTS.md` 变红，还原后树干净。
- 定向：`tests/test_pi_review_repair.py tests/test_workspace.py intelligence/tests/test_llm_timeout_diagnostic.py tests/test_main_gate_receipt.py`，`d36a916ef` 200P，收据 `~/.finance-runtime/test-receipts/20260926T020117Z-d36a916e-1b57ee1b6e15.json`；`13bf6f13e` 200P。终头读数见 PR 评论。
- 范围化独立复核与沙箱探针：`~/.finance-runtime/reviews/unclosed-inventory-20260926/takeover/L1/review.md`。

## 后续与不要做的

- 以后跑真实 #868 审查批次时，重建预检的负控清单，别再引用别人的活 worktree。
- 不要为了让测试变绿去恢复或重建 `~/finance-worktrees/adaptive-research-loop`：它已按收尾清单删除，备份包在 `tree-residue/`。
- 可迁移原则：封存证据里的机器路径是会过期的外部依赖；负控要区分「被拒」和「不存在」，否则环境漂移会把一个负控变成连带失败。
