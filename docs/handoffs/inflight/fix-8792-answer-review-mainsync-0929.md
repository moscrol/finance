# fix/8792-answer-review-mainsync-0929（Arena 会话，2026-09-29 17:40 CST）

## 做了什么

- 起点：`fix/8792-answer-review-0929`@f37629829（Codex 本地两个试验提交：957dc51e2 诊断文档 + f37629829 原文片段选择试验）。
  这两个提交原先只在本机，已推到 Gitea 备份：`checkpoint/8792-answer-review-0929-20260929`。
- 新开 worktree `/Users/a77/fwp-wt-8792-review-mainsync-0929`，合并 gitea/main@f922f5d35 → `0e3d65d94`，零冲突
  （`docs/agent-product-door.md` 自动合并）。分支已推到 Gitea：`fix/8792-answer-review-mainsync-0929`。

## 验证（在 0e3d65d94 干净树上跑，主树 `.venv-workbench`）

- ruff：红 2 条，都在 main 带进来的 `scripts/check_daily_plan_local.py`（F401 / E402），不在 8792 改动里。
  main 随后的 df3e37744 已修（提交说明里写了「ruff 修复」）；本分支还没合入 df3e37744。
- 全量 pytest：`1 failed, 18829 passed, 74 skipped, 2 xfailed`，用时 20:48。
  收据 `~/.finance-runtime/test-receipts/20260929T093338Z-0e3d65d9-f92d14a785a7.json`，
  `check_test_receipt.py --require-full-scope` 判定可采信（collected=18906，收集面没被收窄，干净树）。
  - 唯一失败 `tests/test_cleanup_gate_trees.py::test_chinese_retain_reason_survives_porcelain_quoting`：
    在本树和 main 主树单独重跑都 PASS，和 8792 改动无关，判为全量并发下的不稳定用例（同一时间另一个会话也在跑测试）。
    还没查根因。
- 结论：试验代码合上最新 main 后没有引入回归。这**不等于**质量验收：计划里的「隔离服务四次首发 + 独立内容裁决 +
  预注册保留标准」一步都没做，PR #956 仍是 WIP。

## 注意：有并行会话

- 17:16 起另有会话在 `.worktrees/arena-8792-harness-takeover-0929`（分支 `fix/8792-harness-takeover-0929`，同样基于 f37629829）
  写 `test_material_source_excerpt_boundaries.py`。继续之前先和那条线对齐，不要两边各做一遍。

## 下一步

1. 合入 df3e37744（ruff 修复）后跑一次正式的 `run_main_gate.sh`，要求 ruff 绿。
2. 按 `docs/superpowers/plans/2026-09-29-material-source-excerpts.md` 剩下的两步做：隔离服务首发试验和保留判定。

## 18:17 更新（Arena 会话）

- 17:33 有人把 df3e37744 直推 main，导致 launchd wiring 测试 3 条红。已由 #972 修复（main=5588f6b58，全量门禁 18543 passed / 0 failed）。
- 本分支依次合入 df3e37744（bf9dfe9eb）和 5588f6b58，现在 HEAD 是 **f2ec0e8b7，已推 Gitea**。
  launchd 两个测试文件 55 passed，ruff 绿。上一次全量测试是在 0e3d65d9 上跑的；这两次合并只动了
  plist / 夜跑脚本 / 一处测试常量，没有改 8792 代码。
- #956 仍是 WIP。要不要换成本分支，或者合入 main，等用户决定。
