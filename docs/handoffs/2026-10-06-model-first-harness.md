# 2026-10-06 模型优先 harness：盘面题回 Episode，放开卡模型的上限与门

分支 `feat/model-first-harness-1006`，叠在 #52（`fix/harness-budget-unconstraint-1005`）头 `c6961f4c7` 上。

## 背景

- 10-04/05 同题对照：同一个 GLM-5.3-flash、同一套工具与主库，极简 Pi 答得比 8792 好。盲评报告 `~/.finance-runtime/harness-arms-20261004/blind-review-v5/REPORT.md`（可比 5 对 Pi 4 胜 1 平，8792 0 胜；另一半样本被网关断连吃掉，所以形式结论是「不确定」），只读分析 `~/.finance-runtime/pi-vs-8792-claude-review-1005/ANALYSIS.md`。
- 输的题全在「代码替模型做决定」的地方：盘面题走引擎 B 固定流程（模型零工具、合成器截断换模板、逐句删稿、内部数据包进正文），实体候选先追问，休市一句话；模型自己查的 Episode 题正确性已与 Pi 持平，但篇幅只有 Pi 的四到六成。
- #44–#47 修了取错日期并已上线；#52（Pi 接手，CI 绿，未合）放开合成器 token、截断保留整句、Episode 正文 4000、题目锚点日期。
- 用户 10-06 原话：「按照最优推进，总之我要发挥模型的最大能力，什么时间预算啊等等限制模型能力的，都要做优化，另外8792如果只是和pi持平的话，是不是也说明很多harness设计是冗余了。另外episode可以更好发挥的话就走episode，如果固定的workflow限制了model，那就不要了。总之初衷就是要发挥model的能力，让模型回答的更好」。
- 用户 09-13（记忆 `compliance-is-not-a-design-constraint-license-later`）：「目前我们自己使用，就要达到能力的 max，合规的边界后续再去考虑」，受众红线属于渲染 / 导出 / 分享层。

## 按发现顺序做了什么

1. **盘面题路由**（2c17f271a）：`continuous_turn_adapter.DETERMINISTIC_OWNER_TYPES` 去掉 `market_watch` / `dated_market_review`，`forecast_residual_budget.DO_NOT_LENGTHEN_QUESTION_TYPES`（等式钉住的孪生名单）与评测确定性臂 `episode_tools._FAST_PATH_TYPES` 同步。08-30 编排合同 §7 的「❌ 把包并进 A 当第一执行者」作废，合同文末 §11 记了修订。
2. **读 Pi 的控制台驱动**才知道两边真正的差别：Pi 走同一个注册表，但题型被中性化成 `general_finance_qa`，而且看到的是完整观察（≤5 万字），8792 Episode 的模型视图是 900 / 240 / 120 字。用 Pi 134 次工具调用标定：观察叙述 p95 2210、最大 3000；证据明细 p95 223、最大 619（宽行，比如 market_daily）。→ `tool_result_budget` 放到 4000 / 800 / 300，`agent_research` 读同一常量。
3. 分类器把「高标晋级有没有空档」也判成 `dated_market_review`，旧必需输出（总量 / 主线 / 风险）里没有「回答用户问的那件事」→ 首位加 `direct_assessment`。
4. Episode 正文上限 4000→6000，措辞从「控制在 N 字以内，优先保留决定性依据」改成「篇幅由问题决定，上限只为结构化终止完整，不为压篇幅省掉关键数字」；【何时停止】从「够了就停」改成「关键判断尽量交叉核对后再停」（8792 每题 1–7 次查询，Pi 5–21 次且自发双源互证）。宪法指纹已显式更新。
5. Agent 侧 finance_query 行数 25→60：历史 189 次调用里 29% 要的多于 25 行。
6. 实体候选（「X+主题词」形状的未登记名称）不再先追问：不硬锚任何候选（R13-A3 教训照旧），候选写进 `ambiguities`，`assumptions` 写「先检索核实，查无就说明范围，不反问」。升级前挂起的追问仍能按旧路径收口（有测试）。
7. **旁路首轮 10 题（2c17f271a）**：D9「明天开盘哪个方向会先起来」收了 177 条证据仍降成缺口模板，两个 harness 原因——单次模型调用 75 s 上限截断了已在流式出字的一轮；「明天方向」出口门把模型的方向判断连拒两次。D3 用户自己的「10%」「500亿」被标「待核」。→ a7e9939f2：`DEFAULT_GLM_LLM_TIMEOUT` 75→180（按 `provider_latency` 的强制思考 ~62 s + 出字速度标定，仍受 `min(上限, remaining − reserve)` 约束）；方向门改成 `WORKBENCH_AUDIENCE_DIRECTION_GATE` 受众层开关，缺省关；数值条件检测把题面数字算题设。
8. **复测 D9**：模型请求 PLAN 分支，分支沿用父上下文带着「绑在父 episode 上」的入口身份去存状态，校验报 episode mismatch，整棵树 `storage_failed`。入口身份 09-22 起绑定（691d0ad5c），生产最后一次分支运行是 09-21，所以一直潜伏。→ c65e5fa9a：分支 `entry_identity=None`，回归测试先红后绿（工具分支与 PLAN 分支两种）。
9. **复测 D6**：终稿写成 Markdown 而非 JSON，被拒后模型重写成 215 字摘要。→ cc5e794a5：invalid_finish 回灌要求「正文原样放进 draft，不缩写、不删数字」。
10. 全量门禁 cc5e794a5：20507 过、1 红——契约测试钉了「深读段长 == 可见 detail 上限」，实际不变量是 ≤。→ 6567c24d2。

