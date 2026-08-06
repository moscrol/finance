# Grounded 合成链预算分配 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不提高 turn 根预算、不改变 prompt、模型、retry 或 judge 语义的前提下，让 brief、composer、judge 可触达完整 child 预算，并为 judge 保留固定下限。

**Architecture:** `_shadow_deadline()` 继续把 child 夹在 parent deadline 内，默认 child 上限从 90 秒改为 115 秒。child 创建后只冻结一次初始总额 `T`；纯数值 `_GroundedPhaseBudget` 按 `brief=min(remaining, 0.25T)`、`composer=max(0, remaining-0.25T)`、`judge=remaining` 分配实际 grant，admission control 只读取该 grant。

**Tech Stack:** Python 3、dataclass、pytest、`llm_refine.Deadline`、`AskOptions`、synthesis phase telemetry、Acceptance Board live canary。

**Execution outcome（2026-08-03）：** 计划已执行到 A4 决策门；allocator 生效但 canary 失败。扩大证据窗口后确认历史 artifact 已有 brief 69.740秒完成值与 composer >20.261秒下界，故 brief-only replay和逐级 cap 调参取消，A组未跑。当前分支是负实验收据，不是 merge-ready 产品修复；后续另立 root 扩容或确定性 brief（E）方案。

---

## 文件职责与测试 seam

- `intelligence/services/ask_types.py`：Grounded child timeout 的配置入口，保留环境变量覆盖。
- `intelligence/services/ask_synthesis.py`：唯一预算算法及 brief/composer/judge 消费点。
- `intelligence/tests/test_synthesis_phase_observability.py`：纯数值预算、配置入口、准入与 phase 遥测。
- `intelligence/tests/test_p0_hardening.py`：既有 parent/child deadline 夹逼契约。
- `intelligence/tests/test_phase_slice_enforced.py`：既有网络调用强制读取 timeout 的执行点契约。
- `intelligence/tests/test_judge_outage_degrades.py`：既有 judge fail-closed / 瞬时故障语义。
- `intelligence/tests/test_stream_stall_observation.py`：同步删除旧递归分片说明。

测试 seam 已随设计批准冻结：纯数值分配器与 `AskOptions` 配置入口是单元 seam；真实 `/ask` → acceptance artifact 是产品 seam。单元测试不联网、不 sleep 真实 phase 时长；live A4 才判断三段能否实际完成。

### Task 1: 用红测冻结配置与预算契约

**Files:**
- Modify: `intelligence/tests/test_synthesis_phase_observability.py:278-324`
- Test: `intelligence/tests/test_synthesis_phase_observability.py`

- [ ] **Step 1: 写默认值和环境覆盖红测**

```python
class TestGroundedTimeoutConfiguration:
    def test_default_child_timeout_is_115_seconds(self, monkeypatch) -> None:
        monkeypatch.delenv("WORKBENCH_SHADOW_GROUNDED_TIMEOUT", raising=False)

        options = ask.AskOptions(query="测试")

        assert options.shadow_grounded_timeout == 115

    def test_environment_override_still_wins(self, monkeypatch) -> None:
        monkeypatch.setenv("WORKBENCH_SHADOW_GROUNDED_TIMEOUT", "73")

        options = ask.AskOptions(query="测试")

        assert options.shadow_grounded_timeout == 73
```

- [ ] **Step 2: 运行配置红测**

Run:

```bash
.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_synthesis_phase_observability.py::TestGroundedTimeoutConfiguration -q
```

Expected: 默认值用例 FAIL，实际值为 `90`；环境覆盖用例 PASS。

- [ ] **Step 3: 写纯数值预算红测**

