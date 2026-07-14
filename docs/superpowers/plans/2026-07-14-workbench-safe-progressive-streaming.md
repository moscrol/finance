# Workbench Safe Progressive Streaming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** 让 Workbench 先显示可核验草稿，再在 GLM 完整通过门禁后替换为自然语言精修版，并在 Hybrid RAG 的 dense 依赖不可用时自动回退 BM25。

**Architecture:** 保留现有 SSE 和 AnswerSpec 事实边界，新增具有覆盖语义的版本化 answer.snapshot 事件；模型 chunk 只在服务端缓冲，验证通过后才发布。知识库适配器内部执行有预算约束的 hybrid → BM25 降级，不改变下游 freshness 门禁。

**Tech Stack:** Python 3、FastAPI/SSE、React/TypeScript、Vitest、pytest、BM25、OpenAI-compatible GLM streaming API。

---

## 文件边界

- intelligence/services/kb_rag.py：dense 失败分类、BM25 重试和检索 telemetry。
- intelligence/services/answer_stream.py：snapshot phase、revision 和 payload 校验。
- intelligence/services/ask.py：缓冲 GLM chunk，完整门禁后才采用。
- intelligence/services/llm_refine.py：provider 流式协议与共享 timeout。
- intelligence/services/conversation_orchestrator.py：发布草稿和终态 snapshot。
- intelligence/webapp/src/types.ts、streamEvents.ts：revision 幂等覆盖。
- intelligence/webapp/src/components/MessageBubble.tsx：显示三个用户状态。
- scripts/smoke_workbench_self_use.py：fail-closed 验收 snapshot。

## Task 1: Hybrid RAG 自动回退 BM25

**Files:**
- Modify: intelligence/services/kb_rag.py
- Test: intelligence/tests/test_kb_rag.py

- [ ] **Step 1: 写失败测试**

在 KbRagTelemetryTests 增加 hybrid 首次返回缺 FlagEmbedding、第二次 BM25 返回 fresh hit 的测试：

~~~python
failed = mock.Mock(
    returncode=1,
    stdout="",
    stderr="ModuleNotFoundError: No module named 'FlagEmbedding'",
)
success = mock.Mock(
    returncode=0,
    stdout=json.dumps([fresh_hit("wiki/concepts/光刻机.md")]),
    stderr="",
)
with mock.patch("subprocess.run", side_effect=[failed, success]) as run:
    result = kb_rag.retrieve("光刻机", wiki, mode="hybrid", timeout=5)

assert result.ok
assert run.call_count == 2
assert "hybrid" in run.call_args_list[0].args[0]
assert "bm25" in run.call_args_list[1].args[0]
assert result.telemetry.requested_mode == "hybrid"
assert result.telemetry.effective_mode == "bm25"
assert result.telemetry.fallback_reason == "dense_dependency_missing"
~~~

再覆盖：BM25 stale hit 仍被丢弃；剩余预算不足不重试；普通脚本错误不误判。

- [ ] **Step 2: 运行并确认红灯**

~~~bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest intelligence/tests/test_kb_rag.py -q
~~~

Expected: telemetry 缺字段或 subprocess 只调用一次。

- [ ] **Step 3: 最小实现**

给 RetrievalTelemetry 增加 requested_mode、effective_mode、fallback_reason。增加稳定分类器：

~~~python
_DENSE_DEPENDENCY_FAILURES = (
    "flagembedding",
    "bgem3flagmodel",
    "no module named 'sentence_transformers'",
    "no module named 'torch'",
)

def _dense_dependency_failure(stderr: str) -> bool:
    normalized = str(stderr or "").casefold()
    return any(marker in normalized for marker in _DENSE_DEPENDENCY_FAILURES)
~~~

首次进程非零且 requested mode 为 hybrid/dense/rerank、错误命中时，计算
remaining = timeout - elapsed。只有 remaining >= 1 秒才用 mode=bm25 再调用一次；
成功结果继续走原有 JSON、chunk/hash/revision/freshness 解析，禁止旁路门禁。

- [ ] **Step 4: 运行测试并提交**

~~~bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest intelligence/tests/test_kb_rag.py -q
git add intelligence/services/kb_rag.py intelligence/tests/test_kb_rag.py
git commit -m "fix: fall back to bm25 when dense retrieval is unavailable"
~~~

