# 工作清单：R-10 收尾冻结 → 主线切到工具面（2026-08-04d）

> **给执行 agent**：按 Batch A → Batch B 顺序做，每个 Task 做完停下报告，不要连做。
> 每条都写了**验收命令**和**通过标准**，验收方会逐条独立复跑，不看报告看产物。
> **不确定时问，不要猜。** 猜错的代价是下一轮返工。

## 0. 方向变更说明（先读，否则会做错优先级）

原计划 R-10 有 Task 1-6。**Task 3-6 现在取消。**

原因：R-10 修的是 `codex_headless`，而它在代码里标着 `benchmark_only=True`
（`agent_runtime_factory.py:63`、`api/app.py:276` 会直接 `raise`），产品 web UI 永远走不到。
它的价值是"量引擎"这把尺子。

而经过审计，产品的真实差距很可能在**工具面**不在循环：

| | Codex 桌面端 | 我们的 web UI agent |
|---|---|---|
| 工具数 | shell + 文件 + grep + 跑任意脚本 | **2 个**（`finance_query`、`evidence_search`） |
| 能否调用仓内三十来个 skill | ✅ | ❌ 一个都调不到 |

旁证：Knevo 逆向文档自己的结论是「核心壁垒不在模型或 agent 框架，而在自建数据聚合
服务 + 研报纪要库」。B/C 对比 `knevo_wins 9 : workbench_wins 2`。

**所以：R-10 补完两个洞就冻结，主线切到 Batch B。**

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

## Batch B：工具面盘点（新主线第一步）

**这一批只做盘点，不改任何生产代码。** 产出是一份让用户能做决策的清单。

### B1：盘出 agent 当前能力边界

**要求**：读 `intelligence/services/episode_tools.py`，写清楚：

- `finance_query` 实际能查什么：哪几个 dataset、每个 dataset 有哪些字段、
  支持哪些筛选/分组/排序、**不能**做什么（比如能不能跨 dataset join、
  能不能算衍生指标）
- `evidence_search` 实际检索什么：索引里有什么、narrow→broad→counter 是什么策略、
  返回什么结构
- 这两个工具**合起来答不了**的问题类型，举 3 个具体例子

**产出**：`docs/verification/2026-08-04d-agent-tool-surface-inventory.md` 的第 1 节。

### B2：盘出仓内现有能力

**要求**：把 `.claude/skills/` 下所有 skill 过一遍（含知识库仓的跨仓 skill），
每条记录：

| 列 | 说明 |
|---|---|
| skill 名 | |
| 干什么 | 一句话 |
| 数据源 | mootdx / 东财 / iwencai / 巨潮 / DuckDB / 知识库 / … |
| 入口形式 | Python 脚本？CLI？需要 CDP proxy？需要凭证？ |
| 是否只读 | **写库/写飞书的必须标出来** |
| 包成 agent 工具的难度 | 低（纯函数调用）/ 中（要封装参数）/ 高（要浏览器或人工登录态） |

**禁止**：不要真的去跑这些 skill，不要抓数据，不要碰 DuckDB 和飞书。只读 SKILL.md
和脚本签名。

**产出**：同一份文档的第 2 节。

### B3：出候选清单与取舍建议

**要求**：基于 B1 + B2，给出：

1. **收益最大的前 5 个候选工具**，每个写明：补上它能答哪类现在答不了的问题
2. 每个候选的**证据可追溯性**评估——这是硬约束：产品架构建立在
   "每个数字必须绑定出处"（`bound_evidence` / `citation`）上。
   说清楚这个工具的返回值怎么绑定证据；绑不了的要明说
3. 三条技术路线的取舍对比（**必须给替代方案对比，这是用户的明确偏好**）：
   - 逐个包装现成 skill 成工具
   - 放开只读 SQL
   - 受控代码执行（sandbox 内只能调数据 API）

   每条写：能力增益 / 安全风险 / 证据可追溯性 / 实现工作量 / 适合什么场景

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
