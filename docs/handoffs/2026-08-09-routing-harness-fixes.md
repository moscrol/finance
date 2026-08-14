# Handoff — 路由假阳性修复 + Harness 三项改造（2026-08-09）

> 给下一位接手的 agent。两个 commit 已合入 main，未 push。
>
> 本轮最重要的不是改了什么，而是**三次自己推翻自己的判断**——每次都是被实测数据打的。
> 下面按「结论先行 → 根因 → 坑 → 待办」的顺序写。

---

## 0. 提交记录

```
4a65b28a  feat(harness): 接线 check_satisfiability + 判缺结构化落盘
3208be99  fix(routing): scenario_tree 能否/能不能 祈使句不触发推演契约
```

验收：`3910 passed / 13 failed`（13 个宿主环境固有，与本次无关，见 §5）。
ruff 全绿，`scripts/layer_audit.py` 门禁 0 违规。

---

## 1. `3208be99` — scenario_tree 路由修复

**问题**：`_SCENARIO_TERMS` 里的 `能否/能不能` 是裸子串匹配，但它同时是汉语最高频礼貌请求前缀。
「能否帮我把复盘导出成 PDF」被判成推演题 → 追加 `scenario_tree` 验收项 → 导出请求永远填不上
→ 契约门如实拒答，表面症状是「证据不足」。用户会去查检索层——而检索层是好的。

**改动**：`intelligence/services/scenario_tree.py`
- `能否/能不能` 移出 `_SCENARIO_TERMS`
- 新增 `_FEASIBILITY_RE`：要求前面有主语（`[\u4e00-\u9fff...]{2,}` 先行）+ 后面不是请求动词（否定前瞻）
- `parse_scenario_intent` 先查词表，未命中再查 `_FEASIBILITY_RE`

**实测**（62 条去重真实 query，走生产同构路径 `QueryResolver`）：
- 真实用户子集 23 条中 `scenario_tree` 误命中归零
- 「能否帮我把复盘导出成 PDF」等 4 条祈使句全部修正
- 「厦门钨业正极能否扭亏」/ 「量能能不能延续」等可行性问题仍命中

**探针方法论坑（已写进测试注释，别再踩）**：
初版探针直接调 `understand_query(q)` **未传 `anchor`**，`subject` 未解析率 82%，
差点据此得出「结构不完整极其普遍」。走 `QueryResolver.resolve()` 生产路径后降至 53%。
**探针必须复刻生产调用形态，否则量出来的是探针自己的缺陷。**

**新增回归测试（264 项通过）**：
- `test_scenario_tree.py`：祈使句 4 条 + 可行性 4 条
- `test_query_understanding.py`：在 envelope 层断言 `required_outputs` 不含 `scenario_tree`
  （这才是真正防契约拒答的那道断言，只测底层函数不够）

---

## 2. `4a65b28a` — Harness 三项改造

### 2a. 接线 `check_satisfiability`（fail-open 事前观测器）

**背景**：`ToolSpec.produces` 声明 + `check_satisfiability()` 早就建好——11/12 工具已填，
fail-open 三态（covered/unknown/suspicious），防漂移对账测试齐全——**但全仓没有任何生产调用者**。

`intelligence/runtime/continuous_turn_adapter.py:_run_episode` 是接线点：registry 与 contract
同时在手，在 `registry` 建好之后、工具开跑之前调 `_precheck_satisfiability(registry, context)`。
结果写进私有 artifact `satisfiability_precheck`，字段 `enforced=False`，**不参与任何决策**。

```python
# private_artifact 里的形态
"satisfiability_precheck": {
    "enforced": False,
    "counts": {"covered": N, "unknown": N, "suspicious": N},
    "checks": [{"output_id": ..., "status": ..., "contributing_tools": [...], "reason": ...}, ...]
}
```

**为什么 enforced=False 不能改**：声明表是人手维护的，让一张不完整的表拥有拦截权比不做更糟。
实测量化：若拦人则 53% output 被拦（归一前数字），11% 整题被拦——一个观测器会变成系统最大拒答来源。

**下一步**：跑一段观察 `suspicious` 命中率（归一后是 16%，这是离线算的）。
等有了线上真实分布数据，再决定要不要升级为拦截门。
**在 `suspicious` 稳定低于 5% 且人工抽查无误判之前，不改 enforced。**

### 2b. 修预检漏归一（53% → 16% suspicious）

接线后立刻实测发现比对是字面的，而契约侧与 produces 侧不是同一套 id：

| 契约侧 | produces 侧（归一后） |
|---|---|
| `evidence_boundary` | `counterpoint` |
| `direct_answer` | `direct_assessment` |
| `continuation_conditions` | `rebound_case` |

