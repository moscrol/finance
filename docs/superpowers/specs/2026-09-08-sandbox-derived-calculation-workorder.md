# 工单 #41 · 沙箱按 `derived_calculation` 落地（能力扩张，不是修复）

> 母稿：`2026-09-02-capability-amplification-output-gate-design.md` §3.4（协议）、§3.6（三条契约）、§5 第 16–18 条（验收）。
> 分支：`feat/sandbox-derived-calculation`（基线 `f90af450`，P0–P3 运行底座已合）。状态：✅ 代码已落、门禁绿、PR 待用户确认（2026-09-08）。
> 判据：产物强制携带 `input_evidence_hashes` + `script` + `as_of`（取输入最旧）；沙箱不外呼不写库；无输入链的派生证据绑不进结论；跨源口径核对端到端跑通。
> 用户拍板（09-08）：「按最优推进沙箱，knevo 有的工具我们也要有」——机制由执行方定，见「决策」。

## 这一刀开的是什么

现有工具全是**取数**：茅台题、react 1.000 vs 8792 0.357 都是取数类，沙箱一个都不修，冻结题集上测不出信号。它开的是一类目前**完全答不了**的题：两个来源同一指标不一致谁对（D 系列 21 个证据块冲突了没人裁）、差额 / 敏感性、统计检验。第一个用例按母稿建议选**跨源口径核对**而不是 DCF——两边都是已绑定证据、有真值可判、`input_evidence_hashes` 天然完整。

## 决策：两层隔离，产物记档

| | 只用 macOS `sandbox-exec` | 只用子进程 + 环境清洗 | **两层（本单）** |
|---|---|---|---|
| 拦外呼 / 越界写 | 操作系统级，ctypes 也过不去 | Python 层守卫，原则上可被 ctypes / 直接 syscall 绕过 | 进程层永远开；Seatbelt 在 macOS 上叠加 |
| 跨机器 | 只有 macOS；Apple 已标 deprecated（仍在位，pi 的 sandbox 扩展与 Anthropic sandbox-runtime 都用） | 任何机器 | 测试任何机器都跑；生产 Mac 得到系统级门 |
| 调通成本 | allow-list profile 给 Python + DuckDB 是无底洞 | 低 | deny-list profile 三条规则，实测一次过 |
| 可复现性 | 高 | 高（`PYTHONHASHSEED=0`、独立进程、从零构造 env） | 同左 |

产物字段 `enforcement ∈ {seatbelt+process, process}` 如实记这次是在哪一档隔离下算的。`FORESIGHT_SANDBOX_SEATBELT=0` 只关系统层，不关工具。**没选**：bwrap（Linux）、Docker / gVisor / Firecracker（给 90 秒量级的本机 episode 加一套运维面）、Pyodide / WASM（没 duckdb）、托管 code interpreter（产物不带本仓 hash / as_of / source，进不了 `admit_finish`，母稿 §3.5.5）。

## 落地形状

- `intelligence/services/calculation_sandbox.py`：执行层。独立解释器 `-s -B -P`、从零构造的 env、一次性工作目录、stdin 关闭、CPU / FSIZE / NOFILE rlimit、墙钟超时（CPU 限先杀也算超时）；版本化 prelude（`PRELUDE_VERSION` 进 calc_id）换掉 `socket.*`、拦 `urllib.request` / `subprocess` / `http` 等 import、写模式 `open` 只许工作目录、`os.system` / `fork` / `exec*` 一律拒；给脚本 `EVIDENCE` / `duckdb_connect()`（只读）/ `emit()`（唯一结果出口，哨兵行）。Seatbelt profile：`(deny network*) (deny process-fork) (deny file-write*)` + 工作目录放开。
- `intelligence/services/derived_calculation.py`：产物 `DerivedCalculation`（calc_id = sha256(prelude 版本 | 脚本 | 排序后的输入哈希 | DuckDB 指纹)、`input_evidence_hashes`、`input_refs`、`as_of`、`result`、`enforcement`、运行时读数）；`run_derived_calculation` 纯函数；`derived_evidence` 铸成 `evidence_tier=derived_calculation`、`source_date=as_of`、`derived_from=输入哈希` 的证据（数值结果同时进 `observations`）；`bind_derived_calculation_tool(evidence_ledger)` 按 episode 绑 runner（读账本对象，第 N 轮算前 N−1 轮的证据）。
- 注册表：`_DEFAULT_TOOL_METADATA` / `_TOOL_CONTRACTS` / 参数面 `DERIVED_CALCULATION_PARAMETERS` / `parse_derived_calculation_arguments` / `derived_calculation_tool_spec`；`produces={supporting_evidence}`（词表规矩 output_id ≠ 工具名，「派生」由 tier 说明）。`replay="safe"`。
- 绑定点：`ContinuousAgentEpisode._with_episode_bound_tools`（原 `_with_sub_research_tool` 改名，先绑派生计算再绑子研究）；`HarnessReferenceLoop` 无证据账本，没有此工具。
- 授权：`runtime_capabilities_for_frame` 从 `financial_data` 派生（与 `web_fetch` 从 `web_search` 派生同理），不单独进策略表；纯盘面 / 技术面 / 知识题不给。
- 门：`validate_episode_finish` 新增 `derived_without_inputs`（INTEGRITY，与伪造哈希同族）。`AgentEvidence.derived_from` 新字段，不进内容哈希。
- 开关板：`capability_switchboard.json` / `switch_box_default_v1.json` 各加一行；`docs/runtime/tools.md` 重生成（15 个工具）。

