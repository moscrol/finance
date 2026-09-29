# 市场数据停更披露 P0 + 21:00 截止时刻（2026-09-29）

两棵树的成果合在一起：
- P0 实现：`feat/market-staleness-disclosure-p0-0929`@e93472757，PR #967。另一会话在 `/Users/a77/fwp-wt-staleness-0929` 完成，交接原文见下方「P0 原交接」。
- 独立复核和截止时刻：`feat/market-staleness-cutoff-0929`（Arena 会话，用户 23:2x「你逐个动手，不要和其他 agent 做的冲突就行」）。为了不和原作者的分支冲突，另开分支叠在 e93472757 上，没有推原分支。

## 复核发现，已修

P0 版本把「今天」无条件算作应该已入库的交易日。于是每个交易日从 00:00 到当晚换库完成，所有「今天市场怎么样」的回答都会带「停更」。这其实是常态，提示会退化成噪音（PR #967 评论 7738）。

修法：新增 `MARKET_DATA_EXPECTED_BY = time(21, 0)`（上海时间）。
- 21:00 之前，基准是上一个计划交易日；21:00 之后，才把当日算进来。
- 为什么是 21:00：sync 18:30 开跑，换库通常 19:00–20:00 完成，finalize 20:40 出报告。
- `test_cutoff_is_after_nightly_sync_start` 读取 `intelligence/dream/com.financeworkspace.daily-full-review-sync.plist` 的开跑时刻，要求截止时刻至少晚 2 小时。夜跑排期往后挪时，这条测试会先红。
- 文案改成「数据未更新：按交易日历应已有 X 的数据，以下为 Y 数据（落后 n 个交易日）」。21:00 前基准不是「今日」，原来的「今日数据未更新」会说错。
- `run_market_watch_pack(today=…)` 注入日期时，语义仍是「当日已结束」，老测试不用改；新增 `now=` 参数用于按时刻测试。

## 验证

- 定向测试：`test_market_staleness_disclosure.py` 8 条（新增 4 条）。所有引用 market_watch_pack 的 11 个测试文件共 113 条，全部通过。
- 变异自检（`scripts/mutation_check.py`）4/4 KILLED，spec 和摘要在 `~/.finance-runtime/reviews/staleness-cutoff-0929/`：
  - 忽略截止时刻；
  - 基准永远含今天；
  - 基准永远不含今天；
  - 截止时刻挪到 19:00。
- 全量门禁：见 PR 评论。

## 已知边界 / 没做

- **2027 年休市表缺失**：日历不支持的年份一律不报（fail-closed），所以 2027-01-01 起这条提示会静默失效。交易所公告通常 12 月发布，发布后补进 `market_feature_store/trading_days.py`。
- 夜跑某晚超过 21:00 才换库（例如 09-28 那种失败后补发候选），21:00 到换库之间会如实披露落后 1 个交易日。这是有意的。
- 合入 main 不等于上线。8792 要下一次切流才会带上这项改动。上线后要做一次真实问答验收：盘中问一次，不应出现停更提示。

## P0 原交接（`docs/handoffs/inflight/feat-market-staleness-disclosure-p0-0929.md`，随本 PR 归档）

- 服务层新增独立的 `market_staleness_disclosure(standing, today)`，用上海交易日历对照库里的真实站立日。
- 周末和 2026 年公告休市日不误报；日历不支持的年份不猜。
- 既有的 `_structured_freshness_floor`、PIT 钳制、`calendar_disclosure` / `should_stop` 都没改。
- 新增 `MarketWatchPack.staleness_disclosure`：渲染只读取结果；正常的 Ask binder 和公开稿合成都会透传。
- 原交接列的复核义务：
  - 五项变异。本次做了截止时刻相关的 4 项；原单里「自然日计数」「基准改成数据自身」等由原测试覆盖，没重跑；
  - 全量门禁；
  - 独立复核：本次已做；
  - 「交易日盘中尚未完成夜跑」的时点政策：已定为 21:00，依据是用户「逐个动手」时采纳的推荐方案 A。