Expected: 全部通过；BM25 stale 结果仍 ok=false。

## Task 2: 版本化 Answer Snapshot 契约

**Files:**
- Create: intelligence/services/answer_stream.py
- Create: intelligence/tests/test_answer_stream.py
- Modify: intelligence/services/conversation_orchestrator.py
- Test: intelligence/tests/test_conversation_orchestrator.py

- [ ] **Step 1: 写 snapshot 契约失败测试**

~~~python
snapshot = AnswerSnapshot(
    revision=1,
    phase="verified_draft",
    text="# 英维克\n\n证据不足。",
    final=False,
)
assert snapshot.payload() == {
    "revision": 1,
    "phase": "verified_draft",
    "text": "# 英维克\n\n证据不足。",
    "final": False,
}
~~~

并验证 revision < 1、未知 phase、空文本、draft+final、fallback+非 final 均抛 ValueError。
Orchestrator 测试用阻塞 fake synthesis 证明：释放模型前已出现唯一 verified_draft，正文不含
内部路径和 raw warning。

- [ ] **Step 2: 运行并确认红灯**

~~~bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest intelligence/tests/test_answer_stream.py intelligence/tests/test_conversation_orchestrator.py -q
~~~

Expected: answer_stream import 失败或没有 answer.snapshot。

- [ ] **Step 3: 实现纯契约**

~~~python
AnswerPhase = Literal[
    "verified_draft",
    "validated_synthesis",
    "verified_fallback",
]

@dataclass(frozen=True)
class AnswerSnapshot:
    revision: int
    phase: AnswerPhase
    text: str
    final: bool

    def __post_init__(self) -> None:
        if self.revision < 1 or not self.text.strip():
            raise ValueError("invalid answer snapshot")
        if self.phase == "verified_draft" and self.final:
            raise ValueError("draft cannot be final")
        if self.phase != "verified_draft" and not self.final:
            raise ValueError("terminal phase must be final")

    def payload(self) -> dict[str, object]:
        return {
            "revision": self.revision,
            "phase": self.phase,
            "text": self.text,
            "final": self.final,
        }
~~~

- [ ] **Step 4: Orchestrator 先发布草稿再合成**

Base 路径调用 answer_query 时设置 synthesize=False，先得到 AnswerSpec；owner 路径复用
answer_contract.answer_spec。用 render_conversation_answer + sanitize_conversation_answer
生成草稿并发布：

~~~python
self._emit(
    run_id,
    assistant_message_id,
    "answer:snapshot:1",
    "answer.snapshot",
    AnswerSnapshot(1, "verified_draft", verified_draft, False).payload(),
    conversation_id,
)
~~~

合成成功发布 revision=2、validated_synthesis、final=true；否则发布 revision=2、
verified_fallback、final=true。未形成 AnswerSpec 时不发布空 snapshot。最终 message、
answer.md 与 revision 2 文本一致。

- [ ] **Step 5: 运行测试并提交**

~~~bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest intelligence/tests/test_answer_stream.py intelligence/tests/test_conversation_orchestrator.py -q
git add intelligence/services/answer_stream.py intelligence/services/conversation_orchestrator.py intelligence/tests/test_answer_stream.py intelligence/tests/test_conversation_orchestrator.py
git commit -m "feat: publish versioned verified answer snapshots"
~~~

Expected: 事件顺序为 start → 检索 → verified_draft → terminal snapshot → complete。

## Task 3: GLM 安全流式缓冲与共享截止

**Files:**
- Modify: intelligence/services/llm_refine.py
- Modify: intelligence/services/ask.py
- Test: intelligence/tests/test_answer_orchestrator.py
- Test: intelligence/tests/test_conversation_orchestrator.py

- [ ] **Step 1: 写 raw chunk 不外泄的失败测试**

Fake stream 依次产生“越界公司”“ 999亿元”，完整文本被 AnswerSpec 拒绝。断言：

~~~python
assert result.synthesis is None
assert result.llm_fallback_reason == "quality_gate_rejected"
assert "越界公司" not in "".join(public_deltas)
assert "999亿元" not in "".join(public_deltas)
~~~

