```json
{
  "complete": true,
  "claims_examined": [
    "C1",
    "C2",
    "C3",
    "C4",
    "C5",
    "C6",
    "C7"
  ],
  "probe_files": [
    "/Users/a77/.finance-runtime/reviews/pr868-glm-qc-20260924-0415/spec/work/probes/transport_boundary_probe_v2.py",
    "/Users/a77/.finance-runtime/reviews/pr868-glm-qc-20260924-0415/spec/work/probes/llm_paths_probe.py",
    "/Users/a77/.finance-runtime/reviews/pr868-glm-qc-20260924-0415/spec/work/probes/judge_startup_probe.py"
  ],
  "limits": "3 独立探针脚本（作者 fixture 未复制，探针为新写；未运行任何脚本）。覆盖：C1 停滞流/慢头/取消/停滞父进程 worker Timer；C2+C4 五调用路径 10s 片 vs 0.5s 共享 deadline 行为验证；C5 零 call budget 与过期 root 无 HTTP、judge 子窗 vs root 区分；C6 observer 时间戳证明子进程启动计入预算；C3 记录侧（ledger failed/timeout、<2.9s、payload 未解析）。限制：C3 的 report_received/unavailable 语义层字段及 episode_semantic_verifier 判官窗口未做行为探针；diagnose_llm_timeout/prepare_adaptive_l6 系列、currency 校验、runner admission 仅静态核对 API 包。transport_boundary_probe.py 为 v1（取消子用例触发过早），以 v2 为准，勿运行 v1。每个子用例独立报告 trigger_reached，脚本含正向成功对照，任一非对照断言失败 exit 1。",
  "next_stage_commands": [
    "/Users/a77/finance-workspace-private/.venv-workbench/bin/python /Users/a77/.finance-runtime/reviews/pr868-glm-qc-20260924-0415/spec/work/probes/transport_boundary_probe_v2.py",
    "/Users/a77/finance-workspace-private/.venv-workbench/bin/python /Users/a77/.finance-runtime/reviews/pr868-glm-qc-20260924-0415/spec/work/probes/llm_paths_probe.py",
    "/Users/a77/finance-workspace-private/.venv-workbench/bin/python /Users/a77/.finance-runtime/reviews/pr868-glm-qc-20260924-0415/spec/work/probes/judge_startup_probe.py"
  ],
  "stage": "explore",
  "axis": "spec",
  "revision": "e7a6cb412865fdd189cf51a17f93622fa3d4fe55",
  "baseline": "3bb81b9638f97b4773ce0f338df3a505b7c0162f"
}
```
