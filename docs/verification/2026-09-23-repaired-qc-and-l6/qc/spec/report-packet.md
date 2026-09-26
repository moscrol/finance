# Same-axis immutable evidence packet

No model reasoning or other-axis conclusion is included. Host packaging is not a verdict.


## inputs/claims.md

# PR #868 / #72 Claim Set

Source: PR #868 description C1-C7, frozen for candidate ac11027fa75ee6a988ab90ab81e0329159964643. These are author assertions to verify, not reviewer findings.

- C1: llm_http_transport.urlopen(request, timeout, deadline, is_cancelled) applies a monotonic absolute deadline to an entire HTTP call including streaming reads. Parent read/write checks and worker Timer -> os._exit(124) enforce termination even with slow/trickling input or a stalled parent.
- C2: All five llm_refine HTTP call sites use _open_deadline_http_response, passing deadline and, on streaming paths, cancellation. No bypass. Examine upstream origins of timeout and shared deadline separately; same-valued fixture parameters cannot prove forwarding. Deadline has no asserted slice() API.
- C3: A late semantic judge payload (0.8s budget, upstream roughly 2.9s) is recorded failed/timeout, report_received=False, unavailable=True; payload is not accepted, root remaining time reflects elapsed wall clock.
- C4: Wrapper forwards the shared research deadline, not only the per-call timeout. A 10s slice and 0.5s shared deadline must stop before the roughly 2.9s fixture finishes. Missing forwarding must be detectable by a behavioral probe.
- C5: Zero budget means no HTTP request and no reservation; distinguish exhausted root from exhausted judge subwindow.
- C6: Each HTTP call starts an isolated Python subprocess; startup is part of the granted budget. Historical startup durations are observations, not a performance guarantee. Verify inclusion, not those benchmark numbers.
- C7: Historical engineering receipts belong only to clean revision 7ad61a0d3fd9ee63abe2089a4049a0a1b4a8bc16. The current candidate includes a main merge and product fixes, NOT a docs-only delta. Historical receipts do not cover this candidate and cannot be relabeled as current or independent test counts.

Scope limits: broader adaptive-loop behavior and financial answer correctness are not claims covered by #72. The previous L6 natural acceptance did not pass, and this engineering review cannot promote it. The repaired-candidate changes listed below are in scope for correctness findings. No merge/deployment authority.

Inputs alongside this file: author-summary.json and author-pytest-receipt.json are unmodified copies from the historical gate; code-tip-to-candidate.diffstat.txt is host-generated git evidence. Do not treat their existence as proving C1-C6.

Additional repaired-candidate correctness scope (findings, not extra C claim IDs):
- Currency field units in episode_semantic_verifier.py must accept equivalent rounding while rejecting wrong currency scale, non-money fields and unbound evidence.
- pi_review_protocol.mjs and prepare_pi_review_repair.py bind stage/axis/revision/baseline in the controller. Reviewer identity injection, including matching identities, is forbidden. Request/deadline/one-closeout limits are unchanged.
- adaptive_l6_batch.py and prepare_adaptive_l6_runner.py must not submit a next question before an exact-Episode source audit PASS. Missing, failing, late and malformed audits must stop. Synthetic PASS is not a natural financial verdict.
- Offline CLI and archived-input fixture tests need files denied by this review sandbox. Do not weaken the sandbox. Distinguish unrun author tests from independent small probes.



## config.json

{
  "tree": "/Users/a77/.finance-runtime/reviews/pr868-repaired-20260923-2111/candidate",
  "python": "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
  "author": "/Users/a77/.finance-runtime/reviews/pr868-repaired-20260923-2111/candidate",
  "revision": "ac11027fa75ee6a988ab90ab81e0329159964643",
  "baseline": "626d8a508c1c988ff094110b371987e6afdcdd15",
  "axis": "spec",
  "thinking": "low",
  "max_output_tokens": 8192,
  "provider": "glm-direct-review",
  "model": "glm-5.3",
  "upstream_port": 443,
  "upstream_url": "https://open.bigmodel.cn/api/coding/paas/v4",
  "stage_tools": {
    "gateway": [
      "read",
      "write"
    ],
    "explore": [
      "read",
      "write",
      "deliver_stage"
    ],
    "execute": [
      "read",
      "write",
      "bash",
      "deliver_stage"
    ],
    "report": [
      "deliver_stage"
    ]
  }
}



## explore/parsed.json

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
    "/Users/a77/.finance-runtime/reviews/pr868-glm-qc-repaired-20260923-2115/spec/work/probes/probe_transport.py",
    "/Users/a77/.finance-runtime/reviews/pr868-glm-qc-repaired-20260923-2115/spec/work/probes/probe_deadline_forward_v2.py",
    "/Users/a77/.finance-runtime/reviews/pr868-glm-qc-repaired-20260923-2115/spec/work/probes/probe_judge_window.py"
  ],
  "notes": "本阶段仅阅读源码并撰写探针,未执行任何测试。探针均为独立编写(非作者测试重标),使用本地 127.0.0.1 固定端口 26001-26007 的 fake HTTP 服务,不触网、不碰生产。probe_transport.py 覆盖 C1:成功正向路径、滴流响应下的单调绝对 deadline、停滞父进程下 worker Timer 强杀(观察 returncode/EOF)、流式 is_cancelled 取消、已过期 deadline 立即拒绝且不发子进程。probe_deadline_forward_v2.py 覆盖 C2/C4/C5:_post_chat_synthesis 在 timeout=10s 片 + 0.5s 共享 Deadline + 2.9s 慢后端下须于 ~0.5s 内以 LLMDeadlineExceeded 失败(行为性探针,非同值夹具);用 http_transport_override 拦截验证 4 个调用点转发 deadline 与流式 is_cancelled,且 timeout 数值(10.0)与 deadline.expires_at(+0.5)不同值;Deadline.call_timeout 切片语义;零预算 LLMCallLedger(max_calls=0) 下 _reserve_llm_call 先于 HTTP 抛 LLMCallBudgetExceeded。probe_judge_window.py 覆盖 C3/C5/C6:0.8s 判官子窗口 + 2.9s 迟到载荷被 HTTPDeadlineExceeded 拒收;root 剩余 0.6s 主导且 root.remaining() 归零(区分 root 与判官子窗口);semantic_judge_window_seconds/judge_attempt_seconds 地板语义;极小预算(0.05s)下子进程启动计入预算导致失败 vs 充足预算成功(C6 的包含性验证,非基准数字)。已知风险:LLMCallLedger 构造参数(max_calls/max_seconds)未逐行核对源码,若签名不同需在 EXECUTE 阶段微调。C7 无行为探针:历史收据不属于本候选,已按声明处理,不重标计数。",
  "limits": "bash 禁用;本阶段 read/write/deliver_stage only,无执行;网络仅限本地 fake 端口 26001-26007;预算 24 请求/420s 硬关停,当前已用约 12 请求。",
  "next_stage_commands": [
    "cd /Users/a77/.finance-runtime/reviews/pr868-repaired-20260923-2111/candidate && /Users/a77/finance-workspace-private/.venv-workbench/bin/python /Users/a77/.finance-runtime/reviews/pr868-glm-qc-repaired-20260923-2115/spec/work/probes/probe_transport.py",
    "cd /Users/a77/.finance-runtime/reviews/pr868-repaired-20260923-2111/candidate && /Users/a77/finance-workspace-private/.venv-workbench/bin/python /Users/a77/.finance-runtime/reviews/pr868-glm-qc-repaired-20260923-2115/spec/work/probes/probe_deadline_forward_v2.py",
    "cd /Users/a77/.finance-runtime/reviews/pr868-repaired-20260923-2111/candidate && /Users/a77/finance-workspace-private/.venv-workbench/bin/python /Users/a77/.finance-runtime/reviews/pr868-glm-qc-repaired-20260923-2115/spec/work/probes/probe_judge_window.py"
  ],
  "stage": "explore",
  "axis": "spec",
  "revision": "ac11027fa75ee6a988ab90ab81e0329159964643",
  "baseline": "626d8a508c1c988ff094110b371987e6afdcdd15"
}



## explore controller summary (derived whitelist)
{"stage": "explore", "status": "STAGE_COMPLETE", "revision": "ac11027fa75ee6a988ab90ab81e0329159964643", "baseline": "626d8a508c1c988ff094110b371987e6afdcdd15", "requests": 12, "elapsed_seconds": 161.739, "errors": [], "report_structural": true, "inputs_unchanged": true, "candidate_before": {"revision": "ac11027fa75ee6a988ab90ab81e0329159964643", "status": ""}, "candidate_after": {"revision": "ac11027fa75ee6a988ab90ab81e0329159964643", "status": ""}, "model_identities": ["glm-direct-review/glm-5.3"], "probe_sha256": {"work/probes/probe_deadline_forward.py": "b36d0240cfd01f96bb0d8b9c92c5cdd4e278dc4caaa49863623f82bcce32d367", "work/probes/probe_deadline_forward_v2.py": "54ba94b30f06cd719ccd67a2dd55d586ef2be71bec373887a08d073e9dc5a63a", "work/probes/probe_judge_window.py": "a291929c955b2a5f1da666a46944757d23862790fa2207b8087e559b0e9c425a", "work/probes/probe_transport.py": "484225cbfda00a2f50c1ac0b970bbd19e42b0aadc905258ca3db6d2d847f7871"}}


## execute/parsed.json

