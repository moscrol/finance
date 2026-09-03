# 收据：能力放大与输出硬层——P0a / P0b / §3.6 两项 / §4 两个诊断字段

- 日期：2026-09-03
- spec：`docs/superpowers/specs/2026-09-02-capability-amplification-output-gate-design.md`
- 树：`/Users/a77/fwp-wt-capability-amplification` @ `spec/capability-amplification-output-gate`，基线 `gitea/main@daea04a0`
- 解释器：`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`（3.12.13，agents 0.18.3）
- 状态：**已实施、未提交、未推、未开 PR、8792 未切**。落 main 交用户（spec §6 红线）。
- 本轮**未跑任何 live 臂**；P1 / P2 / P3 / P4 的 A/B 本身不在本收据内（见「未做」）。

## 一句话

spec 里今天能落地的四块全部落地并有牙：P0a 一行授权、P0b 报告期窗口 + 披露日 as_of + 模型可传 `report_period`、§3.6 的契约守门与 `web_fetch`、§4 的 `authorized_capabilities` 投影与逐 turn `served_model`。全量 pytest 与基线同一组红（5 = `test_dream_mine` 环境项），passed 只增不减；四道 pre-commit 同款审计与能力图谱审计全过。

## 执行中改写了 spec 的三处事实

1. **§1.3 第二层从 [静态推断] 升为 [实测]。** 2026-09-03 对东财 F10 `RPT_F10_FINANCE_MAINFINADATA`（`SECUCODE=600519.SH`，`pageSize=8`，`REPORT_DATE` 倒序）只读探针：第 1–6 行 2026中报 … 2025一季报，**第 7 行 `2024年报 REPORT_DATE=2024-12-31 NOTICE_DATE=2025-04-03 TOTALOPERATEREVE=1741.44 亿`**；第 3 行 2025年报 1720.54、同比 -1.20（与 `episode.json` 证据 E7 逐字一致）。默认 6 期窗口刚好把答案挡在外面，spec 的日历推断成立。同时确认 F10 每行带 `NOTICE_DATE`（披露日）——P0b 的「as_of = 披露日」有一手字段可取，新浪 / AKShare 不给。
2. **§1.3 第一层「授权集里没有 web」从「现有产物无法区分」升为产物实证。** 私有产物 `finance-base-ab/out/reference-loop-0902b/users/*/runs/*/continuous-episode.json` 一直带 `contract.allowed_capabilities`，两臂同为 `["market_data","financial_data","kb_search","evidence_lookup","l3_lookup","finance_query","evidence_search"]`，**无 `web_search`**。缺的是 finance-base-ab 的投影（`episode.json`）没把它抬上来——§4 第一个缺口的修法因此落在投影层，不在本仓。
3. **§3.6 第 8 条「先跑一遍看谁裸着」的读数：三个。** 生产装配 `build_episode_registry` 自建的 `finance_query` / `evidence_search` / `memory_lookup` 三个 spec 没接 `contract=`——`_TOOL_CONTRACTS` 早为它们写好了条目（含 2026-08-10 冷调用 28.2s、25 行截断、空命中语义等实测依据），模型从没见过。已接上并用守门钉住（`test_tool_contract_gate.py::test_production_episode_registry_ships_no_bare_tool`）。

另有一个上一会话留下的真 bug：P0b 初版用 `\b(20\d{2})\b` 抓年份，Python 的 `\w` 含 CJK，「2024年」里 4 与 年 之间没有词边界，**对茅台问句永远不命中**——那版代码对这道题是空转。改为 `(?<!\d)(20\d{2})(?!\d)`，并写了钉子（`test_p0b_chinese_year_is_not_a_word_boundary`）。

## 改动（18 个已跟踪文件 + 4 个新测试文件 + 3 份 docs + 1 个仓外投影）

**P0a**
- `intelligence/services/evidence_capabilities.py`：`company_financial_evidence` 元组加 `"web_search"`；`runtime_capabilities_for_frame` 末尾派生 `web_fetch`（有 `web_search` 即有）。

