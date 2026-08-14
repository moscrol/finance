# Handoff：给 agent 接 user_memory 检索工具（只接检索，不接降级梯度）

> 承接 `docs/verification/2026-08-04d-four-plane-coverage.md` 的唯一确认差距。
> **这是 Batch B 之后第一个真正动产品代码的改动**，前面全是尺子和诊断。

## 0. 范围（先读，越界会被退回）

**做**：给 agent 加一个可主动调用的用户记忆检索工具。

**不做（用户明确划掉的）**：
- ❌ **不实现"按记忆条数决定检索深度"的降级梯度**。Knevo 那套
  （记忆 ≥10 条→2-3 工具 / 3-9 条→3-4 工具 / 0-2 条→5+ 工具）**本轮不接**。
  理由：它会改变回答的形状，用户要先看只加检索的效果。
- ❌ 不改 `ask.py` 现有的 planner 侧注入（`:621`、`:3733`）。两条路并存，不做迁移。
- ❌ 不动 `finance_query` / `evidence_search` / 其余 9 个工具。
- ❌ 不扩 `skill_tools.SKILL_REGISTRY`。

**越界即使做对了也退回**——用户要的是可控的单步。

## 1. 已核实的事实（别重新发现）

以下每条我都跑过或读过代码，**[实测]**：

| 事实 | 位置 |
|---|---|
| agent 现有 **11** 个工具，全在 `_DEFAULT_TOOL_METADATA` | `research_tool_registry.py`（**从 23 行开始**，别用固定行号读，用 `sed -n '/_DEFAULT_TOOL_METADATA/,/^}/p'` 或 AST） |
| agent 侧**零命中** `user_memory` / `experience_cards` / `corrections` | `agent_research.py`、`research_tool_registry.py` |
| 唯一消费点在 planner 侧，不是 agent 循环 | `ask.py:621`、`ask.py:3733` |
| 检索函数已存在 | `user_memory.memory_block_for_query(query, theme=None, entity=None, user=None, limit=DEFAULT_LIMIT, users_root=None) -> str` |
| 它读四个 JSONL 台账 | `judgments` / `corrections` / `checkpoints` / `verdicts`（`user_memory.py:149-158`） |
| **它返回的是渲染好的 `[M]` markdown 字符串，不是结构化记录**；无命中时返回空串 | `user_memory.py:148` |
| 底层有结构化召回 | `select_relevant(records, query, theme, entity, text_keys=..., limit=...)`（`user_memory.py:161`） |
| `AgentEvidence.internal_locator` 的语义是「仅控制面追踪，**不得进入 Citation/AnswerSpec**」 | `agent_research.py:129` |
| 该约束**已有测试钉住** | `test_agent_runtime.py:196` 断言 payload 里没有 `internal_locator` |
| 同类工具的参考实现（也是纯本地 JSON、用 internal_locator） | `agent_research.build_graph_tools` 的 `_graph_lookup`（`:367` 起） |
| 现有 evidence_tier 取值 | `agent_retrieval` / `agent_assessment` / `concept_graph` / `L3_official` / `L4_structured` / `base_finance` / `company_evidence` / `external_web_snapshot` / `candidate_snapshot` |

## 2. 硬约束（这条比功能本身重要）

运行时契约 §1 明文：

> `user_memory` —— 用户个人判断、偏好、交互史。**可作为用户基线，不能冒充客观事实。**

`ask.py:626-632` 现有的 planner 注入已经体现了这条——它的 Citation 描述是
「历史判断与纠偏原则，**仅作先验，不替代当前市场事实**」。

**新工具必须保持同等强度或更强。** 具体要求：

1. 返回的 `AgentEvidence` **不得**被后续用作事实型 claim 的支撑证据。
2. `internal_locator` 指向台账文件路径（控制面可追溯），`source` 用**用户可见且自我标注**
   的标签，让模型一眼看出这是"用户自己说过的话"而非市场事实。
3. **新增一个专属 `evidence_tier`**（建议 `user_memory`，不要复用 `agent_retrieval`）——
   复用现有 tier 会让下游没法把它和客观检索区分开。