{
  "complete": true,
  "author_tests": {
    "passed": 0,
    "failed": 0,
    "skipped": 0,
    "commands": [],
    "note": "未执行:关停在运行 pytest 选择用例(violation_uses/cli_strict/existing_receipt/rejects_unbounded/endpoint_guard)与探针 judge_window 之前;未观察到任何作者测试结果,不得引用历史收据充当。"
  },
  "reviewer_probes": {
    "passed": 1,
    "failed": 3,
    "commands": [
      {
        "script": "probe_transport.py",
        "cmd": "python .../spec/work/probes/probe_transport.py",
        "exit": 1,
        "result": "A/B/D/E PASS; C FAIL: urlopen 自身在 ~1s 处抛 HTTPDeadlineExceeded(探针假设先返回 response 对象),probe_bug 判定设计"
      },
      {
        "script": "probe_transport_v2.py(修正,新文件)",
        "cmd": "python .../spec/work/probes/probe_transport_v2.py",
        "exit": 0,
        "result": "A/B/D/E PASS; C PASS: read 抛 HTTPDeadlineExceeded 且 worker returncode=124, dt=2.72 —— Timer/os._exit(124) 强杀成立(C1)"
      },
      {
        "script": "probe_deadline_forward_v2.py",
        "cmd": "python .../spec/work/probes/probe_deadline_forward_v2.py",
        "exit": 1,
        "result": "C4/C2 四调用点/call_timeout 全 PASS;末段 LLMCallLedger(max_seconds=None) TypeError —— probe_bug(签名臆测)"
      },
      {
        "script": "probe_deadline_forward_v3.py(修正,新文件)",
        "cmd": "python .../spec/work/probes/probe_deadline_forward_v3.py",
        "exit": 1,
        "result": "C4/C2/call_timeout 再次全 PASS;C5 段仍失败:call_ledger_scope 首参是 max_calls 而非 ledger,传入 ledger 后 try_reserve 比较 int>=LLMCallLedger TypeError —— probe_bug,按规则不再二次修正,C5 行为性验证记 not_verified"
      }
    ],
    "note": "分母=脚本调用次数(4),passed=1;probe_judge_window.py 未运行。"
  },
  "intentional_control": {
    "observed_failed": false,
    "classification": "not_run",
    "command": "/Users/a77/finance-workspace-private/.venv-workbench/bin/python -B .../spec/work/positive_control.py",
    "note": "关停前未执行,无观察结果,不作任何分类。"
  },
  "failures": [
    {
      "cmd": "probe_transport.py",
      "classification": "probe_bug",
      "reason": "C 项假设 urlopen 必先返回 response;实际父侧在返回前即按绝对 deadline 抛 HTTPDeadlineExceeded,属正确行为,探针判定设计错误;修正版 v2 通过(worker rc=124)"
    },
    {
      "cmd": "probe_deadline_forward_v2.py",
      "classification": "probe_bug",
      "reason": "LLMCallLedger 构造参数 max_seconds 不存在(dataclass 仅 records/max_calls/rejected_count 等)"
    },
    {
      "cmd": "probe_deadline_forward_v3.py",
      "classification": "probe_bug",
      "reason": "call_ledger_scope(max_calls,...) 首参不是 ledger;C5 零预算行为探针失败且已用掉唯一修正机会,C5 行为性证据 not_verified(静态证据仍在)"
    },
    {
      "cmd": "author pytest + probe_judge_window.py + positive_control.py",
      "classification": "not_run",
      "reason": "阶段预算关停,均未执行,未观察到任何结果"
    }
  ],
  "claim_evidence": {
    "C1": {
      "static": "llm_http_transport.py: worker threading.Timer(remaining, os._exit,(124,)); urlopen 过期 deadline 立即抛(line 225/237);HTTPResponse 读取侧 deadline/is_cancelled 检查",
      "behavior": "probe_transport_v2: 滴流 1.0s deadline 于 1.02s 截断;停滞父进程 read 抛 HTTPDeadlineExceeded 且 worker rc=124;流式取消 HTTPStreamCancelled;timeout=0 立即拒绝;成功正向读取 200",
      "missing": "无"
    },
    "C2": {
      "static": "llm_refine.py 7 处 _reserve_llm_call,调用点经 _open_deadline_http_response 路径(源码索引)",
      "behavior": "http_transport_override 拦截证实 4 个调用点均转发 deadline(expires_at=+0.5)且 timeout=10.0 与 deadline 不同值;流式两调用点转发 is_cancelled。第五个调用点未单独拦截到(探针只覆盖 4 个),静态未逐行核对第五点",
      "missing": "第五个 HTTP 调用点的独立行为拦截"
    },
    "C3": {
      "static": "episode_semantic_verifier.py 存在 semantic_judge_window_seconds/judge_attempt_seconds(未逐行核对)",
      "behavior": "无:probe_judge_window.py 未运行",
      "missing": "迟到判官载荷拒收、report_received=False/unavailable=True、root remaining 归零等全部行为覆盖"
    },
    "C4": {
      "static": "无单独静态审阅",
      "behavior": "_post_chat_synthesis 在 timeout=10.0 片 + 0.5s 共享 Deadline 下 0.51s 即抛 LLMDeadlineExceeded(2.9s 慢后端未完成);Deadline.call_timeout 切片语义 0.5/10.0 两例 PASS",
      "missing": "无(该子项已验证)"
    },
    "C5": {
      "static": "LLMCallLedger.try_reserve 原子预占;_reserve_llm_call 在各 HTTP 边界调用(如 _post_chat_synthesis line 1205 先于 HTTP);v3 崩溃栈亦显示预留先于传输",
      "behavior": "not_verified:两次探针均在台账作用域构造上失败(probe_bug),零预算拒发与耗尽 root/判官子窗口区分未获行为证据",
      "missing": "C5 行为性探针;root 耗尽 vs 判官子窗口区分(judge probe 未跑)"
    },
    "C6": {
      "static": "每次调用经 urlopen 启动隔离子进程;expires_at 在 Popen 前设定(grep 见 line 213-243 结构)",
      "behavior": "部分:transport 探针 E 项(timeout=0 在发子进程前拒绝)通过;probe_judge_window 的极小预算启动计入对比未运行",
      "missing": "启动计入预算的对比性行为证据"
    },
    "C7": {
      "static": "claims.md 明确历史收据仅覆盖 7ad61a0d,本候选含 merge+修复,不可重标",
      "behavior": "无(声明性声明,无需测试;本评审亦未把任何历史收据计入本次测试数)",
      "missing": "无"
    }
  },
  "limits": "关停前共执行 4 次探针脚本与 3 次源码读取;author pytest、probe_judge_window.py、positive_control.py 均未执行,故无其结果。C3 行为覆盖、C5 行为覆盖、C6 对比、第五调用点拦截为缺口;历史作者收据未用作任何证据。两次修正探针失败原因均为探针自身 API 臆测,未发现产品缺陷;C1/C2(4 点)/C4 获得通过性行为证据。",
  "stage": "execute",
  "axis": "spec",
  "revision": "ac11027fa75ee6a988ab90ab81e0329159964643",
  "baseline": "626d8a508c1c988ff094110b371987e6afdcdd15"
}



## execute controller summary (derived whitelist)
{"stage": "execute", "status": "STAGE_COMPLETE", "revision": "ac11027fa75ee6a988ab90ab81e0329159964643", "baseline": "626d8a508c1c988ff094110b371987e6afdcdd15", "requests": 17, "elapsed_seconds": 226.865, "errors": [], "report_structural": true, "inputs_unchanged": true, "candidate_before": {"revision": "ac11027fa75ee6a988ab90ab81e0329159964643", "status": ""}, "candidate_after": {"revision": "ac11027fa75ee6a988ab90ab81e0329159964643", "status": ""}, "model_identities": ["glm-direct-review/glm-5.3"], "probe_sha256": {"work/probes/probe_deadline_forward.py": "b36d0240cfd01f96bb0d8b9c92c5cdd4e278dc4caaa49863623f82bcce32d367", "work/probes/probe_deadline_forward_v2.py": "54ba94b30f06cd719ccd67a2dd55d586ef2be71bec373887a08d073e9dc5a63a", "work/probes/probe_deadline_forward_v3.py": "8c7270988e3b67791fb2497f4dbae8b32b06f752961fda6c5c69a9786cdc0cb6", "work/probes/probe_judge_window.py": "a291929c955b2a5f1da666a46944757d23862790fa2207b8087e559b0e9c425a", "work/probes/probe_transport.py": "484225cbfda00a2f50c1ac0b970bbd19e42b0aadc905258ca3db6d2d847f7871", "work/probes/probe_transport_v2.py": "e5fb4853b30d36ef8eba0c1ad8714b7e10fdb66794566e74b34e96e90984ff1d"}}


## work/probes/probe_deadline_forward.py

"""C2/C4/C5 探针:deadline 转发、timeout 片与共享 deadline 的区分、零预算。
边界:
  1 行为探针(C4): timeout=10s 片, 共享 Deadline 只剩 0.5s, 后端为 2.9s 慢响应
    (本地 26005 fake)。若 _post_chat_synthesis 正确转发共享 deadline, 调用在
    ~0.5s 内以 LLMDeadlineExceeded 失败, 而不是等完 2.9s。
  2 转发断言(C2): 用 http_transport_override 拦截, 分别驱动
    _post_chat_synthesis / _post_chat_message_stream / _post_chat_message /
    _post_chat_stream_raw, 检查 deadline 参数与(流式)is_cancelled 均被转发,
    且 timeout 与 deadline.expires_at 数值不同(防同值夹具)。
  3 Deadline.call_timeout(C4): 10s 片 + 0.5s 剩余 → 0.5s; 剩余 20s + 10s 片 → 10s。
  4 零预算(C5): LLMCallLedger max_calls=0 时, _reserve_llm_call 在任何 HTTP 前抛
    LLMCallBudgetExceeded(拦截器断言未被调用)。
运行: PYTHONPATH=. python probes/probe_deadline_forward.py
"""
import sys, time, json, threading, dataclasses
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, ".")
from intelligence.services import llm_refine as R

RESULTS = []
def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + " :: " + detail)

PROV = R.LLMProvider(name="fake", base_url="http://127.0.0.1:26005", api_key="k")

class Slow29(BaseHTTPRequestHandler):
    def do_POST(self):
        time.sleep(2.9)
        body = json.dumps({"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]}).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass

def fake_stream_response(req, timeout, *, deadline=None, is_cancelled=None, **kw):
    """模拟一个永远在 deadline 上的慢流: open 即返回, 读时阻塞到 deadline 由传输层终止。"""
    raise AssertionError("interceptor should not be reached in behavioral case")

def main():
    srv = ThreadingHTTPServer(("127.0.0.1", 26005), Slow29)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    # 1 行为探针: 10s 片 vs 0.5s 共享 deadline
    dl = R.Deadline.from_timeout(0.5)
    t0 = time.monotonic()
    try:
        R._post_chat_synthesis(PROV, [{"role": "user", "content": "hi"}], 10.0, 0.2, 16, 1000, deadline=dl)
        check("C4_shared_deadline_wins", False, "no exception, ran to completion")
    except R.LLMDeadlineExceeded:
        dt = time.monotonic() - t0
        check("C4_shared_deadline_wins", dt < 1.5, f"elapsed={dt:.2f} (10s slice, 0.5s shared)")
    except Exception as e:
        dt = time.monotonic() - t0
        check("C4_shared_deadline_wins", isinstance(e, R.LLMDeadlineExceeded), f"elapsed={dt:.2f} exc={type(e).__name__} {e}")

    # 2 转发断言
    captured = []
    class Cap:
        def __call__(self, request, timeout, *, deadline=None, is_cancelled=None, **kw):
            captured.append({"timeout": timeout, "expires": getattr(deadline, "expires_at", None),
                             "cancelled": is_cancelled, "now": time.monotonic()})
            raise AssertionError("capture")
        def __enter__(self): return self
        def __exit__(self, *a): return False
    calls = []
    def run_site(fn, streaming):
        captured.clear()
        try:
            fn()
        except AssertionError:
            pass
        c = captured[0] if captured else {}
        ok = (c.get("expires") is not None
              and abs(c["expires"] - (time.monotonic() + 0.5)) < 1.0
              and abs(c.get("timeout", -1) - 10.0) < 1e-6
              and (not streaming or callable(c.get("cancelled"))))
        return ok, c

    dl2 = R.Deadline.from_timeout(0.5)
    canc = lambda: False
    with R.http_transport_override(Cap()):
        ok, c = run_site(lambda: R._post_chat_synthesis(PROV, [{"role":"user","content":"x"}], 10.0, 0.2, 16, 1000, deadline=dl2), False)
        check("C2_synthesis_forwards_deadline", ok, str(c))
        ok, c = run_site(lambda: R._post_chat_message_stream(PROV, [{"role":"user","content":"x"}], 10.0, 0.2, None, None, None, lambda s: None, canc, deadline=dl2), True)
        check("C2_stream_forwards_deadline_and_cancel", ok, str(c))
        ok, c = run_site(lambda: R._post_chat_stream_raw(PROV, [{"role":"user","content":"x"}], 10, 0.2, lambda s: None, None, canc, dl2, 16, 1000), True)
        check("C2_synthesis_stream_forwards", ok, str(c))
        # _post_chat_message 单独探针 (26005)
        ok, c = run_site(lambda: R._post_chat_message(PROV, [{"role":"user","content":"x"}], 10.0, 0.2, deadline=dl2), False)
        check("C2_message_forwards_deadline", ok, str(c))

    # 3 call_timeout
    dl3 = R.Deadline.from_timeout(0.5)
    v = dl3.call_timeout(10.0, minimum=0.001)
    check("call_timeout_slice", 0.4 < v <= 0.51, f"v={v:.3f}")
    dl4 = R.Deadline.from_timeout(20.0)
    v = dl4.call_timeout(10.0, minimum=0.001)
    check("call_timeout_slice2", 9.5 < v <= 10.0, f"v={v:.3f}")

    # 4 零预算
    hit = {"n": 0}
    class Count:
        def __call__(self, *a, **k):
            hit["n"] += 1
            raise AssertionError("http reached")
        def __enter__(self): return self
        def __exit__(self, *a): return False
    ledger = R.LLMCallLedger(max_calls=0, max_seconds=None)
    with R.call_ledger_scope(ledger):
        with R.http_transport_override(Count()):
            try:
                R._post_chat_synthesis(PROV, [{"role":"user","content":"x"}], 5.0, 0.2, 16, 1000, deadline=R.Deadline.from_timeout(5.0))
                check("C5_zero_budget_no_http", False, "no exception")
            except R.LLMCallBudgetExceeded:
                check("C5_zero_budget_no_http", hit["n"] == 0, f"http_calls={hit['n']}")

    print(json.dumps([{"name": n, "pass": p, "detail": d} for n, p, _ in RESULTS]))
    sys.exit(0 if all(p for _, p, _ in RESULTS) else 1)

if __name__ == "__main__":
    main()



## work/probes/probe_deadline_forward_v2.py

"""v2 of probe_deadline_forward.py — 仅修复 LLMProvider 构造(需 model 字段),
逻辑与 v1 相同。C2/C4/C5:deadline 转发、10s 片 vs 0.5s 共享 deadline、零预算。
运行: PYTHONPATH=. python probes/probe_deadline_forward_v2.py
"""
import sys, time, json, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, ".")
from intelligence.services import llm_refine as R

RESULTS = []
def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + " :: " + detail)

