# 2026-09-17 判官代码退役工单（#56，占位）

> 来源：#55 `2026-09-17-no-llm-judge-deterministic-gate-workorder.md` §3 非目标第一条。机制复用 #55 落下的 `intelligence/services/judge_mode.py` 开关与 `judge_mode` 收据字段。
> 前置：#55 已合并、生产启动器已置 `ASK_SEMANTIC_JUDGE=off` 且**连续 ≥5 个交易日**探针与真实 run 的 `gate_receipt.judge_mode == "deterministic"`、无回滚记录（看 `~/.finance-runtime/deploy-ledger.jsonl` 与 `~/.local/share/finance-workbench/users/*/runs/*/report.json`）。

#55 刻意把默认值留在 `llm`，让设计变更与回归分开落地。本单做第二步：`judge_mode.semantic_judge_mode()` 默认改 `off`；删 `episode_semantic_verifier.py` 里只有 LLM 判官才会走到的路径——`_gap_answer(judge_unavailable=True)` 与 `CAUSE_JUDGE_UNAVAILABLE_HELD` 的「判官不可用即扣稿」（现 L1572 / L3336）、`_guided_retrieve_and_rejudge`（V11 引导回检索，只在判官纯语义拒句时开火）、`judge_source_recheck` 在 `_judge_request` 的挂载（L2322）、`_transient_failure_candidate` 的瞬态放行分支；`ask_synthesis.py` 侧删 `_judge_outage_release` 与 `_JUDGE_OUTAGE_NOTICE`。已知定性结论：**`JudgeStatus` 闭集不缩**（`unavailable` 仍是结构守卫在用的标签，见 #55 非目标第四条的 finding），`judge_mode` 字段保留——旧收据要能继续读。与判官相关的 18 个测试文件（`intelligence/tests/test_judge_*.py`、`test_v11_judge_guided_retrieval.py`、`test_judge_outage_degrades.py` 等）按「结构性迁移必须带着测试一起走」处理：删路径的同时删或改钉它的测试，不许留 skip。

验收：默认无环境变量下 `judge_mode=deterministic`；上述路径的符号 `rg` 零命中；`ASK_SEMANTIC_JUDGE=llm` 仍可显式打开判官供离线实验；四叶全绿、收据绑分支尖；分支独立、pathspec 提交、不合 main。
