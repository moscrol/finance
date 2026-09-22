# 09-22 行情恢复：字段/分母合同

## 这个分支做什么
把「行情恢复」卡住的五项（名称、换手率、历史范围、停牌分母、下游验收）转成可核验合同 + 离线审计，并把两处下游消费口径对齐；不以"继续"扩大写入、发布、合并或部署授权。

## 决策与被否方案
| 选了什么 | 否了什么 / 理由 |
|---|---|
| 名称=具名时刻展示名（带源+观察时刻） | 不当法定名称/官方状态；30 条 XD 前缀差异方向相反，证明它是瞬时态 |
| 拼接优先**当日**名，缺才回落身份基线 | 不再拿几个月前的基线名喂 ST/新股过滤 |
| `turnover` 保持 NULL，只留 `observed_turnover_pct` | 不用「两边都算得对」选真值；21 条差异源于分母口径，最大 3.75pp |
| 范围 = 有 bar 身份 ⊎ 具名停牌身份（严格分区） | 不用容差缩分母；不造平盘 bar；不把未知缺口说成停牌 |
| 恢复路径用冻结身份数当占比分母 | 不沿用日更「取到值的行数」；否则停牌被剔除会抬高涨停占比 |
| 五道门写进产物 `remaining_gates` | 不把「审计 rc=0」当 production_ready |

## 当前状态
新隔离工作树 `fix/market-recovery-contracts-0922`（自 `gitea/main` 建，已并入 `fix/market-recovery-0921`）。新增 `market_feature_store/recovery_coverage.py`（纯函数）、`scripts/audit_recovery_metadata.py`（离线审计 + CLI，输出只写新文件、失败 rc=2），改 `compute_local_stats.py`（可选恢复分母参数，默认日更行为不变）、`sync_local_sector_members.py`（优先当日名）。离线审计对封存原件实跑 rc=0，产物 `tmp/recovery-contracts/metadata-audit.json`（sha256 `abfa67b2…`，tmp 不入库）。证据与结论见 `../2026-09-22-market-recovery-field-contracts.md`。

## 已验证
- 实跑审计：声明 5565 = 有 bar 5553 ⊎ 停牌 12；涨跌平 4536/936/81，停牌单列不算平盘。
- 名称 380 差异 = 6 空格 + 30 除权前缀（20 条对照侧有、10 条具名侧有，方向相反）+ 344 简称/全称；ST/新股分类差异 0。
- 换手率 21 条差异全部两边内部自洽（`internal_denominator_mismatches=0`），分母腾讯大 16 / 新浪大 5。
- 范围双向反例：`689009.SH` 有具名 bar 却不在当前名单；`000016.SZ` 等 9 只在名单却不在全域批次。
- 4 处变异（忽略冻结分母 / 去掉停牌造 bar 前置拒绝 / 名称回退旧基线 / 分区放宽成子集）均被测试捕获。
- 全仓 `2003 passed, 62 skipped`（7m08s）；Ruff 全绿；生产库未连、未写、未发布。

## 未验证 / 已知边界
官方历史上市名册、全量除权完备性、官方流通股本口径仍缺，产物里三个 `*_verified` 固定 false。第二供应商是**当前**名单（`comparison_has_target_date=false`），只能对照不能当 PIT。生产库 09-21 仍是**整日零行**（`fact_market_daily` 最后 = 09-18），local 计划 16 步一步未跑；same-day / cross-day / L2 三门仍 `rc=2` 未复跑。审计 rc=0 ≠ 可写库。生产库 mtime 已于今天 08:08 变动（非我），02:26 保全收据已过期，写库前必须重取基线。

## 路径核对（用户质疑后查证，已纠正旧措辞）
初版把「板块全目录」写进下一步是照抄 full 计划的旧说法，**作废**。只读查库实测：复盘会成分/板块日行情停在 09-02、search payload 全表只剩 09-03；09-17/18 宇宙快照 `provider_source=local:carry`；成分全 `local:stitch`、板块日行情全 `local:agg/pct=eqw`；`fact_market_daily` 走 `local:overview`。夜间 local 计划 16 步零复盘会（还显式 `--no-fupanhui-fallback`），门禁脚本自述「fupanhui 停抓后的自算链路」。验收清单 = `tables_for_plan(registry,"local")` 的 33 张：相对 full 少 12 张复盘会独有表、多 12 张同花顺表。所以 09-21 恢复**零复盘会请求**：唯一外部输入（个股 bar）已封存，其余走 `carry-forward-universe` → `stitch-sector-stocks --max-baseline-age-days 180` → 本地派生链。同花顺那 12 张目前停在 09-08，此刻 PID 92660 在跑 dragon-auction 补（非我发起，未干预）。

## 下一步
先请用户拍三件事：官方名册来源（需在 Chrome 点「允许」才能恢复 CDP 取数）、换手率是否必须官方分母（否则该列长期 NULL）、恢复路径是否启用冻结身份分母。之后按 local 计划重跑 09-21（先写 fact_stock_daily、再 15 步本地派生）→ 新隔离 staging → 逐表回读 → 三门复跑 → 另获发布授权才原子换库。合并/部署仍需单独授权。

## 踩过的坑
- 全域批次**不含**全天停牌身份，必须额外原件补齐，否则 5556 ≠ 5565 会在严格分区处直接拒绝（这次就是这么发现的）。
- 「两源算术各自自洽」极易被误读成「数据一致」：本轮 21 条差异正是各自自洽但分母不同。
- 新工作树跑脚本要 `python -m scripts.x`（直接跑文件导入不到 `market_feature_store`）。
- 封存的 `tmp/recovery-20260921/` 原件只读；审计产物一律写新文件（`open("x")`），不覆盖既有证据。
- **别照抄旧交接的步骤名**：旧文字里的「板块全目录/复盘会」是 full 计划遗留，现行是 plan=local。写下一步前先查 `run_review_sync.py` 的步骤表与库内 source 列，别凭记忆。