成功例产生三个 chunk，门禁通过后 public callback 只收到一次完整文本。
再验证 stream protocol fallback 的 timeout 只能使用原 timeout 剩余值。

- [ ] **Step 2: 运行并确认红灯**

~~~bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest intelligence/tests/test_answer_orchestrator.py intelligence/tests/test_conversation_orchestrator.py -q
~~~

Expected: 当前主路径仍调用非流式 synthesis，或 chunk/telemetry 断言失败。

- [ ] **Step 3: 共享 timeout**

synthesize_messages_stream 记录 started；stream 不支持时只在
remaining = timeout - elapsed >= 1 时调用非流式 fallback，并传
timeout=max(1, int(remaining))。剩余不足直接返回稳定 timeout reason。

- [ ] **Step 4: Ask 层只缓冲，不公开 raw chunk**

AskResult 增加 llm_stream_telemetry 字段。_synthesize_answer_spec 使用内部 capture：

~~~python
chunks: list[str] = []
first_token_ms: int | None = None

def capture(delta: str) -> None:
    nonlocal first_token_ms
    if options.stream_cancel_check and options.stream_cancel_check():
        raise llm_refine.LLMStreamCancelled()
    if first_token_ms is None:
        first_token_ms = elapsed_ms()
    chunks.append(delta)
~~~

调用 synthesize_messages_stream(on_delta=capture)。完成 notice 保留、
validate_llm_answer 和 sanitize 后，才调用旧 public stream_text_delta 一次以兼容旧客户端。
失败时 public callback 不得调用。Telemetry 只记录 first_token_ms、chunk_count、provider、
model，不记录 chunk、prompt 或错误正文。

- [ ] **Step 5: 运行测试并提交**

~~~bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest intelligence/tests/test_answer_orchestrator.py intelligence/tests/test_conversation_orchestrator.py -q
git add intelligence/services/llm_refine.py intelligence/services/ask.py intelligence/tests/test_answer_orchestrator.py intelligence/tests/test_conversation_orchestrator.py
git commit -m "feat: buffer model streams behind the answer quality gate"
~~~

Expected: success、timeout、quality rejection、cancel 全通过，raw chunks 不进入公共事件或 artifact。

## Task 4: 前端幂等 Snapshot 与状态文案

**Files:**
- Modify: intelligence/webapp/src/types.ts
- Modify: intelligence/webapp/src/streamEvents.ts
- Modify: intelligence/webapp/src/App.tsx
- Modify: intelligence/webapp/src/components/MessageBubble.tsx
- Test: intelligence/webapp/src/components/components.test.tsx

- [ ] **Step 1: 写 revision 覆盖失败测试**

~~~typescript
let state = applyChatStreamEvent(initial, snapshot(1, "verified_draft", "可核验草稿", false));
state = applyChatStreamEvent(state, snapshot(2, "validated_synthesis", "自然语言精修版", true));
state = applyChatStreamEvent(state, snapshot(1, "verified_draft", "旧草稿", false));
expect(state.narrative).toBe("自然语言精修版");
expect(state.answerRevision).toBe(2);
expect(state.answerPhase).toBe("validated_synthesis");
~~~

覆盖同 revision 重放、非法 phase/revision、旧 text.delta 兼容和三个状态文案。

- [ ] **Step 2: 运行并确认红灯**

~~~bash
cd intelligence/webapp
pnpm test -- --run
~~~

Expected: LiveMessageState 缺字段或 reducer 忽略 snapshot。

- [ ] **Step 3: 实现类型和 reducer**

~~~typescript
export type AnswerPhase =
  | "verified_draft"
  | "validated_synthesis"
  | "verified_fallback";

answerRevision: number;
answerPhase: AnswerPhase | null;
answerFinal: boolean;
~~~

初始化 revision=0。Reducer 只接受安全正整数 revision、允许 phase、string text 和 boolean
final；仅 revision 更高时覆盖 narrative。已有 snapshot 后忽略 text.delta，避免双写。
App.tsx 公共事件 allowlist 加 answer.snapshot。

- [ ] **Step 4: 实现用户状态**

MessageBubble 映射：

- verified_draft → 可核验草稿 · 模型精修中
- validated_synthesis → 自然语言精修完成
- verified_fallback → 已保留可核验版本