179 个 output 实例里 **65 个纯属字面差异**（`evidence_boundary` 33 次、`direct_assessment` 32 次）。

**修法**：给 `check_satisfiability` 加 `normalize: Callable[[str], str] | None = None` 回调，
由 adapter 侧注入 `_normalize_output_id`（内部延迟 import `_LEGACY_OUTPUT_ALIASES`）。

不直接在 services 层 import orchestrator 的原因：`scripts/layer_audit.py` 门禁禁止
`intelligence/services/**` → `intelligence.runtime.*`，且测试文件 `test_tool_produces_satisfiability.py`
的注释明确禁止抄第二份表——抄一份就等于把 orchestrator 那边的修改和这里的比对解耦。

⚠️ **鸭子类型坑（第二次踩同一个，写进了测试注释）**：
第一版直接调 `registry.authorized_specs(...)`，37 条既有测试立刻转红——
`registry_factory` 的多个替身返回字符串 `"registry"`。与 `38c06356` 那次
（在 `ResearchDeadline` 上加方法）是同一个坑：**在鸭子类型注入点上新增依赖，必须对缺失接口 fail-open。**
`_precheck_satisfiability` 对缺失接口与任何异常都返回空元组。

**新增回归测试（85 项通过）**：
- `test_satisfiability_precheck_survives_registry_without_authorized_specs`（变异验证：删 callable 守卫必红）
- `test_satisfiability_precheck_reports_counts_without_enforcing`
- `test_satisfiability_precheck_normalizes_output_ids_before_comparing`（变异验证：去掉 normalize= 必红）

### 2c. 判缺结果结构化落盘

**根因**（与初步判断不同）：

```
FulfillmentVerdict.to_dict() 早就带 reason_code + candidate_count
  ↓  orchestrator 已写进内部 trace step（:2848 / :2880）
  ↓
但公开 trace API 只对 `answer_synthesis` 步投影 `diagnostic`
  ↓  task_fulfillment 步的结构化载荷一次都没出过内网
  ↓
落盘产物里只剩「最终回答未完成任务契约，已按部分完成标记。」（自由文本）
11 个 turn 命中它，没有一个能回答「缺的是哪一格 output」
```

⚠️ **额外干扰**：落盘产物里确实出现过 `reason_code`，但那是 `ask_synthesis` 的另一套词表
（`validated` / `grounded_required_fallback`）。两套同名字段混在一起，让「已经有了」的错觉更难发现。

**改动**：

`intelligence/api/app.py`：
- `_PUBLIC_TRACE_STAGE_BY_PRIVATE_NAME` 加 `"task_fulfillment": "verification"`
- `_PUBLIC_TRACE_MESSAGE_BY_PRIVATE_NAME` 加 `"task_fulfillment": "已完成回答与任务契约的逐项核对。"`
- 新增 `_public_fulfillment_diagnostic(step)`：只投影 `output_id / status / reason_code / candidate_count`
- `_public_trace_step` 在 `diagnostic` 投影后加 `fulfillment` 投影

`intelligence/eval/acceptance.py`：
- `TurnTrace` 加 `fulfillment: dict[str, Any]` 字段
- 新增 `_capture_fulfillment(steps)` 函数（倒序取终态，修复轮 `task_fulfillment_repair` 优先）

**刻意不外放**：`items[].gap`（给人读的中文长句，可能带内部措辞）、`answer_spans`（正文片段）。
形状不完整时整体不投影——半截结构比没有更难排查。

**新增回归测试（20 项通过，在 `test_acceptance_trace_capture.py`）**：
- 三条正向断言：结构化字段可见、counts 正确、evaluated_output_ids 正确
- 两条负向断言：gap 和 answer_spans 不出内网、形状错误整体不投影
- 一条修复轮倒序断言

---

## 3. 设计文档纠正（均已落地）

`docs/superpowers/specs/2026-08-05-intent-routing-candidate-arbitration-design.md` 四处：

| 节 | 原内容 | 已改成 |
|---|---|---|
| §3.4 | 「全仓不存在静态声明，是新建能力」 | 二次更正：早就建好，只差接线（+表格） |
| §5.2 | 「在 gap 写入点旁加结构化字段」 | 根因链重写：缺的是出口投影，不是生产端 |
| §5.3 | （新增） | 四条独占正则仅 2% 命中不做 / 归一 53%→16% / 鸭子类型坑第二次 |
| §7 第 1 条 | 「registry 不支持事前查询」 / 「108 条真实 run」 | 两条依据均标注失效，实测推翻 |