PROV = R.LLMProvider(name="fake", api_key="k", base_url="http://127.0.0.1:26005", model="fake-model")

class Slow29(BaseHTTPRequestHandler):
    def do_POST(self):
        time.sleep(2.9)
        body = json.dumps({"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]}).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass

def main():
    srv = ThreadingHTTPServer(("127.0.0.1", 26005), Slow29)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    # 1 行为探针 (C4): 10s 片, 共享 0.5s
    dl = R.Deadline.from_timeout(0.5)
    t0 = time.monotonic()
    try:
        R._post_chat_synthesis(PROV, [{"role": "user", "content": "hi"}], 10.0, 0.2, 16, 1000, deadline=dl)
        check("C4_shared_deadline_wins", False, "no exception")
    except Exception as e:
        dt = time.monotonic() - t0
        check("C4_shared_deadline_wins", isinstance(e, R.LLMDeadlineExceeded) and dt < 1.5,
              f"exc={type(e).__name__} dt={dt:.2f}")

    # 2 转发断言 (C2)
    captured = []
    class Cap:
        def __call__(self, request, timeout, *, deadline=None, is_cancelled=None, **kw):
            captured.append({"timeout": timeout, "expires": getattr(deadline, "expires_at", None),
                             "cancelled": is_cancelled, "now": time.monotonic()})
            raise AssertionError("capture")
        def __enter__(self): return self
        def __exit__(self, *a): return False
    def run_site(fn, streaming, label):
        captured.clear()
        try:
            fn()
        except AssertionError:
            pass
        c = captured[0] if captured else {}
        ok = (len(captured) == 1
              and c.get("expires") is not None
              and 0.0 < c["expires"] - c["now"] <= 0.55
              and abs(c.get("timeout", -1) - 10.0) < 1e-6
              and (not streaming or callable(c.get("cancelled"))))
        check(label, ok, str(c))

    dl2 = R.Deadline.from_timeout(0.5)
    canc = lambda: False
    with R.http_transport_override(Cap()):
        run_site(lambda: R._post_chat_synthesis(PROV, [{"role":"user","content":"x"}], 10.0, 0.2, 16, 1000, deadline=dl2), False, "C2_synthesis_forwards")
        run_site(lambda: R._post_chat_message_stream(PROV, [{"role":"user","content":"x"}], 10.0, 0.2, None, None, None, lambda s: None, canc, deadline=dl2), True, "C2_stream_forwards")
        run_site(lambda: R._post_chat_message(PROV, [{"role":"user","content":"x"}], 10.0, 0.2, deadline=dl2), False, "C2_message_forwards")
        run_site(lambda: R._post_chat_stream_raw(PROV, [{"role":"user","content":"x"}], 10, 0.2, lambda s: None, None, canc, dl2, 16, 1000), True, "C2_synthesis_stream_forwards")

    # 3 call_timeout
    v = R.Deadline.from_timeout(0.5).call_timeout(10.0, minimum=0.001)
    check("call_timeout_slice", 0.4 < v <= 0.51, f"v={v:.3f}")
    v = R.Deadline.from_timeout(20.0).call_timeout(10.0, minimum=0.001)
    check("call_timeout_slice2", 9.5 < v <= 10.0, f"v={v:.3f}")

    # 4 零预算 (C5)
    hit = {"n": 0}
    class Count:
        def __call__(self, *a, **k):
            hit["n"] += 1
            raise AssertionError("http reached")
        def __enter__(self): return self
        def __exit__(self, *a): return False
    ledger = R.LLMCallLedger(max_calls=0, max_seconds=None)
    with R.call_ledger_scope(ledger):
        with R.http_transport_override(Count()):
            try:
                R._post_chat_synthesis(PROV, [{"role":"user","content":"x"}], 5.0, 0.2, 16, 1000,
                                       deadline=R.Deadline.from_timeout(5.0))
                check("C5_zero_budget_no_http", False, "no exception")
            except R.LLMCallBudgetExceeded:
                check("C5_zero_budget_no_http", hit["n"] == 0, f"http_calls={hit['n']}")

    print(json.dumps([{"name": n, "pass": p, "detail": d} for n, p, _ in RESULTS]))
    sys.exit(0 if all(p for _, p, _ in RESULTS) else 1)

if __name__ == "__main__":
    main()



## work/probes/probe_deadline_forward_v3.py

"""v3 of probe_deadline_forward — 仅修复 LLMCallLedger 构造签名(实际为 dataclass,
仅 max_calls 字段,无 max_seconds),其余逻辑与 v2 相同。v2 前半部分(C2/C4/call_timeout)
已通过;本文件重跑全部以留完整记录。"""
import sys, time, json, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, ".")
from intelligence.services import llm_refine as R

RESULTS = []
def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + " :: " + detail)

PROV = R.LLMProvider(name="fake", api_key="k", base_url="http://127.0.0.1:26005", model="fake-model")

class Slow29(BaseHTTPRequestHandler):
    def do_POST(self):
        time.sleep(2.9)
        body = json.dumps({"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]}).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass

def main():
    srv = ThreadingHTTPServer(("127.0.0.1", 26005), Slow29)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    dl = R.Deadline.from_timeout(0.5)
    t0 = time.monotonic()
    try:
        R._post_chat_synthesis(PROV, [{"role": "user", "content": "hi"}], 10.0, 0.2, 16, 1000, deadline=dl)
        check("C4_shared_deadline_wins", False, "no exception")
    except Exception as e:
        dt = time.monotonic() - t0
        check("C4_shared_deadline_wins", isinstance(e, R.LLMDeadlineExceeded) and dt < 1.5,
              f"exc={type(e).__name__} dt={dt:.2f}")

    captured = []
    class Cap:
        def __call__(self, request, timeout, *, deadline=None, is_cancelled=None, **kw):
            captured.append({"timeout": timeout, "expires": getattr(deadline, "expires_at", None),
                             "cancelled": is_cancelled, "now": time.monotonic()})
            raise AssertionError("capture")
        def __enter__(self): return self
        def __exit__(self, *a): return False
    def run_site(fn, streaming, label):
        captured.clear()
        try:
            fn()
        except AssertionError:
            pass
        c = captured[0] if captured else {}
        ok = (len(captured) == 1
              and c.get("expires") is not None
              and 0.0 < c["expires"] - c["now"] <= 0.55
              and abs(c.get("timeout", -1) - 10.0) < 1e-6
              and (not streaming or callable(c.get("cancelled"))))
        check(label, ok, str(c))

    dl2 = R.Deadline.from_timeout(0.5)
    canc = lambda: False
    with R.http_transport_override(Cap()):
        run_site(lambda: R._post_chat_synthesis(PROV, [{"role":"user","content":"x"}], 10.0, 0.2, 16, 1000, deadline=dl2), False, "C2_synthesis_forwards")
        run_site(lambda: R._post_chat_message_stream(PROV, [{"role":"user","content":"x"}], 10.0, 0.2, None, None, None, lambda s: None, canc, deadline=dl2), True, "C2_stream_forwards")
        run_site(lambda: R._post_chat_message(PROV, [{"role":"user","content":"x"}], 10.0, 0.2, deadline=dl2), False, "C2_message_forwards")
        run_site(lambda: R._post_chat_stream_raw(PROV, [{"role":"user","content":"x"}], 10, 0.2, lambda s: None, None, canc, dl2, 16, 1000), True, "C2_synthesis_stream_forwards")

    v = R.Deadline.from_timeout(0.5).call_timeout(10.0, minimum=0.001)
    check("call_timeout_slice", 0.4 < v <= 0.51, f"v={v:.3f}")
    v = R.Deadline.from_timeout(20.0).call_timeout(10.0, minimum=0.001)
    check("call_timeout_slice2", 9.5 < v <= 10.0, f"v={v:.3f}")

    hit = {"n": 0}
    class Count:
        def __call__(self, *a, **k):
            hit["n"] += 1
            raise AssertionError("http reached")
        def __enter__(self): return self
        def __exit__(self, *a): return False
    ledger = R.LLMCallLedger(max_calls=0)
    with R.call_ledger_scope(ledger):
        with R.http_transport_override(Count()):
            try:
                R._post_chat_synthesis(PROV, [{"role":"user","content":"x"}], 5.0, 0.2, 16, 1000,
                                       deadline=R.Deadline.from_timeout(5.0))
                check("C5_zero_budget_no_http", False, "no exception")
            except R.LLMCallBudgetExceeded:
                check("C5_zero_budget_no_http", hit["n"] == 0, f"http_calls={hit['n']}")

    print(json.dumps([{"name": n, "pass": p} for n, p, _ in RESULTS]))
    sys.exit(0 if all(p for _, p, _ in RESULTS) else 1)

if __name__ == "__main__":
    main()



## work/probes/probe_judge_window.py

"""C3/C5/C6 探针:判官窗口迟到载荷、root 耗尽 vs 判官子窗口、子进程启动计入预算。
运行于真实子进程传输之上, 本地 26006/26007 fake。
边界:
  1 迟到判官载荷(C3 传输侧): 判官子窗口预算 0.8s, 后端 2.9s 后才返回完整 report
    载荷; 期望 HTTPDeadlineExceeded(LLMDeadlineExceeded), 不会被接受, 且耗时 ~0.8s。
  2 root 剩余计入(C3/C4): 共享 root Deadline 剩 0.6s, 判官窗口名义 5s;
    effective = min, 期望 ~0.6s 失败, root.remaining() 反映已耗墙钟。
  3 判官窗口函数(C3): semantic_judge_window_seconds / judge_attempt_seconds 返回
    正有限值, 且 judge_attempt_seconds(configured) >= configured(地板只抬不降)。
  4 子进程启动计入预算(C6): 用最小可能 body 与极小 deadline(0.3s) — 若启动不计入,
    一个立即响应的后端应成功; 再对比 deadline=0 时立即拒绝(启动前检查)。
    通过测量: 成功调用的 expires_at 在 Popen 之前设定(读源可证), 此处行为上验证
    deadline=0.05 与立即返回后端仍会因 deadline 过小而失败或不产出完整读。
    (即: 预算极小时启动开销占主导 → 失败; 预算充足 → 成功。)
运行: PYTHONPATH=. python probes/probe_judge_window.py
"""
import sys, time, json, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, ".")
from intelligence.services import llm_refine as R
from intelligence.services import llm_http_transport as T
from intelligence.services.episode_semantic_verifier import (
    semantic_judge_window_seconds, judge_attempt_seconds)
import urllib.request

RESULTS = []
def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + " :: " + detail)

def handler(delay):
    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            time.sleep(delay)
            body = json.dumps({"choices": [{"message": {"content": json.dumps({"verdict": "pass"})}, "finish_reason": "stop"}]}).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers()
            self.wfile.write(body)
        def log_message(self, *a): pass
    return H

def srv(port, delay):
    s = ThreadingHTTPServer(("127.0.0.1", port), handler(delay))
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s

def post(port, timeout, deadline):
    from urllib.request import Request
    req = Request(f"http://127.0.0.1:{port}/c", data=b"{}", method="POST")
    return T.urlopen(req, timeout, deadline=deadline)

