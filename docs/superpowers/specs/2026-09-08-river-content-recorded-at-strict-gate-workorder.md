# 工单 #43：时间长河 strict 止血——名单快照 `captured_at` 不再为行情内容作证（OPT-01 第一刀）

> 日期：2026-09-08
> 上游：`2026-09-08-research-foundation-optimization-design.md` **OPT-01**（PR #680；「名单快照 `captured_at` 只能证明名单版本，不能给后补行情、资金值或新成员关系提供更早的可知时间」「先阻断错误的 strict 宣称，再选择与现有写入合同兼容的内容版本存储方式」）与 §1.3「时间事实」行的最小反例；`2026-09-05-river-recorded-at-workorder.md`（写一次不更新的内容 `recorded_at`，是本单之后恢复覆盖面的正路）。
> 优先级：**P0**——当前代码路径能把 T+7 修订后的值标成「T 日 strict 可知」，回放与校准的无前视承诺在这条路径上是假的。
> 分支：`feat/river-pit-strict-gate`，树 `~/fwp-wt-opt01-river-strict`（基线 `gitea/main@f90af450`）。

## 0. 一句话

板块系两张表的 `recorded_at` 只用 `updated_at`；快照台账 `captured_at` 从 `sector_recorded_at_sql` 里拿掉。strict 覆盖面会缩回去，但缩回去的每一天都是本来就证明不了的。

## 1. 现状 [实测 @ `gitea/main` `f90af450`]

`river.py::sector_recorded_at_sql` 返回 `LEAST(v.updated_at, snap.captured_at)`。`captured_at` 是**名单**那一版的抓取时刻，`updated_at` 是**这一行内容**最后一次被写的时刻。各 sync 一律 `ON CONFLICT DO UPDATE`，同一 generation 的行情可以被覆盖而 `sector_universe_snapshot_id` 不变。于是：

| 步骤 | 库里的样子 | 河的回答 |
|---|---|---|
| T 日同步 | `pct_chg=1%`，`updated_at=T`，`snapshot_id=S`（`captured_at=T`） | strict，1% ✓ |
| T+7 修订 | 同一行 `pct_chg=9%`，`updated_at=T+7`，`snapshot_id=S` 不变 | `LEAST(T+7, T) = T` → **strict，9%** ✗ |

`test_river_recorded_at.py::test_dirty_updated_at_recovered_from_ledger` 把这个方向钉成了预期行为——它假设「重发布不改内容」，而 writer 合同不保证这一点。

## 2. 要做什么

1. `sector_recorded_at_sql(alias)` 只返回 `CAST(alias.updated_at AS TIMESTAMP)`；删掉 `with_ledger` 参数与 `sector_ledger_join`；`_market_track` / `_capital_track` 不再连台账表；`SECTOR_LEDGER_TABLE` 保留常量（别处仍有台账语义）。
2. `updated_at` 是内容当前版本「至迟何时已知」的上界：`updated_at <= C` 是「C 时已知」的充分证据；`> C` 时**降档而不猜**。这与模块开头「只会少算不会多算」的保守原则一致，本单只是把不满足它的那一支去掉。
3. `scripts/river_pit_audit.py` 同步：不再连台账、注释改口；仍从 river 取规则（测试 `test_audit_uses_the_same_rule` 守住）。
4. `tests/test_river_recorded_at.py` 重写：最小反例转回归（修订后的行在 `C=T` 下不是 strict；`require_strict` 路径把它滤成 `Gap(pit_filtered)`），保留 legacy / 无台账表 / 不变量三条。
5. 模块注释里「1 天 → 16 天」「47 天 → 20 天」的收益记录改写为：那段收益建立在不成立的假设上，本单主动放弃；恢复靠内容级 `recorded_at`（`2026-09-05-river-recorded-at-workorder.md`）。

## 3. 验收

- [x] 反例夹具：`updated_at=T+7`、台账 `captured_at=T`、`C=T` → `recorded_at[:10] == T+7`，`pit_grade == trade_date_only`，`_enforce_cutoff` 后盘面轨该对象被滤掉（`TestRevisedRowIsNotStrict`；对旧 `river.py` 实测 6 红）
- [x] `updated_at <= C` 的行仍 strict（`test_honest_row_is_still_strict`）
- [x] 表达式里不再出现 `snap.`；有无台账表输出逐字段相同
- [x] `river_pit_audit.py` 与 river 用同一表达式；`--help` 可跑
- [x] `source_hash` 不变（`test_source_hash_excludes_recorded_at`）
- [x] river 七个测试文件 38 passed / 44 skipped（skip 为需真库的原有用例）；ruff 0；pre-commit 全过
- [x] **覆盖面实测（生产库只读，2026-09-08 晚，同一库两版代码）**：`fact_sector_daily` strict 天数 21 → **1**（仅 2026-09-07）；`fact_sector_stock_daily` 50 → 48；六轨联立 strict 重放 **16 天 → 1 天**。缩水的 15 天全部来自名单 `captured_at` 作证的行——正是本单判定为不成立的证据。瓶颈表 `fact_sector_daily`：sync 每日重写 `updated_at`。

## 4. 非目标 / 红线

- 不做内容版本存储（hash / 有效期 / 替代关系 / `published_at`）——那是 OPT-01 的第二刀，落在 `river-recorded-at` 工单的写入合同上。
- 不改 `pit_grade` 的日频语义、不改 `require_strict` / `hindsight` 逻辑。
- 不改 `intelligence/eval/pit_snapshot.py`（它按 `updated_at <= snapshot_captured_at` 冻结整表，与本表达式无关）。
- 不动 sync writer；不回填任何 `updated_at`。

## 5. 交接要求

`docs/handoffs/inflight/feat-river-pit-strict-gate.md` ≤3K：写清 strict 覆盖面预期缩水（合入后用 `river_pit_audit.py` 对生产库重量一次并记进交接，不在本单猜数字）、被反转的旧测试及其原假设、恢复覆盖面的正路。
