# 09 连续研究 · 决策快照（2026-09-09）

分支 `feat/continuous-research-09`，树 `/Users/a77/fwp-wt-continuous-research-09`，基线 `gitea/main@5eb24515`。任务书 `docs/superpowers/plans/2026-09-09-capability-upgrade/09-continuous-research-goal-brief.md`（只在 `codex/docs-capability-upgrade-plan` 分支）；进度与真实读数 `…/progress/09.md`，范围外 `…/blocked/09.md`。本文不限长，写全背景与被否方案。

## 背景（不读会误判后面每个决定）

任务书写「优先给已有 workbench-research-journey 负责人接续」。实测该分支是纯前端「四阶段进度轨道 + 研究收据」，落后 main 863 提交、未合、无交接、树里有他人未提交改动——它**不是**跨日研究项目，只能当 UI 触碰面的白名单来源。真正能接的地基是另外三块：run 链（`session_id=conversation_id`、`parent_run_id=last_run_id`）、消息持久化的 `turn_intent / followups / citations`、判断轨台账（`checkpoints.jsonl` / `verdicts.jsonl`，夜跑回检已在）。缺的是三件：跨轮/跨会话的研究状态没人投影；追问点击只发 `full_prompt` 文本、坐标全丢；回检块 V 只对「持仓/目标价/该不该买」问句开门（`stance_pack` 门控），纯题材研究题看不到旧裁决。

07（方法闭环）前向起点 09-10，第一条真实 recheck 最早 09-17；08 未派发；历史发现 S4 在扩 `run_store.py`（+220 行）未合。09 只能消费判断轨，07/08/S4 留接口。

## 按发现顺序做了什么

1. 任务 0 盘点（探索 agent + 自核）→ 写 `progress/09.md` §0，冻结 P1/P2/P3 三题与判卷点。
2. 基线：`test_followups` + 会话集成 30/31（1 条时序抖动，单跑过）。
3. `followups.py`：卡片加 `kind/kind_label/inherits`，`followup_kind(angle,type)` 由既有选角确定性推出；`order_by_prior` / `prior_kind_rank`。
4. `conversation_store.py`：`Message.continuation`（只在 user 消息上）。
5. 新 `services/research_project.py`：`load_project`（会话 → 轮次 / 当前判断 / 未解问题 / 已读资料 / 产物 / 触发点 / 下一问 / prior_note）、`prior_for_turn`（渲染 ≤600 字先验块 + prior_status）、`find_related_conversation`（跨会话按 `turn_intent.primary_subject` 找同对象）。
6. `app.py`：`ContinuationRequest` + 校验（run 须属本用户本会话，否则 422）、`GET /api/conversations/{id}/research-project`、`research_project_prior` trace 名登记进公开阶段表。
7. `conversation_orchestrator.py`：研究车道开工前 `prior_for_turn` → 并进 `conversation_context`；`_complete_continuous_turn` 读 continuation 设 `parent_followup_prompt / same_bind / standing_date`，按 `prior_status` 重排卡片。
8. 前端：`types/api/App/MessageThread/MessageBubble/RunView/ResearchInspector` 窄改 + 新 `ResearchProjectPanel`（检查器「项目」页）+ `followups.ts`（`continuationFor`）。
9. 真实门验收（sidecar 8847，真模型）三轮：机制全部 [实测]；答案全是 429 降级模板（9 个并发 sidecar 打满网关）。
10. 由真实读数改设计：降级轮的首句不再当「上轮结论」（`ResearchRound.concluded`）。

## 决策与被否方案