⚠️ **你需要自己查清并在报告里说明**：本仓当前**是靠什么机制**阻止某一 tier 的证据进入
事实型 claim 的？是 `episode_semantic_verifier` 的绑定校验、`answer_lint` 的门、还是别的？
- 如果**有**现成机制 → 把新 tier 接进去，并加测试证明它挡得住。
- 如果**没有**现成机制 → **不要自己发明一套**。停下来报告，说明"加了工具但这条约束
  当前无处落地"，让用户决定是先补机制还是接受风险。**这是允许的停点，不算失败。**

## 3. 实现要点

参考 `episode_tools.py` 里 `evidence_search` 的 ToolSpec 注册形状。

1. **runner 返回 `ToolRunResult`**（`evidence=`, `observation=`, `trace=`, `gaps=`）。
   `memory_block_for_query` 返回的是字符串，**不要直接塞进 evidence**——
   走 `select_relevant` 拿结构化记录，逐条构造 `AgentEvidence`。
   若判断走结构化路径成本过高，可以先用字符串做 `observation`、`evidence=()`，
   但**必须在报告里说明这样做的代价**（无法逐条追溯、无法参与证据绑定）。
2. **catalog 加一条**，工具名建议 `memory_lookup`（与 `graph_lookup`/`evidence_lookup` 同族）。
   description 要写清"这是用户自己的历史判断，不是市场事实"——**工具描述是模型唯一
   能看到的语义**，写松了模型就会拿它当事实用。
3. **受 `allowed_capabilities` 门控**，与其余工具一致。默认是否授权由你判断并说明理由。
4. **只读、无外呼**：读本地 JSONL，不碰网络、不写文件。这是 agent 的红线。
5. 空结果要有明确信号（参考 `_graph_lookup` 的 `status="empty"` + observation 文本），
   **不要静默返回空**。

## 4. 验收

```bash
.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_agent_research.py \
  intelligence/tests/test_episode_tools.py \
  intelligence/tests/test_agent_runtime.py \
  intelligence/tests/test_research_tool_registry.py
.venv-workbench/bin/python -m ruff check intelligence/
```

先跑一次**记下改动前的基线数字**，改完对比——新增的红必须能逐条解释。

**通过标准**：

- 上述文件零新红，ruff pass
- 新增测试至少三条：
  1. 工具能召回到已有记忆（用 `users_root=` 指临时目录造 fixture，**不要读用户真实台账**）
  2. 无记忆时返回明确的 empty 信号，不是静默空
  3. `internal_locator` 不泄漏进对外 payload（对齐 `test_agent_runtime.py:196` 的既有断言）
- **每条新测试都要做变异测试**：把被测那行改坏，测试必须转红，然后还原。
  改不红说明没咬住，不算通过。
- 全程 `git status --short` 只出现你打算改的文件

## 5. 报告要求

除常规三段（改了哪些文件 / 验收命令原始输出 / 自己判断的部分及依据）外，**必须回答**：

1. §2 那个问号的答案——本仓靠什么机制阻止某 tier 进入事实型 claim？有还是没有？
2. 你走的是结构化 `AgentEvidence` 还是字符串 observation？为什么？代价是什么？
3. 默认是否进 `allowed_capabilities`？理由？

## 6. 不要踩的坑

- **数数别用固定行号。** catalog 起点在 23 行，用固定行号读会漏三个工具——
  这个错本轮已经犯过两次，一次还写进了 CLAUDE.md。
- **改完 grep 复核，别只看工具返回值。** 本仓有 5 个 worktree、同名文件多份；
  pre-commit 的 stash→restore 窗口也可能盖掉期间的编辑。
- **断言"我们没有 X"之前**：全树 grep 同义词 + 读能力图谱 + 读 MOC 任务看板，
  并写明查过哪些。见 `CLAUDE.md` §🗺️。
- 记忆台账里有用户私有内容，**测试一律用 `users_root=` 指临时 fixture**，
  不读真实台账，不把台账内容写进测试断言或提交物。
- 完成后按能力图谱的维护口径回写节点，并跑
  `python3 /Users/a77/agent-memory/scripts/graph_audit.py`（须 exit 0）。
  **不要新建第二份能力清单。**
