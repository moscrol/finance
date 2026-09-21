## 独立代码验收报告 — watchdog 测试同步 (2026-09-22)

**检出**：`/Users/a77/fwp-wt-watchdog-qc-0922`
**开始 HEAD**：`2007edfa5de9c0db704095a51fa54a318362d59b`，`git status --porcelain` 空
**结束 HEAD**：`2007edfa5…` 同上，`git status --porcelain` 空 → **无漂移、无脏源码**
差分范围 `e82717d9a..2007edfa5`：3 文件（2 份 handoff/md + `intelligence/tests/test_conversation_orchestrator.py` +151/−21），生产代码 0 改动（我逐文件核对 `--stat`，非依赖作者说明）。
证据目录：`/Users/a77/.finance-runtime/reviews/watchdog-qc-20260922/authenticated-claude/`（junit + 原生收据副本 + mutant + 探针日志）。仓内未写任何文件。

---

### 动态证据（全部为定向执行）

| # | 命令 | 实际结果 |
|---|---|---|
| R1 | `pytest intelligence/tests/test_conversation_orchestrator.py -k watchdog -q --basetemp=$E/basetemp-1 --junitxml=$E/junit-watchdog.xml` | `2 passed, 103 deselected in 2.47s`；用例耗时 2.165s / 0.259s；原生收据 `20260921T180502Z-2007edfa.json`（副本已存） |
| R2 | `pytest intelligence/tests/test_research_contract.py -q …` | `2 passed in 1.26s`；该文件 **0 处** `ResearchDeadline`/`monotonic` 覆盖 |
| R3 | 我自拟 Mutant A（拷贝到证据目录，删掉 `watchdog_clock[0] = options.deadline.expires_at` 一行） | `1 failed in 7.90s`，用例 5.19s，`KeyError: 'returned'` @ 我副本 6384 行 → 测试**不能**被"不推进时钟"的实现骗过 |
| R4 | 我自拟时钟作用域探针 `ce-clock-scope.log` | 见下 |

R4 原始输出（要点）：冻结前创建的 deadline `remaining()=1197228.9`；冻结后创建的 deadline 真实 sleep 0.6s 后 `remaining()=0.2, expired=False`；**另一线程**读到同样 0.2；`Event.wait(0.3)`/`Future.result(0.3)` 真实耗时 0.305s；等价 watchdog 轮询循环在 0.4s 真实时间内空转 1,644,640 次且 **未退出**。

---

### 裁决 1：冻结 `research_contract` 自己的 `time` 绑定

`ResearchDeadline.remaining()`（`intelligence/services/research_contract.py:371-372`）在调用时查 **模块全局** `time` → `monkeypatch.setattr(research_contract_service, "time", …)`（测试 6287-6293 行附近）冻结的是 **进程内全部 `ResearchDeadline` 实例**，不只是被测那一个，且对所有线程可见（R4 CE1/CE2，动态证据）。

- **不掩盖被测行为**：watchdog（`intelligence/runtime/conversation_orchestrator.py:4846-4993`）在这条路径上唯一的时间源就是 `deadline.expired` / `deadline.remaining()`；`Future`/`Event` 的超时留在真实时间轴（R4 CE3 证实注释 `Event/Future timeouts stay on real time` 属实）。真实并发未被消除：worker 真在另一线程跑，`task_may_continue: not future.done()` 被断言为 `True`，证明 watchdog 是在 worker 仍活着时返回的。
- **污染窗口存在，但被 teardown 收口**：`monkeypatch` 在用例结束后还原，而 `finally` 的 join 先于 teardown 执行，顺序正确。
- **【中】残余污染面（静态推测，未动态复现）**：窗口内任何**此前用例遗留的活 daemon 线程**若持有冻结前创建的 `ResearchDeadline`，其 `remaining()` 会变成 ~1.2e6 秒即"永不过期"（R4 CE1 实测量级）。本模块两个用例内无此消费者，但这是模块级打桩固有的跨用例面。

### 裁决 2：0.8s 从"整轮"收窄为"到期事件→watchdog 返回"

这是**真实的测量收窄**，不能只看数值没变就说没放宽：

- 旧断言 `elapsed < 0.8`（真实时钟、从 turn 起算、预算 0.2s）同时约束了 *前置准备 + watchdog 轮询粒度 + 真实 deadline 由 `monotonic` 正确派生* 三件事。
- 新断言 `watchdog_timings["returned"] - watchdog_timings["expired"] < 0.8` 只约束**轮询粒度**（实现上界 `min(0.05, remaining)` + 一次 trace 写盘，实测整用例 2.165s 里这段远小于 0.8s）。该断言现在**极其宽松**，几乎不可能失败。
- **【中】遗漏的合同**：`from_timeout` 以真实 `time.monotonic()` 派生 + "0.2s 预算下用户真的在亚秒内拿到降级答案"这条端到端墙钟合同，在 R2 中确认 `test_research_contract.py` **完全没有** `ResearchDeadline` 覆盖；本模块也 0 处引用。也就是说全仓是否别处覆盖我未验证，但这两个最自然的位置都没有。
- **建议（非阻断）**：补一条真实时钟的有界用例（worker 用 `Event.wait(1.0)` 之类自然阻塞，断言 `elapsed < 1.0` 且 `remaining_ms == 0`），与确定性用例并存。确定性用例负责语义与 trace 载荷，真实时钟用例负责"时钟真的在走"。

### 裁决 3：线程释放 / 挂起路径 / 隐藏线程异常