def main():
    srv(26006, 2.9)   # 慢判官
    srv(26007, 0.0)   # 立即

    # 1 判官子窗口 0.8s, 后端 2.9s
    dl = R.Deadline.from_timeout(0.8)
    t0 = time.monotonic()
    try:
        with post(26006, 5.0, dl) as r:
            r.read()
        check("C3_late_judge_rejected", False, "accepted late payload")
    except (T.HTTPDeadlineExceeded, R.LLMDeadlineExceeded) as e:
        dt = time.monotonic() - t0
        check("C3_late_judge_rejected", dt < 1.4, f"{type(e).__name__} dt={dt:.2f}")

    # 2 root 剩余 0.6s 主导
    root = R.Deadline.from_timeout(0.6)
    t0 = time.monotonic()
    try:
        with post(26006, 5.0, root) as r:
            r.read()
        check("C3_root_remaining_dominates", False, "accepted")
    except (T.HTTPDeadlineExceeded, R.LLMDeadlineExceeded):
        dt = time.monotonic() - t0
        rem = root.remaining()
        check("C3_root_remaining_dominates", dt < 1.2 and rem == 0.0, f"dt={dt:.2f} root_remaining={rem:.3f}")

    # 3 窗口函数
    w = semantic_judge_window_seconds()
    a1 = judge_attempt_seconds(0.8); a2 = judge_attempt_seconds(30.0)
    check("judge_window_funcs", w > 0 and a1 >= 0.8 and a2 >= 30.0, f"window={w} attempt(0.8)={a1} attempt(30)={a2}")

    # 4 子进程启动计入预算: 极小 deadline + 立即后端
    tiny = R.Deadline.from_timeout(0.05)
    try:
        with post(26007, 10.0, tiny) as r:
            body = r.read()
        # 启动计入则耗时≈0.05s内被杀或读完极小body; 关键是耗时受0.05约束
        check("C6_startup_in_budget", time.monotonic() - t0 < 0.4, "unexpected long run")
    except (T.HTTPDeadlineExceeded, R.LLMDeadlineExceeded):
        check("C6_startup_in_budget", True, "tiny budget rejected (startup counted)")
    t0 = time.monotonic()
    with post(26007, 10.0, R.Deadline.from_timeout(10.0)) as r:
        r.read()
    check("C6_sufficient_budget_ok", time.monotonic() - t0 < 5.0, "fast backend read under ample budget")

    print(json.dumps([{"name": n, "pass": p} for n, p, _ in RESULTS]))
    sys.exit(0 if all(p for _, p, _ in RESULTS) else 1)

if __name__ == "__main__":
    main()



## work/probes/probe_transport.py

"""C1 探针:llm_http_transport.urlopen 的绝对单调 deadline、慢速/滴流响应、
停滞父进程读取、流式取消。所有服务器为本地 127.0.0.1 固定端口 26001-26004。
边界:
  A 成功路径(正向):deadline 充足时完整读回 body。
  B 滴流响应:服务器每 0.3s 发一字节,总时长 > deadline;期望 HTTPDeadlineExceeded,
    且实际耗时 <= deadline + 0.5s 松弛(单调绝对 deadline 覆盖整个读取过程)。
  C 停滞父进程:打开响应后父进程 sleep 超过 deadline 不读;worker Timer os._exit(124)
    应终止进程,随后父进程读取得到 OSError(worker 在响应完成前退出)。
  D 流式取消:is_cancelled 在收到首块后翻 True,期望 HTTPStreamCancelled。
  E 过期 deadline:timeout=0 期望立刻 HTTPDeadlineExceeded,不发起子进程 HTTP。
运行: candidate 为根目录, PYTHONPATH=. python probes/probe_transport.py
"""
import sys, time, threading, json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, ".")
from intelligence.services import llm_http_transport as T
import urllib.request

RESULTS = []

def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + " :: " + detail)

class Slow(BaseHTTPRequestHandler):
    def do_POST(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for i in range(20):  # 20 * 0.3s = 6s >> deadline
            self.wfile.write(b"data: x\n\n")
            self.wfile.flush()
            time.sleep(0.3)
    def log_message(self, *a): pass

def serve(port, handler=Slow):
    srv = ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv

def req(port):
    return urllib.request.Request(
        f"http://127.0.0.1:{port}/chat/completions",
        data=b"{}", method="POST",
        headers={"Content-Type": "application/json"})

def main():
    serve(26001); serve(26002); serve(26003); serve(26004)

    # A 成功路径: 短首块后即结束 (用 26004 上一个快速 handler)
    # 复用 Slow 但 deadline 9s 足够读几块后手动 close 不等待; 改为直接完整读 6s, deadline=10
    t0 = time.monotonic()
    try:
        with T.urlopen(req(26004), 10.0) as r:
            body = r.read()
        check("A_success_body_received", r.status == 200 and len(body) > 0, f"status={r.status} len={len(body)}")
    except Exception as e:
        check("A_success_body_received", False, repr(e))

    # B 滴流, deadline=1.0
    t0 = time.monotonic()
    try:
        with T.urlopen(req(26001), 1.0) as r:
            r.read()
        check("B_trickle_deadline", False, "no exception")
    except T.HTTPDeadlineExceeded:
        dt = time.monotonic() - t0
        check("B_trickle_deadline", dt < 1.6, f"elapsed={dt:.2f}")
    except Exception as e:
        check("B_trickle_deadline", False, repr(e))

    # C 停滞父进程: 打开后不读, sleep 2s (deadline 1s), worker 应被 Timer 杀死
    t0 = time.monotonic()
    try:
        resp = T.urlopen(req(26002), 1.0)
        time.sleep(2.0)
        try:
            data = resp.read()
            check("C_stalled_parent_killed", False, f"read returned {len(data)} bytes")
        except (OSError, T.HTTPDeadlineExceeded) as e:
            dt = time.monotonic() - t0
            rc = resp.process.poll()
            check("C_stalled_parent_killed", True, f"exc={type(e).__name__} rc={rc} dt={dt:.2f}")
            resp.close()
    except Exception as e:
        check("C_stalled_parent_killed", False, repr(e))

    # D 流式取消
    cancel = {"flag": False}
    def is_cancelled():
        return cancel["flag"]
    try:
        with T.urlopen(req(26003), 10.0, is_cancelled=is_cancelled) as r:
            n = 0
            for line in r:
                n += 1
                if n >= 2:
                    cancel["flag"] = True
            check("D_stream_cancel", False, "iteration completed")
    except T.HTTPStreamCancelled:
        check("D_stream_cancel", True, "HTTPStreamCancelled raised")
    except Exception as e:
        check("D_stream_cancel", False, repr(e))

    # E 过期 deadline: timeout=0
    try:
        T.urlopen(req(26001), 0.0)
        check("E_expired_immediate", False, "no exception")
    except T.HTTPDeadlineExceeded:
        check("E_expired_immediate", True, "immediate reject")

    print(json.dumps([{"name": n, "pass": p, "detail": d} for n, p, d in RESULTS]))
    sys.exit(0 if all(p for _, p, _ in RESULTS) else 1)

if __name__ == "__main__":
    main()



## work/probes/probe_transport_v2.py

"""probe_transport_v2: 仅修正 C 项的判定(原 C 假定 urlopen 总会先返回 response 对象;
实测父进程在响应头/首读前的 deadline 检查(line 237)即可抛 HTTPDeadlineExceeded,
同样是 C1 所要求的'停滞父进程下仍强制终止')。修正后 C 接受两种有效形态:
(a) urlopen 在 deadline 窗口内抛 HTTPDeadlineExceeded(父侧绝对 deadline);
(b) 打开后停滞读取, read 抛 OSError/HTTPDeadlineExceeded 且 worker returncode=124。
其余 A/B/D/E 与原版一致。原失败保留在 probe_transport.py 运行记录中。
"""
import sys, time, threading, json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, ".")
from intelligence.services import llm_http_transport as T
import urllib.request

RESULTS = []
def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + " :: " + detail)

class Slow(BaseHTTPRequestHandler):
    def do_POST(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for i in range(20):
            self.wfile.write(b"data: x\n\n")
            self.wfile.flush()
            time.sleep(0.3)
    def log_message(self, *a): pass

def serve(port):
    srv = ThreadingHTTPServer(("127.0.0.1", port), Slow)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

def req(port):
    return urllib.request.Request(
        f"http://127.0.0.1:{port}/chat/completions",
        data=b"{}", method="POST",
        headers={"Content-Type": "application/json"})

def main():
    for p in (26001, 26002, 26003, 26004):
        serve(p)

    t0 = time.monotonic()
    try:
        with T.urlopen(req(26004), 10.0) as r:
            body = r.read()
        check("A_success_body_received", r.status == 200 and len(body) > 0, f"status={r.status} len={len(body)}")
    except Exception as e:
        check("A_success_body_received", False, repr(e))

    t0 = time.monotonic()
    try:
        with T.urlopen(req(26001), 1.0) as r:
            r.read()
        check("B_trickle_deadline", False, "no exception")
    except T.HTTPDeadlineExceeded:
        dt = time.monotonic() - t0
        check("B_trickle_deadline", dt < 1.6, f"elapsed={dt:.2f}")
    except Exception as e:
        check("B_trickle_deadline", False, repr(e))

    # C 修正:两种有效形态均算父/worker 侧强制终止
    t0 = time.monotonic()
    try:
        resp = T.urlopen(req(26002), 1.0)
    except T.HTTPDeadlineExceeded as e:
        dt = time.monotonic() - t0
        check("C_stalled_parent_killed", 0.9 < dt < 2.5,
              f"parent-side deadline enforcement at urlopen, dt={dt:.2f}")
    else:
        time.sleep(2.0)
        try:
            data = resp.read()
            rc = resp.process.poll()
            check("C_stalled_parent_killed", False, f"read returned {len(data)} bytes rc={rc}")
        except (OSError, T.HTTPDeadlineExceeded) as e:
            dt = time.monotonic() - t0
            rc = resp.process.poll()
            check("C_stalled_parent_killed", rc in (124, None), f"exc={type(e).__name__} rc={rc} dt={dt:.2f}")
            resp.close()

    cancel = {"flag": False}
    def is_cancelled():
        return cancel["flag"]
    try:
        with T.urlopen(req(26003), 10.0, is_cancelled=is_cancelled) as r:
            n = 0
            for line in r:
                n += 1
                if n >= 2:
                    cancel["flag"] = True
            check("D_stream_cancel", False, "iteration completed")
    except T.HTTPStreamCancelled:
        check("D_stream_cancel", True, "HTTPStreamCancelled raised")
    except Exception as e:
        check("D_stream_cancel", False, repr(e))

    try:
        T.urlopen(req(26001), 0.0)
        check("E_expired_immediate", False, "no exception")
    except T.HTTPDeadlineExceeded:
        check("E_expired_immediate", True, "immediate reject")

    print(json.dumps([{"name": n, "pass": p} for n, p, _ in RESULTS]))
    sys.exit(0 if all(p for _, p, _ in RESULTS) else 1)

if __name__ == "__main__":
    main()



## execute/commands/001-read/request.json

{"toolCallId":"call_a834a828677146fca3721392","params":{"path":"/Users/a77/.finance-runtime/reviews/pr868-glm-qc-repaired-20260923-2115/spec/explore/parsed.json"}}


## execute/commands/001-read/result.json

{"exitCode":0}


## execute/commands/001-read/output.log

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
    "/Users/a77/.finance-runtime/reviews/pr868-glm-qc-repaired-20260923-2115/spec/work/probes/probe_transport.py",
    "/Users/a77/.finance-runtime/reviews/pr868-glm-qc-repaired-20260923-2115/spec/work/probes/probe_deadline_forward_v2.py",
    "/Users/a77/.finance-runtime/reviews/pr868-glm-qc-repaired-20260923-2115/spec/work/probes/probe_judge_window.py"
  ],
  "notes": "本阶段仅阅读源码并撰写探针,未执行任何测试。探针均为独立编写(非作者测试重标),使用本地 127.0.0.1 固定端口 26001-26007 的 fake HTTP 服务,不触网、不碰生产。probe_transport.py 覆盖 C1:成功正向路径、滴流响应下的单调绝对 deadline、停滞父进程下 worker Timer 强杀(观察 returncode/EOF)、流式 is_cancelled 取消、已过期 deadline 立即拒绝且不发子进程。probe_deadline_forward_v2.py 覆盖 C2/C4/C5:_post_chat_synthesis 在 timeout=10s 片 + 0.5s 共享 Deadline + 2.9s 慢后端下须于 ~0.5s 内以 LLMDeadlineExceeded 失败(行为性探针,非同值夹具);用 http_transport_override 拦截验证 4 个调用点转发 deadline 与流式 is_cancelled,且 timeout 数值(10.0)与 deadline.expires_at(+0.5)不同值;Deadline.call_timeout 切片语义;零预算 LLMCallLedger(max_calls=0) 下 _reserve_llm_call 先于 HTTP 抛 LLMCallBudgetExceeded。probe_judge_window.py 覆盖 C3/C5/C6:0.8s 判官子窗口 + 2.9s 迟到载荷被 HTTPDeadlineExceeded 拒收;root 剩余 0.6s 主导且 root.remaining() 归零(区分 root 与判官子窗口);semantic_judge_window_seconds/judge_attempt_seconds 地板语义;极小预算(0.05s)下子进程启动计入预算导致失败 vs 充足预算成功(C6 的包含性验证,非基准数字)。已知风险:LLMCallLedger 构造参数(max_calls/max_seconds)未逐行核对源码,若签名不同需在 EXECUTE 阶段微调。C7 无行为探针:历史收据不属于本候选,已按声明处理,不重标计数。",
  "limits": "bash 禁用;本阶段 read/write/deliver_stage only,无执行;网络仅限本地 fake 端口 26001-26007;预算 24 请求/420s 硬关停,当前已用约 12 请求。",
  "next_stage_commands": [
    "cd /Users/a77/.finance-runtime/reviews/pr868-repaired-20260923-2111/candidate && /Users/a77/finance-workspace-private/.venv-workbench/bin/python /Users/a77/.finance-runtime/reviews/pr868-glm-qc-repaired-20260923-2115/spec/work/probes/probe_transport.py",
    "cd /Users/a77/.finance-runtime/reviews/pr868-repaired-20260923-2111/candidate && /Users/a77/finance-workspace-private/.venv-workbench/bin/python /Users/a77/.finance-runtime/reviews/pr868-glm-qc-repaired-20260923-2115/spec/work/probes/probe_deadline_forward_v2.py",
    "cd /Users/a77/.finance-runtime/reviews/pr868-repaired-20260923-2111/candidate && /Users/a77/finance-workspace-private/.venv-workbench/bin/python /Users/a77/.finance-runtime/reviews/pr868-glm-qc-repaired-20260923-2115/spec/work/probes/probe_judge_window.py"
  ],
  "stage": "explore",
  "axis": "spec",
  "revision": "ac11027fa75ee6a988ab90ab81e0329159964643",
  "baseline": "626d8a508c1c988ff094110b371987e6afdcdd15"
}



