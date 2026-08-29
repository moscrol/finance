"""符合性套件共享夹具：脚本化模型 × 契约 × 注册表 × 探针。

驱动方式直接抄既有 doubles，不重造：

- frame/context/registry 三件抄 ``test_dsh_stub_runtime.py``；
- 脚本化 ``AgentModelClient`` 抄 ``test_glm_agent_runtime.py`` 的 complete_fn 思路，
  但直接实现协议（绕过 GLM envelope 转换，夹具与后端解耦）；
- 脚本化 SDK runner 抄 ``test_openai_agents_runtime.py`` 的 ``SuccessfulFakeSdkRunner``；
- 脚本化假 codex CLI 抄 ``test_codex_headless_runtime.py`` 的 ``ValidFakeCodex``
  （通过 gateway wrapper 子进程打工具，stdout 输出 JSONL）。

场景脚本（``ScriptedTurn``）是后端无关的：每个 driver（见 ``backends.py``）
把它翻译成自己后端的输入形状。
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from intelligence.runtime.codex_headless_runtime import (
    HeadlessCommand,
    HeadlessProcessResult,
)
from intelligence.runtime.openai_agents_runtime import (
    AgentsSdkRequest,
    AgentsSdkResult,
)
from intelligence.services.agent_research import AgentEvidence, AgentToolContext
from intelligence.services.agent_runtime import (
    AgentOutcome,
    ModelToolCall,
    ModelTurn,
)
from intelligence.services.evidence_capabilities import EvidencePlan
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.repair_coordinator import CoverageDelta, RepairGoal
from intelligence.services.research_contract import (
    RequiredOutput,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
)
from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolSpec
from intelligence.services.task_frame import TaskFrame

# 授权工具产出的证据 hash（finish bindings 引用它）；悬空引用场景用 MISSING。
MARKET_EVIDENCE_HASH = "conformance-market-hash"
MISSING_EVIDENCE_HASH = "conformance-missing-hash"
AUTHORIZED_TOOL = "market_data"
FORBIDDEN_TOOL = "forbidden_news"


@dataclass(frozen=True)
class ScriptedToolCall:
    name: str
    query: str


@dataclass(frozen=True)
class ScriptedTurn:
    """一轮脚本化模型行为：请求若干工具调用，或输出终止 JSON。

    ``finish`` 是 FINAL_JSON 的 dict 形状（status/draft/gaps/bindings）；
    ``content`` 直接指定原文（优先于 finish，用于构造畸形输出）。
    """

    tool_calls: tuple[ScriptedToolCall, ...] = ()
    finish: Mapping[str, object] | None = None
    content: str = ""

    def rendered_content(self) -> str:
        if self.content:
            return self.content
        if self.finish is not None:
            return json.dumps(self.finish, ensure_ascii=False)
        return ""


@dataclass
class ScenarioProbe:
    """驱动过程中的观测记录。断言读它，而不是猜后端内部。"""

    # 每次模型侧看到的可见工具名（continuous: complete(tools=)，sdk: request.tools）
    visible_tools: list[tuple[str, ...]] = field(default_factory=list)
    # 每次模型调用拿到的窗口（continuous: complete(timeout=)，sdk: request.timeout）
    model_timeouts: list[float] = field(default_factory=list)
    # registry runner 真实执行过的 (tool, query) —— 唯一的「工具真的跑了」事实源
    executed: list[tuple[str, str]] = field(default_factory=list)
    # SDK 形状下脚本想调但在可见工具面里不存在的名字
    denied_tool_requests: list[str] = field(default_factory=list)
    # SDK 工具 invoke 返回的观察值（含 ok=false 的显式拒绝）
    sdk_observations: list[dict[str, object]] = field(default_factory=list)
    # codex 假 CLI 收到的每次命令 args（含 prompt 文本）
    codex_args: list[tuple[str, ...]] = field(default_factory=list)
    # codex 假 CLI 经 wrapper 调工具拿到的 JSON 结果
    codex_tool_results: list[dict[str, object]] = field(default_factory=list)


def completed_finish(
    *,
    draft: str = "截至最新交易日，市场宽度改善。",
    evidence_hashes: Sequence[str] = (MARKET_EVIDENCE_HASH,),
    gap: str = "",
) -> dict[str, object]:
    return {
        "status": "completed",
        "draft": draft,
        "gaps": [],
        "bindings": [
            {
                "output_id": "direct_assessment",
                "evidence_hashes": list(evidence_hashes),
                "gap": gap,
            }
        ],
    }


def partial_finish(*, gap: str = "缺少行情证据") -> dict[str, object]:
    return {
        "status": "partial",
        "draft": "当前缺少行情证据，不能给出确定判断。",
        "gaps": [gap],
        "bindings": [
            {
                "output_id": "direct_assessment",
                "evidence_hashes": [],
                "gap": gap,
            }
        ],
    }


def make_frame(question: str = "目前市场怎么看") -> TaskFrame:
    return TaskFrame(
        raw_question=question,
        user_goal="判断当前市场结构",
        question_type="market_forecast",
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="最近交易日",
        required_outputs=("direct_assessment",),
        assumptions=("按A股市场理解",),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_market_scenarios",
        confidence=0.95,
    )


def make_context(
    frame: TaskFrame,
    *,
    task_id: str = "conformance-test",
    allowed_capabilities: tuple[str, ...] = ("market_data",),
    max_steps: int = 3,
    timeout: float = 30.0,
    synthesis_reserve: float = 0.0,
    root_budget: object | None = None,
) -> ResearchRunContext:
    context = ResearchRunContext(
        contract=ResearchTaskContract(
            task_id=task_id,
            question=frame.raw_question,
            subject=frame.subject,
            subject_kind=frame.subject_kind,
            question_type=frame.question_type,
            required_outputs=(
                RequiredOutput(
                    "direct_assessment",
                    "直接判断",
                    ("market_data",),
                    True,
                ),
            ),
            allowed_capabilities=allowed_capabilities,
            research_tier="quick",
            freshness="current",
            evidence_plan=EvidencePlan(),
            task_frame_hash=frame.task_frame_hash,
        ),
        deadline=ResearchDeadline.from_timeout(
            timeout,
            synthesis_reserve=synthesis_reserve,
        ),
        policy=ResearchPolicy("quick", max_steps, timeout, synthesis_reserve),
        trace_parent_id=task_id,
        today="2026-07-25",
        latest_data_date="2026-07-24",
    )
    if root_budget is not None:
        from dataclasses import replace

        context = replace(context, root_budget=root_budget)
    return context


def make_registry(probe: ScenarioProbe) -> ResearchToolRegistry:
    """两个工具：授权的 market_data + 未授权的 forbidden_news。

    contract 只授 ``market_data`` capability；``forbidden_news`` 挂在
    ``news_search`` 上，用于断言「未授权工具不可见/不可调」。两个 runner
    都把执行记进 ``probe.executed``——它是「工具真的被执行」的唯一事实源。
    """

    def market_runner(query: str, _context: AgentToolContext):
        probe.executed.append((AUTHORIZED_TOOL, query))
        evidence = AgentEvidence(
            tool=AUTHORIZED_TOOL,
            title="A股市场总览",
            detail=f"{query}：上涨家数增加",
            source="本地行情",
            source_date="2026-07-24",
            evidence_tier="L4",
            content_hash=MARKET_EVIDENCE_HASH,
        )
        return (
            [evidence],
            "上涨家数增加",
            ProviderTrace(
                provider="test:market",
                capability="market_data",
                status="success",
                source_trade_date="2026-07-24",
                result_count=1,
            ),
        )

    def forbidden_runner(query: str, _context: AgentToolContext):
        probe.executed.append((FORBIDDEN_TOOL, query))
        return ([], "未授权工具不应被执行", None)

    return ResearchToolRegistry(
        (
            ToolSpec(
                name=AUTHORIZED_TOOL,
                capability="market_data",
                description="结构化行情",
                cost="local",
                freshness="current",
                runner=market_runner,
            ),
            ToolSpec(
                name=FORBIDDEN_TOOL,
                capability="news_search",
                description="未授权新闻",
                cost="network",
                freshness="current",
                runner=forbidden_runner,
            ),
        )
    )


def make_repair_goal(episode_id: str) -> RepairGoal:
    """判官缺口的最小修复目标（抄 test_dsh_stub_runtime._repair_goal）。"""

    return RepairGoal(
        episode_id=episode_id,
        repair_goal_id="conformance-repair-1",
        cycle=1,
        missing_answer_elements=("direct_assessment",),
        unsupported_claims=(),
        missing_evidence_modes=(),
        attempted_actions=(),
        evidence_progress=CoverageDelta(1, 0, 1),
        remaining_calls=1,
        remaining_seconds=5.0,
    )


# ── 脚本化模型（continuous 档）────────────────────────────────────────


class ScriptedModelClient:
    """``AgentModelClient`` 的脚本化实现。

    每次 ``complete`` 弹出一轮脚本；耗尽时返回带显式 error 的空轮
    （episode 会走 model_unavailable 终止路径，可终止且在收据里可见，
    不静默造答案）。
    """

    def __init__(self, turns: Sequence[ScriptedTurn], probe: ScenarioProbe) -> None:
        self._turns = list(turns)
        self._probe = probe
        self._sequence = 0

    def complete(
        self,
        *,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        timeout: float,
    ) -> ModelTurn:
        del messages
        names = []
        for definition in tools:
            function = definition.get("function")
            if isinstance(function, dict):
                names.append(str(function.get("name", "")))
        self._probe.visible_tools.append(tuple(sorted(names)))
        self._probe.model_timeouts.append(float(timeout))
        if not self._turns:
            return ModelTurn(
                "",
                (),
                "scripted",
                "scripted_turns_exhausted",
            )
        turn = self._turns.pop(0)
        calls = []
        for request in turn.tool_calls:
            self._sequence += 1
            calls.append(
                ModelToolCall(
                    f"scripted-call-{self._sequence}",
                    request.name,
                    {"query": request.query},
                )
            )
        return ModelTurn(
            content=turn.rendered_content(),
            tool_calls=tuple(calls),
            provider_name="scripted",
        )


# ── 脚本化 SDK runner（sdk_glm / sdk_gpt 档）─────────────────────────


class ScriptedSdkRunner:
    """``AgentsSdkRunner`` 的脚本化实现。

    一次 runner 调用消费一份脚本（SDK 的一次 run 内部多轮由 SDK 管理，
    在假 runner 里就是顺序执行）。resume 触发第二次调用 → 取下一份脚本。
    """

    def __init__(
        self,
        scripts: Sequence[Sequence[ScriptedTurn]],
        probe: ScenarioProbe,
    ) -> None:
        if not scripts:
            raise ValueError("scripted sdk runner needs at least one script")
        self._scripts = [list(script) for script in scripts]
        self._probe = probe
        self._invocations = 0

    def __call__(self, request: AgentsSdkRequest) -> AgentsSdkResult:
        self._probe.visible_tools.append(
            tuple(sorted(tool.name for tool in request.tools))
        )
        self._probe.model_timeouts.append(float(request.timeout))
        index = min(self._invocations, len(self._scripts) - 1)
        script = self._scripts[index]
        self._invocations += 1
        llm_calls = 0
        final_output = ""
        for turn in script:
            llm_calls += 1
            for call in turn.tool_calls:
                tool = next(
                    (item for item in request.tools if item.name == call.name),
                    None,
                )
                if tool is None:
                    # SDK 形状下「强行调未授权工具」不可表达：provider 只能调
                    # 注册进 FunctionTool 表的名字。裁剪即拒绝，此处如实登记。
                    self._probe.denied_tool_requests.append(call.name)
                    continue
                observation = tool.invoke({"query": call.query})
                self._probe.sdk_observations.append(dict(observation))
            rendered = turn.rendered_content()
            if rendered:
                final_output = rendered
                break
        return AgentsSdkResult(
            final_output=final_output,
            llm_calls=max(1, llm_calls),
            # 真 runner 会带回 provider 历史（result.to_input_list()）；resume
            # 要重开研究工具时以它非 None 为闸（openai_agents_runtime L1246）。
            # 脚本化替身给一份不透明的等价物。
            continuation_input=[
                {"role": "user", "content": "scripted provider continuation"}
            ],
        )


# ── 脚本化假 codex CLI（codex_headless 档）───────────────────────────


class ScriptedFakeCodex:
    """``HeadlessCommandRunner`` 的脚本化实现（抄 ValidFakeCodex 的驱动面）。

    工具调用走 run_dir 里的 gateway wrapper 子进程（mailbox 传输），与真
    codex 子进程同一条路；stdout 输出 codex exec 的 JSONL 事件流。
    一次命令消费一份脚本；runtime 内部的修复轮是第二次命令 → 下一份脚本。
    """

    def __init__(
        self,
        scripts: Sequence[Sequence[ScriptedTurn]],
        probe: ScenarioProbe,
    ) -> None:
        if not scripts:
            raise ValueError("scripted fake codex needs at least one script")
        self._scripts = [list(script) for script in scripts]
        self._probe = probe
        self._invocations = 0

    def __call__(self, command: HeadlessCommand) -> HeadlessProcessResult:
        self._probe.codex_args.append(tuple(command.args))
        index = min(self._invocations, len(self._scripts) - 1)
        script = self._scripts[index]
        self._invocations += 1
        wrapper = command.cwd / "finance-tool"
        events: list[dict[str, object]] = [
            {"type": "thread.started", "thread_id": f"thread-conformance-{index}"},
        ]
        command_sequence = 0
        for turn in script:
            for call in turn.tool_calls:
                command_sequence += 1
                tool_command = [str(wrapper), call.name, call.query]
                completed = subprocess.run(
                    tool_command,
                    cwd=command.cwd,
                    env=dict(command.env),
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=10.0,
                )
                try:
                    payload = json.loads(completed.stdout or "{}")
                except json.JSONDecodeError:
                    payload = {"status": "error", "error": "unparseable_wrapper_output"}
                if isinstance(payload, dict):
                    self._probe.codex_tool_results.append(payload)
                events.append(
                    {
                        "type": "item.completed",
                        "item": {
                            "id": f"command-{index}-{command_sequence}",
                            "type": "command_execution",
                            "command": subprocess.list2cmdline(tool_command),
                            "status": "completed",
                            "exit_code": completed.returncode,
                        },
                    }
                )
            rendered = turn.rendered_content()
            if rendered:
                events.append(
                    {
                        "type": "item.completed",
                        "item": {
                            "id": f"answer-{index}",
                            "type": "agent_message",
                            "text": rendered,
                        },
                    }
                )
                break
        events.append(
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 1000,
                    "cached_input_tokens": 0,
                    "output_tokens": 200,
                    "reasoning_output_tokens": 50,
                },
            }
        )
        stdout = "\n".join(json.dumps(item, ensure_ascii=False) for item in events)
        return HeadlessProcessResult(
            stdout=stdout,
            stderr="",
            returncode=0,
            timed_out=False,
        )


# ── 通用断言辅助 ─────────────────────────────────────────────────────


def evidence_hash_set(outcome: AgentOutcome) -> set[str]:
    return {item.content_hash for item in outcome.evidence if item.content_hash}


def assert_no_dangling_bindings(outcome: AgentOutcome) -> None:
    """completed 的 outcome 不得携带指向不存在证据的绑定。"""

    if outcome.status != "completed":
        return
    collected = evidence_hash_set(outcome)
    for binding in outcome.bindings:
        dangling = set(binding.evidence_hashes) - collected
        assert not dangling, (
            f"binding {binding.output_id!r} 引用了不存在的证据 hash：{sorted(dangling)}"
        )


def tool_event_pairs(
    outcome: AgentOutcome,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    """durable 事件里的 (tool_request, tool_result, tool_error) 三组 payload。"""

    requests: list[dict[str, object]] = []
    results: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    for event in outcome.events:
        if event.kind == "tool_request":
            requests.append(dict(event.payload))
        elif event.kind == "tool_result":
            results.append(dict(event.payload))
        elif event.kind == "tool_error":
            errors.append(dict(event.payload))
    return requests, results, errors


_UNSUPPORTED_KEYWORDS = ("unsupported", "unavailable", "not_supported", "no_resume")


def explicit_repair_unsupported_markers(outcome: AgentOutcome) -> list[str]:
    """收集「修复不支持」的显式报告痕迹（事件 kind/payload、gaps、stop_reason）。

    INV-5 的判据：声明不支持修复的后端，必须在可观测面上显式说出来；
    这里返回空列表就意味着缺席是静默的。
    """

    markers: list[str] = []

    def scan(text: str, where: str) -> None:
        lowered = text.lower()
        if ("repair" in lowered or "resume" in lowered) and any(
            keyword in lowered for keyword in _UNSUPPORTED_KEYWORDS
        ):
            markers.append(f"{where}:{text}")

    scan(outcome.stop_reason, "stop_reason")
    for gap in outcome.gaps:
        scan(gap, "gap")
    for event in outcome.events:
        scan(event.kind, f"event[{event.sequence}].kind")
        scan(
            json.dumps(event.to_dict()["payload"], ensure_ascii=False),
            f"event[{event.sequence}].payload",
        )
    return markers
