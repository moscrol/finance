# feat/opt01-content-versioning · 工单 #47（OPT-01 第二刀）

## 这个分支做什么
冻结快照当内容版本源：`slice_river(..., frozen_snapshot_root=...)` 从 ≤cutoff 最新**封印快照**读事实——数据修订后仍能答「当时看到的是哪个值」。存储侧零新增（复用 `~/fidelity-replay/pit-snapshots/` 每晚在拍的 36 份），补的是取回半边：`river_frozen.connect_frozen` 验完整封印链后把快照装成内存 DuckDB，六轨 provider 原样在其上跑。`list_content_versions` 出一行事实的版本序列 + `supersedes` 链。工单 `2026-09-11-river-frozen-content-versions-workorder.md`；PR **#735**。

## 决策与被否方案
- 对当时的库跑今天的读取面；否了「新建版本表 + 改写入链」（多一个账会漂，日频 PIT 下快照粒度已足）与「对象级 payload 重建」（派生字段要第二份构造逻辑，必漂）。
- `SNAPSHOT_TABLES` 内只用快照数据（这份没拍到 = 空表 = 当时版本不可得）；覆盖集外 VIEW 到主库（舆论表自带写一次不更新的 `created_at`，config 无被冲刷问题）——**不许**用主库冒充覆盖集内的「当时」。
- 封印坏抛 `FrozenSnapshotError` 不回退（spec 验收 3：删内容后回放门必须失败）；快照早于 as_of 回落主库（其回看窗里不可能有 as_of 的行，否则「没拍到」错报成 entity_unresolved）。
- 连接纪律过 T-2 棘轮门：主库连接 `read_only=True`，写全落 `ATTACH ':memory:' (READ_WRITE)` + `USE frozen`（read-only 会被 ATTACH 继承，须显式 READ_WRITE）。
- 装载走 `read_json`（ndjson）批量：逐行 executemany 实测 17s → 2.0s。

## 已验证
- `tests/test_river_frozen.py` 9 条：fixture 用**真冻结入口** `freeze_daily_snapshot` 两拍两改（1.0 → 修订 9.0），非手搓 manifest。`slice(T,C=T)` 回 1.0 且 strict；`C=T+7` 回 9.0；篡改 gz 抛错；无快照 / 快照早于 as_of 两种回落；幂等；版本史 supersedes 链。
- 真库实证：`2026-09-01 存储芯片` 主库直读 `trade_date_only`（recorded_at 混 09-07），`--frozen-snapshot-root` 后 **strict**、四轨齐，2.0s——strict 覆盖恢复的第一个实例（#43 工单预言的「恢复靠内容级 recorded_at」由此路径兑现）。
- 基线 c714eb60 上全量 9215P/0F；09-11 已前向合并 gitea/main@5907c9f6（含 #670/#671/#680/#681/#734），定向 24P 绿，全量重跑在途。

## 未验证 / 已知边界
- 快照序列 2026-07-10 起、有缺日；更早历史按第一刀口径降档,不补编。
- `river_window` / `anchor_windows` 未接版本源（同口径传入即可，接续 G-02c 时做）。
- 严格等级 = 日频 PIT，同日盘中多版本不区分。
- CLI 只有 `python -m intelligence.services.river --frozen-snapshot-root`；Workbench / 带读入口未接（属工作台闭环那组工作）。

## 下一步
1. 用户确认合 PR #735；合后 INDEX #47 行改 ✅。
2. 回放引擎（#25）与校准若要「当时版本」口径，直接传 `frozen_snapshot_root`。
