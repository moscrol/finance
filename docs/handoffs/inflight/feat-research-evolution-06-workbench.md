# feat/research-evolution-06-workbench · 2026-09-14 · 研究进化 06：两轮返修完成，等用户确认合并

## 这个分支做什么

01–05 接进既有 Workbench 会话（GET 投影 + actions/bindings/events + 前端「维护」页），06 只组装不改域算法，单 writer `EvolutionStore`。**两轮 QC 的 22 条（S1–S3/R1–R10 + Q1–Q9）全部返修完**。

## 第二轮关键决策（Q1–Q9）

- Q2 终态收尾：观察器 claim 终态后回调 `facade.fold_run_terminal`（app.py 注入），幂等键 `link_run:{item}:{run}:terminal` 与客户端恢复路径共用；缺新判断诚实拒绝、项可恢复。
- Q3 折回硬闸：必须有**运行中登记的** run_links 行；「同会话」只是注册闸。残留风险：运行中的旧 run 可先注册再折回，彻底关死要 run 来源签名（不存在）。
- Q5 无事件幂等记录：`store.append_action_record`（`event=None`，不进 01 折叠）覆盖「动作被接受但无状态迁移」；终态同键重试升级折回（派生键 `:terminal` 去重）。
- Q9：`store.try_transaction(timeout)` 有界等待；观察器一切写入走它，超时 stderr「跳过」。
- 顺手修：`create_binding` 的 created_at/baseline_cutoff 时区口径（上海日 vs UTC 刻，00:00–08:00 必误拒）；`ContinuationRequest.click_payload` 穿过消息边界。

## 当前状态

- 复审探针对候选树全绿：`test_review_contracts.py` 10/10、`probe_cas.py` 正确、`ResearchEvolutionReview.test.tsx` 3/3。
- 全仓 `pytest -q --ignore=test_codex_sandbox.py`：**10022 passed / 0 failed**，收据 `~/.finance-runtime/test-receipts/20260913T163415Z-089526ab.json`（revision=代码 HEAD `089526ab`，dirty=false；之后的 docs 提交不改代码）。
- 前端：vitest 90、lint/typecheck/build 全过；e2e research-evolution 15 + 新绑定真链路 1（desktop）+ workbench 5 全过。
- **代码 SHA = `089526ab`**；文档提交在其后。等用户确认合并（顺序：规格分支先进 main）。部署未做。

## 抓手

- 06 入口：`intelligence/services/research_evolution/`（facade/store/run_observer）+ `intelligence/api/research_evolution.py` + 前端 `ResearchEvolutionPanel.tsx`。
- 合同测试：`intelligence/tests/test_research_evolution_rework.py`（25 例：返修 17 + Q1–Q9 移植 8）。
- 绑定 e2e：`intelligence/webapp/e2e/research-evolution-binding.spec.ts` + `prepare_re06_fixture.py`（playwright 第二台 webServer，8794，自带真实市场库）。
- 复审记录：`/Users/a77/.finance-runtime/reviews/research-evolution-06-ba10747d/`。
- e2e 在这棵树必须 `WORKBENCH_PYTHON=/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。
