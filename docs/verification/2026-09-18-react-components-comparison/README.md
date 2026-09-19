# ReAct 组件臂 vs Workbench 同题对照（第二轮，2026-09-18）

**这是对照原件的逐字节归档，不是裁决、不是修复、不是生产验收。**

## 身份

- 原题：这里的行情哪个板块更有机会，历史上有相似的阶段吗。行情共同截至 2026-09-17，同一只读 DuckDB 快照。
- 助手稿 `component-answer.md`：pi 助手自选组件、自行综合，19 次注册组件调用 + 1 次开场预取。
- Workbench 稿 `workbench-answer.md`：逐字复制 `run_20260918_113122_450933` 最终公开答案。**它来自隔离候选 8848，跑的是 `feat/research-answer-preservation@af9500ec`（业务 `5f3b5b59`），不是生产 8792。**
- 非盲评、预算未配平、n=1、无金融认证；不能据此归因模型、SDK 或编排谁更强。结论见 `comparison.md`。
- 首轮对照（真 8792 `bf662e93`，数据截至 09-15）在 `docs/verification/2026-09-17-sector-history-comparison/`（分支 `docs/8792-sector-history-diag-0917`）。

## 保真规则

`manifest.json` 记录已归档文件的原路径、字节数、SHA-256；`.py/.log` 追加 `.txt` 后缀但字节不变。仓库红线禁止的类型，以及大于 5120 KiB 的文件，只在 `not_archived_recorded_only` 里记原路径、大小与哈希：包括 `runs/workbench.sqlite3`、`__pycache__/components.cpython-312.pyc` 和两份超限的 `history-query-*.json`。它们仍在 `~/.finance-runtime/reviews/research-components-react-20260918/`；清理该目录须先处理这些外部唯一原件，Git 归档不等于整包异地保全。归档脚本本身以 `archive_react_components.py.txt` 入包。允许文件经过逐字节哈希比对和明文凭据特征扫描。