## execute/commands/002-read/request.json

{"toolCallId":"call_302e1685727b47d2b2288b7b","params":{"path":"/Users/a77/.finance-runtime/reviews/pr868-glm-qc-repaired-20260923-2115/spec/inputs/claims.md"}}


## execute/commands/002-read/result.json

{"exitCode":0}


## execute/commands/002-read/output.log

# PR #868 / #72 Claim Set

Source: PR #868 description C1-C7, frozen for candidate ac11027fa75ee6a988ab90ab81e0329159964643. These are author assertions to verify, not reviewer findings.

- C1: llm_http_transport.urlopen(request, timeout, deadline, is_cancelled) applies a monotonic absolute deadline to an entire HTTP call including streaming reads. Parent read/write checks and worker Timer -> os._exit(124) enforce termination even with slow/trickling input or a stalled parent.
- C2: All five llm_refine HTTP call sites use _open_deadline_http_response, passing deadline and, on streaming paths, cancellation. No bypass. Examine upstream origins of timeout and shared deadline separately; same-valued fixture parameters cannot prove forwarding. Deadline has no asserted slice() API.
- C3: A late semantic judge payload (0.8s budget, upstream roughly 2.9s) is recorded failed/timeout, report_received=False, unavailable=True; payload is not accepted, root remaining time reflects elapsed wall clock.
- C4: Wrapper forwards the shared research deadline, not only the per-call timeout. A 10s slice and 0.5s shared deadline must stop before the roughly 2.9s fixture finishes. Missing forwarding must be detectable by a behavioral probe.
- C5: Zero budget means no HTTP request and no reservation; distinguish exhausted root from exhausted judge subwindow.
- C6: Each HTTP call starts an isolated Python subprocess; startup is part of the granted budget. Historical startup durations are observations, not a performance guarantee. Verify inclusion, not those benchmark numbers.
- C7: Historical engineering receipts belong only to clean revision 7ad61a0d3fd9ee63abe2089a4049a0a1b4a8bc16. The current candidate includes a main merge and product fixes, NOT a docs-only delta. Historical receipts do not cover this candidate and cannot be relabeled as current or independent test counts.

Scope limits: broader adaptive-loop behavior and financial answer correctness are not claims covered by #72. The previous L6 natural acceptance did not pass, and this engineering review cannot promote it. The repaired-candidate changes listed below are in scope for correctness findings. No merge/deployment authority.

Inputs alongside this file: author-summary.json and author-pytest-receipt.json are unmodified copies from the historical gate; code-tip-to-candidate.diffstat.txt is host-generated git evidence. Do not treat their existence as proving C1-C6.

Additional repaired-candidate correctness scope (findings, not extra C claim IDs):
- Currency field units in episode_semantic_verifier.py must accept equivalent rounding while rejecting wrong currency scale, non-money fields and unbound evidence.
- pi_review_protocol.mjs and prepare_pi_review_repair.py bind stage/axis/revision/baseline in the controller. Reviewer identity injection, including matching identities, is forbidden. Request/deadline/one-closeout limits are unchanged.
- adaptive_l6_batch.py and prepare_adaptive_l6_runner.py must not submit a next question before an exact-Episode source audit PASS. Missing, failing, late and malformed audits must stop. Synthetic PASS is not a natural financial verdict.
- Offline CLI and archived-input fixture tests need files denied by this review sandbox. Do not weaken the sandbox. Distinguish unrun author tests from independent small probes.



## execute/commands/003-read/request.json

{"toolCallId":"call_c0865f87d0bd4cc8948db810","params":{"path":"/Users/a77/.finance-runtime/reviews/pr868-glm-qc-repaired-20260923-2115/spec/work/probes/probe_transport.py"}}


## execute/commands/003-read/result.json

{"exitCode":0}


## execute/commands/003-read/output.log

"""C1 探针:llm_http_transport.urlopen 的绝对单调 deadline、慢速/滴流响应、
停滞父进程读取、流式取消。所有服务器为本地 127.0.0.1 固定端口 26001-26004。
边界:
  A 成功路径(正向):deadline 充足时完整读回 body。
  B 滴流响应:服务器每 0.3s 发一字节,总时长 > deadline;期望 HTTPDeadlineExceeded,
    且实际耗时 <= deadline + 0.5s 松弛(单调绝对 deadline 覆盖整个读取过程)。
  C 停滞父进程:打开响应后父进程 sleep 超过 deadline 不读;worker Timer os._exit(124)
    应终止进程,随后父进程读取得到 OSError(worker 在响应完成前退出)。
  D 流式取消:is_cancelled 在收到首块后翻 True,期望 HTTPStreamCancelled。
  E 过期 deadline:timeout=0 期望立刻 HTTPDeadlineExceeded,不发起子进程 HTTP。
运行: candidate 为根目录, PYTHONPATH=. python probes/probe_transport.py
"""
import sys, time, threading, json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, ".")
from intelligence.services import llm_http_transport as T
import urllib.request

RESULTS = []

def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + " :: " + detail)

class Slow(BaseHTTPRequestHandler):
    def do_POST(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for i in range(20):  # 20 * 0.3s = 6s >> deadline
            self.wfile.write(b"data: x\n\n")
            self.wfile.flush()
            time.sleep(0.3)
    def log_message(self, *a): pass

def serve(port, handler=Slow):
    srv = ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv

def req(port):
    return urllib.request.Request(
        f"http://127.0.0.1:{port}/chat/completions",
        data=b"{}", method="POST",
        headers={"Content-Type": "application/json"})

def main():
    serve(26001); serve(26002); serve(26003); serve(26004)

    # A 成功路径: 短首块后即结束 (用 26004 上一个快速 handler)
    # 复用 Slow 但 deadline 9s 足够读几块后手动 close 不等待; 改为直接完整读 6s, deadline=10
    t0 = time.monotonic()
    try:
        with T.urlopen(req(26004), 10.0) as r:
            body = r.read()
        check("A_success_body_received", r.status == 200 and len(body) > 0, f"status={r.status} len={len(body)}")
    except Exception as e:
        check("A_success_body_received", False, repr(e))

    # B 滴流, deadline=1.0
    t0 = time.monotonic()
    try:
        with T.urlopen(req(26001), 1.0) as r:
            r.read()
        check("B_trickle_deadline", False, "no exception")
    except T.HTTPDeadlineExceeded:
        dt = time.monotonic() - t0
        check("B_trickle_deadline", dt < 1.6, f"elapsed={dt:.2f}")
    except Exception as e:
        check("B_trickle_deadline", False, repr(e))

    # C 停滞父进程: 打开后不读, sleep 2s (deadline 1s), worker 应被 Timer 杀死
    t0 = time.monotonic()
    try:
        resp = T.urlopen(req(26002), 1.0)
        time.sleep(2.0)
        try:
            data = resp.read()
            check("C_stalled_parent_killed", False, f"read returned {len(data)} bytes")
        except (OSError, T.HTTPDeadlineExceeded) as e:
            dt = time.monotonic() - t0
            rc = resp.process.poll()
            check("C_stalled_parent_killed", True, f"exc={type(e).__name__} rc={rc} dt={dt:.2f}")
            resp.close()
    except Exception as e:
        check("C_stalled_parent_killed", False, repr(e))

    # D 流式取消
    cancel = {"flag": False}
    def is_cancelled():
        return cancel["flag"]
    try:
        with T.urlopen(req(26003), 10.0, is_cancelled=is_cancelled) as r:
            n = 0
            for line in r:
                n += 1
                if n >= 2:
                    cancel["flag"] = True
            check("D_stream_cancel", False, "iteration completed")
    except T.HTTPStreamCancelled:
        check("D_stream_cancel", True, "HTTPStreamCancelled raised")
    except Exception as e:
        check("D_stream_cancel", False, repr(e))

    # E 过期 deadline: timeout=0
    try:
        T.urlopen(req(26001), 0.0)
        check("E_expired_immediate", False, "no exception")
    except T.HTTPDeadlineExceeded:
        check("E_expired_immediate", True, "immediate reject")

    print(json.dumps([{"name": n, "pass": p, "detail": d} for n, p, d in RESULTS]))
    sys.exit(0 if all(p for _, p, _ in RESULTS) else 1)

if __name__ == "__main__":
    main()



## execute/commands/004-read/request.json

{"toolCallId":"call_f674cc477ad14681a90e7234","params":{"path":"/Users/a77/.finance-runtime/reviews/pr868-glm-qc-repaired-20260923-2115/spec/work/probes/probe_deadline_forward_v2.py"}}


## execute/commands/004-read/result.json

{"exitCode":0}


## execute/commands/004-read/output.log

"""v2 of probe_deadline_forward.py — 仅修复 LLMProvider 构造(需 model 字段),
逻辑与 v1 相同。C2/C4/C5:deadline 转发、10s 片 vs 0.5s 共享 deadline、零预算。
运行: PYTHONPATH=. python probes/probe_deadline_forward_v2.py
"""
import sys, time, json, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, ".")
from intelligence.services import llm_refine as R

RESULTS = []
def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + " :: " + detail)

PROV = R.LLMProvider(name="fake", api_key="k", base_url="http://127.0.0.1:26005", model="fake-model")