```python
class TestGroundedPhaseBudget:
    def test_115_seconds_preserves_brief_cap_and_judge_reserve(self) -> None:
        budget = ask_synthesis._GroundedPhaseBudget.from_total(115.0)

        assert budget.initial_seconds == 115.0
        assert budget.brief_cap_seconds == 28.75
        assert budget.judge_reserve_seconds == 28.75
        assert budget.timeout_for("brief", 115.0) == 28

    def test_brief_unused_time_returns_to_composer(self) -> None:
        budget = ask_synthesis._GroundedPhaseBudget.from_total(115.0)

        # brief 只用 20 秒，composer 可拿 95 - 28.75 = 66.25 秒。
        assert budget.timeout_for("composer", 95.0) == 66

    def test_composer_unused_time_returns_to_judge(self) -> None:
        budget = ask_synthesis._GroundedPhaseBudget.from_total(115.0)

        assert budget.timeout_for("judge", 45.0) == 45

    @pytest.mark.parametrize(
        ("phase", "remaining", "expected"),
        [
            ("brief", 10.0, 10),
            ("composer", 20.0, 0),
            ("judge", 0.9, 0),
        ],
    )
    def test_grant_never_exceeds_current_remaining(
        self,
        phase: str,
        remaining: float,
        expected: int,
    ) -> None:
        budget = ask_synthesis._GroundedPhaseBudget.from_total(115.0)

        grant = budget.timeout_for(phase, remaining)

        assert grant == expected
        assert grant <= remaining

    def test_unknown_phase_is_rejected(self) -> None:
        budget = ask_synthesis._GroundedPhaseBudget.from_total(115.0)

        with pytest.raises(ValueError, match="unsupported grounded phase"):
            budget.timeout_for("revision", 30.0)
```

- [ ] **Step 4: 把 admission control 红测改为检查实际 grant**

用以下两个测试替换旧的 `deadline × share` 参数化测试，保留本类其余 fail-closed 测试：

```python
class TestAdmissionControl:
    """实际 grant 不足 1 秒时不发请求；准入器不重复预算算法。"""

    def test_zero_second_grant_is_detected(self) -> None:
        assert ask_synthesis._phase_slice_collapsed(0)

    def test_one_second_grant_is_not_blocked(self) -> None:
        assert not ask_synthesis._phase_slice_collapsed(1)
```

- [ ] **Step 5: 运行预算红测**

Run:

```bash
.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_synthesis_phase_observability.py::TestGroundedPhaseBudget \
  intelligence/tests/test_synthesis_phase_observability.py::TestAdmissionControl -q
```

Expected: FAIL；核心错误为 `_GroundedPhaseBudget` 不存在或 `_phase_slice_collapsed()` 仍要求 `deadline, share`。

### Task 2: 实现默认 child cap 与纯数值分配器

**Files:**
- Modify: `intelligence/services/ask_types.py:111-115`
- Modify: `intelligence/services/ask_synthesis.py:10,1555-1680`
- Test: `intelligence/tests/test_synthesis_phase_observability.py`

- [ ] **Step 1: 把默认 child timeout 改为 115 秒**

```python
shadow_grounded_timeout: int = field(
    default_factory=lambda: int(
        os.environ.get("WORKBENCH_SHADOW_GROUNDED_TIMEOUT", "115")
    )
)
```

- [ ] **Step 2: 增加冻结预算对象**

将 import 改为 `from dataclasses import dataclass, replace`，并在 `_shadow_deadline()` 前增加：

```python
@dataclass(frozen=True)
class _GroundedPhaseBudget:
    """从 child 初始总额冻结 brief cap 与 judge reserve。"""

    initial_seconds: float
    brief_cap_seconds: float
    judge_reserve_seconds: float

    @classmethod
    def from_total(cls, total_seconds: float) -> "_GroundedPhaseBudget":
        total = max(0.0, float(total_seconds))
        return cls(
            initial_seconds=total,
            brief_cap_seconds=total * 0.25,
            judge_reserve_seconds=total * 0.25,
        )

    def timeout_for(self, phase: str, remaining_seconds: float) -> int:
        remaining = max(0.0, float(remaining_seconds))
        if phase == "brief":
            grant = min(remaining, self.brief_cap_seconds)
        elif phase == "composer":
            grant = max(0.0, remaining - self.judge_reserve_seconds)
        elif phase == "judge":
            grant = remaining
        else:
            raise ValueError(f"unsupported grounded phase: {phase}")
        return max(0, min(int(grant), int(remaining)))
```

