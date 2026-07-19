# Evidence Judge Deadline Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复启用 LLM 语义闸门时 `company_mapping` 因 deadline 参数契约漂移而失败的问题，并用生产 HTTP 端到端测试证明金融 Workbench 可稳定完成日常核心工作流。

**Architecture:** `ResearchDeadline` 仍是 turn 级唯一绝对截止时间；`evidence_providers` 将剩余预算传给 `evidence_judge`，后者把绝对截止时间折算成 `llm_refine.complete()` 已支持的单次 `timeout`。不扩张底层 LLM 公共接口，不关闭语义闸门，不改变 fail-open 语义。

**Tech Stack:** Python 3.12、pytest、FastAPI、GLM OpenAI-compatible API、常驻 Hybrid RAG worker、macOS LaunchAgent、Git detached worktree 原子发布。

---

### Task 1: 固化生产接口漂移回归

**Files:**
- Modify: `intelligence/tests/test_evidence_judge.py`

- [ ] **Step 1: 把旧的“透传 deadline”测试改为当前公共接口契约测试**

使用显式匹配 `llm_refine.complete()` 的 spy；旧实现继续传 `deadline` 时应直接
抛出 `TypeError`：

```python
def test_judge_translates_absolute_deadline_to_complete_timeout() -> None:
    captured: dict[str, object] = {}
    deadline = llm_refine.Deadline.from_timeout(1)

    def complete(
        messages,
        model_override=None,
        timeout=0,
        temperature=0.0,
    ):
        del messages, model_override
        captured["timeout"] = timeout
        captured["temperature"] = temperature
        return '{"keep": [0], "reason": ""}', None, ""

    verdict = evidence_judge.judge_relevance(
        "后市怎么演绎",
        [("市场结构", "指数与量能变化")],
        timeout=2,
        deadline=deadline,
        complete_fn=complete,
    )

    assert verdict is not None
    assert 0 < float(captured["timeout"]) <= 1
    assert captured["temperature"] == 0.0
```

- [ ] **Step 2: 增加截止时间耗尽时零调用测试**

```python
def test_judge_skips_llm_when_absolute_deadline_is_exhausted() -> None:
    called = False

    def complete(messages, timeout=0, temperature=0.0):
        del messages, timeout, temperature
        nonlocal called
        called = True
        return '{"keep": [0], "reason": ""}', None, ""

    verdict = evidence_judge.judge_relevance(
        "问题",
        [("标题", "摘录")],
        deadline=llm_refine.Deadline.from_timeout(0),
        complete_fn=complete,
    )

    assert verdict is None
    assert called is False
```

- [ ] **Step 3: 运行失败测试确认能抓住生产 bug**

Run:

```bash
.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_evidence_judge.py::test_judge_translates_absolute_deadline_to_complete_timeout \
  intelligence/tests/test_evidence_judge.py::test_judge_skips_llm_when_absolute_deadline_is_exhausted -q
```

Expected: 旧实现第一项因 `unexpected keyword argument 'deadline'` 失败，第二项因仍调用 complete 失败。

### Task 2: 实施最小契约修复

**Files:**
- Modify: `intelligence/services/evidence_judge.py`
- Test: `intelligence/tests/test_evidence_judge.py`

- [ ] **Step 1: 在 judge 边界折算有效 timeout**

在构建 prompt 前计算有效预算：

```python
effective_timeout = max(0.0, float(timeout))
if deadline is not None:
    effective_timeout = min(effective_timeout, deadline.remaining())
if effective_timeout <= 0:
    return None
```

- [ ] **Step 2: 只向 complete 传正式支持的参数**

```python
complete_kwargs = {
    "timeout": effective_timeout,
    "temperature": 0.0,
}
```

删除 `complete_kwargs["deadline"] = deadline`。独立 judge provider 的
`provider_override()` 分支保持不变。

- [ ] **Step 3: 运行 judge 与 semantic gate 测试**

Run:

```bash
.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_evidence_judge.py \
  intelligence/tests/test_semantic_judge_gate.py -q
```

Expected: 全部 PASS。

- [ ] **Step 4: 提交修复**

```bash
git add intelligence/services/evidence_judge.py \
  intelligence/tests/test_evidence_judge.py
git commit -m "fix: align evidence judge deadline contract"
```

### Task 3: 回归研究主链与公共边界

**Files:**
- Verify only: `intelligence/tests/test_workbench_research_owner_skills.py`
- Verify only: `intelligence/tests/test_conversation_orchestrator.py`
- Verify only: `intelligence/tests/test_closed_loop_retrieval.py`

- [ ] **Step 1: 跑 owner、orchestrator 与 RAG 预算相关测试**

Run:

```bash
.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_workbench_research_owner_skills.py \
  intelligence/tests/test_conversation_orchestrator.py \
  intelligence/tests/test_closed_loop_retrieval.py -q
```

Expected: 全部 PASS；不出现超时线程残留或断裂 trace。

- [ ] **Step 2: 跑完整 intelligence 测试集**

Run:

