# 工单 #47：时间长河内容版本取回——冻结快照当版本源（OPT-01 第二刀）

> 日期：2026-09-11
> 上游：补强 spec `2026-09-08-research-foundation-optimization-design.md` OPT-01；第一刀 = 工单 #43（PR #683，已合）
> 用户 09-11 拍板的推进顺序第一项：「保存、取回事实的具体历史版本。以后数据修订，仍能回答『当时看到的是哪个值』」
> 分支：`feat/opt01-content-versioning`

## 0. 一句话

第一刀让修订后的行**不再冒充** strict（保守，但答不出旧值）；本刀把「当时的值」真正取回来：
`slice_river(..., frozen_snapshot_root=...)` 从 **≤ cutoff 最新的封印快照**读事实内容——存储侧
**复用已有冻结快照**（spec OPT-01 原文「复用已有冻结快照及分代机制」，`~/fidelity-replay/
pit-snapshots/` 36 份、每晚在拍），零写入链改动；缺的只是取回半边，本刀补它。

## 1. 设计（关键取舍）

- **对当时的库跑今天的读取面**，不做对象级 payload 重建：`river_frozen.connect_frozen` 验证封印
  （`validate_frozen_snapshot` 全链：gz sha → payload sha → as_of/boundary → manifest 封印）后把快照
  装成内存 DuckDB，六轨 provider 原样在其上运行——payload、派生字段、ref 由同一套代码构造，
  不存在第二份重建逻辑可漂。否了「新建版本表 + 改写入链」：多一个账会漂，且日频 PIT 下快照
  粒度已足。
- **覆盖集内外分治**：`SNAPSHOT_TABLES` 内的 14 张表只用快照数据（这份快照没拍到 = 空表 =
  当时版本不可得，**不许** VIEW 到当前库冒充）；覆盖集外的表 VIEW 到当前库——舆论表自带写一次
  不更新的 `created_at`（cutoff 过滤即严格），config / generation 底表无被冲刷问题。`content_source`
  里声明 `config_tables: live`。
- **快照早于 as_of 时回落主库**：那份快照的 20 日回看窗里不可能有 as_of 的行，用它会把「没拍到」
  错报成 `entity_unresolved`；主库行 `updated_at ≤ C` 时本来就是当时版本（未被修订），照常 strict。
- **封印坏 → 抛 `FrozenSnapshotError`，不静默回退**（spec 验收 3：删掉可解析内容后回放门必须
  失败）；无 ≤C 快照 → 如实回落主库并在 `content_source.reason` 里写明。
- 版本史查询 `list_content_versions(root, table, match)`：各快照里该行的内容版本序列（`content_
  sha256` / `first_seen` / `supersedes` 链）+ 主库当前值——「T+7 查询能看到修订与原版本关系」。
- 性能：快照行走 `read_json`（ndjson）批量装载，真库整片切片 17s → **2.0s**。

## 2. 验收（对 spec OPT-01 逐条）

- [x] 验收 1：T 日原值 (1.0) 与 T+7 修订 (9.0) 并存——`slice(T, C=T, frozen)` 返回 1.0 且 strict；
  不带版本源同一查询降档、`require_strict` 下滤成 `Gap(pit_filtered)`，不返回 9.0 标 strict；
  `slice(T, C=T+7, frozen)` 看到 9.0（`tests/test_river_frozen.py`，fixture 用**真冻结入口**
  `freeze_daily_snapshot` 两拍两改，非手搓 manifest）。
- [x] 验收 3：篡改 gz 内容 → `FrozenSnapshotError`，整条查询失败不回退。
- [x] 真库实证：`2026-09-01 存储芯片`——主库直读 `trade_date_only`（recorded_at 混 09-07），
  `--frozen-snapshot-root` 后 **strict**、四轨对象齐、content_source=frozen_snapshot@2026-09-01。
- [x] 幂等；`content_source` 活过 `to_dict`；无 ≤C 快照 / 快照早于 as_of 两种回落各有测试。
- 验收 2（板块成员宇宙 / 跨源联接）由既有分代机制承担，本刀不动。

## 3. 边界 / 未做

- 快照序列 2026-07-10 起 36 份且有缺日：更早的历史与缺日仍按第一刀口径降档——如实，不补编。
- `river_window` / `anchor_windows` 尚未接版本源（G-02c 那组工作接续时同口径传入）。
- 同日盘中多版本不区分（严格等级 = 日频 PIT，spec §4.1）。
- 快照覆盖集外、又会被覆盖冲刷的表（若未来出现）需先进 `SNAPSHOT_TABLES`——写入侧的事，
  不在读取面兜。
