# 设计：领域 Harness 与底座 loop 解耦（ResearchHarness 接缝）

日期：2026-09-02
状态：**P0 已实施**（分支 `refactor/harness-loop-seams`，基于 gitea/main `18bf518b`；未合 main，未切 8792）
收据：`docs/verification/2026-09-02-research-harness-loop-decouple.md`
父稿：

- `docs/superpowers/specs/2026-08-15-agent-base-dsh-absorption-design.md`（§2 两层、§14 两刀、§9.5 静态形状对照）
- `docs/superpowers/specs/2026-09-01-finance-base-shape-alignment-design.md`（§11 后续第三条：「把领域门从 Episode 控制流里抽到外壳钩子。那是解耦，不是 `mv`」——本单就是那一条）
- `scripts/layer_audit.py` 文首（门禁保护的是「底座可替换」；修法是依赖倒置）

对照源（只读）：pi `/Users/a77/pi/packages/agent/src/types.ts`；dsh `/Users/a77/deepseek-harness` @ `99f6f02`（`packages/core/agent/src/runtime-types.ts`、`packages/core/tools/src/index.ts`）。

---

## 0. 一句话

给「金融题怎样才算答完」立一个 Protocol（`ResearchHarness`），把现在**手焊在三条 loop 里**的领域门改成 loop 调它。P0 只抽三道门：终局准入、批后停机、prompt 拼装；默认实现 `FinanceResearchHarness` 是对现有函数的纯委托，行为等价（唯一已知差见 §7）。**不换 loop、不动预算、不改 8792。**

解耦成立的判据不是「目录像 pi」，而是：**换掉 `ContinuousAgentEpisode`，领域门一行不用重写。**

---

## 1. 为什么现在做、为什么这么切

### 1.1 三条 loop 各手拼一遍同一道门

`validate_episode_finish` + `expand_episode_snapshot_bindings` + 驳回分流，在仓内被三条 runtime 各自内联：

| loop | 终局门内联点 |
|---|---|
| `runtime/agent_episode.py` | 5 处（run 主门、死钟结转、resume 修复门、`_recover_finalization`、`_carry_just_written_finish`） |
| `runtime/openai_agents_runtime.py` | 2 处（:1146、:1408） |
| `runtime/codex_headless_runtime.py` | 3 处（:924、:1017、:1415） |

改一次驳回口径要改十处；漏一处不会红。这就是「底座可替换」在今天不成立的证据：换 loop = 重抄领域门。

### 1.2 pi / dsh 都没有「终局准入」这一层——所以它必须是我们的钩子

对照原文（不是转述）：

| 时点 | pi `AgentLoopConfig` | dsh 扩展点 | 决策形状 |
|---|---|---|---|
| 进模型前 | `transformContext` | `agent/pre-step` | dsh：`reject` / `enter(messages)` |
| 工具前 | `beforeToolCall` | `tools/pre-execute` | pi：`{block, reason, terminate}`；dsh：`allow` / `deny(reason)` / `ask` |
| 工具后 | `afterToolCall` | `tools/post-execute` + `tools/result` | pi：字段级覆盖 + `terminate`；dsh：`accept(content/value, additionalContexts)` / `block(feedback)` |
| 模型停下后 | `shouldStopAfterTurn` | —（无） | pi：bool |
| **答案能不能发** | **—（无）** | **—（无）** | — |

两家的 loop 都在「模型不再调工具」处停。我们多一道：模型说完了，**还要过 FINAL_JSON 契约、证据绑定、驳回分类、修复准入**。08-15 §14 第一刀「通用底座不管对错」说的就是这层——它不能塞进任何一家的现成钩子，只能作为领域 Harness 的方法由 loop 调用。P0 把它命名为 `admit_finish`。

### 1.3 为什么不是先做 pi-shape / dsh-shape 第二条 loop

09-01 已证明两份外壳和对照臂是「同一台机器」（首轮 hash / token 带 / `financial_data`）。再写第二条 loop 之前，得先让第一条 loop 把领域门吐出来，否则第二条 loop 抄的还是那十处。顺序：**先抽门（本单）→ 三条 loop 共用（P1）→ 第二条 loop 只调门（P2）**。

---

## 2. 目标与非目标

### 2.1 目标（P0）

