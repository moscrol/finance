# 工作清单：R-10 收尾冻结 → 主线切到工具面（2026-08-04d）

> **给执行 agent**：按 Batch A → Batch B 顺序做，每个 Task 做完停下报告，不要连做。
> 每条都写了**验收命令**和**通过标准**，验收方会逐条独立复跑，不看报告看产物。
> **不确定时问，不要猜。** 猜错的代价是下一轮返工。

## 0. 方向变更说明（先读，否则会做错优先级）

原计划 R-10 有 Task 1-6。**Task 3-6 现在取消。**

原因：R-10 修的是 `codex_headless`，而它在代码里标着 `benchmark_only=True`
（`agent_runtime_factory.py:63`、`api/app.py:276` 会直接 `raise`），产品 web UI 永远走不到。
它的价值是"量引擎"这把尺子。

而产品侧有一个**尚未证实**的假设值得先查清：差距可能在**工具面**而不在循环。

⚠️ **更正记录（重要，别继承错误前提）**：本文件初版写「我们只有 2 个工具」，**那是错的**。
真实工具面是 **8 个**（`research_tool_registry.py:35-42` 的 catalog + `episode_tools.py`
另加的两个）：

```
web_search / news_search / l3_lookup / market_data
financial_data / mainline_context / finance_query / evidence_search
```

覆盖网页、新闻、公告、行情、财务、主线、本地 DuckDB、知识库。**所以"工具面差距很大"
这个结论目前没有证据，Batch B 的任务是去证实或推翻它，不是去确认它。**

已知的旁证只有两条，都不直接指向工具面：
- Knevo 逆向文档的结论是「核心壁垒不在模型或 agent 框架，而在自建数据聚合服务 +
  研报纪要库的数据授权」——指向**数据源覆盖**，未必是工具数量
- B/C 对比 `knevo_wins 9 : workbench_wins 2`——只知道输了，不知道输在哪

**所以：R-10 补完两个洞就冻结，主线切到 Batch B 做诊断。**
Batch B 的结论可能是「工具面没问题，差距在别处」——那也是有效产出，不要为了
凑结论而夸大缺口。

不要主动开 Task 3（watchdog / 派生 context）。那是冻结后的待办，不是现在的活。

## Batch A：R-10 收尾冻结

工作区：`/Users/a77/finance-workspace-private/.worktrees/headless-tool-pairing`
分支：`fix/headless-tool-correlation-observability`
起点 HEAD：`b24bd818 fix(runtime): align headless root budget accounting`

解释器固定用 `.venv-workbench/bin/python`（宿主 `python3` 是 3.14 缺依赖）。

---

### A1：把秒数结算的 check-then-act race 修掉

**问题**：`headless_tool_gateway.py` 的 `_settle_root_seconds()` 先读
`ledger.remaining_seconds` 再调 `consume_seconds(settled)`，两步之间没有锁。
并发结算时第二个会抛 `ValueError`，被 `except (TypeError, ValueError): return`
**静默吞掉**——秒数没扣、超支没记。

这与 Task 2 刚消灭的 call race 是同一个形状，只是量纲从 calls 换成 seconds。
`handoff §6 决议二`明文要求超支必须可见，静默是被禁止的。

**要求**：

1. **钳零必须和扣减在同一把锁内。** 首选做法：在
   `research_contract.py` 的 `InMemoryRootBudgetLedger` 上新增
   `settle_seconds(*, seconds: float) -> float`，在自己的 `_lock` 内
   `settled = min(seconds, remaining_seconds)`，扣减后返回实际扣掉的值。
   同时在 `RootBudgetLedger` Protocol 加上这个方法。
2. gateway 改为调用 `settle_seconds()`，用返回值算 overdraft。
3. **保留向后兼容**：ledger 没有 `settle_seconds` 时（第三方/测试桩）
   回退到现有路径，但回退路径的 `except` **必须发 telemetry**，不许静默 return。
4. 新增并发测试：两个 runner 各消耗接近全部预算，断言
   - 总扣减不超过 `initial_seconds`
   - 至少一个 `root_budget_overdraft` 事件被记录
   - **没有任何一次结算是静默失败的**

**禁止**：不要改 `consume_call` / `consume_seconds` 的现有语义（其他调用方在用）；
不要用 sleep 凑并发，用 `Event`/`Barrier`。

