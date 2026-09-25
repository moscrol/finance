# PR #868 独审批 c3（spec 轴，只审 C3）：已结束，C3 宿主有限采信

执行者：Claude Code 会话 `local_d1bf0c0c-c14a-497a-b465-5db3c3230016`。用户原话「批准执行」（09-25 约 10:0x，批上限 39、累计上限 354），逐字记在 `authorization.json`。
运行 10:03:48–10:06:09，请求 4/8/5/1 = **18 次，累计 333/354**。前文：`../pr868-glm-qc-20260925-c3c7/STATE.md`。

## 结果

- 审查者 PASS：C3 verified，findings 为空；C1/C2/C4–C7 按范围判 out_of_scope（宿主跨批汇总）。
- 审查者探针 `spec/work/probes/probe_c3_judge_window_v2.py`（explore 阶段写，sha256 见 `host-audit.json`）修掉了草稿的接口错：transport 用关键字参数回调 observer，草稿传的是 `list.append`。
- 晚到用例（0.8 s 窗，约 2.9 s 滴流 body）：收到响应头后在 0.805 s 被切断（无 eof），`report_received=False`、`unavailable=True`，账本 `failed/timeout/judge`，根预算扣掉 0.806 s。正常对照：报告收到、`passed=True`、账本 success。
- 宿主复核（零额度）：同一探针在候选树上重跑 3 次全部复现（0.805–0.81 s）；另做放宽窗口对照（5 s），同一滴流 body 在 3.16 s 完整到达并被接收——**被拒是窗口造成的，不是假服务器分片格式的问题**。记录在 `host-rerun/` 与 `host-audit.json`。
- 局限：探针直接设 `verifier._active_policy` 并 patch `judge_provider_chain`，是 `_run_judge_once` 单元层行为，不是整条 episode；晚到用例最终 `_JudgeCall` 的 issue 来自第 2 次尝试（窗口已被第 1 次耗尽），第 1 次的 `LLMDeadlineExceeded` 在 `last_dispatched_failure` 里。

## 候选 f2610293f 汇总

**C1–C7 七条全部已验证，零产品发现。** 独审（spec 轴）闭合。

## 合并前仍需（不在本批范围）

- main 已到 `4db9a42b6`：#920 在 `llm_refine.py` 的 5 个 `_post_chat*` 调用点各插了一行 `_apply_compat_payload`，正是 C2/C4 覆盖的调用点。前向到新候选后要重跑截止相关作者测试与四叶；审查证据属于 f2610293f。
- 并行 Pi 会话在做合并候选（#910 / #911 指向 #868 分支）；若它们并入，候选 revision 会变，须按变更面判断哪些合同要重审。
- L6 自然验收（≤ 3 题，打生产模型额度）需用户另批，且应在最终候选定下之后跑。
