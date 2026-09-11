# feat/knevo-delta-readside · 在途交接（2026-09-11）

执行 spec `docs/superpowers/specs/2026-09-10-knevo-arch-delta-worklist.md`（评审修订版）。
**spec 文档不在本分支**，在 `docs/knevo-e009-arch-delta`（**10 笔提交**、6 个文件、
纯文档，已完整包含 `docs/knevo-m-probes-verification`）。两条都要合，文件不重叠、
顺序无依赖。
基点 `gitea/main @ 3ed44703`。

⚠ **本树同时有多个 agent 在动**（11:56 的 `f7c382a3` 是别人在我提交期间落的）。
接手先 `git log --oneline -8` 认领，别照抄本文件的提交清单。

## 提交（新→旧）

- `5213263a` 把 local 降级与替代源登记进 consumption_registry（消费侧唯一事实源）
- `eaa38d9f` D18 接第二个源（同花顺涨停池）+ 更正上一笔的错误归因
- `5f04f85b` 质检整改：W2b prime 出口归属 + D18 接问句日期 + 两处失真注释
- `f7c382a3` AB-003 本地侧冻结（W4 路径 a，非本轮产出）
- `251a2cf6` W6 判据（日历 as-of + 赔率）
- `45be2a0b` / `f017580a` 合入 event-pricing-slice1 / polymarket-macro-odds-impl
- `ac95d5f0` Q-001 已量 → 结论继续留空
- `cb411e73` W5 封板时间块 [D18]｜`f63a2352` W1/W2/W3 读侧三项

W1–W3、W5、W6 均带红绿变异实测，逐条见各自提交信息与
`docs/verification/2026-09-11-{e007-p3p4-criteria,knevo-qc-followups}.md`。

## 门禁（本轮实测，别抄旧数）

`ruff` 全绿；`pytest -q` **9145 passed / 77 skipped / 1 xfailed，exit 0**。
基线用 `--collect-only` 量：`251a2cf6` 原树 9217、本轮 9223（+6 = 本轮新增六条）。
⚠ 前面几笔提交里的 7988 / 9081 / 9088 都对不上各自 revision 的 collected 数，
是收据错挂。**要数就自己 `--collect-only`，别抄提交信息。**

## 必须知道的一件事：D18 曾惰性，已修

`fact_theme_limit_stock_daily.first_limit_time` 自 2026-09-03 起全 NULL（行照常进），
W5 交付因此在生产上一直交白卷。**原因不是上游断供，是换了写入方**——`source` 列
点名：09-03 起从 fupanhui 切成 `local:limit-rule`（风控后的既定本地自算链路），
按设计只写 12 列，封板时点属盘中事实它产不出。同批 22 列一起归零。

已补第二个源 `fact_limit_pool_hithink`（同花顺官方涨停池，`limit_up` 池），
两源交叉验证 49 只逐只到分钟一致。fupanhui 优先、交白卷才回落、块内自报换源；
历史日输出逐字节不变。**D18 现已可用。**

> 可迁移：多写入方的表看到某列全 NULL，先 `group by trade_date, source` 再谈断供。
> 一条查询就能省掉一次「要外呼比对 payload」的错误提案（我就先写错了一版）。

**没加告警是有意的**：把 `first_limit_time` 加进 `check_daily_review_data` 的空值闸，
风控期会每天响，必然被人关掉。真实损害在消费侧（写 spec 的人不知道输入降级了），
所以登记进 `consumption_registry.yaml` 的 `limit_heat.pitfalls`。
**切源前先跑 `scripts/source_switch_coverage_diff.py`**（仓里现成的，2026-09-08 为
同类问题写的；本次读数 416 vs 394 天、裸切丢 0 天）——我这次是事后才想起来跑的。

## 用户已裁决（2026-09-11）

1. **W4 取路径 a「补分」，已做**（`bcf6ca6e`）。AB-001 本地 partial（A2：写「缩量」
   而当日边际量 +16~19% 全正）、AB-002 本地 **miss**（A3+A5：排序完全反转，排第 1 的
   T+3 -15.86%，而明确排除的农业/养殖 +3.58% 是唯一正收益）。Knevo 侧 AB-001 判 hit
   但**加了不得直接计入胜率的限定**（AB-002 已证实其系统性截止违规，本条未做同等
   来源日期审计）。台账也已补登记进 `ledger-map.md`（此前从未登记）。
   ⚠ **有效样本仍只有 n=2**，任何胜率数字都不成立；周度汇总故意留空，别去填。