1. `intelligence/services/research_harness.py`：`ResearchHarness` Protocol（`runtime_checkable`）+ `FinishAdmission` 值对象 + `FinanceResearchHarness` 默认实现。
2. `ContinuousAgentEpisode.__init__(harness: ResearchHarness | None = None)`；`agent_episode.py` 内 8 处领域焊点改走 `self._harness`，**不再直接 import** `validate_episode_finish` / `expand_episode_snapshot_bindings` / `rejection_response` / `finish_rejection_fields` / `forecast_residual_halt_reason` / `split_episode_prompt`。
3. 行为等价：全量 pytest 与 main 同结果；新增测试证明默认 harness 与直接调函数逐字段相等。
4. 接缝有牙：注入一个「放行一切」的 harness，原本被驳回的终局会被接受——证明 loop 真在问 harness，不是装饰。
5. 棘轮：一条 AST 测试钉住 `agent_episode.py` 不得回退到直接 import 上述符号。

### 2.2 非目标（写死）

- ❌ 不改任何秒数 / 档位 / reserve（`R-20260816-07/-14/-21`；09-02 预算报告已否决抬 T）。
- ❌ 不动 `openai_agents_runtime` / `codex_headless_runtime`（P1，同一接缝、机械替换、另一单变量批次）。
- ❌ 不抽 PLAN 协议、修复协调器、ModeGovernor、空池回退、`_EpisodeToolAccumulator.consume`（P1/P2，见 §9）。
- ❌ 不写第二条 loop，不 import pi / dsh，不改 `finance-base-ab`。
- ❌ 不新开事件种类，不改 durable 事件 payload 一个字节。
- ❌ 不改 8792 / 启动器 / 快照。

---

## 3. 术语与两刀

| 词 | 本单含义 |
|---|---|
| **底座 loop** | `runtime/` 里拥有循环的那段代码：调模型、派工具、算超时、状态机。可替换。 |
| **领域 Harness** | `services/` 里回答「金融题怎样才算对」的那组规则：FINAL_JSON 契约、证据绑定、驳回分类、停机判定、prompt。稳定。 |
| **接缝** | loop 调 Harness 的那个方法名。P0 三条，全部有 pi/dsh 对照或明示「两家没有」。 |
| **有牙** | 换一个 Harness 实现能改变 outcome。没牙的接缝是装饰。 |

两刀（08-15 §14）在本单的落点：① `FinanceResearchHarness` 懂 A 股，`ContinuousAgentEpisode` 不懂；② 「明天做成 dsh 插件挂哪条缝」——`admit_finish` 挂不上任何 dsh 现成缝，这是**正确结果**（领域真源），不是缺陷。

---

## 4. 接缝总表（现状 → 归属）

按 `run()` 控制流顺序。「焊点」是 `agent_episode.py` 里现在直接调领域函数的位置。

| # | 时点 | 焊点（现状） | pi / dsh 对照 | 接缝名 | 归属 |
|---|---|---|---|---|---|
| 1 | 开场 | `split_episode_prompt` :733 | `transformContext` / system-prompt spine | `assemble_prompt` | **P0** |
| 2 | 开场 | `EvidenceLedger(...)` + `open_gap` :741 | —（领域账本） | `open_evidence_ledger` | P1 |
| 3 | 开场 | `_seed_opening_prefetch` :753 | `agent/pre-step`(enter with messages) | `opening_messages` | P1 |
| 4 | 每轮 | `parse_plan_candidate` / `validate_plan_revision` :1070 | —（PLAN 是领域协议） | `interpret_turn` | P1 |
| 5 | PLAN 后 | `_decide_mode` / `_run_sub_research` | —（研究模式治理） | `govern_mode` | P2 |
| 6 | 工具后 | `accumulator.consume`（prune / budget / ledger ingest） | `afterToolCall` / `tools/post-execute`+`tools/result` | `after_tool_batch` | P1 |
| 7 | 工具后 | `forecast_residual_halt_reason` :1225 | `afterToolCall.terminate` / `post-execute block` | `halt_after_tool_batch` | **P0** |
| 8 | 工具后 | `_maybe_execute_empty_pool_fallback` :1242 | —（领域回退） | `fallback_after_empty_batch` | P2 |
| 9 | 工具后 | `_append_tool_budget_state` :1264 | `transformContext`（预算可见） | 属底座，不抽 | — |
| 10 | 工具后 | `_snapshot_surface_satisfied` :1297 | `shouldStopAfterTurn` | `retrieval_complete` | **P0** |
| 11 | 模型停 | `validate_episode_finish` + `rejection_response` + `finish_rejection_fields` + `expand_episode_snapshot_bindings` + `_finish_gaps`（5 处） | **两家没有** | `admit_finish` | **P0** |
| 12 | 驳回后 | 回灌文案 :1342、`_begin_finalization` 文案 | `agent/pre-step`(enter) | `assemble_prompt` 扩展 | P1 |
| 13 | 修复 | `_recover_finalization` / `_repair_model_complete` / `RepairGoal` / `apply_unreachable_downgrade` / `EpisodeFinalizer` | —（修复准入是领域） | `repair_policy` | P2 |

