# 在途交接 · spec/capability-amplification-output-gate

- **工单**：`docs/superpowers/specs/2026-09-02-capability-amplification-output-gate-design.md`
- **收据**：`docs/verification/2026-09-02-capability-amplification.md`（含全部读数、合入后门禁、**P0 live 读数**与复核路径）
- **状态**（2026-09-03 10:45 CST）：**已上生产。** 8792 于 10:41 切到 `ccf9343162d0`（0903b，= #537 代码 + #538 docs），切前 P0 live 两臂在同一快照上读数：两臂 `model_finish`、都只调一次 `financial_data`（Episode 臂传 `report_period=2024年报`）、都以一手证据写出 1741.44（披露日 as_of）、授权集 9 项含 web、`served_models` 与请求一致；生产探针每个 `model_turn` 带 `served_model`。§5 第 7 条 ✅、第 4 条落 (a)、第 3 条 ◐（授权 ✅、实际调用 ✗——一手证据先到手，web 没被需要）。回滚锚 `cutover-20260903b-rollback-8792.txt`。
- ~~**开放项**：两臂首轮 `input_tokens` 14513 vs 14517，差 4 打穿配方 ±3，方向与 P2' 相反、来源未定位~~ → **09-03 静态定位并修（PR #542）**：首轮 user 消息里 `research_contract.task_id` = `run_<时间戳>:msg_<32 位 hex>`，每次运行不同，hex 串分词数随机——两条 loop 的 `[system, user]` 本来就出自同一个 `assemble_prompt`，差的从来是这个 id，不是 loop。#542 让 prompt 不再渲染该键（模型用不上、协议不解析），同题首轮请求跨运行逐字节相同，钉子 `test_first_request_is_byte_stable_across_run_ids`。`finance-base-ab` 的 ±3 硬门自此量的是真差异。
- **分支历史**（2026-09-03 10:20 CST）：**PR #537 已合 `gitea/main=88ac7917`**（实现 `91ddd5c5` + docs `c96cff23` + 合 main `f472f1a8`）。主干门禁 @`f472f1a8` 干净树规程壳整仓全量 **7524P/5F/15S/1X**（收据 `20260903T020730Z-f472f1a8.json`，`check_test_receipt --expect-revision --base-drift-max 5` ✅），5 红 = `test_dream_mine` 基线同组，passed +70 = 64 新增 + 6 条 conformance 参数化；规程壳下 collect-only 逐条对比 main 零丢失。**8792 未带本 PR**：同日 10:11 切到 `6d4a9df1`（= #531–#535 批，本 PR 之前的 main 尖），按两步切流方针，本 PR 上生产要等下面第 2 步的 live 读数。
- **树**：`fwp-wt-capability-amplification` 已拆（补丁在 main、树干净），分支保留在 gitea。后续 live 从含 `88ac7917` 的 main 快照 + `finance-base-ab` 配方跑，不需要这棵树。解释器仍是 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。
- **仓外半边已入库**：`/Users/a77/finance-base-ab` 09-03 `git init` 并推到 `gitea:a77/finance-base-ab`（私有，首提 `10e544c`；`out/` 产物不入库）。`shape_lib/project.py` 三键投影与 `run-reference-loop.sh` 自此有版本。

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

1. ~~用户过目 → 提交本分支 → PR → 主干门禁~~ → 已完成（#537，见上）。
2. ~~P0 live 读数 → 第二次切流~~ → 已完成（09-03 10:36 两臂，10:41 切流；读数见收据「P0 live 读数」节）。
2b. **P0a 单独起效的题**（另案，可选）：本轮 web 授权没被用到，因为 `financial_data` 够得着。要看 P0a 本身，得换一道结构化库里没有的题（如非 A 股公司、或披露日之前的事件）再跑一次两臂。
3. P1 弃权率：**第一步已落（PR #541）**——`intelligence/eval/abstention.py` 分类器 + 消融壳逐题字段 / 并列聚合 / 报告模板 + 08-27 四臂 38 题回溯基线（`docs/verification/2026-09-03-abstain-rate-baseline-offline.md`：组件臂未见题 10/10 复现；8792 该答 32 题弃 8，其中 7 道判官不可用扣稿、模型自弃 1）。**第二步待用户点头（烧配额）**：在含 #537 的快照上**经会话链**重跑 38 题（消融壳走 legacy `ask`，不经 episode；P0 的效果只能在 episode 链上量），产物用 `classify_episode` 判，先看当天 `judge_unavailable_count`。
4. P4（`AGENT_RUNTIME_BACKEND=sdk_glm`）：前置已清——硬门第 3 条 `served_model` 字段在（#537）、首轮请求字节稳定（#542）；剩 `run-reference-loop.sh:48` 写死的 `continuous_glm` 改可覆盖（走 `finance-base-ab` 仓提交）。烧两臂配额，待用户。
5. P2 第一步（判官删句结构化落盘，**不改判据**）、P3 另冻题集——各自另案。

## 边界（读收据前先知道）

- headless 臂调 `financial_data` 现在要发 JSON object（结构化工具路径，同 `finance_query`），纯文本会得到可重试的 `invalid_arguments`；生产 `continuous_glm` 不受影响。
- `web_fetch` 授权由 `web_search` 派生（`runtime_capabilities_for_frame`），不进策略表；显式传 `capabilities=` 的调用方要自己列。
- 全量 5 红 = `test_dream_mine` 环境项，与基线同一组。
