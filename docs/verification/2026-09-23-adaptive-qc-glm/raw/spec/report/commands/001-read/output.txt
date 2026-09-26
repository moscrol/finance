## Explore 阶段终稿（独立 spec 审查 #75）

**已执行并观察到的证据：**

1. `probe_c1_stream_deadline.py`（已运行，PASS）：127.0.0.1:26001 逐字节滴流服务器，timeout=6.0 但共享 deadline=1.5s。流式读取在 1.50s 被 `HTTPDeadlineExceeded` 截断；0.4s 后 worker 子进程 returncode=124，证明是 worker 自身 Timer→`os._exit(124)` 而非父进程 SIGKILL。
2. `probe_c1_stalled_parent.py`（已运行，PASS）：26002 服务器立即发 1MiB；父进程收完 headers 后停读 2.0s，worker 仍自行退出码 124；恢复读取得到 deadline 失败而非 5s 片内完整读取。

**静态核对（未做行为证明）：** 通读 `llm_http_transport.py` 全文；`llm_refine.py` 五个 `_open_deadline_http_response` 调用点（1167/1219/1424/1546/2304）均传 deadline，流式两点（1424/2304）另传 `is_cancelled`；wrapper 层 `synthesize_messages` 有 `min(shared_deadline.expires_at, now+timeout)` 折叠与 `require_remaining(1)` 门槛（0.5s deadline 会被预检拒绝、零请求）。

**未完成/限制：** `probe_c4_wrapper_deadline.py` 已落盘但**未执行**（阶段截止），其结论待下一阶段；C3（迟到判官拒收）、C5（零预算区分）、C6（子进程启动计预算）、C7（7ad61a0d 收据归属）未审查；EXPLORE.md 未及落盘；未运行作者测试，不将其计为独立验证。

```json
{"stage": "explore", "axis": "spec", "revision": "31f1b40dd788d36c71da249d59fb769c50d7cd30", "baseline": "9a02279863733c9b9f60fd92fcc7e840fa83f878", "complete": true, "probe_files": ["/Users/a77/.finance-runtime/reviews/pr868-glm-qc-20260923-1707/spec/work/probes/probe_c1_stream_deadline.py", "/Users/a77/.finance-runtime/reviews/pr868-glm-qc-20260923-1707/spec/work/probes/probe_c1_stalled_parent.py", "/Users/a77/.finance-runtime/reviews/pr868-glm-qc-20260923-1707/spec/work/probes/probe_c4_wrapper_deadline.py"], "claims_examined": ["C1", "C2", "C4"], "limits": ["probe_c4_wrapper_deadline.py 已写未运行，结论未定", "C3/C5/C6/C7 未审查", "C2 仅静态读调用点，未做行为反例", "EXPLORE.md 未落盘", "作者测试未运行，不作为独立验证"], "next_stage_commands": ["/Users/a77/finance-workbench-private/.venv-workbench/bin/python /Users/a77/.finance-runtime/reviews/pr868-glm-qc-20260923-1707/spec/work/probes/probe_c4_wrapper_deadline.py", "为 episode_semantic_verifier 写迟到判官(0.8s预算 vs ~2.9s回包)行为探针验证C3", "为零预算(root耗尽 vs judge子窗耗尽)写区分探针验证C5", "静态核对 7ad61a0d3fd9..31f1b40 diff 仅文档以归档C7"]}
```
