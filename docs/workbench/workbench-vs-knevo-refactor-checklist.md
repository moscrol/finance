# Workbench 输出质量改造清单（对标 Knevo）

> 背景：Workbench 与 Knevo 输出差距的根因不是 skill 数量，而是「未命中专项 skill 后还剩什么」。
> 三轮独立诊断（Devin 读仓 + 两个外部 LLM 读代码）合并后的可执行清单。
> 结论一句话：Knevo 的优势是"基础层永远不掉线 + 统一答案编排出口"；Workbench 缺的是通用兜底链路、统一 Presenter 和长期记忆接入，不是更多 SKILL.md。
>
> 执行约定：每个任务独立分支/独立 commit，按 P0 → P1 → P2 顺序；每项完成后在本文件勾选并注明 commit/PR。

## P0a — 统一运行版本（受控对比前提）

- [x] 盘点 Mac 上同时运行的多个 Workbench 服务（8791/8792/8795/8797/8798，来自不同 worktree/分支），确认各自的分支、模型配置（如 glm-5.2）、数据目录。— `c10baaf` / PR #217；2026-07-13 已核对 PID、worktree、branch/commit、模型与用户数据目录。
- [x] 保留唯一 canonical 端口 + main 分支运行时，其余停掉或明确标注用途。— `1d0355e` / PR #217；2026-07-13 已停止 8791/8795/8797/8798，8792 由 LaunchAgent 从 macOS Keychain 注入 GLM 密钥，运行 `/Users/a77/finance-workspace-runtime` → `main@86b1c7083ca6`，用户数据迁至仓库外持久目录。
- [x] 健康检查收紧：`market_snapshot=false` 等关键数据缺失时不应整体显示 ready，至少在回答里显式披露数据缺口。— `c10baaf` / PR #217；readiness 返回 503，并列出 `missing_critical`。

## P0b — 打开 UI 链路的记忆/纠偏注入（性价比最高）

- [x] `intelligence/services/conversation_orchestrator.py` L648-649：UI 对话链路当前 `include_memory_block=False, include_recall_block=False`，导致纠偏（corrections）、experience cards、长期记忆完全不进合成链。改为默认开启。— `6885108` / PR #218。
- [x] 明确注入语义：**记忆是 prior，不是当前事实**——记忆影响篇幅、语气、增量起点、反方重点；价格/产能/订单等易变项仍以当前检索为终审。— `6885108` / PR #218；M/V prompt 明确增量更新和易变项终审边界。
- [x] 检查市场复盘路径二次清空 experience guidance 的逻辑（ask.py 相关），确认是否有意为之；若无必要则移除。— `6885108` / PR #218；专用 market-review composer 接入 memory/recall/experience，通用路径移除无效二次清空。
- [x] 回归验证：同一问题在"有记忆/无记忆"下输出对比，确认已知上下文时能降级为增量更新而非重跑全模板。— `6885108` / PR #218；相关 92 项测试通过。

## P0c — 常驻 Base Finance Mode + 统一 Presenter 出口

- [ ] 新建常驻基座规则（对标 Knevo `finance-mode`，无论是否命中 skill 都生效）：
  - 检索硬触发：有具体标的必查行情+记忆；问最近事件必查新闻；问产业链必查图谱/关系数据；问财务估值必查财务数据；"快答"只是写短，不跳过检索底线。
  - 输出纪律：先内部写核心矛盾句；结论段固定要素 = 直接定性 / 最强证据 / 主要风险 / 条件边界（翻转条件）/ 下一步验证或替代路径。
  - 缺数三档：区间推理（标"推断"+假设前提）→ 替代锚点 → 显式 gap（"缺 X → 仍可判 Y → 验证窗口 Z"），禁止编造确定性。
  - 反顺从：用户观点先当待检验假设，允许"你的直觉有道理，但我会改成 X"。