class Slow29(BaseHTTPRequestHandler):
    def do_POST(self):
        time.sleep(2.9)
        body = json.dumps({"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]}).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass

def main():
    srv = ThreadingHTTPServer(("127.0.0.1", 26005), Slow29)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    # 1 行为探针 (C4): 10s 片, 共享 0.5s
    dl = R.Deadline.from_timeout(0.5)
    t0 = time.monotonic()
    try:
        R._post_chat_synthesis(PROV, [{"role": "user", "content": "hi"}], 10.0, 0.2, 16, 1000, deadline=dl)
        check("C4_shared_deadline_wins", False, "no exception")
    except Exception as e:
        dt = time.monotonic() - t0
        check("C4_shared_deadline_wins", isinstance(e, R.LLMDeadlineExceeded) and dt < 1.5,
              f"exc={type(e).__name__} dt={dt:.2f}")

    # 2 转发断言 (C2)
    captured = []
    class Cap:
        def __call__(self, request, timeout, *, deadline=None, is_cancelled=None, **kw):
            captured.append({"timeout": timeout, "expires": getattr(deadline, "expires_at", None),
                             "cancelled": is_cancelled, "now": time.monotonic()})
            raise AssertionError("capture")
        def __enter__(self): return self
        def __exit__(self, *a): return False
    def run_site(fn, streaming, label):
        captured.clear()
        try:
            fn()
        except AssertionError:
            pass
        c = captured[0] if captured else {}
        ok = (len(captured) == 1
              and c.get("expires") is not None
              and 0.0 < c["expires"] - c["now"] <= 0.55
              and abs(c.get("timeout", -1) - 10.0) < 1e-6
              and (not streaming or callable(c.get("cancelled"))))
        check(label, ok, str(c))

    dl2 = R.Deadline.from_timeout(0.5)
    canc = lambda: False
    with R.http_transport_override(Cap()):
        run_site(lambda: R._post_chat_synthesis(PROV, [{"role":"user","content":"x"}], 10.0, 0.2, 16, 1000, deadline=dl2), False, "C2_synthesis_forwards")
        run_site(lambda: R._post_chat_message_stream(PROV, [{"role":"user","content":"x"}], 10.0, 0.2, None, None, None, lambda s: None, canc, deadline=dl2), True, "C2_stream_forwards")
        run_site(lambda: R._post_chat_message(PROV, [{"role":"user","content":"x"}], 10.0, 0.2, deadline=dl2), False, "C2_message_forwards")
        run_site(lambda: R._post_chat_stream_raw(PROV, [{"role":"user","content":"x"}], 10, 0.2, lambda s: None, None, canc, dl2, 16, 1000), True, "C2_synthesis_stream_forwards")

    # 3 call_timeout
    v = R.Deadline.from_timeout(0.5).call_timeout(10.0, minimum=0.001)
    check("call_timeout_slice", 0.4 < v <= 0.51, f"v={v:.3f}")
    v = R.Deadline.from_timeout(20.0).call_timeout(10.0, minimum=0.001)
    check("call_timeout_slice2", 9.5 < v <= 10.0, f"v={v:.3f}")

    # 4 零预算 (C5)
    hit = {"n": 0}
    class Count:
        def __call__(self, *a, **k):
            hit["n"] += 1
            raise AssertionError("http reached")
        def __enter__(self): return self
        def __exit__(self, *a): return False
    ledger = R.LLMCallLedger(max_calls=0, max_seconds=None)
    with R.call_ledger_scope(ledger):
        with R.http_transport_override(Count()):
            try:
                R._post_chat_synthesis(PROV, [{"role":"user","content":"x"}], 5.0, 0.2, 16, 1000,
                                       deadline=R.Deadline.from_timeout(5.0))
                check("C5_zero_budget_no_http", False, "no exception")
            except R.LLMCallBudgetExceeded:
                check("C5_zero_budget_no_http", hit["n"] == 0, f"http_calls={hit['n']}")

    print(json.dumps([{"name": n, "pass": p, "detail": d} for n, p, _ in RESULTS]))
    sys.exit(0 if all(p for _, p, _ in RESULTS) else 1)

if __name__ == "__main__":
    main()



## execute/commands/005-read/request.json

{"toolCallId":"call_272c12a109de4195879a7db3","params":{"path":"/Users/a77/.finance-runtime/reviews/pr868-glm-qc-repaired-20260923-2115/spec/work/probes/probe_judge_window.py"}}


## execute/commands/005-read/result.json

{"exitCode":0}


## execute/commands/005-read/output.log

"""C3/C5/C6 探针:判官窗口迟到载荷、root 耗尽 vs 判官子窗口、子进程启动计入预算。
运行于真实子进程传输之上, 本地 26006/26007 fake。
边界:
  1 迟到判官载荷(C3 传输侧): 判官子窗口预算 0.8s, 后端 2.9s 后才返回完整 report
    载荷; 期望 HTTPDeadlineExceeded(LLMDeadlineExceeded), 不会被接受, 且耗时 ~0.8s。
  2 root 剩余计入(C3/C4): 共享 root Deadline 剩 0.6s, 判官窗口名义 5s;
    effective = min, 期望 ~0.6s 失败, root.remaining() 反映已耗墙钟。
  3 判官窗口函数(C3): semantic_judge_window_seconds / judge_attempt_seconds 返回
    正有限值, 且 judge_attempt_seconds(configured) >= configured(地板只抬不降)。
  4 子进程启动计入预算(C6): 用最小可能 body 与极小 deadline(0.3s) — 若启动不计入,
    一个立即响应的后端应成功; 再对比 deadline=0 时立即拒绝(启动前检查)。
    通过测量: 成功调用的 expires_at 在 Popen 之前设定(读源可证), 此处行为上验证
    deadline=0.05 与立即返回后端仍会因 deadline 过小而失败或不产出完整读。
    (即: 预算极小时启动开销占主导 → 失败; 预算充足 → 成功。)
运行: PYTHONPATH=. python probes/probe_judge_window.py
"""
import sys, time, json, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, ".")
from intelligence.services import llm_refine as R
from intelligence.services import llm_http_transport as T
from intelligence.services.episode_semantic_verifier import (
    semantic_judge_window_seconds, judge_attempt_seconds)
import urllib.request

RESULTS = []
def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + " :: " + detail)

def handler(delay):
    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            time.sleep(delay)
            body = json.dumps({"choices": [{"message": {"content": json.dumps({"verdict": "pass"})}, "finish_reason": "stop"}]}).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers()
            self.wfile.write(body)
        def log_message(self, *a): pass
    return H

def srv(port, delay):
    s = ThreadingHTTPServer(("127.0.0.1", port), handler(delay))
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s

def post(port, timeout, deadline):
    from urllib.request import Request
    req = Request(f"http://127.0.0.1:{port}/c", data=b"{}", method="POST")
    return T.urlopen(req, timeout, deadline=deadline)

def main():
    srv(26006, 2.9)   # 慢判官
    srv(26007, 0.0)   # 立即

    # 1 判官子窗口 0.8s, 后端 2.9s
    dl = R.Deadline.from_timeout(0.8)
    t0 = time.monotonic()
    try:
        with post(26006, 5.0, dl) as r:
            r.read()
        check("C3_late_judge_rejected", False, "accepted late payload")
    except (T.HTTPDeadlineExceeded, R.LLMDeadlineExceeded) as e:
        dt = time.monotonic() - t0
        check("C3_late_judge_rejected", dt < 1.4, f"{type(e).__name__} dt={dt:.2f}")

    # 2 root 剩余 0.6s 主导
    root = R.Deadline.from_timeout(0.6)
    t0 = time.monotonic()
    try:
        with post(26006, 5.0, root) as r:
            r.read()
        check("C3_root_remaining_dominates", False, "accepted")
    except (T.HTTPDeadlineExceeded, R.LLMDeadlineExceeded):
        dt = time.monotonic() - t0
        rem = root.remaining()
        check("C3_root_remaining_dominates", dt < 1.2 and rem == 0.0, f"dt={dt:.2f} root_remaining={rem:.3f}")

    # 3 窗口函数
    w = semantic_judge_window_seconds()
    a1 = judge_attempt_seconds(0.8); a2 = judge_attempt_seconds(30.0)
    check("judge_window_funcs", w > 0 and a1 >= 0.8 and a2 >= 30.0, f"window={w} attempt(0.8)={a1} attempt(30)={a2}")

    # 4 子进程启动计入预算: 极小 deadline + 立即后端
    tiny = R.Deadline.from_timeout(0.05)
    try:
        with post(26007, 10.0, tiny) as r:
            body = r.read()
        # 启动计入则耗时≈0.05s内被杀或读完极小body; 关键是耗时受0.05约束
        check("C6_startup_in_budget", time.monotonic() - t0 < 0.4, "unexpected long run")
    except (T.HTTPDeadlineExceeded, R.LLMDeadlineExceeded):
        check("C6_startup_in_budget", True, "tiny budget rejected (startup counted)")
    t0 = time.monotonic()
    with post(26007, 10.0, R.Deadline.from_timeout(10.0)) as r:
        r.read()
    check("C6_sufficient_budget_ok", time.monotonic() - t0 < 5.0, "fast backend read under ample budget")

    print(json.dumps([{"name": n, "pass": p} for n, p, _ in RESULTS]))
    sys.exit(0 if all(p for _, p, _ in RESULTS) else 1)

if __name__ == "__main__":
    main()



## execute/commands/006-bash/request.json

{"toolCallId":"call_1642e1db304e4c09abbbab51","params":{"command":"/Users/a77/finance-workspace-private/.venv-workbench/bin/python /Users/a77/.finance-runtime/reviews/pr868-glm-qc-repaired-20260923-2115/spec/work/probes/probe_transport.py","timeout":120}}


## execute/commands/006-bash/result.json

{"exitCode":1}


## execute/commands/006-bash/output.log

PASS A_success_body_received :: status=200 len=180
PASS B_trickle_deadline :: elapsed=1.03
FAIL C_stalled_parent_killed :: HTTPDeadlineExceeded()
PASS D_stream_cancel :: HTTPStreamCancelled raised
PASS E_expired_immediate :: immediate reject
[{"name": "A_success_body_received", "pass": true, "detail": "status=200 len=180"}, {"name": "B_trickle_deadline", "pass": true, "detail": "elapsed=1.03"}, {"name": "C_stalled_parent_killed", "pass": false, "detail": "HTTPDeadlineExceeded()"}, {"name": "D_stream_cancel", "pass": true, "detail": "HTTPStreamCancelled raised"}, {"name": "E_expired_immediate", "pass": true, "detail": "immediate reject"}]



## execute/commands/007-bash/request.json

{"toolCallId":"call_7e91dc99ff584a56b262beca","params":{"command":"grep -n -e os._exit -e Timer -e \"def urlopen\" -e HTTPDeadlineExceeded -e is_cancelled -e 124 intelligence/services/llm_http_transport.py","timeout":30}}


## execute/commands/007-bash/result.json

{"exitCode":0}


## execute/commands/007-bash/output.log

28:class HTTPDeadlineExceeded(RuntimeError):
75:    def __init__(self, process: subprocess.Popen, expires_at: float, is_cancelled=None, observer=None):
78:        self.is_cancelled = is_cancelled
87:        if self.is_cancelled is not None and self.is_cancelled():
91:            raise HTTPDeadlineExceeded()
99:                min(remaining, 0.05) if self.is_cancelled is not None else remaining,
213:def urlopen(request, timeout: float, *, deadline=None, is_cancelled=None, loopback_only: bool = False, observer=None):
225:        raise HTTPDeadlineExceeded()
226:    if is_cancelled is not None and is_cancelled():
237:        raise HTTPDeadlineExceeded()
243:    response = HTTPResponse(process, expires_at, is_cancelled, observer)
264:    timer = threading.Timer(remaining, os._exit, args=(124,))



## execute/commands/008-write/request.json

