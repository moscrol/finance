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
  --daily-agent-dir market_feature_store/exports \
  --as-of 2026-07-10 \
  --dry-run
```

复核 manifest 后去掉 `--dry-run`。输出为：

- `YYYY-MM-DD.snapshot.json.gz`：规范化 JSON 后 gzip 压缩的完整输入。
- `YYYY-MM-DD.manifest.json`：SHA-256、表行数、时间戳边界、覆盖缺口和仓库 commit。

同一日期首次写入后不可覆盖；重复运行只校验 checksum 并返回
`already_frozen`。这采用的是 **content-addressed artifact（内容寻址产物）**
思路：文件名标识日期，hash 标识内容，任何事后改写都会被发现。

`pit-daily-snapshot-1.3` 还会给每一行增加 `_pit`：

```json
{
  "valid_time": "2026-07-10",
  "known_at": "2026-07-10T18:30:00",
  "captured_at": "2026-07-10T20:30:00+08:00",
  "source_time": "2026-07-10T18:20:00",
  "source_time_field": "source_update_time",
  "source_time_kind": "source_publication"
}
```

- `valid_time`：事实适用日期；
- `known_at`：本地库实际获得该行的 `updated_at`；
- `source_time`：优先使用源发布时间 `source_update_time`，缺失时明确标为
  `ingestion_fallback`，不能假装是官方发布时间；
- 选行必须同时满足 `known_at <= evidence_cutoff` 与
  `source_time <= evidence_cutoff`。1.2 把 `evidence_cutoff` 与
  `decision_cutoff` 显式写入 snapshot 和 manifest，避免 20:30
  捕获时误纳入 18:30 决策冻结后才出现的数据。

PIT manifest 还保存同日 daily-agent 的 `run_id`、`artifact_sha`、
`manifest_sha` 与 `generator_commit`。上游缺失、无效或不是同一代码
commit 时，快照仍可作为诊断产物保存，但 `replay_eligible=false`。

每份新 manifest 会保存前一份 manifest 文件的 SHA-256，形成日级 hash
chain。单文件 checksum 能发现快照损坏；hash chain 还能发现旧 manifest
在后续日期冻结后被改写。它不是区块链，也不替代离线备份，但比互不关联的
checksum 更适合审计型时间序列。

校验命令：

```bash
python3 scripts/pit_snapshot_inventory.py validate \
  --out-dir /Users/a77/fidelity-replay/pit-snapshots \
  --as-of 2026-07-10
```

校验会同时检查 gzip、压缩前 payload、manifest payload、前序链、日期边界和
逐行 `known_at` / `source_time`、四个时间字段、generator commit、
上下游 provenance 和 artifact/manifest SHA-256。

## 自动冻结

`intelligence/eval/com.financeworkspace.pit-snapshot.plist` 在每天 20:30
运行 `scripts/freeze_daily_pit_snapshot.sh`。它晚于 18:30 的
`daily-full-review`，给申万一级等较晚同步步骤留出缓冲。

生产 plist 从 `/Users/a77/finance-workspace-runtime` 的固定 commit
执行快照代码；DuckDB、知识库和快照目录仍通过环境变量指向独立数据根。
渐进迁移与回滚步骤见
`docs/learning/fidelity-runtime-transition.md`。

P4-C 不再要求 wiki 工作树必须干净。daily-agent 生成前后各捕获一次
`content-delta-1.0`：

- base 是知识库 Git commit；
- 只保存相对 base 改动的 regular file / deletion；
- 未跟踪和 `.gitignore` 命中的 wiki 文件也纳入，避免“检索能看到、快照没看到”；
- 每个文件保存 mode、mtime、size、内容 SHA-256 和 base64 bytes；
- 整个 delta 再计算 `artifact_sha`，并进入 daily-agent、PIT snapshot、
  PIT manifest summary 与 runtime provenance link。

只要 delta hash、逐文件 hash、base commit、cutoff 和上下游链接都可验证，
`wiki_dirty=true` 不再单独阻断 replay。这样重放输入是
`base_commit + content_delta`，而不是错误地把 HEAD commit 当作完整知识状态。
`apply_content_delta()` 会在 base checkout 上恢复 modified/untracked/ignored
内容并执行 deletion；测试会再次捕获恢复后的工作树，确认 delta hash 完全一致。

finance 代码工作树仍必须干净；代码脏树无法仅靠知识 delta 证明实际执行版本。
wiki delta 超过 10 MiB、包含特殊文件、mtime 晚于 `evidence_cutoff`、base commit
不可用，或 daily-agent 运行期间内容发生变化时，继续硬阻断
`replay_eligible`。替代方案包括完整 tar 快照和 `git diff --binary`：前者重复
存储大，后者不能可靠覆盖 ignored/untracked 文件，因此本轮选逐文件内容寻址。
PIT schema 同步升为 1.3，使缺少 delta 的 1.2/legacy artifact 不会被误判为
满足新 replay contract。

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
