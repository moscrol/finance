# feat/no-llm-judge-mode

工单 **#55**（`docs/superpowers/specs/2026-09-17-no-llm-judge-deterministic-gate-workorder.md`）：用户 09-17 决策「不用 LLM 判官」。代码尖 `89e8066e`，**PR #781 已合入 main（合并提交 `4d19dc6a`，2026-09-17 13:13 CST），8792 已切 `bf662e9310ff`（含 #781 + #779），但启动器未改——`ASK_SEMANTIC_JUDGE` 未设，生产仍跑 `llm` 模式**。开关翻到 `off` 是工单 §5 第 10 步，需用户另行确认（见下「未做 / 边界」）。原工作树 `/Users/a77/fwp-wt-no-llm-judge` 与分支均已在合并后删除。

## 合并与部署读数（2026-09-17，独立复算）

合并预演树 `b094abf9`（= `gitea/main@18859d37` + #781 + #779，与合并后 main 的树 `239907a4` 逐字节相同）四叶全绿：
pytest **11435 passed / 0 failed / 81 skipped / 2 xfailed**（收据 `20260917T044627Z-b094abf9.json`，
`check_test_receipt.py --expect-revision b094abf9 --base-drift-max 5` 八项全过）、ruff 0、
前端 lint/typecheck/vitest 107/build（`intelligence/api/static` 产物与已跟踪文件零 diff）、
e2e 34 passed / 2 skipped（端口族 `WORKBENCH_E2E_PORT=8793` + `RE06_E2E_PORT=RE06_E2E_URL=8795`）、registry 五项 exit 0。
8792 切换收据 `~/.finance-runtime/cutover-20260917b-bf662e93-8792.md`，回滚锚 `cutover-20260917b-rollback-8792.txt`。

## 已落

- `intelligence/services/judge_mode.py`：`ASK_SEMANTIC_JUDGE=llm|off`，A / B 两侧共用；**默认 `llm`，行为零变化**。
- 引擎 A：`_run_judge` 在 off 下返回合成全过报告（零模型调用），判后机械门 + `_repair` 照常，V11 记 `judge_off`；`SemanticEpisodeOutcome.judge_mode`（llm|deterministic）与 `cited_outside_slot_count` 进 `to_dict`（私有块 `continuous-episode.json → semantic_verifier`）；`JudgeStatus` 闭集不扩。
- 机械探测器 `evidence_date_mismatch`（IssueCode + RELEASE_POLICY=BLOCK，preflight，两种模式）；census `cited_outside_slot_binding` 只记账不删（R-20260821-06）。
- 引擎 B：判官段短路 → `deterministic_only`（可展示白名单、不带掉线告示）；phase `reason_code=judge_off` 由 `stable_llm_fallback_reason` 原样透传且不在 `_TRANSIENT_JUDGE_REASONS`；`synthesis_health` 多一桶。
- 文档：产品门页「判官模式」小节；工单 §2/§6 **执行订正**：公开 `gate_receipt` 键集（`RECEIPT_KEYS`，test_runtime_slo 钉死）不动。

## 已验证（全对 `89e8066e`，解释器主树 `.venv-workbench`）

全量 **11414P/0F/81S/2xf**（收据 `20260916T182101Z-89e8066e.json`，`check_test_receipt.py --expect-revision` 八项全过）；ruff 0；vitest 107；e2e 34P/2S（8793/8795）；registry 五项 0；`merge-tree` 对 `gitea/main@18859d37` 零冲突。变异：`semantic_judge_mode()` 恒返 llm → 新测试 19 条 **12 红**，还原全绿。首轮全量 1 红（IssueCode 穷举门漏登记放行策略）已在 `89e8066e` 修。

## 未做 / 边界

- **开关未翻，等用户确认**（代码已在生产，行为零变化）。工单 §5 第 10 步：备份启动器 → `export ASK_SEMANTIC_JUDGE="off"`、`ASK_EVIDENCE_JUDGE="auto"→"off"` → `launchctl kickstart -k gui/$UID/com.a77.finance-workbench`（代码快照不换，不需要链切五步）→ 探针 run 的 `continuous-episode.json.semantic_verifier.judge_mode == "deterministic"`。回滚 = 还原启动器备份 + kickstart。
  09-17 14:0x 切 `bf662e93` 后的探针实读 `judge_mode=llm`、`judge_status=repaired`，确认默认值仍是 `llm`、本次部署没有改变判官行为。
- 结构守卫的 `judge_status=unavailable` 标签未改（工单非目标四，finding）。
- 默认翻转 + 判官专属路径退役 = #56（占位），等上线满 5 个交易日。

## 坑

- `IssueCode` 有穷举门 `test_release_policy_covers_every_issue_code`——`rg "IssueCode\)"` 搜不到它（写法是 `frozenset(IssueCode)`），加码必登记 `RELEASE_POLICY`。
- B 侧 `_record_synthesis_phase(reason=)` 会被 `stable_llm_fallback_reason` 归一，陌生串塌成 `provider_unavailable`。
- `promote_grounded_answer` 会自己再跑一遍 shadow 链，测试里别先手跑再 promote（假链计数会溢出）。