- 释放与 join 覆盖抢占、异常、失败断言：`finally: release_worker.set()` + `for worker in worker_threads: join(5); assert not worker.is_alive()`，`worker_threads.append(current_thread())` 是 `blocking_answer` 第一条语句。
- **【低】窄泄漏窗**：worker 线程已 `start()` 但尚未进入 `blocking_answer` 时若 try 体先抛出，该线程不在 `worker_threads` 中、不会被 join；它随后在 monkeypatch 已还原的真实时钟下执行，`remaining()` 断言失败 → 异常进 Future 被吞，不会挂起（因 `release_worker` 已 set）。不构成假绿。
- **【低】finally 内 `assert not worker.is_alive()` 会覆盖原始异常**（新异常链式取代主异常的报告位），join 超时时诊断质量下降。
- **隐藏线程异常不会造成假绿（动态证据 R3）**：worker 内的 assert 失败经 `future.set_exception` 被生产层吞掉——R3 中 `run_turn` 仍返回 `status="completed"` 且 `worker_started` 为真——但测试体后续断言把它抓住了（表现为 `KeyError: 'returned'`）。代价是**失败信息误导**：真实原因是 worker 断言超时，报出来的是 KeyError。
- **【中】真正的永久挂起路径（静态，R4 CE4 提供机理证据）**：冻结时钟下 watchdog 的 `while True` 没有任何真实时间出口——唯一出口是 worker 把时钟跳到 `deadline.expires_at`。若日后重构让 `options.deadline` 与 watchdog 实际持有的 deadline 不再是同一 `expires_at`（例如给 worker 发 `bounded_stage` 子 deadline），跳时钟就打不中，且 worker 不抛异常时 **CI 会挂死而不是失败**。仓内 `pytest.ini` 未配置 `pytest-timeout`（我已核对 `pytest.ini`/`conftest.py`，无全局超时），所以没有兜底。R3 之所以只花 7.9s 而非挂死，纯粹是因为 worker 自带的 `release_worker.wait(timeout=5)` 断言把 Future 完成了——这是巧合性保护，不是设计出口。

### 裁决 4：三条语义是否被有效验证 / 能否被错误实现绕过

- **启动前耗尽**：`answer_calls == []` + trace 载荷精确等于 `{"remaining_ms": 0, "worker_started": False}`，对应 `conversation_orchestrator.py:4917-4939` 的 `deadline.expired` 早返分支。"先起 worker 再超时"的错误实现会因 `worker_started: True` 与 `answer_calls` 非空双重失败。有效。
- **启动后超时**：因为时钟只能由 worker 推进，**通过该用例的前提就是 worker 必须先真正跑起来**（R3 证明反向变异会失败）。再加 `task_may_continue: True`、`not release_worker.is_set()`，排除了"提前返回"和"其实等到了 worker 结束"两类错误实现。这是比旧版更强的约束。
- **迟到进度/文本屏障**：`capture_delta` 被包在 `options.stream_text_delta` 上、再由生产的 `guarded_text_delta` 在**外层**包裹（`replace(options, stream_text_delta=guarded_text_delta)`，`original_text_delta` 即 `capture_delta`）。层序正确：只有**穿过闸门**的 delta 才会进 `forwarded_deltas`，所以 `forwarded_deltas == []` 是真正的闸门断言，而不是重复断言最终文本。再叠加 `run_store.load_trace(run_id) == trace_before_release` 全等比较（挡住迟到 trace 追加）与 `"迟到片段" not in assistant.content`。有效，不易被绕过。

---

## 结论

**规格结论（这次改动是否做了它声称做的事）：PASS_WITH_LIMITS**
增量确为测试 + 交接文档，生产零改动（已独立核对 diff）。新用例把不确定的"真实 0.2s 竞速"换成"worker 就绪后才触发到期"的确定性编排，并新增了启动前耗尽分支覆盖；三条语义均由我的变异/探针验证为载荷断言而非形式断言。

**质量结论（作为回归资产的可信度）：PASS_WITH_LIMITS**
限制与未验证边界，按严重度：
1. **【中】墙钟合同缺口**：全仓已无（至少这两个最相关文件里没有）断言 `ResearchDeadline` 基于真实 `monotonic` 派生、以及 0.2s 预算下端到端亚秒返回的用例。建议补一条真实时钟有界用例。
2. **【中】挂死而非失败的风险**：冻结时钟 + 无 `pytest-timeout` ⇒ 时钟跳跃打不中 `expires_at` 的未来重构会挂死 CI。建议给轮询等待加真实时间兜底，或在该用例上加显式超时。
3. **【中】模块级 `time` 打桩的跨用例面**：窗口内所有 `ResearchDeadline` 被冻结、对全线程可见；冻结前创建的实例退化为"永不过期"。
4. **【低】** worker 早期抛出时的窄泄漏窗；`finally` 内断言覆盖原始异常；worker 内断言失败表现为误导性 `KeyError`。

**适用范围**：仅限本轮 `e82717d9a..2007edfa5` 的测试增量、在本检出、用 `.venv-workbench` 解释器、定向执行这两个用例 + `test_research_contract` 的证据。

**明确不构成本轮结论**：未跑全量、未跑前端、未评估全仓门禁与生产质量、未判定 main 红灯是否解决；**历史那条全量唯一失败 `worker_started.is_set()` 的成因我无法确证**（原 trace 丢失），本轮只能说新编排在机理上消除了"watchdog 早于 worker 启动就超时"这一类竞态，不能说已证明它就是当时的失败原因。作者的 QC 报告与通过数字未作为证据采信。
