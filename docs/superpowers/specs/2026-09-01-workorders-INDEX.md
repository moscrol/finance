# 2026-09-01 工单索引（分发用）

`docs/superpowers/specs/2026-08-28-backlog-workorders-INDEX.md` 当时不在 `gitea/main`。本文件只登记 09-01 起从本基座分发的单。

| # | 工单 | 优先级 | 主仓 | 一句话 |
|---|------|--------|------|--------|
| 20 | `2026-09-01-episode-budget-grant-workorder.md` | **P0** | 金融 | P0/P0.1 已提交。finalize 离线量完：生产 P95=26.9s，20s 地板证伪。P1 仍挂起。 |
| 21 | `2026-09-04-methodology-backtest-p0-workorder.md` | **P0** | 金融 | ✅ P0 已合（PR #573）：旁路库 12 标签 671,440 行 + 前瞻结果表 + 规则 JSON→参数化 SQL 编译器 + Wilson/基准率/前后半段/BH 四态 + CLI + 自测 + 32 测试；三条种子规则真库均 `not_distinguishable`。✅ P1 第一刀已合（PR #576）：`DEFAULT_CALIBRATION_MIN_N` 2→10、经验卡带 `rule_id` 晋升须收据 `supported`。✅ P1 第二刀已合（PR #581）：`propose` 纠偏→候选规则登记入口、日期配对基准率对照列（种子规则 1 的 +10 点提升全是择时）。**剩余 P1**：个股标签、`lifecycle_stage` 人工对照集、`report --refuted` 证伪库汇总。设计稿 `2026-09-04-methodology-backtest-structured-history-design.md`（§6 分期、§10 学习闭环路线图）。交接 `feat-methodology-backtest-p0/p1-gate/p1-propose.md`。 |
| 22 | `2026-09-04-rag-worker-resident-memory-workorder.md` | **P0** | 金融（B 步在 KB 仓） | 生产 RAG worker 在请求间被整个换出（RSS 3.7 MB，机器 swap 14.4/15.4 GB），每次查询先付 20–60s 换入，30s 帽必超时。先量干净 p95，再 keepalive / mmap；预算闸在此之前一律不动。#21 号被 `perf/wiki-hybrid-25s` 与 `docs/finance-agent-bp`（PR #573）两棵未合分支各占一次，故跳到 22。 |
| 23 | `2026-09-04-judge-token-usage-workorder.md` | P1（小单，半天到一天） | 金融 | ⏳ 待派。判官侧 token 用量记进 `LLMCallLedger`（API 读 usage / grok CLI 先探明有无 usage、无则估算并带 `estimated` 标记）+ `metrics.judge_usage` + 读者 `intelligence/eval/research_cost.py` 出「写手 / 判官 / 合计」元/次报表（价目表 JSON 手工核对）。动机：BP 承诺 6 个月内公开单次研究全口径成本，现只量到写手侧（中位 0.34 元）。分支 `feat/judge-token-usage`。**原在 `docs/finance-agent-bp` 分支登记为 #22，与 main 上的 #22（RAG worker）撞号，2026-09-04 合 main 时改为 #23**；工单正文的代码锚点（`llm_refine.py` 440/452/505/683/742/762、verifier 1071/1286/1427、adapter 477/1430–1488）已对 `gitea/main@5c7fe2eb` 复核无漂移。 |
