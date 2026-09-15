# 2026-09-16 · #592 / #747 用户授权合并回执

## 合并事实

用户明确指令「合并」，范围为前轮约定的#592→#747；不含生产切换。Gitea API已核实：

| PR | 被测head | 合入main | 时间（+08） |
|---|---|---|---|
| #592 | 9550a9313b7b3353c5f229629d3e56ac1126dff6 | c1f8416a4290770f469cb56b250ff4e4f9b57465 | 00:54:07 |
| #747 | 8052003ea4ea25b49594d0069b8bfc6aa099d825 | 918f8d5aab3248d3ed2b1193b501ceb2f85ed4d5 | 00:54:47 |

#592合前fetch核main仍1bcb1ebc，receipt-check与merge-tree均通过。#747在#592合后改base=main，head不变；merge-tree exit0，结果tree等于已测8052003e。合后918f8d5a与8052003e逐文件零diff。不删除作者分支、不强推、不改其他PR。

## 真正的main批次门禁

独立干净检出：`~/.finance-runtime/release-merge-20260916/finance-workspace-private` @ **918f8d5a**。
解释器：`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`；`env -i PATH="$PATH" HOME="$HOME"`、umask022；前端pnpm10.12.1按锁文件独立安装。未软链canonical主库，非脏主检出收据。

| 检查 | 结果 |
|---|---|
| Ruff整仓 | exit0 |
| pytest全仓 | 9749 passed / 0 failed / 77 skipped / 2 xfailed，367.84s |
| pnpm lint / typecheck / test / build | 全exit0，76 tests |
| Playwright端到端 | 15 passed，46.7s |
| registry check-parseability / check / backfill-tables --check / generate-views --check | 全exit0 |
| ledger-spec-crosswalk | exit0 |

Python收据：`~/.finance-runtime/test-receipts/20260915T170134Z-918f8d5a.json`。
在被测树fetch后执行 `check_test_receipt.py <receipt> --expect-revision "$(git rev-parse gitea/main)" --base-drift-max 5` → **exit0、漂移0**。
原始证据根 `~/.finance-runtime/release-merge-20260916/`：
- `pr592-merged.json` / `pr747-merged.json`：API合入事实；
- `pr592-merge-tree.log` / `pr747-merge-tree.log`：合并模拟；
- `main-*.log` / `main-*.exit`：各叶原始输出；
- `main-gate-summary.json` / `main-receipt-check.log`：汇总与条件校验。

裁决已写PR评论：#592 comment4598、#747 comment4599。后续纯文档状态回写也单独执行门禁；其精确head、merge提交及最终main收据由该文档PR评论承载，避免不断改收据文件造成自指revision循环。这里的9749读数只绑定918f8d5a，不冒充其他提交。

## 运行面与剩余事项

- 8792 health：`e40f22b837178322169f47e565282450b4381a3a`、source_dirty=false、code_matches_repo=true；**未切生产**。
- 上轮共享旁路v6发布及四规则收据维持，不重复写库、不改生产判断台账。
- 人工stage_manual 0/42（上轮实读），需创始人标≥30后才出一致率。
- 成本观察：上轮扫描1318个生产run，自#593合入时刻起统计合格新run0；非当前实时计数、非上线日口径。另约部署窗口后验第一条judge_usage，自然积累≥20，再同调用CLI成本对账与BP回填。
- 主检出原有代码/文档/ingest改动全保留，不将它们纳入任何提交。
- 当前接续：`docs/handoffs/inflight/fix-release-gate-closeout.md`；背景与数据决策：`docs/handoffs/2026-09-15-release-gate-closeout.md`。
