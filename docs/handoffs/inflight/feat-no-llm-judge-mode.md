# feat/no-llm-judge-mode

工单 **#55**（`docs/superpowers/specs/2026-09-17-no-llm-judge-deterministic-gate-workorder.md`）：用户 09-17 决策「不用 LLM 判官」。树 `/Users/a77/fwp-wt-no-llm-judge`，代码尖 `89e8066e`，**PR #781 open，未合、未部署、启动器未改**。

## 已落

- `intelligence/services/judge_mode.py`：`ASK_SEMANTIC_JUDGE=llm|off`，A / B 两侧共用；**默认 `llm`，行为零变化**。
- 引擎 A：`_run_judge` 在 off 下返回合成全过报告（零模型调用），判后机械门 + `_repair` 照常，V11 记 `judge_off`；`SemanticEpisodeOutcome.judge_mode`（llm|deterministic）与 `cited_outside_slot_count` 进 `to_dict`（私有块 `continuous-episode.json → semantic_verifier`）；`JudgeStatus` 闭集不扩。
- 机械探测器 `evidence_date_mismatch`（IssueCode + RELEASE_POLICY=BLOCK，preflight，两种模式）；census `cited_outside_slot_binding` 只记账不删（R-20260821-06）。
- 引擎 B：判官段短路 → `deterministic_only`（可展示白名单、不带掉线告示）；phase `reason_code=judge_off` 由 `stable_llm_fallback_reason` 原样透传且不在 `_TRANSIENT_JUDGE_REASONS`；`synthesis_health` 多一桶。
- 文档：产品门页「判官模式」小节；工单 §2/§6 **执行订正**：公开 `gate_receipt` 键集（`RECEIPT_KEYS`，test_runtime_slo 钉死）不动。

## 已验证（全对 `89e8066e`，解释器主树 `.venv-workbench`）

全量 **11414P/0F/81S/2xf**（收据 `20260916T182101Z-89e8066e.json`，`check_test_receipt.py --expect-revision` 八项全过）；ruff 0；vitest 107；e2e 34P/2S（8793/8795）；registry 五项 0；`merge-tree` 对 `gitea/main@18859d37` 零冲突。变异：`semantic_judge_mode()` 恒返 llm → 新测试 19 条 **12 红**，还原全绿。首轮全量 1 红（IssueCode 穷举门漏登记放行策略）已在 `89e8066e` 修。

## 未做 / 边界

- 合入等用户确认。合入后按工单 §5 第 10 步：备份启动器 → `export ASK_SEMANTIC_JUDGE="off"`、`ASK_EVIDENCE_JUDGE="auto"→"off"` → 链切五步 → 探针 run 的 `continuous-episode.json.semantic_verifier.judge_mode == "deterministic"`。回滚 = 还原启动器 + kickstart。
- 结构守卫的 `judge_status=unavailable` 标签未改（工单非目标四，finding）。
- 默认翻转 + 判官专属路径退役 = #56（占位），等上线满 5 个交易日。

## 坑

- `IssueCode` 有穷举门 `test_release_policy_covers_every_issue_code`——`rg "IssueCode\)"` 搜不到它（写法是 `frozenset(IssueCode)`），加码必登记 `RELEASE_POLICY`。
- B 侧 `_record_synthesis_phase(reason=)` 会被 `stable_llm_fallback_reason` 归一，陌生串塌成 `provider_unavailable`。
- `promote_grounded_answer` 会自己再跑一遍 shadow 链，测试里别先手跑再 promote（假链计数会溢出）。