**验收命令**：
```bash
.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_headless_tool_gateway.py \
  intelligence/tests/test_research_contract.py
.venv-workbench/bin/python -m ruff check intelligence/
```

**通过标准**：
- gateway 文件 **≥ 34 passed, 0 failed**（现 33 + 至少 1 条新并发测试）
- `test_research_contract.py` 零新红
- ruff pass
- **变异测试**：把 `settle_seconds` 的 `min()` 改成直接用 `seconds`，新测试必须转红。
  改不红说明测试没咬住，不算通过。

---

### A2：把新事件 kind 接进归一化器

**问题**：`root_budget_overdraft` 是全新事件类型，
`intelligence/eval/normalize_harness_trace.py` 的映射表（`:334` 附近，
`"finalization": ("synthesize", "generation")` 那张）里没有它。
未知 kind 会落到 `("unmapped", "unmapped", "unknown")`（`:431`）。

**R-20260804-06 是已结案 `confirmed` 的预测**，内容正是「归一化后
`unmapped_count` 仍为 0」。放着不管，Task 4/5 会炸，且看起来像凭空回归。

**要求**：

1. 在映射表加 `"root_budget_overdraft"`，归到 **control** 角色。
   step 归哪一步自己判断并在 commit message 里说明理由（参考相邻的
   `"invalid_action": ("observe", "control")`）。
2. 在 `intelligence/tests/test_normalize_harness_trace.py` 加一条测试：
   含 `root_budget_overdraft` 的事件序列归一化后 `unmapped_count == 0`。

**验收命令**：
```bash
.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_normalize_harness_trace.py
```

**通过标准**：零红；新测试存在且**去掉映射表那一行会转红**（变异测试）。

---

### A3：冻结 R-10，更新账本与 handoff

**要求**：

1. 更新 `docs/handoffs/2026-08-04c-headless-inflight-tool-pairing-wip.md`：
   - 标记 Task 2 **已完成**（commit `b24bd818` + A1/A2 的修复 commit）
   - 标记 **Task 3-6 冻结**，写明冻结原因（见本文件 §0）和恢复条件
   - 更新验证基线为 A1/A2 完成后的真实数字
2. 更新 `docs/prediction-ledger.md`：
   - `R-20260804-10` 的 `outcome` **保持 `pending`**。
     ⚠️ 不准写 `confirmed`——离线主门没跑完、live 没跑，部分验证写 confirmed
     是账本明令禁止的。
   - 在 Open 表的处理列注明「已冻结，Task 3-6 未执行，恢复条件见 08-04d 清单」
3. **不 push、不合并 main。**

**验收命令**：
```bash
git log --oneline -6
git status --short          # 期望干净
git diff HEAD~1 --check
```

**通过标准**：handoff 与账本的数字能与 A1/A2 的真实 pytest 输出逐字对上；
`R-20260804-10` 仍是 `pending`。

---

### A4：补上 Protocol 的最后一个实现（验收时新发现）

**问题**：A1 给 `RootBudgetLedger` Protocol 加了必需方法 `settle_seconds`
（`research_contract.py:431`），但同仓的另一个实现 **`_BranchBudgetView`
（`sub_research.py:45`）没有它**。而 `sub_research.py:339` 正是把它赋给
`root_budget=`，那个字段类型是 `RootBudgetLedger | None`
（`research_contract.py:867`）。

两个后果：

1. **Protocol 声明与代码事实不符。** 本仓只跑 ruff，不做类型检查，所以没人报错——
   下一个引入 mypy/pyright 的人会撞上。
2. **运行时静默降级。** gateway 用 `getattr` 探测，`_BranchBudgetView` 会落到
   **legacy 那条仍然 racy 的路径**——正是 A1 要消灭的形状。
   （gateway 目前是 benchmark-only，sub-research 是否真能走到它未经证实；
   因此定 P1 不是 P0。但"静默退回有 bug 的旧路"正是这条线一直在修的东西。）

**要求**：给 `_BranchBudgetView` 实现 `settle_seconds`，在它自己的 `_lock` 内
`min(requested, remaining_seconds)`，**先向 parent 结算再扣自己**，返回实际扣减值。
注意与该类现有 `consume_seconds` 的委托顺序保持一致，父账本可能扣得比请求少——
以父账本的返回值为准，不要假设两边同额。

