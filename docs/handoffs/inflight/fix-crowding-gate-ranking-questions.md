# fix/crowding-gate-ranking-questions · 2026-09-11

## 状态：可合（等用户确认），全量测试 9066 passed / 0 failed @ 0f9dc397

工作树 `/Users/a77/fwp-wt-crowding-gate`，基于 `gitea/main` (0a58f516)。

## 做了什么

AB-002（2026-07-10）方向排序完全反转（排第 1 的半导体链 T+1 -5.13%，被明确排除的
农业/养殖 +2.40%），台账归因写「漏拥挤度」。**但拥挤度不是缺口**：`market_midterm.py`
的 D6 块 2026-07-09 就进仓（`aaf75e93`），比那份答案冻结（`288ea7b` 07-10 11:00）早一天，
还自带「拥挤度分位 ≥80% 中期赔率应下调」的指示语。真因是**两层接不上**：

1. D6 受 `midterm_intent_for` 词面门控，排序题式一个都不命中 → 拥挤度从未进上下文。
2. **只放宽门控没用**：这类问句不点名题材，`resolve_query_themes` 必然为空，块长度
   仍是 0（实测）。加 `top_board_themes` 兜底（最新交易日成交额头部 6 板块）后 968 字节。

同时 `answer_lint._FORECAST_DIMS` 补两维：`crowding_percentile`、`same_family_risk`。
既有 `double_red_marginal` 只查绝对量词（双红/边际量/放量），所以那份错到反转的答案
原先 **lint 满分 7/7**。补维后该红样本 **7/7 → 7/9**，恰好红在这两维。

## 接手要知道的坑

- `same_family_risk` 关键词**不能收「分散」**：AB-002 原文「第 2 名结构更分散」说的是
  容量结构，收了红样本就假过（已实测）。
- `parse_midterm_intent` **不放宽**：它另有两个调用点（`query_understanding` 的时间尺度
  判定、`ask.py:3471` 时序直查回退），那两处问的是「用户真的问了中期吗」。
- `board_fallback` 默认 False，既有调用方逐字节不变；只有 `ask.py::_build_d6` 在
  `is_direction_ranking_query(query)` 为真时传 True。
- 两条负向测试（`test_plain_queries_stay_closed` / `test_parse_midterm_intent_not_widened`）
  修复前后都绿——它们是防过度放宽的护栏，不是缺陷探测器。真正咬住缺陷的是另两条
  （已用未修复代码证伪：TypeError + gate 返回 None）。

## 遗留（本次刻意不改，避免一个 PR 动两件事）

- **L3 拥挤度窗口 60 行 ≈ 47 日**：`_fetch_theme_trend` 按行 limit，而同日同板块有重复行
  （实测「芯片」60 行覆盖 47 个不同交易日）。改成 distinct trade_date 会改动既有答案里的
  数字，单独一件事做。
- **L4 D6 无 as_of 管道**：`resolve_query_themes` 与本次兜底都取库尾。触发条件只有前瞻性
  排序题，与「今天」一致；要问历史某日的方向排序必须先接 as_of。
  ↑ **这条两句都错，见文末「2026-09-11 复核改口」。**
- **坑点文档 `docs/data-sources/runtime-and-pitfalls.md` 从未提交**（`git log --all` 无记录），
  而 AGENTS.md 把它当规范源引用；R3 内容写进去了但不传播。它第 32 行的飞书 sheet token
  同时在**已跟踪**的 `skills/sector-data/references/execution-flow.md` 里——既有明文凭证暴露。
  ↑ **定性错了，见下。**

清单侧修订在 `feat/knevo-delta-readside` 的 `9037d180`（absorption-plan-2026-09-11.md）。

## 2026-09-11 复核改口（用户两句质疑，两句都对）

分支 `docs/recheck-pit-and-feishu`。上面两条遗留写得不准，实测结果如下。

**（a）「无 as_of 管道 + 只有前瞻题会走到」——两句都不成立。**

- 开关一直在：`resolve_query_themes(..., as_of=None)`（market_midterm.py:211）是 D8/D11
  截断那轮加的；`query_understanding.market_review_requested_date` 与
  `asof_prefetch.standing_iso_from_query` 对「2026-07-10 最值得关注的三个方向」
  都直接返回 `2026-07-10`；D0 已用前者锚日，D9/D12 已在用 `options.date`。
  只有 D6 一个都没接——是「有但没接线」，不是「没有」。
- 历史题真的会走到（实测，库 `db/market_feature_store.duckdb`）：

  ```
  "2026-07-10 最值得关注的三个方向是哪三个"
    is_direction_ranking_query = True
    themes = 芯片/数据中心/新能源车/电子/机器人概念/储能（库尾 top6）
    窗口 = 2026-08-13 ~ 2026-09-10，拥挤度 1.7%
  ```

  问 7 月、答 9 月，且三个问法（前瞻 / 带日期 / 「站在某日」）返回完全相同。
  块头会把 `first_date ~ last_date` 写出来，所以模型看得见，但没有门禁拦，
  也不会被标 `hindsight`（river 的 `knowledge_cutoff > as_of` 拒绝只管 river 读取面，
  ask 的 D 块不经过它）。
- 修法（单独一个 PR，本分支不做）：as_of 穿过 `_fetch_theme_trend` /
  `top_board_themes` / `load_midterm_trend_artifact` / `midterm_trend_block_for_llm`，
  `ask._build_d6` 取 `options.date or market_review_requested_date(options.query)`。
  测试照搬 `test_analog_as_of_truncation` 的两种断言（块内无晚于 as_of 的日期；
  截止日当时不存在的题材解析不到）——只截取数不截名录的改法它能照出来。

**（b）飞书：我标错了目标。**

- 仓内那串 `AHqIw…`（execution-flow.md:44 / CLAUDE.md:373）是 **spreadsheet token = 文档标识符**，
  不是凭证；没有 tenant_access_token 拿它干不了事。本分支只把它换成取值位置指针，
  与已入库的坑点文档保持一致，属卫生，不算安全修复。
- 真正的凭证泄露在 `skills/advancers-chart/scripts/migrate_dates.py` 的历史里：
  `26446460`（2026-07-02）把明文 `APP_ID` / `APP_SECRET` / `APP_TOKEN` 从工作树拿掉，
  历史仍在；实测当前 `~/.claude/shared/feishu_config.json` 与泄露值 **逐字相同**，
  今天换 token 仍 `code=0`，可枚举「复盘数据」 base 下 8 张表（含自选股）。
- 所以「飞书退役」≠ 这事完了：退的是 IM 问答入口（`709d0e6e`）与
  `sync-market-daily`（`cc5d2e4e`）；`scripts/notify_feishu.py` 还在夜跑链里
  （`~/.local/bin/nightly-full-review-s7.sh:75`，2026-09-10 还调过，拿到 token 后卡在
  `im:chat` 权限 400），`feishu_chart.py` 仍是 `daily-full --with-chart` 的一步，
  CLI 还挂着 `sync-limit-advance-feishu`。要么轮换并改这三处，要么删应用并拆掉告警依赖。
