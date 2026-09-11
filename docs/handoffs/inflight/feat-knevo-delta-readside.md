# feat/knevo-delta-readside · 在途交接（2026-09-11）

执行 spec `docs/superpowers/specs/2026-09-10-knevo-arch-delta-worklist.md`（评审修订版）。
**spec 文档不在本分支**，在 `docs/knevo-e009-arch-delta`（7 笔提交、6 个文件、纯文档，
已完整包含 `docs/knevo-m-probes-verification`）。两条都要合，文件不重叠、顺序无依赖。
基点 `gitea/main @ 3ed44703`。

⚠ **本树同时有多个 agent 在动**（11:56 的 `f7c382a3` 是别人在我提交期间落的）。
接手先 `git log --oneline -8` 认领，别照抄本文件的提交清单。

## 提交（新→旧）

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

## 等用户裁决

1. **W4（AB 双盲台账）裁决进行中，已偏向 (a) 补样本**。`f7c382a3` 冻结了 AB-003
   本地侧（数据截止 09-10、预测 09-14，中间夹 09-11 一个交易日是**有意的污染
   检测窗**），等 Knevo 回贴。台账正文 `docs/learning/knevo-distill/ab-ledger.md`
   **在 main 和本分支上都有**（前一版交接写「只在 docs 分支」是错的）。
   仍要定的：AB-001/002 两个旧样本的 verdict 怎么处置（逾期两月），以及这张台账
   **从未在 `ledger-map.md` 登记过**——补样本也得补登记。
   AB-002 的 Knevo 侧已判 `unverifiable / protocol violation`（用了预测日信息），
   **不得再拿 07-10 走势给它打 hit**。
2. **两笔本地 merge 的授权存疑**。`f017580a` / `45be2a0b` 于 11:02 合入。spec W6 与
   本分支 12 分钟前的交接都写着「合并须用户确认」；现交接自述「用户授权后合入」，
   但仓里无任何授权记录，质检方对此存疑。合的是特性分支不是 main、未推送，
   未触 main 红线。**请用户认账或回退。**
3. **W2b 未回写 spec**。spec 的 W2 做法一节字面只圈了 `user_memory`，没圈 prime
   出口——是评审漏圈范围，不是执行漏做。合 docs 分支时补一行 W2b。

## 坑 / 后人须知

- **W3 阈值故意留空，且已量过、结论是继续留空**。`RELIABILITY_DOWNWEIGHT_THRESHOLD
  = None` 时降权与警告行逐字节不生效。Q-001 测量记录与复现命令在
  `evolution/backtest-queue.md`「测量记录 · 2026-09-11」：只 1 个 category 桶达 min_n，
  召回池仅 1 条且其 category 无对应桶——**候选值 0.3/0.4/0.5 行为完全相同，填数
  不改变任何召回结果**。重量的触发条件：≥2 个桶各达 min_n 且召回池能解析到这些桶。
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
