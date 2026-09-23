# 2026-09-22 行情恢复：同花顺桥合入、缺口定性与三份合同签字工单

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
姊妹：#60（东财传输层 + 熔断，同样影响 09-23 夜跑，部署动作要协调同一个 sync 代码根）、#62（RAG readiness 复验，等本单数据到位后跑）、#74（#857 单快照排查）。
本单含**三处要用户拍板**，执行方先把决策项整理成一页贴给用户，拿到答案再动第 5 步以后的写库动作。

## 背景与动机

- 生产库 `db/market_feature_store.duckdb` 09-22 22:00 只读实测（`max(trade_date)` 分组，34 张带日期的 fact 表）：11 张到 09-22（`fact_stock_daily`、`fact_market_daily`、`fact_sector_kline_daily`、`fact_sector_universe_daily`、`fact_sw_l1_daily` 与 6 张 `*_hithink`）；**13 张停在 09-18**（`fact_core_leader_daily`、`fact_core_stock_daily`、`fact_leader_height_daily`、`fact_limit_advance_daily`、`fact_mainline_sector/stock/theme_daily`、`fact_sector_daily_generation`、`fact_sector_stock_daily_generation`、`fact_sector_period_rank_daily`、`fact_stock_high_daily`、`fact_theme`…）；`fact_theme_flow_daily` 停在 09-15；**7 张停在 09-02**（`fact_auction_stock_daily`、`fact_dragon_seat/summary/tiger_daily`、`fact_global_index/stock_daily`、`fact_limit_advance_presence`，全是复盘会独有表，复盘会已停抓、夜间 local 计划 16 步零复盘会请求）。
- 09-22 21:47 用户授权后已换库一次（`run_id=92f6604e22f4`，staging 克隆 + 闸门 + 原子换名，回滚点 `db/market_feature_store.duckdb.bak-20260922T214745-92f6604e22f4` 带 sha256 收据）：`fact_stock_daily` 补进 09-21 / 09-22 各 5551 行，`source='hithink:daily-k-10d'`，走的是本地分支 `fix/mootdx-history-0922` 的桥 `market_feature_store/sync/bridge_hithink_stock_daily.py`（复用 `preview_stock_calculation` 的除息/舍入，默认拒绝覆盖已有行，越界校验在 COMMIT 前）。09-18 回测 OHLC 5552/5552 逐位一致；链条闸 `pre_close == round(前日 close − 当日红利, 2)` 5549 只零例外。**这段代码未合 main，但已写过生产**。
- 仍缺：`fact_market_daily` 没有 09-21 行 → `compute_features` 拒跑 → 09-21 `feature_stock_*` 0 行；13 张本地派生表要在 09-21 / 09-22 重跑 local 计划才能到位；换手率 `turnover` 桥写 NULL（同花顺不提供）；`stock_name` 取库内历史名标 unverified；两家分红金额分歧 2 只（`000703.SZ` 0.90/0.82、`002255.SZ` 0.06/0.05）；全市场范围 5553 vs 5565 口径未定；53 只除权/送转被桥正确拒写待处置。
- 字段/分母合同已在本地分支 `fix/market-recovery-contracts-0922`（HEAD `93b4a90c6`，纯函数 `market_feature_store/recovery_coverage.py` + 离线审计 `scripts/audit_recovery_metadata.py`，产物写 `remaining_gates`，`production_ready=false`）。canonical 投影三份未签合同的决策请求书已在 main：`docs/superpowers/specs/2026-09-22-canonical-projection-contracts-decision-request.md`。
- **已定的形态决策**：复盘事实只走 `daily-full`（staging 写 + 原子换库），不手搓 SQL；历史日走回填规程、当日走 `/daily-full-review` 手动门（该 skill 有副作用，用户输入 `/daily-full-review` 调用，agent 不绕开复现）；mootdx 判定为供应商停供，不修客户端（39 台扫描 15 台可连、K 线 body 恒 2 字节）；名称是「具名时刻展示名」不是法定名；`turnover` 保持 NULL 只留 `observed_turnover_pct`；范围 = 有 bar 身份 ⊎ 具名停牌身份（严格分区，不造平盘 bar）。

## 目标

1. **一页决策请求**贴给用户，含五问：(a) 官方历史名册来源（是否恢复 CDP 取数，要在 Chrome 点「允许」）；(b) 换手率是否必须官方分母（否则该列长期 NULL）；(c) 恢复路径是否启用冻结身份分母；(d) 53 只除权/送转两日行怎么补（第三源仲裁 / 保持缺行 / 桥放宽）；(e) 15 张老缺口表逐张定性：停采 or 失修（7 张复盘会独有 + `fact_theme_flow_daily` + 其余）。加上三份合同（决策请求书里的名称来源、换手率来源、停复牌分母）。
2. `fix/mootdx-history-0922` 前向到最新 `gitea/main`、推送、开 PR：桥、`mootdx_source` 健康探针（源不可用 rc=2）、夜跑 `run_bridge_stock_daily_step`（同花顺日线之后、compute-features 之前）。四叶收据 revision == head。PR 描述写明「该分支已写过生产一次，换库收据见 …」。
3. `fix/market-recovery-contracts-0922` 前向、推送、开 PR；离线审计对封存原件复跑 rc=0，产物 sha 记进 PR。
4. 拿到决策后按 local 计划补 09-21：先补 `fact_market_daily` 09-21（来源按决策 a），再 15 步本地派生 → 新隔离 staging → 逐表回读 → same-day / cross-day / L2 三门复跑 → **另获发布授权**才原子换库。09-22 当日走 `/daily-full-review`。
5. 回读表：34 张 fact 表 `max(trade_date)` 与 09-21 / 09-22 行数，每张对照 `market_feature_store/consumption_registry.yaml` 的 `tables_for_plan(registry,"local")` 33 张验收清单；停采表单列不算缺口。
6. #810（`feat/hithink-research-data` @ `7596751d8`，同花顺研究观察值与 sync 部署审计）前向、四叶、决定合入或关闭留指针。

