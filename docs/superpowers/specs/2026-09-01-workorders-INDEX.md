# 2026-09-01 工单索引（分发用）

`docs/superpowers/specs/2026-08-28-backlog-workorders-INDEX.md` 当时不在 `gitea/main`。本文件只登记 09-01 起从本基座分发的单。

| # | 工单 | 优先级 | 主仓 | 一句话 |
|---|------|--------|------|--------|
| 20 | `2026-09-01-episode-budget-grant-workorder.md` | **P0** | 金融 | P0/P0.1 已提交。finalize 离线量完：生产 P95=26.9s，20s 地板证伪。P1 仍挂起。 |
| 21 | `2026-09-04-methodology-backtest-p0-workorder.md` | **P0** | 金融 | ⏳ 待派。结构化历史标签层（旁路库）+ 声明式规则编译器 + Wilson/基准率四态结论；治 `DEFAULT_CALIBRATION_MIN_N=2` 的「一次错误否定一套方法」。设计稿 `2026-09-04-methodology-backtest-structured-history-design.md`（P1/P2 占位见其 §6；**09-04 晚补入三条 P1 产品约束**：规则 `scope∈{shared,private}` / 证伪库当资产 / 共享层合规硬门，P0 只占位字段）。分支 `feat/methodology-backtest-p0`。 |
| 22 | `2026-09-04-judge-token-usage-workorder.md` | P1（小单，半天到一天） | 金融 | ⏳ 待派。判官侧 token 用量记进 `LLMCallLedger`（API 读 usage / grok CLI 先探明有无 usage、无则估算并带 `estimated` 标记）+ `metrics.judge_usage` + 读者 `intelligence/eval/research_cost.py` 出「写手 / 判官 / 合计」元/次报表（价目表 JSON 手工核对）。动机：BP 承诺 6 个月内公开单次研究全口径成本，现只量到写手侧（中位 0.34 元）。分支 `feat/judge-token-usage`。 |