2. **两笔 merge：用户记不清批没批，改按内容审 → 结论「可以留」**。两条都是
   **加法且惰性**：polymarket 只加了手动 CLI 子命令、没进夜跑计划，且在
   `finance_query._UNREGISTERED_TABLES` 里主动声明不对 agent 暴露；event-pricing
   只被 `scripts/event_reaction.py` 这个手动脚本消费，没进任何 ask 路径 / launchd。
   两次都是 ort 干净自动合并（无冲突），全量 9145 绿。
   **唯一的副作用是耦合**：本分支合 main 会把这两个特性一起带走。
   `feat/event-pricing-slice1` 在 gitea 上已有（8706c0e3），`polymarket-macro-odds-impl`
   **只在本地、从没推过**。想解耦就先让它俩各自合 main，本分支的两个 merge 就变空操作。
3. **09-08 缺数：用户说补，但工具不能由 agent 调**（`duckdb-backfill` 标了
   `disable-model-invocation`）。诊断已备齐，见下节，**等用户敲 `/duckdb-backfill`**。

## 坑 / 后人须知

- **W3 阈值故意留空，已量过、结论是继续留空**。样本不足以区分候选值，填数不改变
  任何召回结果。测量记录、复现命令、重量的触发条件全在
  `evolution/backtest-queue.md`「测量记录 · 2026-09-11」——**动手前读那份，别凭直觉填**。
  直接填数会让 `test_threshold_defaults_to_none_until_backtested` 变红，那是故意的闸。
- **D18 fupanhui 路径的 `if not rows` 是死代码**（守卫 A 之后不可达，已实测），
  留作防御，别指望它变红。
- **SPT-A06 仍在 `_PENDING_RULES`，G1b 没解决**，D18 块不得夹带该规则文本。
  hithink 的 `turnover_ratio_pct` 看着像能顶上换手那半，**实测 0% 填充**，
  别再当它可用（这是第三根被识破的空壳柱子，前两根是 `open_times` 与 `first_limit_time`）。
- **`truncated` 不落库的洞有意不补**，用 documented gap 测试钉住：**洞被补上时它会变红
  并要求更新 W6 判据。到那天请改判据，别删测试。**
- **测试夹具别照抄生产**：D18 的 `pool='limit_up'` 过滤第一版测不住——夹具照生产把
  炸板行的 `limit_up_time` 写成 NULL，挡住它的其实是隔壁的 not-null 条件，删掉 pool
  过滤一片绿。要给每个过滤条件造一行「只被它拒掉」的对抗数据，再删掉它看会不会红。

## 本轮之外、建议单开的

- **2026-09-08 是真交易日，但主复盘链路整天缺数**：`fact_market_daily` /
  `fact_sector_stock_daily` / `fact_theme_limit_stock_daily` 从 09-07 直接跳到 09-09，
  `fact_stock_daily` 只有 930 行（平常 ~5550）；同花顺两张表有该日。
  （`f7c382a3` 的 AB-003 里记的「09-08 全库缺数据未查」就是这个，现已定位到
  「不是全库缺，是 fupanhui/本地链路缺」。）**未修。**

## 09-08 补数：已备好的诊断（用户跑 `/duckdb-backfill` 时直接用）

- **范围**：19 张 fact 表在 2026-09-08 整天为 0 行（`fact_market_daily` /
  `fact_sector_daily(_generation)` / `fact_sector_stock_daily(_generation)` /
  `fact_sector_universe_daily` / `fact_sw_l1_daily` / `fact_theme_limit_*` /
  `fact_limit_advance_daily` / `fact_mainline_*` / `fact_core_*` /
  `fact_leader_height_daily` / `fact_stock_high_daily` / `fact_sector_period_rank_daily`）。
  根因是那晚整条链没跑起来：`local` 计划首步 `stock-daily` 只拿到 930/5550 行，
  下游全部无输入。
- **好消息：那 930 行是干净的**，来自 `ifind:get_stock_performance`（09-09 19:25 写入），
  抽样 close 与 `fact_stock_daily_hithink` 同日**逐只 0.000% 差异**。
  → **是补齐不是清理**，不用先删。
- **交叉源已在库**：`fact_stock_daily_hithink` 09-08 有 5549 行 OHLCV（无 stock_name/pct_chg），
  `fact_limit_pool_hithink` 09-08 有 109 行。可作补数后的对账基准。
- **红线**：09-08 是历史日，**不能用 `eastmoney:snapshot` / 申万 realtime 这类
  「取最新」语义的源**——会把当天盘中价写成 09-08 收盘（AGENTS.md 点名的坑）。