运行详情继续使用稳定 fallback label，不显示 raw provider exception。

- [ ] **Step 5: 运行前端门禁并提交**

~~~bash
cd intelligence/webapp
pnpm test -- --run
pnpm typecheck
pnpm lint
pnpm build
cd ../..
git add intelligence/webapp/src/types.ts intelligence/webapp/src/streamEvents.ts intelligence/webapp/src/App.tsx intelligence/webapp/src/components/MessageBubble.tsx intelligence/webapp/src/components/components.test.tsx intelligence/webapp/static
git commit -m "feat: render progressive answer snapshots in the workbench"
~~~

Expected: tests、typecheck、lint、build 全通过。

## Task 5: Smoke、全量回归和真实 UI 验收

**Files:**
- Modify: scripts/smoke_workbench_self_use.py
- Test: tests/test_smoke_workbench_self_use.py

- [ ] **Step 1: 写 fail-closed smoke 测试**

成功 summary 必须包含：

~~~python
assert summary["answer_stream"] == {
    "draft_seen": True,
    "terminal_phase": "verified_fallback",
    "highest_revision": 2,
    "snapshot_count": 2,
}
~~~

非法 revision、未知 phase、旧 revision 覆盖新 revision、completed 缺 terminal snapshot 均
exit_code=2；secret scanner 必须扫描 snapshot payload。

- [ ] **Step 2: 运行红灯并实现**

~~~bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest tests/test_smoke_workbench_self_use.py -q
~~~

在 public event allowlist 加 answer.snapshot；逐事件验证 revision/phase/text/final，维护最高
revision。Completed 时要求 draft 与 terminal snapshot 均存在、终态 text 非空。Summary 只
写统计，不保存正文。

- [ ] **Step 3: 运行全量门禁**

~~~bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest intelligence/tests tests/test_smoke_workbench_self_use.py -q
cd intelligence/webapp
pnpm test -- --run
pnpm typecheck
pnpm lint
pnpm build
cd ../..
git diff --check
~~~

Expected: 全部通过。

- [ ] **Step 4: 真实 8795 smoke**

使用 canonical data root、临时 users dir 和 Keychain 内置 GLM 启动隔离分支，运行：

~~~bash
mkdir -p /tmp/workbench-safe-progressive-streaming-evidence
/Users/a77/finance-workspace-private/.venv-workbench/bin/python scripts/smoke_workbench_self_use.py --base-url http://127.0.0.1:8795 --user local-qa --timeout 75 --output /tmp/workbench-safe-progressive-streaming-evidence/company.json --question "深挖英维克，它在液冷产业链的位置如何？请给出公司定位、最强证据、反证和下一步验证。"
~~~

Expected: exit 0；run/report completed；cutoff 不早于 readiness；draft_seen=true；终态为
validated_synthesis 或 verified_fallback；secret hits=0；dense 不可用时 effective mode=BM25。

- [ ] **Step 5: 真实 UI 截图验收**

在应用内浏览器提交同一问题，确认草稿先出现、终态原地替换或安全保留、状态文案正确、
Inspector 不再因缺 FlagEmbedding 直接宣告知识库不可用、无 raw traceback/密钥/无关公司
污染。截图和 JSON 只存 /tmp/workbench-safe-progressive-streaming-evidence/。

- [ ] **Step 6: 提交并检查分支**

~~~bash
git add scripts/smoke_workbench_self_use.py tests/test_smoke_workbench_self_use.py
git commit -m "test: verify progressive streaming in workbench runs"
git status --short
git diff origin/main...HEAD --check
git log --oneline origin/main..HEAD
~~~

Expected: 工作树干净；不 push、不 merge、不切换 canonical 8792；停止临时 8795。

## 计划自检

- 规格覆盖：双阶段 snapshot、安全模型缓冲、BM25 降级、硬截止、重放幂等、UI 文案、smoke 和真实验收均有任务。
- 类型一致：后端和前端共用 verified_draft、validated_synthesis、verified_fallback；revision 从 1 开始只增不减。
- 安全一致：raw model chunk 永不进入公共事件；最终 artifact 与最高 revision snapshot 一致。
- 范围一致：不安装 FlagEmbedding，不修改 relation 数据，不合并 main 或切换 8792。