P0 = #1 / #7 / #10 / #11。选它们的理由：都是**纯函数式判定**（输入 context/evidence/registry，输出值），不持有 loop 状态，抽出来不用改控制流；#11 又是三条 loop 重复最多的那道。

---

## 5. P0 协议

位置：`intelligence/services/research_harness.py`。只 import `services.*`（layer_audit 绿）。

```python
@runtime_checkable
class ResearchHarness(Protocol):
    def assemble_prompt(self, task_frame, context, registry) -> tuple[str, str]: ...
    def halt_after_tool_batch(self, *, context, batch_errors) -> str | None: ...
    def retrieval_complete(self, *, context, registry, successful_tools) -> bool: ...
    def admit_finish(self, content, *, context, evidence, registry) -> FinishAdmission: ...
```

`FinishAdmission`（frozen dataclass）把「异常驱动的控制流」改成值：

| 字段 | 接受时 | 驳回时 |
|---|---|---|
| `accepted` | True | False |
| `status` / `draft` / `bindings` / `gaps` / `caveat_slips` | 校验+展开+合并 gaps 后的结果 | `None` / `""` / `()` / `()` / 0 |
| `rejection` | `finish_rejection_fields()`（code=none） | `finish_rejection_fields(exc)` |
| `reason` / `kind` / `response` | `""` / `""` / `None` | `str(exc)` / `exc.kind.value` 或 `unclassified` / `RejectionResponse` |

`bindings` 已做 snapshot 展开与比较集展开（`draft=finish.draft`）；`gaps` 已按原 `_finish_gaps` 合并 declared + binding gaps。loop 不再自己拼这两步。

`FinanceResearchHarness`：四个方法各自一行委托到 `episode_protocol` / `forecast_residual_budget` / registry 判定。**没有新逻辑。**

---

## 6. Loop 侧改动（`agent_episode.py`）

| 焊点 | 改成 |
|---|---|
| :733 `split_episode_prompt(...)` | `self._harness.assemble_prompt(...)` |
| :938–977 死钟结转（carry + 二次校验） | `self._carry_just_written_finish` 改为实例方法，内部一次 `admit_finish`；status/gaps 直接取自 admission |
| :1225 `forecast_residual_halt_reason(...)` | `self._harness.halt_after_tool_batch(context=, batch_errors=)` |
| :1297 `self._snapshot_surface_satisfied(...)` | `self._harness.retrieval_complete(...)`；原静态方法删除 |
| :1311–1401 run 主门 | 一次 `admit_finish`；`except ValueError` 分支改为 `if not admission.accepted`，事件 payload 字段来源逐个对应（`reason` / `code` / `kind` / `disposition=response.stop_reason`） |
| :1894–1963 resume 修复门 | 同上；`finish_rejection_fields(code=..., reason=...)` 那处（:1863，与 finish 校验无关）**保留直接调用**——它不是校验，是给「修复轮还在调工具」造字段 |
| :2609–2660 `_recover_finalization` | 同上 |
| :2787 `_carry_just_written_finish` / :2820 `_carry_repair_finish` | 实例方法，走 `admit_finish` |
| :2771 `_finish_gaps` | 删除；合并逻辑搬进 `FinanceResearchHarness._merge_gaps` |

`__init__` 新增 `harness: ResearchHarness | None = None`，默认 `FinanceResearchHarness()`。`glm_agent_runtime.py` / `continuous_sub_research.py` 两处生产构造**不传**，拿默认——生产行为不变。

`resume()` 若也调 `split_episode_prompt`（实施时 grep 确认）同样改走 harness。

---

## 7. 行为等价与唯一已知差

**等价**：默认 harness 每个方法都是对原函数的同参调用；事件种类、payload 键、顺序不变；`AgentOutcome` 字段不变。全量 pytest 是回归网（main 上约 5.4k 例）。

**唯一已知差（死钟结转路径，:938–977）**：现状先调 `_carry_just_written_finish`（展开时带 `draft`），随即再校验一次并用 **不带 `draft`** 的展开**覆盖** bindings——比较集展开（`expand_comparison_set_bindings`，`draft=""` 时是 no-op）在这条路径上被丢掉。改走一次 `admit_finish` 后，该路径的 bindings 与其它四处一致（带 draft）。

可观测条件：稿含比较句（`_COMPARISON_SET_CLAIM_RE` 命中）**且**根钟在模型返回后已死。此时 bindings 是原来的**超集**（多出同题排名的兄弟证据哈希），status / draft / gaps 不变。这是把一处不一致改成一致，不是新规则；单独一条测试钉住（§8 第 6 条）。若审稿认为该保留旧行为，改法是给 `admit_finish` 加 `expand_draft: bool` 旗标——**本单不这么做**，理由：协议上长一个只为复刻一处疏漏的旗标，是把债写进接口。

