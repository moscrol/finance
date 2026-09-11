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
- **坑点文档 `docs/data-sources/runtime-and-pitfalls.md` 从未提交**（`git log --all` 无记录），
  而 AGENTS.md 把它当规范源引用；R3 内容写进去了但不传播。它第 32 行的飞书 sheet token
  同时在**已跟踪**的 `skills/sector-data/references/execution-flow.md` 里——既有明文凭证暴露。

清单侧修订在 `feat/knevo-delta-readside` 的 `9037d180`（absorption-plan-2026-09-11.md）。
