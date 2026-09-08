# feat/river-recorded-at-ledger

## 这个分支做什么

把时间长河的**可严格重放长度从 1 天拉到 16 天**，不采一条新数据、不动同步管线、不加列、不回填。

做法：板块系两张 VIEW（`fact_sector_daily` / `fact_sector_stock_daily`）的记录时刻，从只看
`updated_at` 改成 `LEAST(updated_at, ops_sector_universe_snapshot_daily.captured_at)`。
`updated_at` 是刷新时间、会被重发布推到今天；`captured_at` 是那一版板块宇宙的真实抓取时刻、不动。

收据 `docs/verification/2026-09-06-river-recorded-at-ledger.md`。

## 当前状态

**未合、未推、未切 8792。** 分支栈：`gitea/main` ← `feat/river-slice-v0` ← `feat/observation-script`
← 本分支。**合并必须按这个顺序**，跳着合会因为缺上游文件而炸。

三棵都在主工作树 `/Users/a77/finance-workspace-private` 上，主树还带着 BP 那批不属于这几条线的
未提交改动（`docs/bp/*`、`UBIQUITOUS_LANGUAGE.md`、`scripts/build_bp_public.py`）——提交时逐个
`git add`，不要 `git add -A`。

## 三条别踩

1. **不要整轨换成 `captured_at`**。资金轨会从 47 天 strict 掉到 20 天：台账 2026-07-27 才开始，
   之前的行都是 `snapshot_id='legacy'`，而它们的 `updated_at` 里有一批是诚实的。
   两个来源都是「那时已存在」的合法证据，**取较早**才是升级。方向已被
   `test_earlier_updated_at_wins_over_later_capture` 钉死；把 `LEAST` 改成 `GREATEST` 会红 4 条。
2. **审计脚本必须从 river 导入同一份 SQL**。`scripts/river_pit_audit.py` 现在 `from
   intelligence.services.river import sector_recorded_at_sql, ...`。各写一套的话，审计会替河说谎
   ——报出来的 strict 天数不是河真能给出的那些天。`test_audit_uses_the_same_rule` 钉住这条。
3. **聚合用 `MAX(逐行取较早)`，不是 `取较早(MAX)`**。整份聚合要等最后一条成分股落地才算可知；
   反过来会把某一行的早时刻安到整份聚合上，等于宣称聚合比它的成分先存在。

## 一条方法论（值得带走）

「这个值丢了」之前先问「**谁唯一知道它**」。本例里 `updated_at` 被重发布抹平，看上去记录时刻不可恢复，
于是第一反应是「加一列 `first_seen_at`，从今天开始攒」——那要等半年才有样本，而且**不追溯**。
实际上上游的快照台账一直在诚实地记着 `captured_at`，只是读取面没去读它。
**修法归上游，读取侧不要靠补猜。**

## 下一步

- **384 天拿不回来**：`fact_sector_daily` 里 384 天是 legacy，记录时刻确实丢了，不猜。
- **要再长只有两条路**：等台账继续积累；或给其余表（`fact_stock_daily` 37 天、
  `fact_theme_limit_stock_daily` 45 天）也各自找「上游真时刻」——先查有没有，别先加列。
- **给未来的行补只写不改的 `first_seen_at`** 仍然值得做，但它是另一件事：本刀接的是已经存在的证据，
  那一刀保证的是以后每天都诚实。
- **两个截止线要分清**：回放用「T 日收盘」，产品带读实际用「T+1 开盘前」。夜跑滑过午夜的四天
  （08-04 / 08-13 / 08-14 / 08-31）就掉在这个缝里。要给回放放宽必须显式改口径并单独出读数，不能顺手混用。
