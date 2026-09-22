# 2026-09-22 自适应研究回路 · 传输层绝对截止复核（工单 #72）

接手方独立复核，不复用作者收据。被测提交 `aa0509d61fb063be6fd2d2ac3ddc15732e6fd16e`（分支 `feat/adaptive-research-loop`），
隔离树 `~/fwp-wt-adaptive-deadline-0922`（`git worktree add --detach … aa0509d61`，首尾 `dirty=false`），
解释器 `~/finance-workspace-private/.venv-workbench/bin/python`，独占 `basetemp`，开跑时 load 5.18。
原始日志根 `~/.finance-runtime/adaptive-deadline-0922/`。

## 目标 1：严格探针（13 场景）

`PYTHONPATH=. python scripts/review_probes/diagnose_llm_timeout.py --assert-deadline --output strict-deadline.json`
→ **exit 0，`deadline_violations: []`**，本目录 `strict-deadline.json`（容差 0.2 s，`source_before == source_after`）。

| 场景 | 获批 | 实测墙钟 | 台账 status/reason |
|---|---:|---:|---|
| fast | 0.8 | 0.109 | success |
| header_delay | 0.8 | 0.805 | failed/timeout |
| body_stall | 0.8 | 0.802 | failed/timeout |
| headers_then_body | 0.8 | 0.808 | failed/timeout |
| body_trickle | 0.8 | 0.808 | failed/timeout |
| tools_stream_trickle | 0.8 | 0.805 | failed/timeout |
| tools_stream_partial_line | 0.8 | 0.806 | failed/timeout |
| synthesis_stream_trickle | 1.2 | 1.214 | failed/timeout |
| synthesis_stream_partial_line | 1.2 | 1.211 | failed/timeout |
| zero_deadline | 0.0 | 0.000 | 无请求、无预占 |
| judge_window_stalls | 0.8 | 0.807 | failed/timeout |
| judge_late_report | 0.8 | 0.812 | failed/timeout |
| judge_root_expired | 0.0 | 0.000 | 无请求 |

作者在 `a9ba35159` 上测到的 7 个越窗（+0.25 ～ +3.16 s）在 `aa0509d61` 上全部归零；接手方独立复现，与作者
`final-strict-deadline.json` 结论一致。非流式场景 `content_present=False`，流式场景 `emitted_chars>0` 但正文未被采纳。

## 目标 2：判官迟到回包

`judge_late_report`（批 0.8 s、对端 ~2.9 s 才吐完）：`report_received=False`、`unavailable=True`、
台账唯一一行 `status=failed / reason=timeout`、`request_count == reserved_count == len(records) == 1`、
`remaining_root_seconds=8.79`（根预算按实际消耗扣，不再按「对方守约」记）。
常规回归 `test_real_late_judge_report_is_rejected_at_the_transport_boundary` 守这一条。

## 验收「阳性对照」：变异存活 → 补用例 → 杀死

工单要求：把 `_open_deadline_http_response` 的 `deadline` 改为不传，至少一条**常规** pytest 用例红。

| 步骤 | 命令 / 改动 | 结果 |
|---|---|---|
| 变异 | `llm_refine.py:222` `deadline=deadline` → `deadline=None`（`git diff` 1 行） | — |
| 定向套件（作者版 25 条） | `pytest intelligence/tests/test_llm_timeout_diagnostic.py` | **25 passed，变异存活** |
| 广域（另 13 个引用传输层的测试文件） | `pytest conformance_transport test_ask_call_provenance … test_served_model_receipt` | **351 passed，变异存活** |
| 补用例 | 新增 `test_refine_wrapper_forwards_the_shared_deadline_to_the_transport`：单发片 10 s、共享截止 0.5 s、对端 ~2.9 s 滴流，断言 `LLMDeadlineExceeded` 且墙钟 < 2 s | 变异下 **1 failed（DID NOT RAISE）** |
| 还原 | `git checkout -- intelligence/services/llm_refine.py`，sha256 `ff587c50…a424` 与 `HEAD` 一致 | 26 passed，ruff 通过 |

为什么此前无人守：探针与 `test_call_timeout_never_outlives_the_shared_research_deadline` 里「单发片」与「共享截止」
两个值要么相等、要么直接驱动传输层绕过了包装函数，所以丢掉包装函数里的 `deadline=` 转发对它们不可见。
两个入参在所有夹具里同值时，删掉其中一个的变异一定存活——阳性对照必须让这两个值分开。
（同族原则：`~/agent-memory` 的 `two-defence-layers-need-two-separate-assertions`。）

变异全程 `PYTHONDONTWRITEBYTECODE=1`，日志 `mut-broad.log` / `mut-newtest.log` / `post-restore-targeted.log`，
sha256 见 `llm_refine.head.sha256` / `llm_refine.restored.sha256`，结构化记录见本目录 `mutation-record.json`。

## 工单步骤 1 的「2 个未提交路径」处置

工单以 22:20 的分支状态为起点，当时树上 2 个未提交路径。接手时（23:39）作者树 `~/finance-worktrees/adaptive-research-loop`
`git status --short` 为空；`git show --stat aa0509d61`（22:35）恰好只含 `docs/handoffs/2026-09-22-adaptive-deadline-transport.md`
与 `docs/handoffs/inflight/feat-adaptive-research-loop.md` 两个文件。判定：那 2 个路径已由作者以 `aa0509d61` 提交，无需另行落盘。

## 非目标（按工单原样未动）

未改 T900 / 75 / 150 预算；未开 `derived_calculation`；未碰数字门单位错位（issue #852）；未跑真实模型；
未给 `--assert-deadline` 探针加容忍；未动生产 8792。

## 交 #76 / #75 的条件卡

见分支交接 `docs/handoffs/inflight/feat-adaptive-research-loop.md`「交姊妹单」一节。