---

## 8. 验收（可执行，缺一条不算）

解释器一律 `.venv-workbench/bin/python`（hooks 已警告宿主 python3 会给偏高失败数）。

1. `python -m pytest -q intelligence/tests/test_research_harness.py` 全绿，且包含：
   - 默认 harness 四方法 vs 直接调函数：接受 / 驳回（FORMAT / INTEGRITY）三种输入逐字段相等；
   - `isinstance(FinanceResearchHarness(), ResearchHarness)` 为真；少一个方法的类为假；
   - 录音 harness 注入 `ContinuousAgentEpisode`，一次 plan→tool→finish 的 episode 上，四个接缝各被调用且参数形状正确；
   - **有牙**：放行 harness 让一个 INTEGRITY 驳回（伪造哈希）的 finish 被接受为 `model_finish`；默认 harness 下同一脚本停在 `integrity_violation`；
   - 棘轮：AST 读 `agent_episode.py`，`from intelligence.services.episode_protocol import` 里不含 `validate_episode_finish` / `expand_episode_snapshot_bindings` / `rejection_response` / `split_episode_prompt`；不 import `forecast_residual_budget`。`finish_rejection_fields` 允许保留（§6 :1863 那处）。
   - §7 那条差：构造比较句稿 + 死钟，断言 bindings 含兄弟哈希。
2. `python -m pytest -q intelligence/tests/test_agent_episode.py intelligence/tests/test_repair_carry_just_written_finish.py intelligence/tests/test_episode_tools.py intelligence/tests/test_empty_pool_fallback.py intelligence/tests/test_runtime_fault_matrix.py intelligence/tests/test_tool_stage_events.py` 全绿（直接构造 Episode 的六个文件）。
3. 全量 `python -m pytest -q` 与 main 同 passed/failed 数；`python -m ruff check .` 绿；`python3 scripts/layer_audit.py` ERROR 数不超基线。
4. `git diff --stat` 里 `agent_episode.py` 的 import 段净减少；`glm_agent_runtime.py` / `continuous_sub_research.py` **零改动**。
5. 事件 payload 零改动：任选 `test_agent_episode.py` 里三条断言 `outcome.events` payload 的用例，改前改后同绿（由第 2 条覆盖，此处只要求在收据里点名）。
6. 收据 `docs/verification/2026-09-02-research-harness-loop-decouple.md`：树 / revision / 解释器 / dirty / 读数 / §7 差的实测复现。

---

## 9. 后续（本单不施工，按顺序立案）

- **P1a** 三条 loop 共用：`openai_agents_runtime` / `codex_headless_runtime` 的 5 处终局门改走 `FinanceResearchHarness.admit_finish`；验收是三条 loop 对同一份 FINAL_JSON 给出同一 `FinishAdmission`。
- **P1b** `interpret_turn`（PLAN 协议）+ `after_tool_batch`（accumulator 的 prune / budget / ledger ingest）+ `assemble_prompt` 扩展（回灌与 finalization 文案）。这三条抽完，loop 里不再出现「PLAN」「FINAL_JSON」字面。
- **P2** `repair_policy` / `govern_mode` / `fallback_after_empty_batch`。这些持有状态、改控制流，要先在 P1 之后画状态机。
- **P2'** 第二条 loop：在 `finance-base-ab/pi-shape/packages/agent_core` 里写一条**只调 `ResearchHarness` 四方法 + `ResearchToolRegistry`** 的最小 loop，跑 09-01 的同一题，硬门沿用 09-01（首轮 hash / token 带 / `financial_data`）。这一步做完，「run 层可替换」才是实测，不是设计图。
- 预算 90/60/30 与「库里没有 2024 年报」两件事**与本线正交**：前者是 Episode / 生产单（`2026-09-01-episode-budget-grant-design.md` P1 待拍 25–35s），后者是 ingest 单。本单不碰。

---

## 10. 红线

- 领域对错仍归 `FinanceResearchHarness` 背后的 `episode_protocol` / `evidence_ledger` / verifier；loop 不得自判「这数对不对」，harness 不得持有 loop 状态。
- 不得为让测试绿而改 `episode_protocol.py` 的判定；本单改动集只在 `research_harness.py`（新）、`agent_episode.py`、测试、文档。
- 不得用 `git add -A`；提交一律 pathspec。合 main 等用户确认。
- 生产快照、8792、启动器零改动。
