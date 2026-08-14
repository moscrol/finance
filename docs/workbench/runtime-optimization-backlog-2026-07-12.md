# Workbench 实跑优化 Backlog（2026-07-12）

> **状态更正（2026-08-06 归档时补）**：本文写于 2026-07-12，当时状态是「待实施」。
> 从那天到归档，main 推进了 **1151 个提交**。文中 4 个 P0 各自派生过一条修复分支
> （`fix/workbench-manual-skill-primary` / `-evidence-claim-gate` / `-readiness-contract`
> / `-evidence-registry`），**全部未合并**，代码已被 main 另一条路取代
> （证据-声明校验现由 `episode_semantic_verifier.py` 2894 行 + `task_fulfillment.py`
> + `repair_coordinator.py` 承担；分支那个 122 行正则 gate 是早期原型）。
>
> **本文保留的是 7-12 那次真实实跑的问题现场，不是当前待办。** 条目状态未逐项复核，
> 当 TODO 用之前必须先验 main 现状——否则会重修一遍已经解决的问题。
>
> 原始状态标记：待实施
>
> 证据类型：真实本地启动、自动化 smoke、浏览器核心流程验证
> 本文只登记问题、复现步骤、建议实现与验收标准，不包含功能代码修改。

## 0. 开工前上下文

先读：

- `docs/workbench/knevo-distillation-context-2026-07-12.md`
- `docs/learning/knevo-distill/README.md`
- 与当前 P0 相关的 `docs/learning/knevo-distill/q*.md`

Knevo 只作为机制基准，不是逐项照抄的验收标准。优化时必须同时保留 Workbench 的证据可审计、缺数诚实、时间冻结和双盲回检优势。

## 1. 执行边界

本轮已真实运行 Workbench，不是静态代码推断。

已验证：

- FastAPI 启动和健康接口；
- 前端 lint、typecheck、Vitest、production build；
- 后端关键测试；
- self-use smoke；
- 新建会话、提交问题、Skill 手动选择；
- 结构化报告、Run、产物库；
- 历史会话持久化和刷新恢复。

本轮运行环境存在以下降级：

- 未连接本地 DuckDB；
- fallback snapshot/export 截止 `2026-07-01`；
- 知识库 `.rag_index` 不存在；
- 未配置 LLM key；
- VM 的用户运行目录不含真实长期记忆；
- Level2 资金流特征库缺失；
- 部分题材历史信号缺失。

这些环境缺口不能直接算作代码 bug。P0/P1 条目均来自不依赖上述完整环境、可稳定复现的产品或代码问题。

## 2. 基线结果

| 检查 | 结果 |
|---|---|
| 前端 lint | 通过 |
| 前端 typecheck | 通过 |
| 前端 Vitest | 通过 |
| 前端 build | 通过 |
| 后端关键测试 | 103 个通过 |
| 首页健康检查 | 通过 |
| `/api/skills` | 包含 `daily-review`、`daily-agent` |
| self-use smoke | Run 完成，终态实际为 degraded |
| smoke SSE | 33 个事件，无重放 |
| smoke secret scan | 0 命中 |
| 浏览器核心导航 | 通过 |
| 历史线程重新打开 | 通过 |
| 刷新恢复活动线程 | 失败 |
| 手动 Daily Agent 最终回答 | 失败，Skill 已执行但回答语义漂移 |

本轮关键 Run：

- 市场 smoke：`run_20260712_172232_573263`
- 光刻胶研究：`run_20260712_172619_645943`
- Daily Agent：`run_20260712_172912_433276`

## 3. 推荐实施顺序

先完成 P0，再做 P1。不要在 P0 尚未闭环时先更换模型或调整 prompt。

原因：

- P0 是确定性编排、证据状态和质量门禁问题；
- 更强 LLM 可能掩盖错误，但不会修复 Skill 主产物被通用 Ask 覆盖、readiness 误报或证据 Registry 为空；
- 先修确定性契约，后续才能客观比较不同 LLM 和 RAG 方案。

## 4. P0：必须先修

### P0-1 手动选择 Skill 后，最终回答没有以 Skill 结果为主