**P0b**
- `intelligence/services/market_financials.py`：`target_report_end_from_query`（年份 + 期别 → 季末日，只认显式年份）、`periods_to_cover`（从站立日所在季度回数到目标，`max(默认, 距离)`，回溯上限 40 季）、`periods_for_financial_query`；`QuarterFinancials.notice_date`（F10 `NOTICE_DATE`）；D7 块两张表各加「披露日」列，报告期单元格带截止日 ISO（`2024年报（2024-12-31）`），口径说明加一句「每行日期是披露日，缺则报告期截止日，不是取数日」。
- `intelligence/services/ask_blocks.py`：`_financials_block_for_llm` 透传 `periods`。
- `intelligence/services/episode_tools.py`：`financial_data_runner` 窗口来源按优先级 `report_period` 参数 → 问句/主体年份 → 默认；参数传了解析不出时**说出来**（观察值前缀），trace.detail 记 `periods= / window= / target_report_end=`；证据行数随窗口放宽。
- `intelligence/services/research_tool_registry.py`：`FINANCIAL_DATA_PARAMETERS`（可选 `report_period`）+ `parse_financial_data_arguments`（空参合法，多余键拒）；`financial_data` 契约加两句（默认 6 期要点名更早的期；行日期是披露日）。
- `intelligence/tests/conformance_tools/tools.py`：`is_snapshot_tool` 判据改为 `query_scope == "episode"`（financial_data 仍是快照，解析器换了）。

**§3.6 第 8 条 契约守门**
- `research_tool_registry.py`：`ToolContractMissing` + `require_tool_contracts()`；`default_registry` 出口调用。
- `episode_tools.py`：三个自建 spec 接 `contract=_TOOL_CONTRACTS[...]`；`build_episode_registry` 出口调用守门。

**§3.6 第 9 条 `web_fetch`**
- `intelligence/services/web_research.py`：`fetch_web_page`（CDP 代理可用走渲染，否则直连 HTTP 剥标签；gb2312/gbk 解码；`invalid_url` / `disabled` / `error`（HTTP 码或异常类名+消息）/ `empty` 分状态）、`extract_page_date`（meta / `<time>` / 正文开头日期，未来日期丢弃）、`html_to_text`。
- `intelligence/services/agent_research.py`：`_web_fetch` runner（tier `public_web`、`source` = 最终 URL、`source_date` = 页面日期或抓取日且观察值标明是哪一种、`independent_key` = URL；失败观察值带原因并写明「不是页面没有该信息」）；`page_text_chunks`（800 字/段，封顶 6 段）。
- `research_tool_registry.py`：`_DEFAULT_TOOL_METADATA["web_fetch"]`、`URL_TOOL_PARAMETERS`、`parse_url_arguments`（只收绝对 http(s) URL）、`_TOOL_CONTRACTS["web_fetch"]`（三条契约逐条落）。
- `episode_tools.py`：fixture policy 关外部检索时连带 pop `web_fetch`。
- `intelligence/services/episode_progress.py`：`_TOOL_LABELS["web_fetch"] = "网页正文"`。
- `intelligence/eval/fixtures/capability_switchboard.json`：加 `web_fetch` 行（`close_via`: 授权移除 / `FINANCE_WEB_FETCH=0` / fixture policy）；`switch_box_default_v1.json` 由 `scripts/generate_default_switch_box.py` 重新生成（+1 行）。
- conformance：`tools.py` 加 `is_url_tool` / `invalid_arguments`；T-3 加 url 契约分支；T-4 按形状取坏参数。

**§4 / §3.5.4 硬门 3 `served_model`**
- `intelligence/services/llm_refine.py`：`_post_chat_message` 与 `_post_chat_message_stream` 都把响应体 `model` 放进 `message["_served_model"]`（未回 → `""`，**不**回填配置值）。
- `intelligence/services/agent_runtime.py`：`ModelTurn.served_model: str | None`（三态：None 未到 provider / "" 未回 / 非空生效值）；`to_dict()` 非 None 即写。
- `intelligence/runtime/glm_agent_runtime.py`：`_turn_from_message` 全部分支透传。
- `intelligence/runtime/openai_agents_runtime.py`：`ServedModelLog`（httpx 响应钩子，只读 JSON 响应，SSE 不读）挂在 `build_glm_sdk_model` / `build_gpt_sdk_model_factory` 自建的 `AsyncClient` 上；`AgentsSdkResult.served_models`；`runtime_result` 与修复轮 `model_turn` 事件带 `served_models`（与配置值 `model` 并列）。
- 产物落点：continuous / 参考 loop 的 `model_turn` 事件是 `turn.to_dict()`，字段自动到 `continuous-episode.json`。