## 非目标（写死认领）

- ❌ 不修东财传输层与熔断（#60）。
- ❌ 不把 `scripts/fast_daily_sync.py`、`scripts/backfill_sector_marginal.py`、旧库 `db/market.duckdb` 恢复成第二条写入链（AGENTS.md 已退役）。
- ❌ 不用飞书 Bitable 写复盘事实。
- ❌ 不改板块名单分代语义（`published` 按日唯一，#851 已合）；换源必须显式 `supersede_provider=<在位 provider>`。
- ❌ 不给 `turnover` 用「两边都算得对」选真值（21 条差异源于分母口径，最大 3.75pp）。
- ❌ 不删 `tmp/…/production-before.duckdb`（sha `3da5260b…`，唯一完整回滚点）；其余旧副本按 21:47 会话列的表处置，删前 `df` 前后各记一次。

## 证据路径

| 文件 | 看什么 |
|---|---|
| 分支 `fix/mootdx-history-0922`：`docs/handoffs/inflight/fix-mootdx-history-0922.md` | 桥的决策表、已执行的换库、未验证边界、同名列语义错位坑 |
| `db/market_feature_store.duckdb.bak-20260922T214745-92f6604e22f4.receipt.json` | 换库收据与 6 步恢复法 |
| 分支 `fix/market-recovery-contracts-0922`：`docs/handoffs/inflight/…` 与 `docs/handoffs/2026-09-22-market-recovery-field-contracts.md` | 五道门、名称 380 差异分解、换手率 21 条、范围双向反例 |
| `docs/superpowers/specs/2026-09-22-canonical-projection-contracts-decision-request.md` | 三份合同的选项与推荐 |
| `market_feature_store/sync/sync_daily_full.py::run_bridge_stock_daily_step`、`sync/bridge_hithink_stock_daily.py`、`mootdx_source.py`（分支版） | 桥与健康探针 |
| `market_feature_store/consumption_registry.yaml`、`skills/daily-full-review/SKILL.md`、`skills/daily-full-review/references/ops-pitfalls.md` | 验收清单口径、正门、坑 |
| `docs/learning/current-duckdb-source.md`、`docs/data-sources/runtime-and-pitfalls.md` | 验鲜方法、跨日名单变化须留痕 |
| `~/Library/LaunchAgents/com.financeworkspace.daily-full-review-sync.plist` | 生产 `MARKET_FEATURE_STORE_DB` 与 sync 代码根 |

## 步骤

1. 开工三连；只读验鲜：`duckdb.connect(db, read_only=True)` 跑 34 张表 `max(trade_date)` 与 09-21/09-22 行数，落 `docs/verification/<日期>-market-recovery/readback-before.json`。
2. 起草决策一页（目标 1），贴给用户；等答复期间做第 3、4 步。
3. 两条分支各自 `merge-tree` 探冲突、前向、推送、`gitea_pr.py open`；低负载时四叶。
4. 桥的阳性对照：在隔离副本上对 09-18 再跑一次 `build_bridge_day` 干跑，`apply` 必须因「已有行」拒写零行（默认守卫）；把守卫去掉再跑必须报 5552 行将被覆盖，还原。
5. 拿到决策后：历史日 09-21 按 `skills/duckdb-backfill`（用户手动 `/duckdb-backfill`）或 `market_feature_store.cli` 的回填正门，`MARKET_FEATURE_STORE_DB` 显式指生产库（分支树默认解析到本树 `db/`）；隔离 staging → 回读 → 三门。发布授权单独要。
6. 09-22 当日：请用户输入 `/daily-full-review`。
7. 回读表 + INDEX #61 行 + inflight ≤3K；两 PR 合入需用户确认。

## 验收

- [ ] 决策一页贴出，用户五问 + 三合同各有答复记录（原话 + 出处）。
- [ ] 两 PR 四叶收据 revision == head；桥的阳性对照两向都有读数。
- [ ] 换库后回读：`fact_market_daily` 有 09-21 行；13 张 09-18 表到 09-22；停采表在回读表里单列并标「停采（用户 <日期> 确认）」。
- [ ] 每次换库有 `pre-swap-backup` 收据，`restore_steps` 完整；`df` 前后各一次。
- [ ] `fact_stock_daily` 09-21 / 09-22 抽 `close / pct_chg / amount` 非空率 ≥ 99.9%，且与 `fact_stock_daily_hithink` 同日 diff 只差被拒写的除权行（清单落盘）。

## 红线

- 复盘事实只走 `daily-full` 正门；不 inline SQL / heredoc 写库；不用 `daily-update` / `daily-full-exec` 直写生产库。
- 有副作用的 skill（`daily-full-review`、`duckdb-backfill`）由用户手动 `/<skill>` 调用，agent 不复现步骤。
- 每次写生产库前重取基线（生产库 mtime 会被别的 agent 改）；写前 `df` 可用 ≥ 8G（一次合规换库 ≈ 7.4G）。
- 只用 pathspec 提交；合入 main 等用户确认；不强推。
- pytest / ruff 一律 `.venv-workbench/bin/python -m …`；新树跑脚本用 `python -m scripts.x`。
- 不写明文密钥；不提交 `*.duckdb` 与备份。
