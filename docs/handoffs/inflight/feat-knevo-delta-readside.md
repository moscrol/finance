# feat/knevo-delta-readside · 在途交接（2026-09-11）

执行 spec `docs/superpowers/specs/2026-09-10-knevo-arch-delta-worklist.md`（评审修订版）。
**spec 文档不在本分支**，在 `docs/knevo-e009-arch-delta`（7 笔提交、6 个文件、纯文档，
已完整包含 `docs/knevo-m-probes-verification`）。两条都要合，文件不重叠、顺序无依赖。
基点 `gitea/main @ 3ed44703`。

## 提交（新→旧）

- `5f04f85b` 质检整改：W2b prime 出口归属 + D18 接问句日期 + 两处失真注释
- `251a2cf6` W6 判据（日历 as-of + 赔率）
- `45be2a0b` / `f017580a` 合入 event-pricing-slice1 / polymarket-macro-odds-impl
- `ac95d5f0` Q-001 已量 → 结论继续留空
- `cb411e73` W5 封板时间块 [D18]｜`f63a2352` W1/W2/W3 读侧三项

W1–W3、W5、W6 均带红绿变异实测，逐条见各自提交信息与
`docs/verification/2026-09-11-{e007-p3p4-criteria,knevo-qc-followups}.md`。

## 门禁（本轮实测，别抄旧数）

`ruff` 全绿；`pytest -q` **9141 passed / 77 skipped / 1 xfailed，exit 0**。
基线用 `--collect-only` 量：原树 9217、本轮 9219（+2 = 新增两条）。
⚠ 前面几笔提交里的 7988 / 9081 / 9088 都对不上各自 revision 的 collected 数，
是收据错挂。**要数就自己 `--collect-only`，别抄提交信息。**

## 必须知道的一件事：D18 源列已断供

`fact_theme_limit_stock_daily.first_limit_time` 到 2026-09-02 逐日 100% 非空，
**2026-09-03 起连续 5 个交易日全 NULL，行照常进**。只数行数看不见（AGENTS.md
点名的空壳形状）。后果：**W5 交付在生产上目前是惰性的**，最近交易日走第一道守卫
直接返回空串。spec 写的「149,728 行非空」是累计数，落笔那天已断供 5 天。
`leader_succession.py` 的一字板判定此前只卡 `open_times`，现在两个输入同时为空。
上游补回则自动恢复，代码侧不用改。**追上游要外呼比对 payload 字段名，未做。**

## 等用户裁决

1. **W4（AB 双盲台账）未动**。spec 写「二选一，请用户定」，红线是不许维持现状
   （目标 25 / 实际 2 / verdict 逾期两月）。裁决前先知道：台账正文在 docs 分支；
   AB-002 的 Knevo 侧已判 `unverifiable / protocol violation`（用了预测日信息，
   **不得再拿 07-10 走势给它打 hit**）；这张台账**从未在 `ledger-map.md` 登记过**，
   两条路都要动它，区别只在写什么。
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
- **D18 的 `if not rows` 是死代码**（守卫 A 之后不可达，已实测），留作防御，别指望它变红。
- **`truncated` 不落库的洞有意不补**，用 documented gap 测试钉住：**洞被补上时它会变红
  并要求更新 W6 判据。到那天请改判据，别删测试。**
- SPT-A06 仍在 `_PENDING_RULES`（G1b 未修），D18 块**不得**夹带该规则文本。
