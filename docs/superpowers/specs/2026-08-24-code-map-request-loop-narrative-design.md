# Code Map 请求 Loop 叙事页设计

- 日期：2026-08-24
- 状态：Approved
- 基线：`gitea/main@904aba62`
- 目标分支：`codex/code-map-request-loop`

## 1. 目标

让编码 agent 用一个稳定的叙事入口定位一次金融 Agent 请求的五个阶段，同时继续由 Code Map 的三层查询契约分别回答：

- `doors`：系统规定应该怎样；
- `structure`：当前代码里有哪些节点和连接；
- `narrative`：方便人阅读和继续追问的入口页。

本变更只补导航，不新增能力、不复制结构图，也不改变生产请求 Loop。

## 2. 当前问题

现有 `.code-review-graph/wiki-steering.json` 已覆盖复盘入口、工具面、DuckDB VIEW、`intelligence` 分层和常用脚本，但没有一页把请求路径的 L0–L4 串起来。

因此单独查询 `conversation_orchestrator` 或 `research_tool_registry` 能得到结构命中，但用户需要自己知道五个入口词，无法从一个叙事页顺着请求路径学习。

## 3. 方案比较

### 方案 A：新增一个 steering 页（采用）

在现有 `pages` 数组增加 `agent-request-loop`，用五个真实符号分别锚定 L0–L4。生成器仍只投影正门命中；结构命中继续由 `query` 实时返回。

优点：变更小、可测试、不会形成第二份架构真源，下一次 full build 会自动重生页面。

### 方案 B：手工维护生成页（拒绝）

直接编辑 `.code-review-graph/wiki/doors/agent-request-loop.md`。

拒绝原因：`wiki/` 是忽略的生成物，无法稳定交付，下一次 build 还会覆盖。

### 方案 C：扩生成器，把结构结果抄进叙事页（拒绝）

让 `_write_steering_pages()` 同时保存 CRG structure hits。

拒绝原因：同一结构事实会同时存在于 `graph.db` 和生成 Markdown，增加漂移面；也会把“叙事导航”和“结构检索”两个职责重新揉在一起。

## 4. 采用设计

新增页面：

```json
{
  "id": "agent-request-loop",
  "title": "Agent 请求 Loop",
  "queries": [
    "validate_runtime_selection",
    "conversation_orchestrator",
    "research_tool_registry",
    "episode_semantic_verifier",
    "experience_cards"
  ]
}
```

五个锚点的教学含义：

| 阶段 | 查询锚点 | 回答的问题 |
|---|---|---|
| L0 入口 | `validate_runtime_selection` | 模式和视角选择在哪里被校验？ |
| L1 调度 | `conversation_orchestrator` | 谁拥有请求 Loop、预算和引擎选择？ |
| L2 工具 | `research_tool_registry` | 有哪些工具，能力契约在哪里定义？ |
| L3 验收 | `episode_semantic_verifier` | 答案交付前怎样验证和降级？ |
| L4 学习 | `experience_cards` | 本轮经验怎样变成后续可召回材料？ |

`title` 负责让“Agent 请求 Loop”这类自然提问命中该页；五个 `queries` 负责精确锚定各阶段。页面不声称这五项穷尽所有实现，`completeness_claim.recall` 继续保持 `untested`。

## 5. 数据流

```text
用户查询某一阶段或“Agent 请求 Loop”
  → scripts/code_map.py query
  → doors：检索 AGENTS / CLAUDE / specs / 可选能力图谱
  → structure：从当前 graph.db 搜真实符号
  → narrative：由 steering 命中 agent-request-loop.md
  → conflicts：若正门与生成页冲突，doors_win
```

full postprocess 时：

```text
wiki-steering.json
  → _write_steering_pages()
  → wiki/doors/agent-request-loop.md
  → wiki/index.md 登记链接
```

## 6. 改动范围

Tracked 文件：

- `.code-review-graph/wiki-steering.json`
- `tests/test_code_map.py`

生成但不提交：

- `.code-review-graph/graph.db`
- `.code-review-graph/status.json`
- `.code-review-graph/wiki/`

不修改 `scripts/code_map.py`，因为现有接口已经足够。

## 7. 验收

### 静态测试

1. steering 中恰好存在一个 `agent-request-loop`。
2. 标题为 `Agent 请求 Loop`。
3. 五个查询锚点按 L0–L4 顺序存在且无重复。
4. `purpose` 仍是 `steer narrative pages only; not a capability inventory`。

### 生成测试

1. full build 后生成 `wiki/doors/agent-request-loop.md`。
2. `wiki/index.md` 出现该页面链接。
3. 五个查询分别命中该 narrative 页面。

### 本地收据

1. `python3 scripts/code_map.py build --postprocess full` 成功；显式 full，不能依赖热点文件阈值碰巧触发叙事页重建。
2. `status=ready` 且 `head_matches_build=true`。
3. 五个锚点分别得到 `structure.state=ok` 与 `narrative.state=ok`。
4. tracked worktree 无意外改动，生成物继续被 ignore。

## 8. 失败处理与回滚

- 某个结构锚点搜不到：不伪造页面正文，先确认图是否 `ready`，再检查符号是否改名。
- narrative 页面未生成：检查 full postprocess 和 steering JSON；不手改 `wiki/` 补洞。
- 正门与叙事冲突：沿用现有 `doors_win`，不改优先级。
- 回滚只需删除 steering 条目及对应测试；重新 full build 即会重生索引，不涉及生产数据迁移。

## 9. 非目标

- 不修改金融 Agent 的 L0–L4 运行逻辑。
- 不把五个锚点登记成新的能力清单。
- 不把二维教学图写成第二份架构真源。
- 不修改 `code_map.py` 的 JSON schema、查询排序或冲突规则。
- 不移动或合并本地 `main`。
