# Agent 能力单调性清单验收 · 2026-07-20

> 目标：证明工具、证据和 verifier（事实/语义校验器）加入后，长尾问题的可用能力不低于裸模型；同时保留真值、权限和证据缺口硬门。
>
> 验收代码：`fix/agent-architecture-p13@9519fc78`；代码改动在验收前已 clean，本报告文件随后作为验收产物新增。canonical `8792` 尚未切换，下面的 E2E 均在隔离候选 runtime `8793` 完成。

## 总结果

8 项清单全部有实现、测试和运行证据；X3/X4 两个最小对照已在当前 tip 重跑。全量回归为 **1785 passed, 2 skipped, 3 subtests passed**。

这里的“完成”不是“答案返回了文字”：

- 事实层仍由 claim → EvidenceAtom（证据原子）和过期/无效证据门禁负责；
- 研究层允许 agent 自主选白名单工具，但 ResearchState（本轮研究状态）持续保存假设、支持/反驳证据和 gap（缺口）；
- 展示层保留模型措辞，只有事实/语义 verifier 失败的句子被删除或定向修复；无充分证据时进入 `evidence_gap_fallback`，不伪装成已核验结论。

## 逐项证据矩阵

| 清单 | 当前实现（文件/函数） | 自动化证据 | 结论 |
|---|---|---|---|
| **P13-a** 全题型 Grounded Presenter；旧 marker 链只作 fallback | `intelligence/services/ask_synthesis.py:858` `synthesize_prepared_answer()` 先调用 `promote_grounded_answer()`；`:1176` 负责 Grounded Composer（决策简报 → 合成 → 门禁 → 定向修复）。旧链仅在新链不可用时继续，generic 失败走 `render_decision_brief_fallback()`。 | `test_daily_agent_grounded.py:322,349,477` 断言保留 LLM 措辞、正常路径先于 legacy、拒句删除不回填模板；X3 当前 run `run_20260720_232827_324781`：`validated_synthesis`、GLM 使用、37.92s、0 degrade。 | **完成** |
| **P13-b** quality context/plan 按题型×深度裁剪 | `answer_quality.py:37` `AnswerQualityContext.compact_for()`；`answer_orchestrator.py:148` `QuestionPlan.to_prompt_block(compact=True)`；`ask.py:2254,2608` 使用 compact 投影。methodology/general 不继承个股骨架，deep 题才扩大视角。 | `test_answer_quality.py:64,76` 约束 methodology `<1800` 字、deep stock `<3600` 字；`test_answer_orchestrator.py:770` 保留计划但不要求模板输出。 | **完成** |
| **P13-c** 工程词按题型豁免，标题白名单改建议式 | `answer_model.py:1021+` 按 `presentation_profile` 放行 methodology/review/general 的技术术语；`:1123+`/`:1235` 标题事实走硬门，普通自定义标题不再整篇退稿；`:3267` `humanize()` 负责展示清洗。 | `test_answer_model.py:59,64`；`test_p0_hardening.py:129,142,198` 分别覆盖技术术语、事实型标题硬拦和自然标题保留；`test_agent_eval.py:124` 断言方法论中的 RAG/BM25/DuckDB 不计作控制面泄漏。 | **完成** |
| **P13-d** methodology/answer review 不套 BaseFinance 五要素；降级展示人话化 | `answer_orchestrator.py:175` compact plan 对 methodology/review/general 豁免金融检索骨架；`answer_model.py:3267` 及各 renderer 的 `humanize()` 清洗内部码/工程词；通用 profile 不再复用 theme/company schema。 | `test_answer_model.py:50,59,146,542,563`；X3 当前答案直接解释控制流、抽象税、状态契约和替代方案，没有“直接定性/最强证据/风险/下一步”金融模板。 | **完成** |
| **T1** L3 默认/缺口驱动，不能用弱证据补硬事实 | `evidence_providers.py:162` `should_request_l3_lookup()`；`l3_evidence.py:480` 对 deep/valuation/financial analysis 判断；`ask.py` owner prefetch 在客户事实题先跑官方 L3，失败/空结果立即 gap stop。 | `test_l3_evidence.py:28,47,80`；`test_generic_research_owner.py:87` 断言客户确认缺 L3 后不继续 KB/Web 弱替代；当前 tip customer E2E `run_20260720_233548_100202` 0.546s，trace 只有 `agent:l3_lookup` 一次且为空，最终 `evidence_gap_fallback`。 | **完成** |
| **P9-a** 评测增加模板相似度 | `intelligence/eval/presentation_diversity.py:73` `template_similarity()`；`eval/runner.py` 接入 advisory（建议性）多样性报告，不把多样性误作事实门。 | `test_presentation_diversity.py:7,13`：相同五标题不同数字会被标记，自然因果/方法论结构不被误判；全量回归通过。 | **完成** |
| **P4/P6** 进窗总预算 + 硬度/相关性排序 | `evidence_window.py:128` `select_agent_evidence()` 按 query relevance、source hardness、freshness、independence 排序并执行全局 `max_chars`；`:180` `select_text_window()`；`ask_blocks.py:29` 对 LLM 证据窗硬限 9000 字，Grounded registry 在 `ask_synthesis.py` 限 12000 字，完整 trace 留在审计侧。 | `test_answer_model.py:525` 断言窗口硬上限和硬证据置顶；`test_answer_model.py:542` 断言展示隐藏内部字段。 | **完成** |
| **验证** X3/X4 最小对照 | X3 methodology 走模型原生 lane，不进金融 RAG；X4 relation guard 无图边时 fail-closed。 | 当前 tip X3：`run_20260720_232827_324781`，37.92s、`validated_synthesis`、0 degrade、GLM used=true。当前 tip X4：`run_20260720_232905_320841`，0.552s、`evidence_gap_fallback`、LLM used=false；`trace.jsonl` 的 `relation_graph_guard` 为 `empty`，答案明确“没有可核验上游关系边”，没有把共现拼成上下游。 | **完成** |