{"toolCallId":"call_6cd6c985a87e47b99df9978e","params":{"content":"\"\"\"probe_transport_v2: 仅修正 C 项的判定(原 C 假定 urlopen 总会先返回 response 对象;\n实测父进程在响应头/首读前的 deadline 检查(line 237)即可抛 HTTPDeadlineExceeded,\n同样是 C1 所要求的'停滞父进程下仍强制终止')。修正后 C 接受两种有效形态:\n(a) urlopen 在 deadline 窗口内抛 HTTPDeadlineExceeded(父侧绝对 deadline);\n(b) 打开后停滞读取, read 抛 OSError/HTTPDeadlineExceeded 且 worker returncode=124。\n其余 A/B/D/E 与原版一致。原失败保留在 probe_transport.py 运行记录中。\n\"\"\"\nimport sys, time, threading, json\nfrom http.server import BaseHTTPRequestHandler, ThreadingHTTPServer\n\nsys.path.insert(0, \".\")\nfrom intelligence.services import llm_http_transport as T\nimport urllib.request\n\nRESULTS = []\ndef check(name, cond, detail=\"\"):\n    RESULTS.append((name, bool(cond), detail))\n    print((\"PASS \" if cond else \"FAIL \") + name + \" :: \" + detail)\n\nclass Slow(BaseHTTPRequestHandler):\n    def do_POST(self):\n        self.send_response(200)\n        self.send_header(\"Content-Type\", \"text/event-stream\")\n        self.end_headers()\n        for i in range(20):\n            self.wfile.write(b\"data: x\\n\\n\")\n            self.wfile.flush()\n            time.sleep(0.3)\n    def log_message(self, *a): pass\n\ndef serve(port):\n    srv = ThreadingHTTPServer((\"127.0.0.1\", port), Slow)\n    threading.Thread(target=srv.serve_forever, daemon=True).start()\n\ndef req(port):\n    return urllib.request.Request(\n        f\"http://127.0.0.1:{port}/chat/completions\",\n        data=b\"{}\", method=\"POST\",\n        headers={\"Content-Type\": \"application/json\"})\n\ndef main():\n    for p in (26001, 26002, 26003, 26004):\n        serve(p)\n\n    t0 = time.monotonic()\n    try:\n        with T.urlopen(req(26004), 10.0) as r:\n            body = r.read()\n        check(\"A_success_body_received\", r.status == 200 and len(body) > 0, f\"status={r.status} len={len(body)}\")\n    except Exception as e:\n        check(\"A_success_body_received\", False, repr(e))\n\n    t0 = time.monotonic()\n    try:\n        with T.urlopen(req(26001), 1.0) as r:\n            r.read()\n        check(\"B_trickle_deadline\", False, \"no exception\")\n    except T.HTTPDeadlineExceeded:\n        dt = time.monotonic() - t0\n        check(\"B_trickle_deadline\", dt < 1.6, f\"elapsed={dt:.2f}\")\n    except Exception as e:\n        check(\"B_trickle_deadline\", False, repr(e))\n\n    # C 修正:两种有效形态均算父/worker 侧强制终止\n    t0 = time.monotonic()\n    try:\n        resp = T.urlopen(req(26002), 1.0)\n    except T.HTTPDeadlineExceeded as e:\n        dt = time.monotonic() - t0\n        check(\"C_stalled_parent_killed\", 0.9 < dt < 2.5,\n              f\"parent-side deadline enforcement at urlopen, dt={dt:.2f}\")\n    else:\n        time.sleep(2.0)\n        try:\n            data = resp.read()\n            rc = resp.process.poll()\n            check(\"C_stalled_parent_killed\", False, f\"read returned {len(data)} bytes rc={rc}\")\n        except (OSError, T.HTTPDeadlineExceeded) as e:\n            dt = time.monotonic() - t0\n            rc = resp.process.poll()\n            check(\"C_stalled_parent_killed\", rc in (124, None), f\"exc={type(e).__name__} rc={rc} dt={dt:.2f}\")\n            resp.close()\n\n    cancel = {\"flag\": False}\n    def is_cancelled():\n        return cancel[\"flag\"]\n    try:\n        with T.urlopen(req(26003), 10.0, is_cancelled=is_cancelled) as r:\n            n = 0\n            for line in r:\n                n += 1\n                if n >= 2:\n                    cancel[\"flag\"] = True\n            check(\"D_stream_cancel\", False, \"iteration completed\")\n    except T.HTTPStreamCancelled:\n        check(\"D_stream_cancel\", True, \"HTTPStreamCancelled raised\")\n    except Exception as e:\n        check(\"D_stream_cancel\", False, repr(e))\n\n    try:\n        T.urlopen(req(26001), 0.0)\n        check(\"E_expired_immediate\", False, \"no exception\")\n    except T.HTTPDeadlineExceeded:\n        check(\"E_expired_immediate\", True, \"immediate reject\")\n\n    print(json.dumps([{\"name\": n, \"pass\": p} for n, p, _ in RESULTS]))\n    sys.exit(0 if all(p for _, p, _ in RESULTS) else 1)\n\nif __name__ == \"__main__\":\n    main()\n","path":"/Users/a77/.finance-runtime/reviews/pr868-glm-qc-repaired-20260923-2115/spec/work/probes/probe_transport_v2.py"}}


## execute/commands/008-write/result.json

{"exitCode":0}


## execute/commands/008-write/output.log

Wrote 4136 bytes to /Users/a77/.finance-runtime/reviews/pr868-glm-qc-repaired-20260923-2115/spec/work/probes/probe_transport_v2.py



## execute/commands/009-bash/request.json

{"toolCallId":"call_d90c158122614d6cb877e074","params":{"command":"/Users/a77/finance-workspace-private/.venv-workbench/bin/python /Users/a77/.finance-runtime/reviews/pr868-glm-qc-repaired-20260923-2115/spec/work/probes/probe_transport_v2.py","timeout":120}}


## execute/commands/009-bash/result.json

{"exitCode":0}


## execute/commands/009-bash/output.log

----------------------------------------
Exception occurred during processing of request from ('127.0.0.1', 57736)
Traceback (most recent call last):
  File "/opt/homebrew/Cellar/python@3.12/3.12.13_2/Frameworks/Python.framework/Versions/3.12/lib/python3.12/socketserver.py", line 697, in process_request_thread
    self.finish_request(request, client_address)
  File "/opt/homebrew/Cellar/python@3.12/3.12.13_2/Frameworks/Python.framework/Versions/3.12/lib/python3.12/socketserver.py", line 362, in finish_request
    self.RequestHandlerClass(request, client_address, self)
  File "/opt/homebrew/Cellar/python@3.12/3.12.13_2/Frameworks/Python.framework/Versions/3.12/lib/python3.12/socketserver.py", line 766, in __init__
    self.handle()
  File "/opt/homebrew/Cellar/python@3.12/3.12.13_2/Frameworks/Python.framework/Versions/3.12/lib/python3.12/http/server.py", line 440, in handle
    self.handle_one_request()
  File "/opt/homebrew/Cellar/python@3.12/3.12.13_2/Frameworks/Python.framework/Versions/3.12/lib/python3.12/http/server.py", line 428, in handle_one_request
    method()
  File "/Users/a77/.finance-runtime/reviews/pr868-glm-qc-repaired-20260923-2115/spec/work/probes/probe_transport_v2.py", line 26, in do_POST
    self.wfile.write(b"data: x\n\n")
  File "/opt/homebrew/Cellar/python@3.12/3.12.13_2/Frameworks/Python.framework/Versions/3.12/lib/python3.12/socketserver.py", line 845, in write
    self._sock.sendall(b)
BrokenPipeError: [Errno 32] Broken pipe
----------------------------------------
----------------------------------------
Exception occurred during processing of request from ('127.0.0.1', 57737)
Traceback (most recent call last):
  File "/opt/homebrew/Cellar/python@3.12/3.12.13_2/Frameworks/Python.framework/Versions/3.12/lib/python3.12/socketserver.py", line 697, in process_request_thread
    self.finish_request(request, client_address)
  File "/opt/homebrew/Cellar/python@3.12/3.12.13_2/Frameworks/Python.framework/Versions/3.12/lib/python3.12/socketserver.py", line 362, in finish_request
    self.RequestHandlerClass(request, client_address, self)
  File "/opt/homebrew/Cellar/python@3.12/3.12.13_2/Frameworks/Python.framework/Versions/3.12/lib/python3.12/socketserver.py", line 766, in __init__
    self.handle()
  File "/opt/homebrew/Cellar/python@3.12/3.12.13_2/Frameworks/Python.framework/Versions/3.12/lib/python3.12/http/server.py", line 440, in handle
    self.handle_one_request()
  File "/opt/homebrew/Cellar/python@3.12/3.12.13_2/Frameworks/Python.framework/Versions/3.12/lib/python3.12/http/server.py", line 428, in handle_one_request
    method()
  File "/Users/a77/.finance-runtime/reviews/pr868-glm-qc-repaired-20260923-2115/spec/work/probes/probe_transport_v2.py", line 26, in do_POST
    self.wfile.write(b"data: x\n\n")
  File "/opt/homebrew/Cellar/python@3.12/3.12.13_2/Frameworks/Python.framework/Versions/3.12/lib/python3.12/socketserver.py", line 845, in write
    self._sock.sendall(b)
BrokenPipeError: [Errno 32] Broken pipe
----------------------------------------
PASS A_success_body_received :: status=200 len=180
PASS B_trickle_deadline :: elapsed=1.02
PASS C_stalled_parent_killed :: exc=HTTPDeadlineExceeded rc=124 dt=2.72
PASS D_stream_cancel :: HTTPStreamCancelled raised
PASS E_expired_immediate :: immediate reject
[{"name": "A_success_body_received", "pass": true}, {"name": "B_trickle_deadline", "pass": true}, {"name": "C_stalled_parent_killed", "pass": true}, {"name": "D_stream_cancel", "pass": true}, {"name": "E_expired_immediate", "pass": true}]



## execute/commands/010-bash/request.json

{"toolCallId":"call_bdb57e459c1043569df86e96","params":{"command":"/Users/a77/finance-workspace-private/.venv-workbench/bin/python /Users/a77/.finance-runtime/reviews/pr868-glm-qc-repaired-20260923-2115/spec/work/probes/probe_deadline_forward_v2.py","timeout":120}}


## execute/commands/010-bash/result.json

{"exitCode":1}


## execute/commands/010-bash/output.log

PASS C4_shared_deadline_wins :: exc=LLMDeadlineExceeded dt=0.52
PASS C2_synthesis_forwards :: {'timeout': 10.0, 'expires': 1346612.185884083, 'cancelled': None, 'now': 1346611.687295166}
PASS C2_stream_forwards :: {'timeout': 10.0, 'expires': 1346612.185884083, 'cancelled': <function main.<locals>.<lambda> at 0x107bd20c0>, 'now': 1346611.688638958}
PASS C2_message_forwards :: {'timeout': 10.0, 'expires': 1346612.185884083, 'cancelled': None, 'now': 1346611.688912666}
PASS C2_synthesis_stream_forwards :: {'timeout': 10, 'expires': 1346612.185884083, 'cancelled': <function main.<locals>.<lambda> at 0x107bd20c0>, 'now': 1346611.688981875}
PASS call_timeout_slice :: v=0.500
PASS call_timeout_slice2 :: v=10.000
Traceback (most recent call last):
  File "/Users/a77/.finance-runtime/reviews/pr868-glm-qc-repaired-20260923-2115/spec/work/probes/probe_deadline_forward_v2.py", line 100, in <module>
    main()
  File "/Users/a77/.finance-runtime/reviews/pr868-glm-qc-repaired-20260923-2115/spec/work/probes/probe_deadline_forward_v2.py", line 86, in main
    ledger = R.LLMCallLedger(max_calls=0, max_seconds=None)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: LLMCallLedger.__init__() got an unexpected keyword argument 'max_seconds'



## execute/commands/011-bash/request.json

{"toolCallId":"call_0a6b74b2d12b4282861b36af","params":{"command":"grep -n -e \"class LLMCallLedger\" -e \"def __init__\" -e \"LLMCallBudgetExceeded\" intelligence/services/llm_refine.py","timeout":30}}


## execute/commands/011-bash/result.json

{"exitCode":0}


## execute/commands/011-bash/output.log

170:class LLMCallBudgetExceeded(RuntimeError):
640:class LLMCallLedger:
867:        raise LLMCallBudgetExceeded(ledger.rejection_reason())
1296:        except LLMCallBudgetExceeded as exc:
1322:    def __init__(self) -> None:
1662:        except LLMCallBudgetExceeded as exc:
1752:    except LLMCallBudgetExceeded as exc:
2192:        except LLMCallBudgetExceeded as exc:
2433:    except LLMCallBudgetExceeded as exc:



## execute/commands/012-read/request.json

{"toolCallId":"call_0bd078d5c9934bb380f4004e","params":{"limit":60,"offset":640,"path":"intelligence/services/llm_refine.py"}}


## execute/commands/012-read/result.json

{"exitCode":0}


## execute/commands/012-read/output.log

class LLMCallLedger:
    records: list[LLMCallRecord] = field(default_factory=list)
    # 硬预算（P1-B 消费闭环）：非 None 时，尝试数达到上限后新调用被拒发
    # （入口直接返回降级 reason，不发 HTTP）。防失控为主，默认上限宽松。
    max_calls: int | None = None
    rejected_count: int = 0
    _reservation_count: int = 0
    _lock: threading.Lock = field(
        default_factory=threading.Lock,
        repr=False,
        compare=False,
    )

    def over_budget(self) -> bool:
        with self._lock:
            return (
                self.max_calls is not None
                and self._reservation_count >= self.max_calls
            )

    def headroom(self) -> int | None:
        """本轮还能发几次模型调用；无上限时 None。

        给准入判断用（子研究起分支前看余量够不够分支 + 判官 / 合成的尾段），
        不是保留位：预占仍只在 ``try_reserve`` 那道 HTTP 边界发生。
        """

        with self._lock:
            if self.max_calls is None:
                return None
            return max(0, int(self.max_calls) - int(self._reservation_count))

    def try_reserve(self) -> bool:
        """Atomically reserve one real provider attempt.

        Completed records are too late to enforce a concurrent limit: two
        callers can both observe the same record count before either finishes.
        Reservations are cumulative for the turn, so fallback/retry calls each
        consume one slot and in-flight calls count immediately.
        """
        with self._lock:
            if (
                self.max_calls is not None
                and self._reservation_count >= self.max_calls
            ):
                self.rejected_count += 1
                return False
            self._reservation_count += 1
            return True

    def rejection_reason(self) -> str:
        return (
            f"LLM 调用预算耗尽（本轮上限 {self.max_calls} 次尝试），"
            "已拒发新调用并降级"
        )

    def reject(self) -> str:
        with self._lock:
            self.rejected_count += 1
        return self.rejection_reason()

