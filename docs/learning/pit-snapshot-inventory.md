# PIT 每日快照与历史证据盘点

## 目标

历史重放必须回答一个比“数据行的 `trade_date` 是哪天”更严格的问题：
**这条数据在当时是否已经可见？**

本流程把两个问题分开：

1. 从 2026-07-10 起，每日盘后冻结当时可见的 DuckDB 行和 wiki commit。
2. 对 2026-03-02～2026-07-03，只盘点 cutoff 前已经提交的旧资料；后补数据不冒充 PIT。

## 每日冻结

先 dry-run：

```bash
python3 scripts/pit_snapshot_inventory.py freeze \
  --db db/market_feature_store.duckdb \
  --finance-root . \
  --kb-root /Users/a77/knowledge-base-private \
  --out-dir /Users/a77/fidelity-replay/pit-snapshots \
  --as-of 2026-07-10 \
  --dry-run
```

复核 manifest 后去掉 `--dry-run`。输出为：

- `YYYY-MM-DD.snapshot.json.gz`：规范化 JSON 后 gzip 压缩的完整输入。
- `YYYY-MM-DD.manifest.json`：SHA-256、表行数、时间戳边界、覆盖缺口和仓库 commit。

同一日期首次写入后不可覆盖；重复运行只校验 checksum 并返回
`already_frozen`。这采用的是 **content-addressed artifact（内容寻址产物）**
思路：文件名标识日期，hash 标识内容，任何事后改写都会被发现。

## 自动冻结

`intelligence/eval/com.financeworkspace.pit-snapshot.plist` 在每天 20:30
运行 `scripts/freeze_daily_pit_snapshot.sh`。它晚于 18:30 的
`daily-full-review`，给申万一级等较晚同步步骤留出缓冲。

## 历史资料盘点

```bash
python3 scripts/pit_snapshot_inventory.py inventory \
  --db db/market_feature_store.duckdb \
  --finance-root . \
  --kb-root /Users/a77/knowledge-base-private \
  --start 2026-03-02 \
  --end 2026-07-03 \
  --out-json /Users/a77/fidelity-replay/inventory/historical.json \
  --out-md /Users/a77/fidelity-replay/inventory/historical.md
```

三种状态：

- `ready_db`：基线表所有行都满足 `updated_at < as_of + 1 day`。
- `artifact_candidate`：DuckDB 不可证明，但 cutoff 前已有日期化 Git 文件。
- `pending`：两类证据都没有。

`artifact_candidate` 不是通过。它只证明文件当时存在，仍需人工判断其字段、
实体和事件覆盖是否足以还原当日输入。

## 技术取舍

- **为什么不用当前 DuckDB 直接回放？** 当前库允许后补和修订，`trade_date`
  不能证明可见时间。
- **为什么用 gzip JSON？** JSON 可审计、跨语言，gzip 能显著降低 2–3 万行
  板块成分数据的体积；替代方案 Parquet 更小更快，但人工 diff 和长期兼容性较差。
- **为什么只把 hash/manifest 作为索引？** 大快照不进入 Git，避免仓库膨胀；
  Git 中的代码与规则负责可重复生成，外部快照由 checksum 防篡改。
- **为什么不把旧资料直接判为 ready？** “当时存在”和“足够回答问题”是两层
  不同的证据门槛，自动合并会重新引入认识论幻觉。
