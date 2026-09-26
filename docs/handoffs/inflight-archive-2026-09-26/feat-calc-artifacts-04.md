# feat/calc-artifacts-04

## 这个分支做什么
能力升级任务包 04「计算与产物」（`docs/superpowers/plans/2026-09-09-capability-upgrade/04-calculation-artifacts-goal-brief.md`，在 `codex/docs-capability-upgrade-plan` 分支）。叠在 `feat/sandbox-derived-calculation@2ebbc04f`（PR #682 未合）之上：财务证据带结构化观察值、`financial_data` 多公司、沙箱 prelude v2（`fincalc` 助手 / `PARAMS` / `emit_result`）、`params` 与 `inputs_from_calc` 沿用输入、`calc-<id>.json|csv|html` 产物落 run、冻结 6 题 + 独立参照 + Workbench 验收驱动。进度真值 `…/progress/04.md`，范围外改动 `…/progress/blocked/04.md`。

## 决策与被否方案
- 计算记录走 `ToolRunResult.telemetry → tool_result 事件 → private_artifact.events`，orchestrator 在 `continuous-episode.json` 之后渲染发布。否：给 `AgentOutcome` / `ContinuousTurnResult` 加 artifacts 字段（动核心类型）；runner 直写 run 目录（破单写者）。
- 多公司靠 `subjects` 一次传；`query_scope=episode` 不改（改批次执行器越界）。
- 指标名带口径单位（`revenue_cum_yi`），累计→单季只走 `to_single_quarter`；零分母 / 缺季度 / 单位不认识回 None + note，不填 0。
- 验收实例 `RAG_WORKER_ENABLED=0` + `KB_RAG_PYTHON=/nonexistent`：16 GB 机、交换区 28 GB 已满，第二个 4.3 GB BGE worker 会把生产挤进交换（blocked §5）。

## 当前状态
提交 `42c55bda`、`2931a40e`、`aa6b83eb`，树干净。相关套件 396P；全量 pytest 正在跑（`~/.finance-runtime/calc-04/pytest-full.log`，收据按 revision 取）。8794 实例：`~/.finance-runtime/calc-04/{users,episodes,logs}`。**真实验收未完成**：模型网关 15:04 `model_cooldown`（reset ≈16:05），15:14 起 `localhost:57244` 无进程监听；01 题首探 run failed（HTTP 429 ×4、0 次工具调用），不是代码问题。已排 16:08 自动重试（session cron）。

## 已验证 / 未验证
- ✅ 数据通路端到端（脚本化模型）：`emit_result` → 派生证据 observations 含每个表格数字 → telemetry → durable 投影 → `publish_calculation_artifacts` 落 3 个文件（`test_end_to_end_structured_calculation_reaches_the_run_artifacts`）。
- ✅ orchestrator 真 RunStore 落盘 + API 下载 + 注册表投影（csv=download / html=legacy_html）在 8794 实测。
- ✅ 沿用输入：空账本 + `inputs_from_calc` + 改 `params` → 新 calc_id、`derived_from` 不变、as_of 不变。
- ❌ 真模型是否会用 `series` / `to_single_quarter` / `emit_result`、判官对派生证据的处置、正文引用计算编号——全要 live 才知道。
- ❌ 基线（2ebbc04f）同题差分未跑（需第二实例 8795，等内存与网关）。

## 下一步
1. 网关恢复后：`scripts/calc_case_acceptance.py --base-url http://127.0.0.1:8794 --cases …/progress/04-cases.json --out …/progress/04-acceptance-<tag>.json`（先 `--only 01_single_quarter`）；看第一份 `continuous-episode.json` 的 tool_result / judge。
2. 有余量再起 2ebbc04f 基线实例跑同题 `--answer-only` 差分。
3. 全量 pytest 绿后开 PR（叠 #682，#682 先合则差量自动缩小）；四项报告写进 progress/04.md。

## 踩过的坑
- 观察值 / 证据 detail 的模型视图各只有 900 / 240 字符且从头数：计算编号与产物名要放开头。
- `public_agent_evidence` 不投 `observations`：模型看不到结构化字段，财务观察文本开头列指标名。
- 模型视图里 `"derived_calculation"` 作为工具名一定出现，别拿它断言「记录没泄进上下文」，断 `telemetry` / 脚本首行。