- [ ] 统一唯一出口：所有路径（含 LLM 不可用/解析失败/门禁拒绝的 fallback）都走 `Evidence → Claim → AnswerSpec → Presenter`；内部表名、检索状态、证据计数、warning 只进 Inspector 面板，不进主正文（参考 ask.py L3569-3607 现有确定性列表路径）。
- [ ] 正则 humanizer（conversation_orchestrator.py L287 附近）降级为安全兜底，不再承担主要"人话转换"；叙事组织由 composer 负责（复用 `llm_refine` 中已有的 narrative composer 约束，见 agent-memory `finance-narrative-answer-composer.md`：rubric 防漏项、composer 防模板化）。
- [ ] 精简 `llm_refine.py` L332 附近的合成 prompt：十几个维度从"强制逐项覆盖"改为"内部自检清单 + 围绕核心矛盾选段"（对标 Knevo 的 L1 固定段 + L2 弹性段型库 + 结论元素配方）。

## P1 — Router 与检索闭环

- [ ] `intelligence/workbench_skills/router.py` L115-129：去掉"LLM 只能在触发词命中的 allowlist 里选择"的硬门槛。规则命中作为加分/优先候选，LLM 可从全量 registry 语义路由；miss 时不再直接 fallback_to_ask，而是进入 P0c 的基座链路（orchestrator → 检索 → composer）。
- [ ] `intelligence/services/answer_orchestrator.py` L152-194 分类器修复脆弱规则：
  - "输出"→回答质检(0.86)、"怎么看"→个股深挖、≤12 字短问题默认题材分析(0.52) 等误路由案例，改为关键词+LLM 混合分类或提高置信度阈值，低置信走通用兜底而非硬套骨架。
- [ ] 检索改闭环（对标 Knevo 窄/宽/反三口径）：
  - 窄口径（实体+代码多形态）+ 宽口径（上下游/同业/宏观，从窄口径命中结果里抽词）+ 反方向（为每个核心假设构造反事实检索词）。
  - 空结果改写重试（上限 3 次即停、报 gap）；召回结果三桶分层（结论桶/线索桶/丢弃桶），弱相关不得因排名靠前进主结论；反方线索即使不充分也保留。
- [ ] Skill 成为答案 owner：命中专项 skill 时由 skill 决定检索计划与输出契约，而非仅作 `supplemental_evidence`（conversation_orchestrator.py L591 附近）塞回 generic Ask。

## P2 — 扩充专项 Skill（最后做）

- [ ] 在 P0/P1 完成、通用出口不再是模板之后，把 CLI 侧 ~31 个 SKILL.md 中的核心能力逐步注册进 Workbench runtime（当前 registry.py 只有 daily-review、daily-agent 两个）。
- [ ] 优先顺序：个股深挖 → 题材研究 → 消息/公告冲击 → 财报分析。
- [ ] 每个新 skill 按 P1 的"答案 owner"契约接入：定义自己的检索计划 + AnswerSpec 骨架，不走补证据包模式。

## 验收标准

- [ ] 未命中任何专项 skill 的自由提问（如"XX 最近怎么样""这只股怎么看"），输出仍包含：直接定性、证据+来源、反方/风险、条件边界、下一步验证——且读起来是裁决后的答案，不是检索运行记录。
- [ ] 已聊过的标的再次提问时，回答是增量更新（引用既有记忆/纠偏），不重跑全模板。
- [ ] 数据缺失时显式披露 gap，不伪造确定性。
- [ ] 工程术语/表名/证据计数不出现在主正文。

## 参考材料

- `agent-memory/10_knowledge/knevo-reverse-engineering.md`（Knevo 架构逆向：finance-mode 硬规则、三桶去噪、结论五元素、缺数三档；注意部分为 Knevo 自述，非源码证明）
- `agent-memory/10_knowledge/finance-answer-orchestrator.md`（QuestionPlan 设计，直接复用）
- `agent-memory/10_knowledge/finance-narrative-answer-composer.md`（rubric 防漏项 / composer 防模板化）
- `docs/learning/knevo-distill/`（检索硬触发、路由表等蒸馏笔记）