## 关键长尾回归

| 问题 | 运行证据 | 观察 |
|---|---|---|
| “这一周行情下跌的主要原因你认为是什么” | `run_20260720_231930_351135`，74.84s，GLM used，0 degrade，`validated_synthesis` | trace 的 query ledger 记录真实执行 `news_search`、`web_search` 共 5 次（含 provider 投影）；网页结果因没有与本周对齐的事件日期被排除为外部原因，回答保留“风险偏好收缩/卖压释放”机制判断并明确外部触发缺口。 |
| 科创50 支撑/压力位 | 当前 tip `run_20260720_233547_476972`，0.559s，LLM unused，`verified_fallback` | Controller 识别 `market_technical`/科创50；trace 只有 `tencent_kline`，输出收盘、支撑区、压力位、计算依据和失效条件。 |
| 客户是否已确认合作 | 当前 tip `run_20260720_233548_100202`，0.546s，LLM unused，`evidence_gap_fallback` | 官方 L3 缺口即停，query ledger 仅 1 次真实查询，无弱 KB/Web 替代，单一 gap 短答。 |
| 液冷 vs PCB 谁上游 | `run_20260720_232905_320841` | 图谱无边显式失败关闭，不发生语义拼接。 |

## 回归与边界

```text
env -u FORESIGHT_USERS_DIR -u FORESIGHT_USER \
    -u SUBCONSCIOUS_VAULT -u AGENT_MEMORY_VAULT \
    PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q intelligence/tests
→ 1785 passed, 2 skipped, 3 subtests passed in 20.15s
```

已知边界：本分支只完成 P13/P9/T1/P4/P6 清单，不等于已经把代码发布到 canonical `8792`；切换仍须遵守 `docs/workbench/canonical-8792-cutover.md` 的合并、snapshot readiness、蓝绿切换和回滚门禁。外部因果源本轮若没有时点对齐资料，系统会报告 gap，这是可靠性要求，不是失败降级。