- [ ] **Step 3: 删除递归比例分配，准入器只读 grant**

删除 `_shadow_phase_timeout()`，把 `_phase_slice_collapsed()` 替换为：

```python
def _phase_slice_collapsed(grant_seconds: int) -> bool:
    """实际 grant 小于 1 秒时不发 provider 请求。"""

    return grant_seconds < 1
```

- [ ] **Step 4: 运行第一条 vertical slice 的红/绿测试**

Run:

```bash
.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_synthesis_phase_observability.py::TestGroundedTimeoutConfiguration \
  intelligence/tests/test_synthesis_phase_observability.py::TestGroundedPhaseBudget \
  intelligence/tests/test_synthesis_phase_observability.py::TestAdmissionControl::test_zero_second_grant_is_detected \
  intelligence/tests/test_synthesis_phase_observability.py::TestAdmissionControl::test_one_second_grant_is_not_blocked -q
```

Expected: PASS。

### Task 3: 让三段消费同一份冻结计划

**Files:**
- Modify: `intelligence/services/ask_synthesis.py:1740-2000`
- Test: `intelligence/tests/test_synthesis_phase_observability.py`

- [ ] **Step 1: child deadline 创建后冻结一次 `T`**

```python
deadline = _shadow_deadline(options)
phase_budget = _GroundedPhaseBudget.from_total(deadline.remaining())
```

必须从实际 child 冻结，而不是从配置值冻结；显式较小 parent 才能继续约束 child。

- [ ] **Step 2: brief 从计划取 grant**

```python
brief_started = time.monotonic()
brief_remaining = max(0.0, deadline.remaining())
brief_remaining_ms = brief_remaining * 1000
brief_timeout = phase_budget.timeout_for("brief", brief_remaining)
if _phase_slice_collapsed(brief_timeout):
    _record_synthesis_phase(
        result,
        name="brief",
        status="skipped",
        remaining_ms_at_entry=brief_remaining_ms,
        timeout_s=brief_timeout,
        started=brief_started,
        reason=_INSUFFICIENT_BUDGET_REASON,
    )
```

后续 provider 调用继续同时接收 `timeout=brief_timeout` 和共享 `deadline=deadline`。

- [ ] **Step 3: composer 接 brief 回吐并减去 judge reserve**

```python
compose_started = time.monotonic()
compose_remaining = max(0.0, deadline.remaining())
compose_remaining_ms = compose_remaining * 1000
compose_timeout = phase_budget.timeout_for("composer", compose_remaining)
if _phase_slice_collapsed(compose_timeout):
    _record_synthesis_phase(
        result,
        name="composer",
        status="skipped",
        remaining_ms_at_entry=compose_remaining_ms,
        timeout_s=compose_timeout,
        started=compose_started,
        reason=_INSUFFICIENT_BUDGET_REASON,
    )
```

- [ ] **Step 4: judge 获得当前全部剩余**

```python
judge_started = time.monotonic()
judge_remaining = max(0.0, deadline.remaining())
judge_remaining_ms = judge_remaining * 1000
judge_timeout = phase_budget.timeout_for("judge", judge_remaining)
judge_skipped = _phase_slice_collapsed(judge_timeout)
```

judge provider override、瞬时故障白名单、`released_unverified` 与 fail-closed 分支不改。

- [ ] **Step 5: 运行完整 phase 测试**

Run:

```bash
.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_synthesis_phase_observability.py -q
```

Expected: PASS；full chain 仍记录 `brief, composer, judge`，预算不足仍记录 `skipped/insufficient_budget`。

### Task 4: 同步说明并提交单变量代码 commit

**Files:**
- Modify: `intelligence/services/ask_synthesis.py:1020-1031`
- Modify: `intelligence/tests/test_stream_stall_observation.py:8-15`
- Modify: `docs/superpowers/specs/2026-08-03-grounded-chain-budget-allocation-design.md:5`
- Modify: `docs/superpowers/plans/2026-08-03-grounded-chain-budget-allocation.md`