**重要教训（已写进文档，这里摘要）**：
「全仓不存在静态声明」这句话沿用了文档的断言没独立验证，而文档**自己带着一条「⚠️ 成本更正」**——
一份纠过错的文档读起来比没纠过的更可信，于是没再查。搜索也搜偏了：查的是自己猜的实现方式
（`_claim_candidates`），没查能力的所有可能命名（`produces` / `satisfiab`）。
这正是 `CLAUDE.md` 「负面断言规矩」要防的：说「我们没有 X」前必须全树 grep 同义词。

---

## 4. 还没做的事

**① `suspicious` 命中率的线上观测**（优先级高）

接线后的线上真实分布还没有数据。归一后离线算的 16% 是下限，线上可能更高
（真实流量题型比测试集更集中在市场/行情类）。
建议跑 2-3 个工作日后查 `private_artifact.satisfiability_precheck.counts.suspicious`
的分布——这是决定预检能不能升级为拦截门的唯一依据。

**② `produces` 声明表扩充**（中优先级）

目前 11/12 工具已填，19 个 output_id 覆盖。归一后 suspicious 仍有 16%（29/179），
最常见的有 `continuation_conditions`（4 次）、`invalidation_conditions`（4 次）、
`scenario_paths`（3 次）、`valuation_assessment`（3 次）、`scenario_range`（3 次）。

**扩充规则**（从现有代码注释学来，不能凭猜填）：
- 只填有实测证据的（45 个 episode 历史 run + `TestProducesMatchesHistory` 对账）
- 补完之后必须跑 `python -m pytest intelligence/tests/test_tool_produces_satisfiability.py`
- 空 `frozenset()` 是保守选择，宁缺勿滥

**③ 判缺四码的历史回填**（低优先级，等线上数据再看）

现在公开 trace 已经投影了，新的 run 会带上 `fulfillment` 字段。
历史 eval/runs/*.json 里没有这个字段，要统计历史趋势需要重跑。
可以等 `③` 有线上数据后一起做，不急。

---

## 5. 既有失败（13 条，与本次无关）

```
FAILED test_acceptance_board.py::test_board_keeps_operational_truth_and_experience_axes_separate
FAILED test_acceptance_board.py::test_board_accepts_only_explicit_hash_bound_sidecars
FAILED test_subconscious.py::StartAndBufferTests::* (4 条)
FAILED test_subconscious.py::CommitAndArchiveTests::* (4 条)
FAILED test_userspace.py::* (3 条)
```

根因：本机真实 `agent-memory` vault（`/Users/a77/agent-memory/.foresight/`）覆盖了
这些测试的 tmp 目录 mock——它们 `mock.patch.object(userspace, "USERS_DIR", Path(tmp))` 但
vault 路径走了另一条非 USERS_DIR 的分支。与 `08-08c` 记的宿主环境固有失败同源，不是本次引入。

**对照证据**：在 t2 之前用 `git stash` 摘掉本次全部改动重跑，同样 13 个红。
**不修这 13 个，不改无关代码去凑绿。**

---

## 6. 工作树警告

主检出树 `/Users/a77/finance-workspace-private`（`main`）有其他 agent 的在途改动：
```
M  docs/learning/forecast-review-ledger/2026-07-*.md / *.json（多份）
M  复盘/matrices/*.html（4 份）
M  skills/daily-full-review/state/runlog.md
```

本次两个 commit **只通过 pathspec 提交**，上述文件一个都没碰。下一位接手时：
- 先 `git worktree list` 确认有无其他 agent 在同一树
- `git status` 逐条认领，不属于自己的改动**不要 `git add .`**
- 提交一律 `git commit -- <明确文件列表>`

main 领先 origin/main 5 个提交，**未 push**——push 前请先确认其他 worktree 状态。

---

## 7. 关键文件速查

| 文件 | 改动摘要 |
|---|---|
| `intelligence/services/scenario_tree.py` | 能否/能不能 祈使句修复 |
| `intelligence/services/research_tool_registry.py` | `check_satisfiability` 加 `normalize` 回调 |
| `intelligence/runtime/continuous_turn_adapter.py` | 预检接线 + 归一注入 + 鸭子类型防御 |
| `intelligence/api/app.py` | 判缺投影 `_public_fulfillment_diagnostic` |
| `intelligence/eval/acceptance.py` | `TurnTrace.fulfillment` + `_capture_fulfillment` |
| `intelligence/tests/test_scenario_tree.py` | 祈使句/可行性回归（+24 行） |
| `intelligence/tests/test_query_understanding.py` | envelope 层断言（+31 行） |
| `intelligence/tests/test_continuous_turn_adapter.py` | 鸭子类型/归一/计数回归（+100 行） |
| `intelligence/tests/test_acceptance_trace_capture.py` | 投影/安全/倒序回归（+124 行） |
| `docs/superpowers/specs/2026-08-05-intent-routing-candidate-arbitration-design.md` | 四处纠正 |