**验收命令**：
```bash
.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_research_contract.py \
  intelligence/tests/test_sub_research.py \
  intelligence/tests/test_headless_tool_gateway.py
```

**通过标准**：三个文件零红；新增一条测试证明 branch 视图并发结算不丢账，且
**变异测试**（把 `min()` 换成直接用 requested）能让它转红。

---

## Batch B：按四平面模型做差距诊断（新主线第一步）

**这一批只做诊断，不改任何生产代码。** 产出是一份让用户能做决策的清单。

### ⚠️ 开工前必读（不读会重复已有工作）

本清单前两版都因为没读这些资料而写错前提。**先读，再动手**：

| 资料 | 为什么必读 |
|---|---|
| `/Users/a77/agent-memory/10_knowledge/finance-agent-capability-graph.md` | **能力图谱已存在**（30 节点 / 32 路径 / mermaid 总览）。诊断的基线是它，不是从零盘点。跑 `python3 /Users/a77/agent-memory/scripts/graph_audit.py` 确认它没漂移（应 exit 0） |
| `/Users/a77/agent-memory/10_knowledge/finance-agent-knevo-derived-knowledge-runtime-contract.md` | **本批的判据来源**：四类数据平面 + §9 吸收优先级 P0/P1/P2 |
| `/Users/a77/agent-memory/20_projects/finance-workspace-private.md` | 任务看板 + 交接记录。**很多"缺口"其实已完成或已有结论** |
| `/Users/a77/agent-memory/10_knowledge/knevo-reverse-engineering.md` | 竞品对照基线（1 入口 + 8 专项 skill + 7 底层工具） |

**已知事实，不要再"发现"一遍**：
- agent 工具约 **10 个**：`research_tool_registry.py:35-42` 的 6 个 catalog +
  `agent_research.build_graph_tools` 的 `graph_lookup`/`evidence_lookup` +
  `episode_tools.py` 的 `finance_query`/`evidence_search`
- **技能桥已存在**：`skill_tools.py`（已注册 `serenity-alpha`）、
  `theme_modules.run_module`。其余 skill 未接入是**刻意设计**——大多要拉实时数据
  或写库，接入会破坏 agent 的只读/无外呼红线。**不要把这个约束当缺口去"补"**
- **编排层已存在**：`answer_orchestrator` / `conversation_orchestrator` /
  `question_router` / `route_table` / `research_task_planner` / `ask_planner` /
  `retrieval_planner` / `research_plan` / `generic_research_owner`
- MOC 交接记录 2026-07-19 已确立的可迁移原则：**配额在副作用前预占**、
  **全链 deadline 传绝对时刻**、**per-key single-flight 去重**

---

### B1：四平面覆盖体检

用运行时契约 §1 的四类数据平面当坐标系，逐个平面回答「有没有 / 谁提供 / agent 能不能
直接调 / 缺什么」：

| 平面 | 承载 | 已知候选实现 | 要查清的 |
|---|---|---|---|
| `provider` | 行情/财务/公告/新闻等当前事实 | `market_data` `financial_data` `news_search` `web_search` `l3_lookup` `finance_query` `mainline_context` | 覆盖是否够；哪些受 `allowed_capabilities` 门控、日常问答实际开几个 |
| `graph` | 实体/关系/结构化事实/证据切片 | `graph_lookup` `evidence_lookup` | 返回值是否满足契约 §5 的六字段（entities/edges/edge_claims/facts/evidence/gaps）；**空结果有没有结构化降级门** |
| `shared_memory` | 沉淀的观察/洞察/推理模式 | `evidence_search`、W Wiki RAG | 检索是否走契约 §4 的窄/宽/反三口径；有没有跨 query 去重 |
| `user_memory` | 用户判断/偏好/交互史 | `experience_cards` `corrections` `foresight`（能力图谱显示 `Cards → Planner`、`Verdicts → Foresight`） | **重点**：这些只喂给 planner，还是 agent 能作为工具主动查？Knevo 每次研究第一步就是 `finance_memory_query` |

**必答的判断题**：`user_memory` 平面 agent 能不能**主动检索**？
不能的话，Knevo 那条「按记忆条数定检索深度」（记忆 ≥10 条→2-3 工具 / 0-2 条→5+ 工具）
在我们这就实现不了——这是本批最值得确认的单点。

**产出**：`docs/verification/2026-08-04d-four-plane-coverage.md` 第 1 节。

