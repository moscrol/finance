# 2026-08-29 运行时后端契约符合性套件工单

> 可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。

## 背景与动机

运行时经工厂装配，循环执行器是可替换位：四个后端（`continuous_glm` / `sdk_glm` / `sdk_gpt` / `codex_headless`）+ 一个协议参照桩（`DshStubRuntime`，未注册进工厂）。2026-08-29 零成本核查（`~/Developer/career-ops/interview-prep/runtime-factory-audit-2026-08-29.md`，后端 × 不变量表）确认：**符合性断言散落在各后端单测里（各测各的），成套的跨后端统一夹具不存在**。已知的真实缺口例：codex 档判官照跑、修复静默跳过（`continuous_turn_adapter._resume_for_gap` 对无 `resume` 的 session 返回 None，无任何收据）。

本单目标：把「后端 × 不变量」表变成**一套夹具 × N 个后端**的 pytest 参数化套件，让「行为静默缺席」从只能靠人读代码发现，变成 CI 里显式的红/绿/声明不支持。

**形态决策（已定，勿改）**：pytest 套件，不是常驻服务。符合性是二值断言（确定性、零 LLM、零网络），不需要 8796 那类打分 sidecar 的运维成本。选档规则：能用 0 档复现的绝不上 4 档。

## 目标

1. `intelligence/tests/conformance/` 参数化套件：同一套契约场景逐后端跑。
2. **能力声明表**：每后端显式声明支持哪些不变量。声明支持 → 断言必须绿；声明不支持 → 断言「行为显式报告不支持」（收据/异常/outcome 字段），**静默跳过判红**。
3. **棘轮 baseline**：存量后端当前红的登记进 baseline 文件（带原因），不阻塞合并；新增后端必须全绿；baseline 只许缩不许涨。
4. 核查表中每行不变量至少一条夹具。

## 非目标（写死认领，别顺手做）

- ❌ 不做质量等价性验证（那是盲评/评测的事，2026-07-25 九题盲评已有基线 Continuous 195 / SDK 175）。
- ❌ 不改生产代码。发现「缝缺失导致某不变量无法从外部断言」时，登记 finding，不在本单重构。
- ❌ 不给 codex/SDK 补齐缺失能力（如 Scope 构造、流式）。本单只让缺席**显式化**。
- ❌ 不动工具注册表缝（12 工具 × `ToolObservation` 契约）与 providers 链缝——已立后续工单 `2026-08-29-conformance-seam-census-workorder.md`（缝普查 + 工具注册表套件 + TOOLKIT.md 资产回写）。
- ❌ 不注册 `dsh_stub` 进工厂（既有测试钉死 `"dsh_stub" not in RUNTIME_BACKEND_NAMES`）。

## 证据路径（先读这些，勿臆测）

| 文件 | 看什么 |
|---|---|
| `intelligence/runtime/agent_runtime_factory.py` | 解析 + readiness 探针（fail-closed 形状的参照） |
| `intelligence/api/app.py` 组合根（`resolve_runtime_backend()` 调用处，分发块约 L380–507） | 四路装配的真实参数；`synthesis_reserve_for_task` 仅 continuous 档、draft 流式仅 continuous 档 |
| `intelligence/runtime/continuous_turn_adapter.py` | 判官→修复链；`_resume_for_gap` L1165 鸭子类型探测 `resume`（静默跳过点）；`start` 探测 L560 |
| `intelligence/runtime/agent_episode.py` | `run` L683 / `resume` L1554；修复轮 `synthesis_reserve=0`；冷启动三道准入 |
| `intelligence/runtime/episode_tool_batch.py` | 批次上限 4 / 全局 8 worker / 共享 deadline / 取消排空 / 排队与执行分账 |
| `intelligence/services/runtime_handle.py` | 六态生命周期 + docstring 里「哪些臂接了、哪些没接、为什么」的逐条裁定 |
| `intelligence/services/agent_runtime.py` L444 | `ResumableAgentRuntime` 协议（runtime_checkable） |
| `intelligence/runtime/dsh_stub_runtime.py` + `intelligence/tests/test_dsh_stub_runtime.py` | 脚本化参照实现——夹具驱动方式直接抄它 |
| 既有 test doubles：`test_glm_agent_runtime.py` / `test_continuous_turn_adapter.py` / `test_codex_headless_runtime.py` | 假模型客户端、假 model factory、`CODEX_HEADLESS_BIN=sys.executable` 假 CLI 的现成做法，**复用勿重造** |

## 不变量清单（夹具即此表，编号入库）

