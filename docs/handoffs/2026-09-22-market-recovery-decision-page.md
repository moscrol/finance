# 2026-09-22 决策一页 · 09-21 行情恢复：五问 + 三份合同（工单 #61）

> session S4 · `market-recovery-bridge-and-contracts` · 这是 #61。
> 工单：`docs/superpowers/specs/2026-09-22-market-recovery-bridge-and-contracts-workorder.md`（PR #858 分支）。
> 桥 PR **#871**（`fix/mootdx-history-0922`，已获授权于 09-22 21:47 写过生产一次）· 合同 PR **#861**（`fix/market-recovery-contracts-0922`，含纯候选枝 `fix/market-recovery-0921` 全部提交；误开的 #859 已关并指向 #861）· 基线 `gitea/main@6f4265256`。
> 本会话零写库、零 staging、零发布；工单第 5 步起的写库动作一律等用户口令。本页写完不改；答复与后续状态看 `inflight/fix-market-recovery-contracts-0922.md`。
> 首版（同名文件 `fef0c849b` 版）问题集合是自拟的、且「09-21 整日零行」在 21:47 换库后已不成立，本版覆盖之。

## 现状（只读回读，2026-09-22 17:50 UTC，`docs/verification/2026-09-22-market-recovery/readback-before.json`）

生产库带 `trade_date` 的 `fact_*` 共 36 张（34 张基表 + 2 张 VIEW）：

| 组 | 表 | 说明 |
|---|---|---|
| 到 09-22（11 张） | `fact_stock_daily`（09-21 / 09-22 各 **5551** 行，21:47 桥换库补入，`hithink:daily-k-10d`）、`fact_market_daily`（**有 09-22、无 09-21**）、`fact_sector_kline_daily`、`fact_sector_universe_daily`（无 09-21）、`fact_sw_l1_daily`（无 09-21）、6 张 `*_hithink` | 个股底行情已齐 |
| 停 09-18（13 基表 + 2 VIEW） | `fact_core_leader/core_stock/leader_height/limit_advance/mainline_sector/mainline_stock/mainline_theme/sector_period_rank/stock_high/theme_limit_heat/theme_limit_stock_daily`、`fact_sector_daily_generation`、`fact_sector_stock_daily_generation`（两 VIEW 随之） | 全在 local 计划 33 张验收清单里（generation 表是 VIEW 的写入目标）；**不是老缺口，是本轮卡点的下游**，`fact_market_daily` 09-21 有了就能跟着重算 |
| 停 09-15（1 张） | `fact_theme_flow_daily` | 仅 full 计划产（复盘会题材资金） |
| 停 09-02（7 张） | `fact_auction_stock_daily`、`fact_dragon_seat/summary/tiger_daily`、`fact_global_index/stock_daily`、`fact_limit_advance_presence` | 复盘会独有；前 6 张仅 full 计划产，`limit_advance_presence` 不在任何计划 |
| 空表（2 张） | `fact_polymarket_macro_odds_daily`、`fact_stock_technical_snapshot` | 不在任何计划 |

**卡点一句话**：`fact_market_daily` 缺 09-21 一行 → `compute_features` 拒跑 → 09-21 `feature_stock_*` 0 行 → 13 张本地派生表停在 09-18。个股 bar 不缺了，缺的是市场行 + 口径。

## 五问（工单定的 a–e，要用户拍）