- [ ] **Step 1: 把 stall 注释改成不依赖旧分片数字**

两处说明统一表达以下事实：

```text
这里故意不设阈值：通用 provider 的 stall 阈值不能直接套进各 phase；新分配器会让
brief 回吐给 composer、composer 回吐给 judge，所以单段 grant 不是固定比例。先记录
真实分布，再决定是否中断。
```

- [ ] **Step 2: 运行格式与目标回归**

Run:

```bash
.venv-workbench/bin/python -m ruff check \
  intelligence/services/ask_types.py \
  intelligence/services/ask_synthesis.py \
  intelligence/tests/test_synthesis_phase_observability.py \
  intelligence/tests/test_stream_stall_observation.py
.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_synthesis_phase_observability.py \
  intelligence/tests/test_phase_slice_enforced.py \
  intelligence/tests/test_judge_outage_degrades.py -q
```

Expected: Ruff PASS；pytest 全部 PASS。

- [ ] **Step 3: 检查差异和风险文件**

Run:

```bash
git diff --check
git status --short
git diff -- \
  intelligence/services/ask_types.py \
  intelligence/services/ask_synthesis.py \
  intelligence/tests/test_synthesis_phase_observability.py \
  intelligence/tests/test_stream_stall_observation.py \
  docs/superpowers/specs/2026-08-03-grounded-chain-budget-allocation-design.md \
  docs/superpowers/plans/2026-08-03-grounded-chain-budget-allocation.md
```

Expected: 只检查列出的任务文件；不含 `.env*`、数据库、压缩包、PDF、缓存或用户私有产物。

- [ ] **Step 4: 提交可独立回滚的预算修复**

```bash
git add \
  intelligence/services/ask_types.py \
  intelligence/services/ask_synthesis.py \
  intelligence/tests/test_synthesis_phase_observability.py \
  intelligence/tests/test_stream_stall_observation.py \
  docs/superpowers/specs/2026-08-03-grounded-chain-budget-allocation-design.md \
  docs/superpowers/plans/2026-08-03-grounded-chain-budget-allocation.md
git commit -m "fix(ask): make grounded phase budget reachable"
```

### Task 5: 跑相关与全量回归并对账基线红项

**Files:**
- No source changes expected
- Read: pytest output（只用于失败 node id 对账）

- [ ] **Step 1: 运行 deadline / ask / conversation 相关套件**

Run:

```bash
.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_p0_hardening.py \
  intelligence/tests/test_daily_agent_grounded.py \
  intelligence/tests/test_grounded_presenter_general.py \
  intelligence/tests/test_answer_orchestrator.py \
  intelligence/tests/test_ask_chat.py -q
```

Expected: 本次修改不新增失败；宿主环境用例若失败，保存 node id 与修改前基线比较。

- [ ] **Step 2: 运行全量测试并保存摘要**

Run:

```bash
.venv-workbench/bin/python -m pytest -q
```

Expected: 新预算测试通过；既有 vault/userspace 宿主环境红项与修复前同名同数。集合变化时先定位，不进入 live canary。

### Task 6: 重启 8801 并做 A4 post-fix canary

**Files:**
- Create: `intelligence/eval/runs/<UTC>-a4-post-budget-fix.json`（不提交）
- Create: `docs/verification/2026-08-03-a4-grounded-budget-m2-triage.md`
- Modify: `docs/trace-profile.md`

- [ ] **Step 1: 从现有 tmux pane 继承环境并重启当前分支**

先只读核对 pane/session 与 cwd，再复用现有 pane；禁止从文档手抄密钥或把环境打印到日志：

```bash
tmux list-panes -t codex-workbench-8801:server -F '#{pane_id} #{pane_current_path} #{pane_pid}'
tmux respawn-pane -k -t codex-workbench-8801:server
```