```bash
.venv-workbench/bin/python -m pytest intelligence/tests -q
```

Expected: 全部 PASS。

- [ ] **Step 3: 检查提交边界与红线文件**

Run:

```bash
git diff origin/main...HEAD --check
git status --short
git diff --name-only origin/main...HEAD
```

Expected: 仅设计、计划、judge 源码和测试为已跟踪变更；用户已有未跟踪
market export 与 `market_snapshot/` 保持未触碰。

### Task 4: 合并并原子发布唯一生产版本

**Files:**
- Follow: `docs/workbench/canonical-8792-cutover.md`
- Runtime pointer: `/Users/a77/finance-workspace-runtime`

- [ ] **Step 1: 推送修复分支并合并 main**

用户已明确授权本轮合并。使用非强推流程：

```bash
git push -u origin fix/evidence-judge-deadline-contract
git switch main
git pull --ff-only
git merge --no-ff fix/evidence-judge-deadline-contract \
  -m "merge: repair evidence judge deadline contract"
git push origin main
```

- [ ] **Step 2: 从新 main commit 创建 detached runtime**

```bash
target_sha="$(git rev-parse main)"
target_short="$(git rev-parse --short=12 main)"
new_runtime="/Users/a77/.finance-runtime/finance-workspace-$target_short"
git worktree add --detach "$new_runtime" "$target_sha"
```

- [ ] **Step 3: 原子切换 8792**

按 runbook 停止 `com.a77.finance-workbench`，切换软链，再 bootstrap：

```bash
launchctl bootout gui/$(id -u)/com.a77.finance-workbench
ln -sfn "$new_runtime" /Users/a77/finance-workspace-runtime
launchctl bootstrap gui/$(id -u) \
  /Users/a77/Library/LaunchAgents/com.a77.finance-workbench.plist
```

- [ ] **Step 4: 验证唯一版本与 readiness**

```bash
test "$(readlink /Users/a77/finance-workspace-runtime)" = "$new_runtime"
test "$(git -C /Users/a77/finance-workspace-runtime rev-parse HEAD)" = "$target_sha"
test -z "$(git -C /Users/a77/finance-workspace-runtime status --short)"
lsof -nP -iTCP:8792 -sTCP:LISTEN
lsof -nP -iTCP:8795 -sTCP:LISTEN || true
curl -fsS http://127.0.0.1:8792/api/readiness
```

Expected: 仅 8792 监听；readiness 为 ready，知识库索引 fresh，RAG worker ready。

### Task 5: 生产 HTTP 端到端验收

**Files:**
- Runtime artifacts: `/Users/a77/.local/share/finance-workbench/users/linxiaoqi5111/runs/`

- [ ] **Step 1: 题材研究**

提交：

```text
请深挖光模块题材的产业链、核心矛盾、证据分层、反证和后续验证信号。
```

Expected: `theme-research` 完成；`company_mapping` 非 failed；有 citations、
EvidenceAtom 与公司证据表；无内部错误；运行后 RAG worker 仍 ready。

- [ ] **Step 2: 个股深挖**

提交：

```text
请深挖中际旭创：公司定位、客户证据硬度、业绩传导、板块生命周期、反证和后续验证信号。
```

Expected: 路由 `stock-deep-dive`，有公司锚点、引用、反证和验证条件；无内部异常。

- [ ] **Step 3: 新闻冲击**

提交：

```text
请分析近期光模块相关消息对产业链和核心公司的影响，区分已证实事实、推断、受益与受损方向，并给反证。
```

Expected: 路由 `news-impact`；明确原始披露缺口时可以诚实降级，但不得出现 TypeError、
空白报告或无来源强结论。

- [ ] **Step 4: 观察清单/日常复盘**

提交一条观察清单问题和一条每日复盘问题，要求两者均产生结构化报告、使用 GLM、
没有 secret/path/内部控制面泄漏。

- [ ] **Step 5: 每轮后健康检查**

每轮检查 run/report/trace/message 与 `/api/readiness`：

```text
status terminal
report present
llm.used true
no internal exception degrade
no public secret/path leakage
RAG worker state ready and model_load_count unchanged or healthy
```

### Task 6: 完成审计与交接

**Files:**
- Modify: `docs/superpowers/plans/2026-07-20-evidence-judge-deadline-contract.md`
- Modify: `/Users/a77/agent-memory/20_projects/finance-workspace-private.md`

- [ ] **Step 1: 回填计划复选框与真实 run_id/结果**

只把实际执行且有证据的步骤标记完成；任何失败项保持未完成并继续修复。

- [ ] **Step 2: 回写项目级记忆**

记录根因、修复 commit、main merge commit、runtime commit、五类 E2E run_id 与最终
可用性结论；不写 API key、不复制用户私有数据正文。

- [ ] **Step 3: 最终完成审计**

逐项核对：唯一 main 版本、8792 readiness、RAG freshness、五类 E2E、无内部异常、
用户未跟踪文件未改。证据不足时继续优化，不以单元测试替代生产端到端。