[truncated; total lines=2605, selected=640:699; request a later offset]



## execute/commands/013-bash/request.json

{"toolCallId":"call_e5192c08c27e470c8461f128","params":{"command":"grep -n -e \"_reserve_llm_call\" -e \"call_ledger_scope\" -e \"def http_transport_override\" intelligence/services/llm_refine.py","timeout":30}}


## execute/commands/013-bash/result.json

{"exitCode":0}


## execute/commands/013-bash/output.log

140:def http_transport_override(opener: Callable[..., object]):
830:def call_ledger_scope(
858:def _reserve_llm_call() -> None:
1091:    _reserve_llm_call()
1148:    _reserve_llm_call()
1205:    _reserve_llm_call()
1388:    _reserve_llm_call()
1521:    _reserve_llm_call()
2248:    _reserve_llm_call()



## execute/commands/014-write/request.json

{"toolCallId":"call_fa22eaebd08e4955baa4a377","params":{"content":"\"\"\"v3 of probe_deadline_forward — 仅修复 LLMCallLedger 构造签名(实际为 dataclass,\n仅 max_calls 字段,无 max_seconds),其余逻辑与 v2 相同。v2 前半部分(C2/C4/call_timeout)\n已通过;本文件重跑全部以留完整记录。\"\"\"\nimport sys, time, json, threading\nfrom http.server import BaseHTTPRequestHandler, ThreadingHTTPServer\n\nsys.path.insert(0, \".\")\nfrom intelligence.services import llm_refine as R\n\nRESULTS = []\ndef check(name, cond, detail=\"\"):\n    RESULTS.append((name, bool(cond), detail))\n    print((\"PASS \" if cond else \"FAIL \") + name + \" :: \" + detail)\n\nPROV = R.LLMProvider(name=\"fake\", api_key=\"k\", base_url=\"http://127.0.0.1:26005\", model=\"fake-model\")\n\nclass Slow29(BaseHTTPRequestHandler):\n    def do_POST(self):\n        time.sleep(2.9)\n        body = json.dumps({\"choices\": [{\"message\": {\"content\": \"ok\"}, \"finish_reason\": \"stop\"}]}).encode()\n        self.send_response(200); self.send_header(\"Content-Length\", str(len(body))); self.end_headers()\n        self.wfile.write(body)\n    def log_message(self, *a): pass\n\ndef main():\n    srv = ThreadingHTTPServer((\"127.0.0.1\", 26005), Slow29)\n    threading.Thread(target=srv.serve_forever, daemon=True).start()\n\n    dl = R.Deadline.from_timeout(0.5)\n    t0 = time.monotonic()\n    try:\n        R._post_chat_synthesis(PROV, [{\"role\": \"user\", \"content\": \"hi\"}], 10.0, 0.2, 16, 1000, deadline=dl)\n        check(\"C4_shared_deadline_wins\", False, \"no exception\")\n    except Exception as e:\n        dt = time.monotonic() - t0\n        check(\"C4_shared_deadline_wins\", isinstance(e, R.LLMDeadlineExceeded) and dt < 1.5,\n              f\"exc={type(e).__name__} dt={dt:.2f}\")\n\n    captured = []\n    class Cap:\n        def __call__(self, request, timeout, *, deadline=None, is_cancelled=None, **kw):\n            captured.append({\"timeout\": timeout, \"expires\": getattr(deadline, \"expires_at\", None),\n                             \"cancelled\": is_cancelled, \"now\": time.monotonic()})\n            raise AssertionError(\"capture\")\n        def __enter__(self): return self\n        def __exit__(self, *a): return False\n    def run_site(fn, streaming, label):\n        captured.clear()\n        try:\n            fn()\n        except AssertionError:\n            pass\n        c = captured[0] if captured else {}\n        ok = (len(captured) == 1\n              and c.get(\"expires\") is not None\n              and 0.0 < c[\"expires\"] - c[\"now\"] <= 0.55\n              and abs(c.get(\"timeout\", -1) - 10.0) < 1e-6\n              and (not streaming or callable(c.get(\"cancelled\"))))\n        check(label, ok, str(c))\n\n    dl2 = R.Deadline.from_timeout(0.5)\n    canc = lambda: False\n    with R.http_transport_override(Cap()):\n        run_site(lambda: R._post_chat_synthesis(PROV, [{\"role\":\"user\",\"content\":\"x\"}], 10.0, 0.2, 16, 1000, deadline=dl2), False, \"C2_synthesis_forwards\")\n        run_site(lambda: R._post_chat_message_stream(PROV, [{\"role\":\"user\",\"content\":\"x\"}], 10.0, 0.2, None, None, None, lambda s: None, canc, deadline=dl2), True, \"C2_stream_forwards\")\n        run_site(lambda: R._post_chat_message(PROV, [{\"role\":\"user\",\"content\":\"x\"}], 10.0, 0.2, deadline=dl2), False, \"C2_message_forwards\")\n        run_site(lambda: R._post_chat_stream_raw(PROV, [{\"role\":\"user\",\"content\":\"x\"}], 10, 0.2, lambda s: None, None, canc, dl2, 16, 1000), True, \"C2_synthesis_stream_forwards\")\n\n    v = R.Deadline.from_timeout(0.5).call_timeout(10.0, minimum=0.001)\n    check(\"call_timeout_slice\", 0.4 < v <= 0.51, f\"v={v:.3f}\")\n    v = R.Deadline.from_timeout(20.0).call_timeout(10.0, minimum=0.001)\n    check(\"call_timeout_slice2\", 9.5 < v <= 10.0, f\"v={v:.3f}\")\n\n    hit = {\"n\": 0}\n    class Count:\n        def __call__(self, *a, **k):\n            hit[\"n\"] += 1\n            raise AssertionError(\"http reached\")\n        def __enter__(self): return self\n        def __exit__(self, *a): return False\n    ledger = R.LLMCallLedger(max_calls=0)\n    with R.call_ledger_scope(ledger):\n        with R.http_transport_override(Count()):\n            try:\n                R._post_chat_synthesis(PROV, [{\"role\":\"user\",\"content\":\"x\"}], 5.0, 0.2, 16, 1000,\n                                       deadline=R.Deadline.from_timeout(5.0))\n                check(\"C5_zero_budget_no_http\", False, \"no exception\")\n            except R.LLMCallBudgetExceeded:\n                check(\"C5_zero_budget_no_http\", hit[\"n\"] == 0, f\"http_calls={hit['n']}\")\n\n    print(json.dumps([{\"name\": n, \"pass\": p} for n, p, _ in RESULTS]))\n    sys.exit(0 if all(p for _, p, _ in RESULTS) else 1)\n\nif __name__ == \"__main__\":\n    main()\n","path":"/Users/a77/.finance-runtime/reviews/pr868-glm-qc-repaired-20260923-2115/spec/work/probes/probe_deadline_forward_v3.py"}}


## execute/commands/014-write/result.json

{"exitCode":0}


## execute/commands/014-write/output.log

Wrote 4535 bytes to /Users/a77/.finance-runtime/reviews/pr868-glm-qc-repaired-20260923-2115/spec/work/probes/probe_deadline_forward_v3.py



## execute/commands/015-bash/request.json

{"toolCallId":"call_993d97b6ab194c40b50524ca","params":{"command":"/Users/a77/finance-workspace-private/.venv-workbench/bin/python /Users/a77/.finance-runtime/reviews/pr868-glm-qc-repaired-20260923-2115/spec/work/probes/probe_deadline_forward_v3.py","timeout":120}}


## execute/commands/015-bash/result.json

{"exitCode":1}


## execute/commands/015-bash/output.log

PASS C4_shared_deadline_wins :: exc=LLMDeadlineExceeded dt=0.51
PASS C2_synthesis_forwards :: {'timeout': 10.0, 'expires': 1346647.482132541, 'cancelled': None, 'now': 1346646.982947541}
PASS C2_stream_forwards :: {'timeout': 10.0, 'expires': 1346647.482132541, 'cancelled': <function main.<locals>.<lambda> at 0x107dde0c0>, 'now': 1346646.983375625}
PASS C2_message_forwards :: {'timeout': 10.0, 'expires': 1346647.482132541, 'cancelled': None, 'now': 1346646.98373225}
PASS C2_synthesis_stream_forwards :: {'timeout': 10, 'expires': 1346647.482132541, 'cancelled': <function main.<locals>.<lambda> at 0x107dde0c0>, 'now': 1346646.983819333}
PASS call_timeout_slice :: v=0.500
PASS call_timeout_slice2 :: v=10.000
Traceback (most recent call last):
  File "/Users/a77/.finance-runtime/reviews/pr868-glm-qc-repaired-20260923-2115/spec/work/probes/probe_deadline_forward_v3.py", line 95, in <module>
    main()
  File "/Users/a77/.finance-runtime/reviews/pr868-glm-qc-repaired-20260923-2115/spec/work/probes/probe_deadline_forward_v3.py", line 85, in main
    R._post_chat_synthesis(PROV, [{"role":"user","content":"x"}], 5.0, 0.2, 16, 1000,
  File "/Users/a77/.finance-runtime/reviews/pr868-repaired-20260923-2111/candidate/intelligence/services/llm_refine.py", line 1205, in _post_chat_synthesis
    _reserve_llm_call()
  File "/Users/a77/.finance-runtime/reviews/pr868-repaired-20260923-2111/candidate/intelligence/services/llm_refine.py", line 866, in _reserve_llm_call
    if ledger is not None and not ledger.try_reserve():
                                  ^^^^^^^^^^^^^^^^^^^^
  File "/Users/a77/.finance-runtime/reviews/pr868-repaired-20260923-2111/candidate/intelligence/services/llm_refine.py", line 683, in try_reserve
    and self._reservation_count >= self.max_calls
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: '>=' not supported between instances of 'int' and 'LLMCallLedger'



## execute/commands/016-read/request.json

{"toolCallId":"call_88f50d8934754543bf8e39cf","params":{"limit":15,"offset":628,"path":"intelligence/services/llm_refine.py"}}


## execute/commands/016-read/result.json

{"exitCode":0}


## execute/commands/016-read/output.log

        requested_model=provider.model,
        endpoint_id=provider_endpoint_id(provider),
        transport="cli" if provider.transport == "cli" or provider.base_url.startswith("cli://") else "http",
        request_sha256=_canonical_sha256(messages),
        started_at=datetime.now(timezone.utc).isoformat(),
    )


UNLABELLED_PURPOSE = "unlabelled"


@dataclass
class LLMCallLedger:
    records: list[LLMCallRecord] = field(default_factory=list)
    # 硬预算（P1-B 消费闭环）：非 None 时，尝试数达到上限后新调用被拒发

[truncated; total lines=2605, selected=628:642; request a later offset]



## execute/commands/017-read/request.json

{"toolCallId":"call_15d618fdcbc54e5ba31ca941","params":{"limit":30,"offset":830,"path":"intelligence/services/llm_refine.py"}}


## execute/commands/017-read/result.json

{"exitCode":0}


## execute/commands/017-read/output.log

def call_ledger_scope(
    max_calls: int | None = None,
    *,
    reuse_existing: bool = True,
) -> Iterator[LLMCallLedger]:
    """开启 turn 级 LLM 调用台账；已有活动台账时复用（不重置嵌套作用域）。

    ``max_calls`` 只在新建台账时生效；嵌套复用时以外层限额为准。"""
    existing = _CALL_LEDGER.get()
    if existing is not None and reuse_existing:
        yield existing
        return
    ledger = LLMCallLedger(max_calls=max_calls)
    token = _CALL_LEDGER.set(ledger)
    try:
        yield ledger
    finally:
        _CALL_LEDGER.reset(token)


def _budget_rejection() -> str | None:
    """入口预算检查：超额时返回拒发 reason，未超额/无台账返回 None。"""
    ledger = _CALL_LEDGER.get()
    if ledger is not None and ledger.over_budget():
        return ledger.reject()
    return None


def _reserve_llm_call() -> None:
    """Reserve one attempt at the actual HTTP boundary.

[truncated; total lines=2605, selected=830:859; request a later offset]