Expected: 8801 新进程 cwd 仍为 `/Users/a77/finance-workspace-private`，revision 为本分支代码，`ASK_CONTINUOUS_RUNTIME` 未设置，readiness 成功。

- [ ] **Step 2: 单跑固定 A4**

```bash
.venv-workbench/bin/python -m intelligence.eval.acceptance run \
  --base http://127.0.0.1:8801 \
  --user linxiaoqi5111 \
  --case A4-dual-red \
  --timeout 180 \
  --output "intelligence/eval/runs/$(date -u +%Y%m%dT%H%M%SZ)-a4-post-budget-fix.json"
```

Expected: 只产出一题的新 artifact，不提前跑 A 组。

- [ ] **Step 3: 按 phase 门禁判定**

必须同时满足：

```text
phase names = [brief, composer, judge]
all phase status = ok
judge record exists
synthesis_diagnostic.state = accepted
judge.remaining_ms_at_entry - judge.elapsed_ms > 0
grounded_required_fallback absent
released_unverified absent
```

`turn.status=completed` 与 `elapsed_s<=120` 不计入成功条件。

### Task 7: 做 M2 单变量 trace 差分并决定是否跑 A 组

**Files:**
- Modify: `docs/verification/2026-08-03-a4-grounded-budget-m2-triage.md`
- Modify: `docs/trace-profile.md`
- Create conditionally: `intelligence/eval/runs/<UTC>-group-a-post-budget-fix.json`（不提交）

- [ ] **Step 1: 用 agent-run-triage 对比修复前后 A4**

固定 baseline：

```text
before artifact: intelligence/eval/runs/20260803T082342Z-a4-pre-budget-fix.json
before run:      run_20260803_162718_999605
after artifact:  Task 6 新产物
```

报告按 `Evidence → Finding → Path` 写第一次分叉，分别标 PRIMARY / SECONDARY，并给建议标 `fix_type`；不得从 phase 缺失推断未观测阶段耗时。

- [ ] **Step 2: 只在 A4 六项门禁全过时跑 A 组 10 题**

先从 acceptance CLI help 或现有 handoff 精确确认组参数，再执行 A 组命令，输出到新 UTC artifact。对照口径固定为：

```text
修复前：完整通过 1 / 放行未核验 1 / 模板降级 8
修复后：按相同四态分类器统计
```

若 A4 未过，停在单题证据层：brief 失败只说明 brief cap 不足；judge 饿死才支持关键路径仍装不下。不得直接上 E 或扩大 root。

- [ ] **Step 3: 提交 M2 证据文档，不提交评测 JSON**

```bash
git add \
  docs/verification/2026-08-03-a4-grounded-budget-m2-triage.md \
  docs/trace-profile.md
git commit -m "docs(agent): record grounded budget M2 evidence"
```

### Task 8: 收口交接与项目记忆

**Files:**
- Create: `docs/handoffs/2026-08-03b-grounded-chain-budget-result.md`
- Modify: `.agent-memory/20_projects/finance-workspace-private.md`（仅项目级稳定结论）

- [ ] **Step 1: 写交接**

只记录已实测事实：revision、测试对账、服务 runtime、A4 phase 读数、M2 第一次分叉、A 组是否运行、尚未回答的问题。把“代码保证”与“模型性能实测”分栏。

- [ ] **Step 2: 写项目级记忆**

只沉淀最终架构决策与可复用原则：串行阶段不能反复按“当时剩余 × 固定 share”切片；应从初始总额预留尾段并允许前段回吐。单题评分、临时日志和 JSON artifact 不写共享记忆。

- [ ] **Step 3: 最终风险扫描与提交**

```bash
git diff --check
git status --short
git add \
  docs/handoffs/2026-08-03b-grounded-chain-budget-result.md \
  .agent-memory/20_projects/finance-workspace-private.md
git diff --cached --name-only
git commit -m "docs(agent): hand off grounded budget result"
```

Expected: 不合并 `main`、不强推、不提交评测 JSON 或任何红线文件；最终汇报分支、commits、测试、live 门禁结果与下一决策点。