| # | 不变量 | 断言形状 | 预期首轮结果 |
|---|---|---|---|
| INV-1 | 未授权工具不可见/不可调 | 契约不含 capability X → 模型可见工具表无 X；脚本化模型强行调 X → 落 `invalid_actions`/拒绝收据 | 四后端应绿 |
| INV-2 | 工具预算耗尽强制收工 | 预算 N，脚本化模型请求 N+1 次 → 第 N+1 次不执行，进入 finalization，`stop_reason` 如实 | 应绿 |
| INV-3 | 绝对 deadline + 合成保底 | 检索窗烧穿场景 → 合成仍拿到 ≥ reserve 的窗口；修复轮 reserve=0 | continuous 全量；SDK 缩减版按其声明断言；codex 声明不支持 |
| INV-4 | 取消语义 | 批次执行中置取消 → 未完成调用落 `rejected/cancelled`，无新派发；`QueryPublishGuard` 回滚 | 待实测 |
| INV-5 | 判官缺口 → 修复续跑**或显式报告不支持** | 造一个必然缺口的 outcome → 断言发生 resume，或收据/结果里有显式 `repair_unsupported` 类标记 | **codex 预期红**（静默跳过）→ 进 baseline，这就是本单的样板案例 |
| INV-6 | trace/收据对账 | `model_turn`/`tool_request`/`tool_result` 成对完整；接了 Handle 的臂六态收据合法（只进不退） | 按声明 |
| INV-7 | finish 协议 | 悬空引用（bindings 指向不存在的证据）→ 拒绝/修复，不直出 | 应绿 |
| INV-8 | resume 五不变量（仅声明 resumable 的后端） | episode 身份不变 / task_frame_hash 校验 / 事件不丢 / 前缀不改写 / 必产新 model_turn | GLM/SDK/stub 跑；codex 声明不支持即过 |

## 步骤

1. 开分支：`git checkout main && git pull && git checkout -b test/runtime-conformance-suite`。开工三连（status/branch/worktree）+ 逐条认领 status。
2. 建 `intelligence/tests/conformance/`：`backends.py`（后端参数注册表 + 能力声明表）、`fixtures.py`（脚本化模型/契约/注册表夹具，复用既有 doubles）、`test_inv_*.py` 每不变量一个文件。
3. 能力声明表初值：从核查表抄（该表每格已给出处）；执行中发现表与代码不符，**以代码为准并回写核查表**。
4. 棘轮 baseline：`intelligence/tests/conformance/baseline.py`（或 JSON），格式 `{"INV-5:codex_headless": "修复静默跳过，_resume_for_gap 无 resume 返回 None，2026-08-29 登记"}`。断言逻辑：红且在 baseline → xfail（strict=False）；红且不在 → fail；绿但在 baseline → 提示清账（strict xpass 报错，逼人删行）。
5. 全套用 `.venv-workbench/bin/python -m pytest intelligence/tests/conformance/ -q` 跑通。
6. 交付物附一页 `README.md`（套件内）：怎么加新后端、怎么清 baseline、能力声明表怎么改。
7. 通用件回写：套件形态（参数化符合性 + 能力声明 + 棘轮 baseline）属「审计」件,在 `~/harness-reference/KIT.md` 追加一行指针，不另建清单。

## 验收

- [ ] 四后端 + stub 全部进参数表；每个 INV 至少一条夹具。
- [ ] `continuous_glm` 全绿。
- [ ] INV-5 在 codex 档如预期红，且以 baseline xfail 形式存在（这是套件有效性的阳性对照）。
- [ ] baseline 每行带原因与日期；无一条「不明原因 xfail」。
- [ ] 零网络、零真实 LLM 调用、零生产代码 diff（`git diff --stat` 只含 tests/ 与文档）。
- [ ] 叶子检查绿：`.venv-workbench/bin/python -m ruff check . && .venv-workbench/bin/python -m pytest -q`（受他人在途改动影响时按 AGENTS.md 只跑 pathspec 范围并如实登记条件）。
- [ ] 分支推 gitea，**不合 main**，交接文档登记（`docs/handoffs/inflight/test-runtime-conformance-suite.md`）。

## 红线

- 禁 `git add -A`，一律 pathspec 提交；不合 main、不强推。
- 不改生产代码（含「顺手修」INV-5 的静默跳过——那是发现，不是本单任务）。
- 用 `.venv-workbench/bin/python`，宿主 python3 缺依赖会得到假失败数。
- 若需登台账号：`python3 scripts/claim_ledger_id.py claim --branch test/runtime-conformance-suite`，禁手工取号。