**§4 投影（仓外，`/Users/a77/finance-base-ab/shape_lib/project.py`，⚠ 该目录不受版本控制）**
- 新增 `extract_authorized_capabilities` / `extract_served_models`；`notes` 加 `authorized_capabilities` / `requested_model` / `served_models` 三键，只增不改。对 09-02 两臂真实 `continuous-episode.json` 验证：授权集 7 项无 `web_search`；`served_models=[]`（那个 revision 还没落盘该字段，属实）。

**其它测试维护**
- `intelligence/tests/test_episode_factory.py`：手抄的 `RUNTIME_CAPABILITIES` 改为从 `_DEFAULT_TOOL_METADATA` 推导（加 web_fetch 时红过，同 `test_turn_control_core` 的教训）。

## 验收对照（spec §5，26 条）

| # | 条目 | 结果 |
|---|---|---|
| 1 | P0a 静态：茅台 `TaskFrame` 过 `runtime_capabilities_for_frame` 含 `web_search`；不含 web 的恰为 4 条本地盘面/技术面 | ✅ `test_capability_amplification_p0.py::test_p0a_*`（名单断言） |
| 2 | P0a 变异：去掉 `"web_search"` → 第 1 条红 | ✅ 实做：两条 P0a 测试红（`assert 'web_search' in (...)` / 名单集合差），回滚后绿 |
| 3 | P0a live：授权集含 web 且至少一臂实际调用 | ⏸ 未跑 live。投影字段已就位（`notes.authorized_capabilities`） |
| 4 | P0a 三分法读数 | ⏸ 依赖第 3 条 |
| 5 | P0b：「2024 年 600519」返回 2024-12-31 行、1741.44、D7 来源、披露日 as_of（日历固定 2026-09） | ✅ `test_p0b_maotai_question_widens_the_window_to_the_2024_annual_report`：fixture 逐字复刻 F10 8 行，`periods==7`，行 `2024年报（2024-12-31）`，`source_date=="2025-04-03"`，tier `L2_structured`，trace `periods=7; window=question; target_report_end=2024-12-31`。对照用例：无年份问句仍 6 期、2024 年报不在返回（09-02 两臂看到的世界） |
| 6 | P0b 变异：runner 不再放宽窗口 → 第 5 条红 | ✅ 实做：`periods = DEFAULT_PERIODS` 后两条端到端红（问句路径与 `report_period` 路径），回滚后绿 |
| 7 | P0b live：至少一臂以一手证据写出 1741.44 并过 `admit_finish` | ⏸ 未跑 live |
| 8 | 注册表守门：无契约 → 装配期抛；现役先跑一遍看谁裸着 | ✅ `test_tool_contract_gate.py`（4 条）：stub 进元数据 → 红；生产装配读数 3 裸 → 已接上并钉住 |
| 9 | `web_fetch`：新浪指标页 URL → tier `public_web`、as_of 非空且标明来源、source 为该 URL；不可达 → `error` 带原因 | ✅ `test_web_fetch_tool.py`（17 条，全离线打桩）：页面日期 `2025-04-03` / 无日期记抓取日并写「页面无日期，记抓取日」/ HTTP 404 · URLError · TimeoutError 都是 `error` 带原因 / 非 http 不碰网络 / 经注册表 `execute` 铸 hash 且 error 状态保留 |
| 10–12 | P1 弃权率 | ⏸ 未做（另案，见下） |
| 13–15 | P2 删句事件 | ⏸ 未做 |
| 16–18 | P3 沙箱 | ⏸ 未做 |
| 19 | P4 硬门四条落盘 | ◐ 第 3 条（逐 turn 响应体 `model`）的采集已落两臂（`test_served_model_receipt.py` 10 条：非流式/流式/三态/SDK 钩子/`runtime_result` 并列写）；其余三条是跑 A/B 时的对照项 |
| 20–23 | P4 读数 | ⏸ 未跑 |
| 24 | 全量 pytest 与基线同一组红，passed 只增不减 | ✅ 见下「读数」 |
| 25 | `layer_audit.py` ERROR 0 | ✅ 「通过，ERROR 0 条 == 基线」 |
| 26 | `graph_audit.py` exit 0 | ✅ 见下 |

## 读数