#### 复现

1. 新建对话；
2. 研究工具选择方式切到“手动指定研究工具”；
3. 选择 `Daily Agent`；
4. 发送：

   ```text
   请生成最新 Daily Agent 研究雷达，并列出值得继续追踪的信号。
   ```

#### 实际结果

- UI 显示“已指定工具 · Daily Agent”；
- `daily-agent-skill-result.json` 正确生成；
- Skill 原始结果正确包含：
  - 9 个旧逻辑重新活跃；
  - 3 项需要补题材研究；
  - 4 项需要补官方证据；
  - 氢能源、AI 眼镜、风电、光刻胶等候选；
- 最终回答却把完整问题继续交给通用题材检索；
- “研究雷达”被识别为“雷达”概念，回答漂移到四创电子、AIGC 和 AI Agent。

#### 已定位的代码链

- `intelligence/services/conversation_orchestrator.py`
  - Skill 执行成功并写入 `skill_outputs`；
  - 随后仍无条件调用 `answer_query()`；
  - Skill 结果仅以 `supplemental_evidence` 进入通用 Ask；
  - 最终 `answer_text` 完全来自 `render_conversation_answer(result)`。
- `intelligence/services/ask.py`
  - 仍对原始 query 做题材/entity 识别和六段式通用回答生成。

#### 实现要求

- `skill_mode=manual` 且 Skill 成功时，显式选择优先级必须最高；
- Skill projection/modules 成为最终回答的主结构；
- 通用 Ask 只能补充 Skill 没有覆盖的证据，不能覆盖 Skill 的任务语义；
- 不允许再把 Skill 名称或问题中的“研究雷达”当作题材实体；
- 若手动选择多个 Skill，应先组合 Skill 主模块，再决定是否调用通用 Ask。

#### 推荐方案

方案 A，推荐：

```text
manual Skill
  -> execute Skill
  -> render Skill projection as primary answer
  -> optional targeted enrichment
  -> quality gate
```

方案 B，不推荐：

```text
manual Skill
  -> execute Skill
  -> flatten to supplemental_evidence
  -> generic Ask parses original query again
```

方案 A 的优势是任务契约清晰、可单测、不会被关键词误路由；方案 B 正是本次漂移的根因。

#### 测试要求

- 为 `ConversationOrchestrator.run_turn()` 增加手动 Skill 契约测试；
- Daily Agent 回答首屏必须覆盖 Skill 的：
  - `plain_summary`
  - `metrics`
  - 首要候选
  - `next_action`
- 最终回答不得出现“雷达(10)”或四创电子，除非它们真实存在于 Daily Agent Skill 产物；
- `selected_skill_ids`、`invoked_skill_ids`、最终报告模块必须一致；
- 同样覆盖 `daily-review`。

#### 验收标准

- 手动选择 Daily Agent 后，回答首屏出现 `9 / 3 / 4` 指标；
- 候选与 `daily-agent-skill-result.json` 一致；
- 通用 Ask 不再把整句问题识别为主题。

---

### P0-2 “弱证据硬写”已被质检发现，但没有阻断或改写

#### 复现

发送：

```text
光刻胶现在处于什么阶段？请结合盘面、知识库、历史信号和我的纠偏，给出反证与下一步验证点。
```

#### 实际结果

Run warning 已识别：

```text
输出质检：弱证据硬写——无 L3/公告等硬证据却出现确定性措辞：确定
```

但正文仍出现：

- “方向被确认”；
- “结论与交易含义为确定性结构化结果”；
- “事实验证并继续重估”等硬措辞。

#### 已定位的代码链

- `intelligence/services/ask.py`
  - `stance_bits` 直接生成“新高成簇，方向被确认”；
  - `conclusion` 固定加入“结论与交易含义为确定性结构化结果”；
  - `output_review.review_output()` 在正文组装后才产生 warning。
- `intelligence/services/conversation_orchestrator.py`
  - 调用 `AskOptions` 时：

    ```python
    compose_self_review=False
    compose_revise_on_warn=False
    ```

  - 无 LLM 时本来也无法依赖 LLM revision 修复模板硬写。