### B2：对照 §9 吸收优先级，逐条判落地状态

运行时契约 §9 给了五条优先级。逐条给 **已落地 / 部分 / 未落地 / 不适用**，
每条附**代码位置或反证**（不许只写结论）：

| # | 条目 | 判据 |
|---|---|---|
| P0 | 类型纯度：每条召回带 `source_plane`/`kind`/`evidence`/`status`，回答前来源隔离 | 看 `AgentEvidence` / `EvidenceAtom` 有没有这几个字段 |
| P0 | 图谱空结果门控：无边/事实/证据时结构化降级，禁止 LLM 自由补关系 | 看 `graph_lookup` 空结果路径 |
| P1 | 检索 provenance 与 `cross_query_support` | 看检索结果有没有留 query_id / rank / 跨 query 支持度 |
| P1 | 推荐与长期 memory 分库分状态，用户确认是显式写入 seam | 看 `experience_cards` / `corrections` 的写入权限 |
| P2 | 运行一致性验收（payload/事件/持久化/索引四层） | 看 SSE / run 的验收检查 |

**这一步的价值**：把"我们缺什么"从猜测变成对着已有清单打勾。

**产出**：同一文档第 2 节。

### B3：出差距清单与取舍建议

基于 B1 + B2：

1. **确认的差距**（有代码证据的），按「补上能答哪类现在答不了的问题」排序
2. 每条差距的**证据可追溯性**评估——硬约束：架构建立在"每个数字绑定出处"
   （`bound_evidence` / `citation`）上。绑不了的要明说
3. **取舍对比**（用户明确偏好：必须给替代方案对比）。至少覆盖：
   - 接 `user_memory` 检索工具
   - 扩 `skill_tools` 注册表（**必须论证不破坏只读/无外呼红线**）
   - 放开只读 SQL
   - 受控代码执行（sandbox 内只能调数据 API）

   每条写：能力增益 / 安全风险 / 证据可追溯性 / 实现工作量 / 适合场景

4. **反向结论也算有效产出**：如果诊断下来四个平面覆盖都够、§9 的 P0 都已落地，
   那就明确写「工具面不是瓶颈」，并指出证据指向哪里。
   **不要为了凑结论夸大缺口。**

**产出**：同一文档第 3 节。

### B4：把本批发现回写能力图谱

能力图谱是**已有的机器可读事实源**，有维护纪律（见其文件头）。

**要求**：若 B1-B3 发现图谱缺节点或路径漂移，按其维护口径追加/修正，然后跑：

```bash
python3 /Users/a77/agent-memory/scripts/graph_audit.py    # 必须 exit 0
```

**禁止**：不要新建一份平行的"能力清单"文档。已经有一份且是绿的，再建一份就是
第二事实源，下一个 agent 会读到过期的那份。

**禁止**：不要在这一批实现任何工具，不要改 `episode_tools.py`。

**验收命令**：
```bash
ls -la docs/verification/2026-08-04d-agent-tool-surface-inventory.md
git status --short          # 只应出现这一个新文件
```

**通过标准**：
- 三节齐全
- B2 的表覆盖 `.claude/skills/` 下**全部** skill，数量对得上（漏一个算不通过）
- B3 的每个候选都写了证据绑定评估，没有"待定"
- 全程零生产代码改动

---

## 三方对齐约定

| 角色 | 职责 |
|---|---|
| 用户 | 定方向、拍取舍 |
| 执行 agent | 按本清单做，每 Task 停下报告 |
| 验收 agent | 独立复跑验收命令、做变异测试、读产物不读报告 |

**验收方会做的事**（执行方提前知道，省得来回）：

1. 所有 pytest / ruff **重跑一遍**，不采信报告里的数字
2. 对新增测试做**变异测试**：把被测那行改坏，测试必须转红
3. 检查有没有引入新的事件 kind / 错误码 / 配置项而没有接进消费方
4. 检查 `git status` 是否干净、有没有碰红线文件
   （`.env*` / `*.duckdb` / `*.pdf` / 凭证 / 缓存）
5. 检查是否越界做了清单外的事——**越界即使做对了也要退回**，
   因为它绕过了用户的取舍

**报告格式要求**：每个 Task 报告必须含
「改了哪几个文件」「验收命令的原始输出」「哪些是我判断后决定的、依据是什么」。
不要写"已完成""全部通过"这类无法核对的结论。
