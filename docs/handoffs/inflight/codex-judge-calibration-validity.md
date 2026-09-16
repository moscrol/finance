# codex/judge-calibration-validity

实施 `docs/superpowers/plans/2026-09-14-judge-calibration-validity.md`：主评/补评/重评只能用**同一有效评审批次**出结论；未知身份的记录可读可探索，但不产生 `callable`。

树 `/Users/a77/fwp-wt-judge-calibration-validity`（非 `.claude/worktrees/`），主树 `/Users/a77/finance-workspace-private`。HEAD `26f18e99`，干净，**已推 gitea、未合 main、未部署**。

## 状态：Task 1–5 已实施并验收，等合并授权

`09c3a8b5`(T1–4) → `184eac97`(资格门反证) → `7117125e`(覆盖率收口 `batch_coverage`) → 文档三提交 → `ffb0d281`(并 `main@c29a6401`，解两处冲突) → `26f18e99`(并 `main@d433b907`，无冲突)。本轮＝并主干＋落 P1＋重跑全部验收。

- **冲突两保**：主干的 token 计费与本枝的身份证据写**同一条** `LLMCallRecord`，不新开账本；`records_for_call()` 与 `summary()` 收口成唯一投影 `_record_to_dict`。删 `GrokCliResponse`，元数据并入 `GrokCliText`（保 `str` 子类契约）。
- **P1**（`identity_state` 三态跨层无一致性断言）：新增 `intelligence/call_identity.py` 三常量，接入 `llm_refine.py`(6)/`eval/judge_validity.py`(4)/`run_quality_ablation.py`(2)，＋`tests/test_call_identity_contract.py`。定位**防漂移**，无证据说它此前放行过未知身份。

## 已验证（全对 `26f18e99`，解释器 `<主树>/.venv-workbench/bin/python`）

全量 `pytest -q` **11359P/0F/83S/2xfail**（901 s）；`ruff check .` 0；frontend 四步全过、vitest **107P**；e2e **34P/2S**；registry 五项 0。
收据 `~/.finance-runtime/test-receipts/20260916T152203Z-26f18e99.json`，`check_test_receipt.py --expect-revision 26f18e99` 七项全过。变异反证：服务层误标身份→3 红，评测层常量拼错→3 红，还原全绿。
详解 → `docs/handoffs/2026-09-16-judge-calibration-main-integration.md`。

## 未验证 / 边界

- **没调过真实判官**：全部假传输 + 内存夹具，零付费调用。「门会拦」已证，「真实模型分差与质量增益」**未测**。
- 结论只覆盖 legacy `intelligence.cli ask --compose`（引擎 B），**不代表 Workbench Episode**；已登记在 `docs/agent-product-door.md`。
- `decision=callable` ≠ 合并授权；判官身份只取响应结构化字段，是「按对端声明相同/不同」的审计强度，不等于已认证真模型。旧 v1 收据不追认。
- 未改生产判官准入与时间长河写入，未重测生产库覆盖面。

## 下一步

PR 已开，**合入 main 等用户确认**。真实模型消融（唯一没做的验证类别）：先按 `probe-shared-llm-gateway-before-a-batch` 预检网关，再串行逐题。

## 坑

- `e2e/research-evolution-binding.spec.ts` 硬编码 `RE06_E2E_URL ?? "http://127.0.0.1:8794"`，**端口与 URL 不联动**：只改 `RE06_E2E_PORT` 会被拒，两个都要传。
- 本树无 `.venv-workbench`（在主树），跑 e2e 必须显式 `WORKBENCH_PYTHON=<主树venv>`，否则 webServer 先死。
