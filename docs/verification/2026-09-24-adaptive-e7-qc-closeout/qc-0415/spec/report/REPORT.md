```json
{
  "complete": true,
  "verdict": "PASS_WITH_LIMITS",
  "claims": [
    {
      "id": "C1",
      "status": "verified",
      "evidence": "transport_boundary_probe_v2 exit 0, 6/6：body_deadline_0p5_of_10 (HTTPDeadlineExceeded, wall 0.506s，10s timeout vs 0.5s deadline 分离)、slow_headers_deadline (0.507s)、cancel_midstream (HTTPStreamCancelled, cancel_to_stop 12ms, headers 后才武装)、zero_deadline_no_spawn (observer_events=[])、stalled_parent_timer (worker Timer 截断, 2.58s)，含正向 success_ok 对照"
    },
    {
      "id": "C2",
      "status": "verified",
      "evidence": "静态：llm_refine.py 1139-1234/1366+ 各调用点均传 deadline 给 _open_deadline_http_response，流式路径传 is_cancelled（offset 1366 读取确认）；行为：llm_paths_probe_v2 五路径 (post_chat/synthesis/message/message_stream/stream_raw) 均 10s 片 + 0.5s 共享 deadline 于 0.503-0.510s 停止，未等 ~3s fixture；限：message_stream 异常类型为 LLMStreamAlreadyEmitted（内容 delta 已发出后的设计语义），非探针 strict 断言的 LLMDeadlineExceeded，行为证据（截止生效）仍成立"
    },
    {
      "id": "C3",
      "status": "not_verified",
      "evidence": "部分验证：judge_startup_probe late_judge_failed_recorded——0.805s LLMDeadlineExceeded（0.8s 预算 vs 2.9s 服务器），ledger status=failed、n_records=1；root_remaining_after=1.593 证明 root 剩余时间反映已流逝 wall clock。限：report_received=False / unavailable=True 语义层字段未做行为探针，payload 未被接受仅由异常路径间接推断"
    },
    {
      "id": "C4",
      "status": "verified",
      "evidence": "llm_paths_probe_v2：五路径 10s timeout 片 + 0.5s 共享 Deadline 全部 ~0.5s 停止（wall 0.503-0.510），证明共享 deadline 被转发而非仅 per-call timeout；message_stream 路径 wall=0.508 同样被截止（异常类型差异见 C2）"
    },
    {
      "id": "C5",
      "status": "verified",
      "evidence": "llm_paths_probe：zero_budget_no_http (LLMCallBudgetExceeded, wall=0.0)、expired_root_no_http (LLMDeadlineExceeded, wall=0.0)；transport 探针 zero_deadline_no_spawn 无 spawn 事件；judge_startup_probe judge_subwindow_vs_root 区分子窗 (0.407s 触发) 与 root (剩余 1.593s)"
    },
    {
      "id": "C6",
      "status": "verified",
      "evidence": "judge_startup_probe startup_in_budget：0.9s 预算下 spawn_started(0.0004s)/spawned/request_sent 事件均在预算内，HTTPDeadlineExceeded 于 0.908s（非 2.9s 服务器完成时），证明子进程启动计入预算；未验证基准数值（claims 明确不要求）"
    },
    {
      "id": "C7",
      "status": "not_verified",
      "evidence": "本轴未独立重放 gate 收据生成流程；engineering-history.json 披露内容仅静态承认；作者 receipt 相关测试 16 项通过（含 receipts_inside_disposable）为间接支持；未独立评估 RAG/coverage 根因风险（claims 未声称修复）"
    }
  ],
  "findings": [],
  "author_tests": {
    "passed": 16,
    "failed": 0,
    "skipped": 0,
    "source": "reviewer 在原 candidate 路径以 -k 子集运行 pytest（16 passed, 81 deselected, exit 0, junitxml 存 work/author-tests.xml）；非历史收据"
  },
  "reviewer_probes": {
    "scripts": 4,
    "passed_scripts": 2,
    "failed_scripts": 2,
    "detail": "transport_boundary_probe_v2 6/6 子用例 PASS；judge_startup_probe 4/4 PASS；llm_paths_probe 3/9（探针缺陷）；llm_paths_probe_v2 4/6 子用例 PASS（message_stream 两例 strict 断言失败，见 failures）"
  },
  "intentional_control": {
    "observed": true,
    "command": "python -B work/positive_control.py",
    "exit_code": 1,
    "output": "AssertionError: intentional probe_bug control"
  },
  "failures": [
    {
      "command": "llm_paths_probe.py",
      "classification": "probe_bug",
      "reason": "服务器仅匹配 path=='stall' 而 _post_chat 追加 /chat/completions，stall 用例走 /ok 快速分支；流式返回非 SSE 触发 LLMStreamingUnsupported。探针缺陷，非产品缺陷"
    },
    {
      "command": "llm_paths_probe_v2.py",
      "classification": "probe_expectation_mismatch",
      "reason": "message_stream 两条子用例在内容 delta 已发出后命中截止/取消，产品按设计抛 LLMStreamAlreadyEmitted（不可重试语义）而非探针断言类型；截止行为本身成立（wall=0.508, cancel_to_stop=13ms）。每探针限一次修正，按 strict 断言计 failed"
    }
  ],
  "limits": [
    "C3 的 report_received/unavailable 语义层字段与 episode_semantic_verifier 判官窗口未做行为探针",
    "附加范围（diagnose_llm_timeout、prepare_adaptive_l6 系列、currency 校验、runner admission、run_main_gate.sh、/usr/bin/security 拒绝）仅经作者测试子集 16 项与静态核对间接覆盖，未逐一独立行为探针",
    "C7 未独立重放 gate 收据；RAG/coverage 历史失败根因风险未独立评估（claims 未声称修复）",
    "llm_paths v1 失败为探针缺陷；v2 message_stream 异常类型差异未二次修正（每失败探针限一次）",
    "网络仅 127.0.0.1:26001-26003 本地假服务；L6 natural 验收维持 NOT_PASSED，latest-head/main gate 不在本评审范围"
  ],
  "stage": "report",
  "axis": "spec",
  "revision": "e7a6cb412865fdd189cf51a17f93622fa3d4fe55",
  "baseline": "3bb81b9638f97b4773ce0f338df3a505b7c0162f"
}
```
