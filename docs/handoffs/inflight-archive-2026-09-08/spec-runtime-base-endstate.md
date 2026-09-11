# spec/runtime-base-endstate · 运行底座终局（pi / dsh 工程设计补齐）+ P0 落地

更新：2026-09-07 · 树 `/Users/a77/fwp-wt-runtime-base` · 基线 `gitea/main@504cbbc9`

## 这条线做什么
用户拍板「换不了底座，就把 pi / dsh 的工程设计里我们欠缺的补上，达到他们那种运行底座的效果；领域 harness 另由 agent 打磨」。母本 `docs/superpowers/specs/2026-09-07-runtime-base-endstate-design.md`：六条不变量 R1–R6、十条 [实测] 差距 G1–G10、五阶段 P0–P4、与 harness 的文件级分工（§5）、待拍板五题（§12）。INDEX #27 母单。

## 当前状态
- 终态稿已落，**待用户审 §12**（未拍板前按推荐执行）。
- **P0 已落地（零行为改动）**：`services/episode_messages.py`（`derive_messages` 纯 fold + 四种消息构造器 + 三个发射助手 + `check_derivation`）；三种新 durable kind `prompt_assembled` / `model_input` / `tool_budget_state`；`tool_result` / `tool_error` 事件加 `model_content`；两条 loop 每次 `model.complete` 前对账（生产记 `EpisodeScope.dump()["derive_mismatches"]` 不炸，`conftest` 强制 `FORESIGHT_STRICT_DERIVATION=1` 测试即炸）；`project_durable_events` 默认剔模型可见正文只留 sha256 + 字符数（`include_model_visible_text` 给私有读者）；`scripts/gen_runtime_catalog.py` → `docs/runtime/{events,tools,harness-seams}.md` + `test_runtime_catalog` 保鲜。
- 门禁：ruff 0、`layer_audit` 0、全量 pytest 见分支最新收据（`~/.finance-runtime/test-receipts/`）。两条既有测试因契约变化改断言：`test_agent_episode` 首轮前事件 `["task"]` → `["task","prompt_assembled"]`；`test_research_harness` 的缩进敏感 needle 改正则。
- P1–P4 未开：各开工单与分支，编号分派时取。

## 卡点 / 需要用户的
1. §12 五题拍板（存储后端 JSONL vs SQLite；拆码要不要 live 探针；重启后只登记还是自动恢复；P3 Workbench 端点本轮做不做；编号方式）。
2. 本分支合 main 需用户确认（AGENTS.md 纪律）；P0 零 live 判据，随下次切流带上即可。
3. 与 harness 那拨 agent 的分工以 §5 为准；两处接触点（`ToolSpec.replay`、`admit_inbox_message`）分别在 P2 / P3 开工前单独过。

## 下一步（本线）
1. 用户审过 §12 → P1 开单：`EpisodeMessage` 类型 + `CancelCause` + `tool_not_dispatched` 拆码（一次 live 探针）。
2. P2 前先补一条：`EpisodeFinalizer.recover` 的兜底 prompt 也发 `prompt_assembled{source: finalizer}`（§6.1 已知边界 a）。

## 不要做
- 不动 `research_harness.py` 16 方法语义、不动 90/60/30、不动 Evidence Ledger / verifier。
- 不 import pi / dsh、不拷源文件、不把 lanes / Cordis / LLM 压缩当本线缺口。
- 不在本分支切 8792。
- 改了 `DURABLE_EVENT_KINDS` / `_TOOL_CONTRACTS` / `ResearchHarness` 签名后忘了跑 `python3 scripts/gen_runtime_catalog.py`——`test_runtime_catalog` 会红。