## 决策对比

| 决策 | 选 | 否 | 理由 |
|---|---|---|---|
| 盘面题 | 走 A | 继续修 B（#52 方向）；给 B 加工具 | B 的上限来自「包 + 写手 + 逐句删」结构，修完截断还有删句、删句完还有模板；A 同题已与 Pi 持平 |
| B 盘面包 | 停止路由，代码暂留 | 同 PR 删除 | 旁路证明 A 不比 Pi 差之后再删，回滚只需改一张名单 |
| 观察上限 | 4000 / 800 / 300 | 不设上限；只放大叙述不动明细 | 不设上限有病态大输出撑爆上下文的风险；240 会截宽行，盘面题正好靠宽行 |
| 深读段长 | 保持 240，与可见上限解耦 | 跟着放到 800 | 段长只需 ≤ 可见上限；保持 240 则同一总预算下段粒度和跨页分配不变 |
| 行数上限 | 60 | 100 / 200 | 60 行 × 明细 ≤800 约 2–5 万字一次，单轮上下文可承受；宽表上 100+ 有撑爆风险 |
| 单次调用上限 | 180 s | 300 s；不设 | 覆盖强制思考 + 6000 字终稿；更大会在 600 s 研究预算里挤掉重试 |
| 方向门 | 受众层开关，缺省关 | 直接删；保留 | 删了对外部署回不来；保留违背 09-13 / 10-06 两次决策，且 Pi 同类答案被盲评判可用 |
| （待核）注记 | 只修题面数字误报 | 挪到文末脚注；全去掉 | 脚注会被交付复检重新分句，可能触发金融断言删句与修复债；全去掉丢掉对自拟阈值的披露 |
| 分支入口身份 | 记为未绑定 | 按分支 id 重绑 | 恢复要求 `contract.task_id == episode_id`，分支本来就不能单独恢复；重绑会在 capture 时与 task_id 校验冲突 |
| 盘面必需输出 | 加 `direct_assessment` | 全改成 direct_answer + evidence_boundary | 宽泛复盘仍需要总量 / 主线 / 风险，只缺「回答所问」一格 |

## 验证与收据

- 旁路实例：`~/.finance-runtime/model-first-harness-1006/side-8797/launch.sh`（端口 8797，RAG 向量 worker 关，kb_search 快速失败——这是相对生产与 Pi 的环境差异）。每轮前 `probe_gateway.zsh` 探网关。
- 运行：`live-1`（2c17f271a，10 题）、`live-2`（a7e9939f2，D3 / D9）、`live-3`（c65e5fa9a，10 题）、`live-4`（cc5e794a5，D6）；驱动 `run_live.py`、打分 `score_live.py`，台账 `ledger.jsonl` 带 revision 与 tree_dirty（全部 clean）。
- live-3 / live-4 读数：9 题走 Episode，53–133 s，3–10 次工具；machine-truth 9 题 1.0、D1 0.857（判分器把「环比缩量 10.27%」判成没写 -10.27，内容正确）。D8 仍是休市一句话（2 s）。
- 全量门禁：cc5e794a5 收据 `~/.finance-runtime/test-receipts/gate-Z2omgZWl/pytest.json`（20507 过、1 红，已修）；最终头的门禁读数贴 PR 评论。
- **不成立的结论**：每题 n=1，不读快慢；只有我自己并排读，不是独立盲评；Pi 没有时间上限而 8792 有；旁路关了向量 KB；machine-truth 给模板答案也能打高分，不能当验收。

## 后续要做

- 新 8792 对 Pi 的独立盲评（沿用 v5 协议与冻结真值）。
- #52 与本枝合并、按 `docs/workflows/acceptance-workflow.md` 切 8792。
- （待核）剩余误报：区间写法「2至5」「121→47」、推算计数「1只」「14 条」、模型自拟阈值；先量误报率再改判据。
- D8 休市补最近交易日；external_market / watchlist_digest / disclosure_scan 是否回 A 按同法 A/B；B 盘面包代码清理。

## 不要做

- 不要直接删方向门：对外部署要靠它，开关缺省关就够了。
- 不要把深读段长跟着可见上限一起调：会改段粒度和跨页预算分配，cap02 整组用例的前提都变了。
- 不要拿 machine-truth 分数验收 harness 改动：10-05 的模板答案拿过 6/6 和 PASS。
