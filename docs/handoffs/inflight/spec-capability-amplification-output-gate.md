# 在途交接 · spec/capability-amplification-output-gate

- **工单**：`docs/superpowers/specs/2026-09-02-capability-amplification-output-gate-design.md`（本分支 untracked）
- **收据**：`docs/verification/2026-09-02-capability-amplification.md`（本分支 untracked，含全部读数与复核路径）
- **分支状态**（2026-09-03）：P0a / P0b / §3.6 两项 / §4 两个诊断字段 **已实施、未提交、未推、未开 PR、8792 未切**。基线 `gitea/main@daea04a0`。落 main 那一下交用户（spec §6）。
- **树**：`/Users/a77/fwp-wt-capability-amplification`；解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`（本树没有自己的 venv）。

## 交付物

| 块 | 落点 | 钉子 |
|---|---|---|
| P0a 补授权 | `evidence_capabilities.py` `company_financial_evidence` + `web_search` | `test_capability_amplification_p0.py::test_p0a_*`（含 4 条名单断言；变异实做红） |
| P0b 报告期窗口 | `market_financials.py`（`target_report_end_from_query` / `periods_to_cover` / `notice_date` / 披露日列）、`episode_tools.py` runner、`research_tool_registry.py`（可选 `report_period`）、`ask_blocks.py` 透传 | `test_p0b_*`（fixture 逐字复刻 09-03 F10 live 8 行；变异实做红） |
| §3.6 #8 契约守门 | `require_tool_contracts` 在 `default_registry` / `build_episode_registry` 出口；三个裸 spec 接上契约 | `test_tool_contract_gate.py` |
| §3.6 #9 `web_fetch` | `web_research.fetch_web_page`、`agent_research._web_fetch`、注册表条目/URL schema/契约、进度标签、开关板行 | `test_web_fetch_tool.py`（全离线）、conformance T-3/T-4 加 url 形状 |
| §4 `served_model` | `llm_refine` 两条路径 → `ModelTurn.served_model` → `model_turn` 事件；SDK 臂 `ServedModelLog` httpx 钩子 → `runtime_result.served_models` | `test_served_model_receipt.py` |
| §4 `authorized_capabilities` | **仓外** `/Users/a77/finance-base-ab/shape_lib/project.py` `notes` 加三键（该目录不受版本控制） | 手工对 09-02 两臂真实产物验证，见收据 |

## 下一步（按 spec 顺序）

1. 用户过目 → 提交本分支（pathspec：上表文件 + 两份 docs）→ PR → 主干门禁。
2. P0 live 读数（§5 第 3、4、7 条）：`finance-base-ab/run-reference-loop.sh` 同题重跑；`episode.json` 现在会带 `notes.authorized_capabilities`（应含 `web_search` / `web_fetch`）与 `notes.served_models`。三分法记。
3. P1 弃权率基线（38 题 live）→ 然后才是 P4（`AGENT_RUNTIME_BACKEND=sdk_glm`，`run-reference-loop.sh:48` 写死的 `continuous_glm` 要改成可覆盖）。
4. P2 第一步（判官删句结构化落盘，**不改判据**）、P3 另冻题集——各自另案。

## 边界（读收据前先知道）

- headless 臂调 `financial_data` 现在要发 JSON object（结构化工具路径，同 `finance_query`），纯文本会得到可重试的 `invalid_arguments`；生产 `continuous_glm` 不受影响。
- `web_fetch` 授权由 `web_search` 派生（`runtime_capabilities_for_frame`），不进策略表；显式传 `capabilities=` 的调用方要自己列。
- 全量 5 红 = `test_dream_mine` 环境项，与基线同一组。
