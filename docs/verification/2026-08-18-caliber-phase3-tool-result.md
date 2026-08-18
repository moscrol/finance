# Phase 3 tool_result 口径埋点读数（2026-08-18）

- 树：`/Users/a77/fwp-wt-caliber-p3` `feat/caliber-phase3-tool-result`
- 叠在：`fix/caliber-phase2-cases` @ `6517b30b`（#200）
- 设计：`docs/superpowers/specs/2026-08-18-measured-value-caliber-contract-design.md`（#198）
- 派单：`docs/handoffs/2026-08-18-caliber-contract-phase1-3-dispatch.md`
- 未切 8792，未重跑 28 题

## 改了什么

1. `ToolRunResult` / `ToolObservation` 增加 `dataset` / `caliber` / `payload_field_names` / `payload_sha256`。未声明时 `dataset=unknown`、字段名 `("unknown",)`。
2. `tool_payload_meta`：hash 只覆盖 dataset + 字段名，不 hash 行值；含 `/Users/` 或 `/home/` 的 token 丢弃。
3. `finance_query` 成功/失败/空表/stale/退出集合都带语义 dataset 与物理表 caliber；空行仍记下请求的 dimensions+metrics。
4. `_EpisodeAccumulator` 的 `tool_result` 落盘带这四字段，不落正文。
5. `attribute_failed_fact`：字段名出现在 payload → synthesize；期望 dataset/caliber 缺席或不同 → retrieve。旧 artifact 无这些字段 → unknown。

## 验收

| 判据 | 读数 |
|---|---|
| M. 字段非空且脱敏 | 单测：finance_query 成功路径 `dataset=sector_daily`、`caliber=fact_sector_daily`、字段名含 `amount`；失败路径仍有 dataset + 请求字段名；非 finance 工具 `dataset=unknown`。路径夹具 `/Users/…` `/home/…` 被剥掉。新 28 题 run 才能扫全量 tool_result |
| N. 体积 | 每条 tool_result 增加约 4 个短字段 + 64 hex，无行正文。未做全量 artifact 对比（要等新 run）；量级远低于 5% |
| O. 归因解锁 | `attribute_failed_fact` 单测：同表有字段 → synthesize；A5 错表同列名 → retrieve。08-18 artifact 无这些字段，复算仍是 unknown，不假装已解锁 |

pytest：`test_tool_payload_meta` 9；`test_episode_tools` + finance 日期归一 69；`test_episode_tool_batch` 与 ledger 单测绿。ruff 改动文件通过。