| # | 问 | 实测证据 | 建议（不是决定） |
|---|---|---|---|
| **(a)** | 官方历史名册来源：恢复 CDP 取数（要在 Chrome 点「允许」）拿官方名册，还是先按 5565 声明范围恢复、产物固定 `official_historical_universe_verified=false`？`fact_market_daily` 09-21 的分母随此定 | 双向反例：`689009.SH` 有具名 bar 却不在当前名单；`000016.SZ` 等 9 只在名单却不在全域批次 | **先按 5565 恢复**，名册留作后续门；CDP 是否点允许由用户决定 |
| **(b)** | 换手率是否必须官方分母？不必须则 `turnover` 长期 NULL，只留 `observed_turnover_pct` | 21 条两源差异 >0.011pp、最大 3.75pp，两边各自内部自洽（分母口径不同）；全仓无全市场流通股本；存量 mootdx 行本就 NULL | **不必须，保持 NULL**（= 合同 2 选 A）；要真值走东财 f8 另接（D） |
| **(c)** | 恢复路径是否启用冻结身份分母（`denominator_basis=frozen_identity`）：12 只停牌留分母、不造 bar、不计涨跌家数？ | 5565 = 5553 ⊎ 12；日更硬约束会剔无值成员抬高涨停占比（测试锁 2/4=50%，非 2/3）；`compute_limit_stats_local` 已有可选参数、默认行为不变 | **启用**（= 合同 3 选 A 的恢复路径实现） |
| **(d)** | 53 只除权/送转两日行怎么补：第三源仲裁 / 保持缺行 / 桥放宽？ | 桥按设计拒写送转配股等不支持事件（正确拒写，清单待落盘）；两家分红金额分歧 2 只（`000703.SZ` 0.90/0.82、`002255.SZ` 0.06/0.05） | **保持缺行 + 第三源仲裁后逐只具名补**；不放宽桥（放宽 = 让代码替业务裁决除权） |
| **(e)** | 老缺口表逐张定性：停采 or 失修？ | 见现状表。工单写「15 张」，只读回读能点名的老缺口是 **10 张**：7 张复盘会独有（09-02）+ `fact_theme_flow_daily`（09-15，仅 full 计划）+ 2 张空表；13 张 09-18 表是本轮下游不算老缺口 | 7 张复盘会独有 + `theme_flow` 定「**停采**（复盘会 09-07 起停抓）」；2 张空表 + `limit_advance_presence`（无计划产出）请用户定「失修」或「停采」；验收表里停采单列不算缺口 |

## 三份合同（请求书 `docs/superpowers/specs/2026-09-22-canonical-projection-contracts-decision-request.md` 已在 main；回一个字母即可，如「1=B，2=A，3=A」）

| 合同 | 选项 | 请求书建议（待裁） | #861 / #871 已落的实现 |
|---|---|---|---|
| 1 `stock_name` 来源 | A 保留旧行名 / B 另接东财快照只为名称 / C 置 NULL + 声明缺口 / D 建 `dim_stock` 名册（schema 变更） | 目标态 D，过渡期 B；**不建议 A**（静默用旧名，ST 加帽当天看不出） | #861：拼接优先当日具名名 + `name_source` / `name_observed_at`；#871 桥当前取库内历史名标 unverified（A 的形状，签后要改） |
| 2 `turnover` 来源 | A 置 NULL + 能力声明 / B 保留旧行 / C 从 `circ_mv` 推导 / D 另接东财 f8 | **A**（存量已 NULL；B 最危险：换手率是快变量） | 两枝都写 NULL；#861 另存 `observed_turnover_pct` |
| 3 停复牌分母 | A 名单锚定 + 缺口入账 / B 观察分母 / C 保留旧行补齐（平盘） | **A**（把两处已在跑的口径写成合同；C 与「不凭零成交合成平盘 K 线」冲突） | #861：`recovery_coverage.partition_scope` 严格分区 + `compute_limit_stats_local` 冻结身份分母（可选） |

## 两张 PR 与门禁

- **#871 桥**：`fix/mootdx-history-0922` 已前向到 `gitea/main@6f4265256`（`ecde76527`），8 文件 +1172/−20，merge-tree clean，`intelligence/webapp` 零改动。PR 正文写明已写过生产一次，换库收据 `db/market_feature_store.duckdb.bak-20260922T214745-92f6604e22f4.receipt.json`（`backup_sha256=869a3a0f…5dcb82`）。
- **#861 合同**：merge-tree clean。离线审计对封存原件复跑 rc=0，产物 sha256 `abfa67b21d908436451ea87909cc3c855592e86d10a5f1d85fe72ad4f10fdae8`，与 09-22 18:23 首跑逐字节相同。
- 四叶读数在各自最终 head 上跑完后贴 PR 评论（python 全仓 + registry-check；frontend / e2e 以 webapp 零 diff 说明不适用）。合并等用户确认。

## 拿到答复后的下一步 / 还没关的门

1. 补 `fact_market_daily` 09-21（分母按 a / c）→ 15 步本地派生 → 新隔离 staging → 逐表回读 → same-day / cross-day / L2 三门 → **另获发布授权**才原子换库；写前 `df` ≥ 8G、重取基线（21:47 已换过一次库）。
2. 09-22 当日：用户输入 `/daily-full-review`。
3. 桥的阳性对照（工单步骤 4，隔离副本 09-18 干跑两向）读数贴 #871。
4. #810 前向 / 四叶 / 去留（工单目标 6）本轮未做。
5. 官方名册、除权完备性、官方流通股本三个 `*_verified=false`；三门最近 `rc=2` 未复跑。