| 决策 | 选了什么 | 否了什么 | 为什么 |
|---|---|---|---|
| 研究项目的存在形式 | 对现有对象的**只读投影**（`research_project.py`，零写入） | 新建 `ResearchProject` 台账 / 表；把整段聊天摘要另存一份 | 任务书红线「不双写台账、不另造案例库」；写入者不变，投影随时可重算；聊天正文留在消息里，视图只取标题与计数 |
| 先验进模型的通道 | 并进既有 `conversation_context`（它已是 `prompt_assembled` 的 durable 字段） | 新开 `research_prior` 上下文字段；改 `stance_pack` 门控让 V 块对研究题也开 | 不新增模型可见通道即不动 INV-R1 派生规则；`stance_pack` 是「持仓 × 现价」接合核，把题材先验塞进去会让它的价格纪律（袋外价格删除）误伤研究题 |
| 卡片种类 | 由既有 `angle/type` 确定性映射出三分法 `kind` | 让 LLM 给卡片分类；再建第二套选角 | 选角已有 A/B/C/D 且确定性；LLM 分类会让「三张同义改写」这类失败无法用测试钉死 |
| 点击继承什么 | 只传坐标 `continuation{run_id, kind, source, label, full_prompt, inherits}` | 把上轮答案正文随请求回传；改 TaskFrame 装配 | 正文服务端本来就有；TaskFrame 归 05 |
| 换题判定 | 当前对象与项目对象**都识别出且不同**才判换题（先验块为空）；卡片延续时不判 | 只要问句变了就重置；不判换题一律注入 | 前者会把「追问」误判成换题；后者会把农业题喂上光模块先验 |
| 裁决改先验 | 只改卡片**先后**（miss/partial → 检验条件先；到期待判/暂无法判定 → 补缺口先）+ 一句 prior_note | 改卡片文案或张数；按胜率给判断加权 | 排序可测且可解释；胜率进入会重演「一次反馈静默改共享输出」的禁忌（09-06 spec §5.2） |
| 降级轮 | `concluded=False`，块里明说「上轮未形成可用结论」，当前判断回退更早一轮 | 照抄首句 | 真实读数：429 降级模板被当成了「上轮结论」喂给下一轮，是把系统失败伪装成研究判断 |
| 跨会话延续 | 扫最近 40 个活跃会话的最后一条助手消息 `turn_intent.primary_subject`，精确匹配 | 全文检索历史答案；按标题模糊匹配 | 只比结构化字段，不读正文猜对象；40 是成本上限，真实用户 496 会话下够用，超出再加索引 |
| `run_store.py` | 不改 | 在 Run 上加 `continuation` 字段 | 历史发现分支正扩该文件 +220 行，撞车代价高；用户消息承载同样可查 |
| 前端布局 | 检查器新增「项目」页 + 卡片种类小标签（`aria-hidden`，可访问名不变） | 在消息流顶部放项目卡；把 journey 分支合进来当底座 | 不动主流阅读顺序；journey 落后 863 提交，合入不是本单的事 |
| 派生静态资产 | `pnpm build` 只作门禁，产物还原不提交 | 随提交带上 `intelligence/api/static/*` | 多分支各自 build 必冲突；部署时重建 |

## 验证与收据

- Python：新增/改动 46 条绿；触及面 240 绿（`test_workbench_api` / 会话集成 / `test_conversation_orchestrator` / `test_conversation_store`）；全仓 `ruff check .` 与全量 pytest 读数见 `progress/09.md` §3。
- 前端：lint / typecheck / vitest 76 / build 绿。
- 真实门：三轮 run 与 durable 事件路径见 `progress/09.md` §3.1；**结论不成立的部分**：研究差量、点击是否推进不同未解问题——三轮 24 次模型调用全 429，不能读答案质量。

## 后续要做 / 不要做

- 要做：网关空闲时按 §3.1 命令重跑 P1，再跑 P2 / P3；次日同会话续研一轮记差量；07 合入后接 `method_recheck` 触发点；S4 合入后把案例原件列进「计算产物」。
- 不要做：不要为了让先验块「更像结论」去解析 Markdown 正文猜核心判断（journey 设计稿 §3.2 同一条红线）；不要把 `continuation` 改成服务端自动猜（点击才有坐标，没点就没有，这是刻意的）；不要在 429 期间反复重跑刷样本。
