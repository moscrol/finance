# G-05 `market_stage` 归一

- **状态**：实现已提交，等待用户确认是否合并 `fix/g05-market-stage-normalize@cf060a43`；未切运行时。
- **基线**：`gitea/main@7664af48`，独立干净 worktree `/Users/a77/fwp-wt-g05`。
- **改动**：新增共享 `normalize_market_stage()`；旁路标签写入统一去掉末尾一个「阶段」后缀并保留 NULL；`LABEL_VERSION` 从 v2 升为 v3；规则、示例、测试同步 canonical 值。主库 `fact_market_daily` 未写入。
- **数据**：`/Users/a77/finance-workspace-private/db/history_labels.duckdb` 已重建 labels/outcomes，两个 metadata 记录均为 v3；`market_stage` 只剩 canonical 值。该 DuckDB 不进 Git。
- **验收**：全量 `pytest -q`：7914 passed / 76 skipped / 1 xfailed；ruff 0 error；方法论 selftest 21/21；真实主库 river query 9/9。收据：`/Users/a77/.finance-runtime/test-receipts/20260906T103225Z-cf060a43.json`。
- **规则复跑**：四条第五刀规则整体 N、命中数和总体 verdict 不变；旧「下跌阶段=refuted」及「顶部横盘=supported」因与短写法合并而撤回，详见 `docs/verification/2026-09-06-g05-market-stage.md`。
- **下一步**：用户确认后再合并；合并时保留 v3 旁路库或按同命令重建，不要复用 v2 收据做横向比较。