## 三条契约（§3.6）落点

1. 空结果语义：没 emit / 报错 / 超时 / 越界 / 本回合无证据 → 结构化错误码（`no_result_emitted` / `script_error` / `sandbox_timeout` / `sandbox_violation` / `no_bound_evidence` / `script_rejected` / `sandbox_unavailable`），观察值写明「不是任何数值、不能当否定证据」。
2. 来源分档与 `as_of`：档次不高于输入最低档；`as_of` 取输入最旧，不是运行日；与 provider 数不一致时看输入是否同一批。
3. 参数与拒绝：四个键各按类型读，多余键 / 空脚本 / 空目的 / 超时越界拒；禁用模块在 runner 里回码（模型改一次脚本就能过，不按参数错计 invalid_action）。

## 验收（§5 第 16–18 条）

- 16 ✅ `test_finish_bound_to_derived_evidence_without_inputs_is_rejected_as_integrity`：去掉输入链 → `derived_without_inputs`；带链 → 放行。变异：把门关掉 → 红。
- 17 ✅ `test_as_of_is_the_oldest_input_not_the_run_date`：2025-04-03 / 2025-05-01 两条输入 → 产物 2025-04-03。变异：取最新 → 3 红。
- 18 ✅ `test_cross_source_reconciliation_end_to_end_keeps_the_hash_chain`：`ContinuousAgentEpisode` + 脚本化模型，两源净利润 1741.44 / 1740.0 → 派生证据 `derived_from` == 两条输入哈希、`as_of` == 2025-04-03、结论绑 E1/E2/E3 被 `admit_finish` 接受、`tool_result` 事件带 `calc_id`（严格派生全程开着）。
- 沙箱层：进程守卫（网络 / import / 起进程 / 越界写）四红当守卫整段关掉；Seatbelt 单独一层（Python 守卫关掉）实测拦下 connect / 越界写 / fork（`PermissionError`）；DuckDB 只读（insert 失败）。

## 已知边界

- 脚本里 `EVIDENCE[i]["ref"]` 的 E 号按证据账本序编；账本跳过晚于信息截止日的证据而模型视图不跳，极少数情形两边错一位——脚本同时拿到 hash / tool / observations，产物 `input_refs` + 哈希可对账。
- `input_evidence_hashes` 是**本回合全部已绑定证据**（母稿原文），不是脚本实际读过的子集；「实际读过哪几条」的遥测未做。
- 挂 DuckDB 用生产库文件的只读连接 + 路径 / 大小 / mtime 指纹进 calc_id，没做快照拷贝。
- Seatbelt 只在 macOS；Linux 生产（若有）落 `enforcement=process`。
- 无 CLI / Workbench 入口；第二条 loop（`HarnessReferenceLoop`）无此工具。
- 还没另冻计算类题集，母稿说的「衡量它得另冻一组」未做。

## 不做（写死）

不给写库、不外呼、不做托管 code interpreter、不让模型写 SQL 直连生产库改数据、不做 allow-list Seatbelt profile、不为沙箱换底座。