#### 实现要求

- 质量门禁不能只在右侧 Inspector 告警；
- 无 L3/硬证据时，确定性模板也必须使用条件句；
- 对“确认、确定、兑现、事实验证”等词执行 evidence-level 约束；
- 高风险 warning 命中后：
  - 自动确定性改写；或
  - 把结论状态降为“待验证”；或
  - 无法安全改写时阻止普通 completed 终态。

#### 推荐方案

使用两层门禁：

1. **生成前约束**：根据最高证据层选择措辞模板；
2. **生成后门禁**：扫描硬结论词，并校验对应 statement 是否绑定 L3。

不要只依赖 LLM 自审。LLM 自审可作为第三层，但确定性规则必须兜底。

#### 测试要求

- 无 L3 时正文禁止出现：
  - `方向被确认`
  - `确定性结构化结果`
  - 无条件的 `兑现`
- 有 L4、无 L3 时应输出：
  - “盘面候选”
  - “市场反馈增强”
  - “仍待 L3 验证”
- 为模板模式和 LLM 模式分别增加测试。

#### 验收标准

- 同一光刻胶问题不再触发 `weak_evidence_hard_claim`；
- 若仍触发，Run 不能显示为普通“已完成”。

---

### P0-3 服务 readiness 与研究 readiness 混为一体

#### 复现

调用：

```bash
curl http://127.0.0.1:8788/api/health/ready
```

#### 实际结果

返回：

```json
{
  "status": "ready",
  "checks": {
    "vector_index": false,
    "market_snapshot": false
  }
}
```

#### 已定位的代码链

`intelligence/api/app.py` 的 `health_ready()` 只把以下项视为 critical：

- repo root；
- run store writable；
- knowledge wiki；
- relations。

市场快照和向量索引缺失不影响顶层 `status=ready`。

#### 实现要求

区分两个概念：

- **service readiness**：API 可以接请求、Run 可写；
- **research readiness**：关键研究能力可用。

建议响应结构：

```json
{
  "service_status": "ready",
  "research_status": "degraded",
  "capabilities": {
    "market": "blocked",
    "rag": "blocked",
    "llm": "optional_unavailable",
    "memory": "unknown",
    "artifact_store": "ready"
  }
}
```

LLM 在当前产品设计中允许缺失，因此可标记 optional；市场事实是否允许缺失应按任务类型决定。

#### 测试要求

- `market_snapshot=false` 时 `research_status != ready`；
- `vector_index=false` 时 RAG capability 为 blocked/degraded；
- service HTTP status 是否仍为 200，由部署探针契约决定；
- UI 首页与 API 使用同一 capability 模型。

#### 验收标准

- 运维探针能判断进程存活；
- 用户和 smoke 不会把“进程可用”误解为“研究数据完整”。

---

### P0-4 证据 Registry 为空，导致“无可验证来源”和“证据 0”与报告矛盾

#### 复现

完成任一包含公司证据和引用来源的 Run，然后：

1. 打开回答；
2. 打开研究检查器；
3. 查询 `/api/runs/{run_id}/context`。

#### 实际结果

- 回答正文列出多条公司证据和引用来源；
- 结构化报告含 citations；
- UI 额外显示：

  ```text
  本轮没有可验证来源，以下内容只能作为待验证推测。
  ```

- Inspector 显示“证据 0”；
- Daily Agent Run 的 context evidence 实际为空。

#### 已定位的代码链

- `intelligence/webapp/src/components/MessageBubble.tsx`
  - 只要 context 中没有 `bound_evidence`，就显示“无可验证来源”；
- `intelligence/webapp/src/components/ResearchInspector.tsx`
  - 只统计 `classification === "bound_evidence"`；
- 后端报告和 citations 已有来源，但没有同步进入 context Evidence Registry。

#### 需要先做的产品决策

不能简单把所有 citation 都算作硬证据。应明确：

- `fact_source`：检索到的来源；
- `bound_evidence`：已绑定到具体 statement 的可验证证据；
- `context_only`：背景资料；
- `weak_candidate`：弱关联候选。