- **全量 pytest**（`.venv-workbench`，`intelligence tests`）：见文末「终读数」。三轮：① P0 + served_model 后 `5 failed / 7439 passed`；② 加契约守门 + web_fetch 后 `9 failed / 7458 passed`，多出的 4 红全是「新工具要登记到哪」的门（switchboard 双向校验、进度标签表、`test_episode_factory` 手抄上界 ×2）——按门的要求补登记，不放宽门；③ 终轮见文末。5 红恒为 `test_dream_mine.py::RunMineTests` 五例（`calls[0]` IndexError，无 LLM key 的环境项），与 spec 第 24 条写的基线一致。
- **新增测试** 64 条：`test_capability_amplification_p0.py` 33、`test_served_model_receipt.py` 10、`test_tool_contract_gate.py` 4、`test_web_fetch_tool.py` 17。
- **pre-commit 同款审计**：`audit_tool_reachability.py` 通过（声明 13 = 无条件装配 12 + 条件装配 1（memory_lookup））；`layer_audit.py` ERROR 0；`check_unread_fields.py` 无新增「写了没人读」（当前 39 文件 / 96 字段 < 基线 100）；`check_path_literals.py` 无新增；`ruff` 全过；`check_agent_workspace_facts.py` 通过。
- **能力图谱** `graph_audit.py`：exit 0（工具目录节点按 AST 计数，13 项不需改图）。

## 有意不做 / 边界

- **不跑 live**：P0a 第 3–4 条、P0b 第 7 条、P4 全部要烧两臂配额并走 `finance-base-ab` 隔离配方；spec §3.5.6 也要 P0 先落。本收据只交代码与静态读数。
- **P1 / P2 / P3 未动**：P1 要在 38 题上重跑拿基线（live）；P2 是「先量后改」的第一步（判官删句结构化落盘）——独立一刀；P3 是新子系统。都在 spec 排期之后。
- **headless 臂的 `financial_data`**：`headless_tool_gateway._is_snapshot_tool` 按「properties 为空」判快照，`financial_data` 有了 `report_period` 后走结构化路径——headless 模型须发 JSON object（`{}` 或 `{"report_period":"2024年报"}`），发纯文本会得到 `invalid_arguments` + `expected_parameters` 的可重试拒绝。这是既有的结构化工具处理方式（与 `finance_query` 同），没改网关；生产臂 `continuous_glm` 不受影响。
- **`web_fetch` 授权是派生的**，不进 `_RUNTIME_CAPABILITY_FLOOR` 表：spec §1.3 那张「不含 web 的恰为 4 条」名单因此不变。显式传 `capabilities=` 的调用方（测试、评测）拿不到派生，要自己列。
- **`finance-base-ab` 的改动不受版本控制**：`shape_lib/project.py` 只加了三个 `notes` 键与两个函数，未动 `compare.py` 的硬门（那是 P4 跑臂时的活）。
- **`served_model` 的三态**：`None` 与 `""` 是两个不同事实（没到 provider / 到了但未回），投影把 `""` 原样保留，读的人按「未回」念，不要当空缺。

## 复核路径

```
cd /Users/a77/fwp-wt-capability-amplification
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
$PY -m pytest -q intelligence/tests/test_capability_amplification_p0.py intelligence/tests/test_served_model_receipt.py intelligence/tests/test_tool_contract_gate.py intelligence/tests/test_web_fetch_tool.py intelligence/tests/conformance_tools
$PY scripts/audit_tool_reachability.py && $PY scripts/layer_audit.py && $PY scripts/check_unread_fields.py
$PY /Users/a77/agent-memory/scripts/graph_audit.py
```

变异复现：把 `evidence_capabilities.py` 里 `company_financial_evidence` 的 `"web_search"` 删掉跑 `-k p0a`；把 `episode_tools.py` `financial_data_runner` 的 `periods = (...)` 改成 `periods = market_financials.DEFAULT_PERIODS` 跑 `-k maotai`。两处都应红。

## 终读数

全量 `intelligence tests`，`.venv-workbench`，本树 @ `daea04a0`（脏，18 改 + 7 新）：

```
5 failed, 7462 passed, 15 skipped, 1 xfailed in 370.76s
```

收据 `~/.finance-runtime/test-receipts/20260902T190936Z-daea04a0.json`；`failed_ids` 恰为 `test_dream_mine.py::RunMineTests` 五例，与 spec 第 24 条写的基线同一组。`scripts/check_test_receipt.py` 对该收据判「需重跑——来自脏树」，这是它的设计（未提交改动无法被 revision 描述），不是读数问题；提交后在干净树上再跑一遍即可采信。

三轮对照：7439（P0 + served_model）→ 7458（+ 守门 + web_fetch，4 门红后补登记）→ 7462（终）；红始终是那 5 条。