如果本轮来源没有完成 statement binding，UI 显示“证据 0”可能技术上正确，但正文就不能同时写强结论。正确修法是统一证据语义，不是只改数字。

#### 实现要求

- 建立唯一 Evidence Registry；
- citation、结构化报告、context、Inspector 统一从 Registry 派生；
- 每个结论 statement 绑定 `evidence_id[]`；
- UI 分别展示：
  - 来源数；
  - 已绑定证据数；
  - 硬证据数；
  - 弱候选数；
- “无可验证来源”只在确实没有可验证 citation 时显示。

#### 测试要求

- 报告 citations 非空时，context 不得无条件为空；
- Inspector 数字与结构化报告一致；
- 无 `bound_evidence` 但有 `fact_source` 时，文案应为：

  ```text
  已检索到来源，但尚未绑定为支持当前结论的硬证据。
  ```

- 增加后端和 React 组件的一致性测试。

#### 验收标准

- 不再同时出现“无可验证来源”和十余条引用来源；
- Inspector 不再误导性显示单一“证据 0”。

## 5. P1：P0 完成后处理

### P1-1 清晰问题仍按通用问答处理

复现：

- “光刻胶现在处于什么阶段？”
- 手动选择 Daily Agent 后发送研究雷达问题。

要求：

```text
显式 Skill 选择
  > 结构化实体/任务规则
  > 意图分类器
  > 通用 fallback
```

建议记录每一级路由的置信度、触发规则和最终仲裁原因。

### P1-2 Run 终态没有表达降级严重度

当前 Run 顶层为 `completed`，但报告多个模块为 `degraded`，且含 8–9 条降级。

建议区分：

- `completed`
- `completed_degraded`
- `blocked`
- `failed`
- `cancelled`

Inspector、消息状态和产物库应使用同一终态。

### P1-3 警告重复且未分组

把 warnings 按以下原因归并：

- 市场数据；
- RAG；
- LLM；
- 用户记忆；
- 输出质量；
- Skill。

默认显示聚合状态和可行动项，原始 warning 放在高级详情。

### P1-4 内部实现术语泄露到研究正文

需处理的例子：

- `MarketAdapter.get_*`
- `capacity_industry`
- `missing concept 审计`
- `DeepDive_Theme_Radar`
- “公告等硬证据官方验证”等机械重复。

建议增加 presentation mapping/sanitizer；原始字段只保留在 trace/artifact。

### P1-5 长回答完成后强制滚到底部

已定位：

`intelligence/webapp/src/components/MessageThread.tsx`

```tsx
useEffect(() => {
  endRef.current?.scrollIntoView?.({ block: "end" });
}, [messages, liveMessages]);
```

这会在流式更新期间持续滚到底部，Run 完成后用户首先看到引用尾部。

要求：

- 仅当用户本来就在底部附近时继续自动滚动；
- 用户主动向上滚动后停止跟随；
- 提供“回到结论”和模块目录。

### P1-6 刷新后不恢复活动线程

当前 `App.tsx` 中 `surface` 和 `activeConversationId` 都只保存在 React state。

要求：

- 优先使用 URL 表达工作区状态，例如：

  ```text
  /ask/conversations/{conversation_id}?run={run_id}&inspector=evidence
  ```

- 可用 localStorage 作为兼容方案，但 URL 更可分享、可刷新、可前进后退；
- 刷新后恢复 conversation、run、surface 和 inspector tab。

### P1-7 模块级数据新鲜度不一致

首页明确显示市场库缺失，但信号和验证页仍可展示旧 snapshot/历史统计。

要求每个研究模块统一展示：

- `as_of`
- `source_mode`
- `freshness`
- `fallback_reason`

跨日期拼装时必须显式提示，不能视觉上混成“当前态”。

## 6. P2：体验与维护

### P2-1 产物库同时显示生成日期和研究日期

本轮 Run 在 `2026-07-12` 生成，但按 `source_date=2026-07-01` 排序，用户难以找到最新产物。

增加：

- `generated_at`
- `as_of`
- 两种排序方式。

### P2-2 Run 详情默认显示人类可读时间线

默认展示：

```text
路由 -> Skill -> 检索 -> 证据绑定 -> 质检 -> 输出
```

每步包含状态、耗时、输入/输出摘要和失败原因。原始 JSON 放高级详情。

### P2-3 “需处理产物”增加原因和动作

产物库显示“45 项需处理”，但缺少：

- 缺失原因聚合；
- 重新生成；
- 定位 canonical source；
- 标记忽略。

### P2-4 补 favicon

`/favicon.ico` 当前返回 404。低优先级，仅用于清理日志噪声。

## 7. 环境恢复后再验证

以下项目必须在完整运行态二次验证，不能用本轮结果下最终结论：

| 能力 | 本轮状态 | 二次验证目标 |
|---|---|---|
| DuckDB | 缺失 | 最新交易日、实时/历史模块一致性 |
| Hybrid RAG | `.rag_index` 缺失 | BM25 + dense + RRF + rerank 命中和 freshness |
| LLM 综合 | key 缺失 | 叙事质量、引用纪律、质检回灌 |
| 用户长期记忆 | VM 目录为空 | corrections/checkpoints/verdicts 召回 |
| Level2 | 特征库缺失 | 资金流跨日趋势 |
| 历史信号 | 部分缺失 | 题材生命周期回放 |

### RAG 二次验证说明

Hybrid RAG 不是“有向量库就完成”：

- BM25 擅长专有名词、公司名、代码和精确关键词；
- dense retrieval 擅长语义近似；
- RRF 用排名融合避免不同分数尺度直接相加；
- rerank 对少量候选做更贵但更精确的相关性排序。

二次验证必须记录：

- index revision；
- index built_at；
- query；
- BM25 命中；
- dense 命中；
- RRF 后排名；
- rerank 是否启用；
- stale/unknown 被过滤的原因。

替代方案：

- 只用 BM25：部署简单、可解释，但语义召回弱；
- 只用向量：语义较强，但专有词和数字容易漏；
- Hybrid + RRF：更稳健，适合本项目；
- Hybrid + learned reranker：质量更高，但延迟和运维成本更高。

## 8. 分批实施建议

建议每个 P0 独立 PR，避免一次修改编排、证据模型、健康接口和 UI 状态后难以回归。

### PR 1：Skill 主回答链

- P0-1；
- 后端 orchestrator 契约测试；
- Daily Agent / Daily Review 回归。

### PR 2：证据等级与质量门禁

- P0-2；
- P0-4；
- Evidence Registry；
- 模板和 LLM 两条路径测试。

### PR 3：运行状态契约

- P0-3；
- `completed_degraded`；
- readiness 和 UI 状态测试。

### PR 4：前端恢复与可读性

- 刷新恢复；
- 自动滚动；
- 警告聚合；
- 人类可读 Run 时间线。

## 9. 每个 PR 的最低检查

后端相关：

```bash
source .venv-workbench/bin/activate
python -m pytest -q <相关测试文件>
python -m ruff check <修改的 Python 文件>
```

前端相关：

```bash
cd intelligence/webapp
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

提交前：

```bash
pre-commit run --all-files
```

真实运行：

```bash
python scripts/smoke_workbench_self_use.py \
  --base-url http://127.0.0.1:8788 \
  --user linxiaoqi5111 \
  --question "今天市场怎么样" \
  --timeout 180 \
  --output /tmp/workbench-self-use-smoke.json
```

P0-1 还必须手动或用 E2E 测试：

```text
手动选择 Daily Agent
-> 发送研究雷达问题
-> 核对回答首屏与 Skill 原始产物
```

## 10. 完成定义

P0 全部完成时必须同时满足：

- 手动 Daily Agent 回答与 Skill 原始结果一致；
- 无 L3 时不再输出硬确认措辞；
- `market_snapshot=false` 时 research readiness 不为 ready；
- report、context、Inspector 的证据语义和数量一致；
- 不再同时显示“无可验证来源”和大量引用；
- 降级 Run 不再只显示普通“已完成”；
- 现有 lint、typecheck、test、build、smoke 全部通过。
