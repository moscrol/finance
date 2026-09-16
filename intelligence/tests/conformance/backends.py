"""后端参数注册表 + 能力声明表 + 统一驱动器。

能力声明表初值抄 2026-08-29 零成本核查
（``~/Developer/career-ops/interview-prep/runtime-factory-audit-2026-08-29.md``
「后端 × 不变量」表，每格该文件里有代码出处）；执行中发现表与代码不符，
以代码为准并回写核查表。

声明语义（工单第 2 条验收）：

- ``SUPPORTED``       声明支持 → 行为断言必须绿；
- ``REDUCED``         后端自带缩减版语义 → 按它自己声明的缩减形状断言；
- ``UNSUPPORTED_EXPLICIT`` 声明不支持，且链路上游照跑（缺席是隐形的）→
  必须在运行时可观测面显式报告不支持；静默跳过判红（INV-5 codex 即此类，
  是本套件的阳性对照）；
- ``UNSUPPORTED_DECLARED`` 机制整体不在场（装配层从未接入）→ 声明表本身
  即显式化，断言只验证「确实不在场」——防止有人加了机制却不改声明；
- ``NOT_APPLICABLE``  该不变量对此后端无意义 → 显式 skip 并给理由，
  理由必须写在 notes 里（不是静默跳过）。
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

from intelligence.runtime.codex_headless_runtime import CodexHeadlessRuntime
from intelligence.runtime.dsh_stub_runtime import DshStubRuntime, ScriptedDshAction
from intelligence.runtime.glm_agent_runtime import GLMAgentRuntime
from intelligence.runtime.openai_agents_runtime import OpenAIAgentsRuntime
from intelligence.services.agent_runtime import AgentOutcome
from intelligence.services.research_contract import ResearchRunContext
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.task_frame import TaskFrame

from intelligence.tests.conformance.fixtures import (
    ScenarioProbe,
    ScriptedFakeCodex,
    ScriptedModelClient,
    ScriptedSdkRunner,
    ScriptedTurn,
)


class Verdict(str, Enum):
    SUPPORTED = "supported"
    REDUCED = "reduced"
    UNSUPPORTED_EXPLICIT = "unsupported_explicit_required"
    UNSUPPORTED_DECLARED = "unsupported_declared"
    NOT_APPLICABLE = "not_applicable"


INVARIANT_IDS: tuple[str, ...] = (
    "INV-1",
    "INV-2",
    "INV-3",
    "INV-4",
    "INV-5",
    "INV-6",
    "INV-7",
    "INV-8",
    # 运行底座终态稿 R 系列（2026-09-07 §3）：只对生产臂 continuous 与参考 loop 要求成立，
    # 其余臂声明 UNSUPPORTED_DECLARED（母单 §3 末段），断言只验「确实不在场」。
    # R2 效果三明治 / R3 程序计数器恢复（P2）；R4 取消类型化（P1）；R5 收件箱三事实（P3）；
    # R6 竞态目录两序 + 写序 oracle（P4，``conformance/races/``）。
    "INV-R2",
    "INV-R3",
    "INV-R4",
    "INV-R5",
    "INV-R6",
)

# R 系列在非适用臂上的统一理由（每个非 SUPPORTED 声明都必须带 notes）。
_R_SERIES_NOT_APPLICABLE_ARM = (
    "运行底座 R 系列只对 continuous_glm 与 HarnessReferenceLoop 要求成立"
    "（2026-09-07-runtime-base-endstate-design.md §3 末段）；本臂的取消终局不带 "
    "cancel_cause，断言验证「确实不在场」，不要求实现。"
)
_R_DURABLE_NOT_APPLICABLE_ARM = (
    "运行底座 R2 / R3 只对 continuous_glm 要求成立（母单 §6.3 P2：store 只接在 "
    "ContinuousAgentEpisode 上）；本臂事件流里没有 model_intent、tool_request 不带 "
    "replay，断言验证「确实不在场」，不要求实现。"
)
_R_INBOX_NOT_APPLICABLE_ARM = (
    "运行底座 R5 收件箱只对 continuous_glm 要求成立（母单 §6.4 P3：Inbox 挂在 "
    "_EpisodeLedger 上，只有 ContinuousAgentEpisode 认领）；本臂事件流里没有 "
    "inbox_inserted / inbox_claimed / inbox_discarded，断言验证「确实不在场」，不要求实现。"
)
_R_RACES_NOT_APPLICABLE_ARM = (
    "运行底座 R6 竞态目录只对 continuous_glm 要求成立（母单 §6.5 P4：单步驱动 "
    "manual_drive / step() 只有 ContinuousAgentEpisode 有，竞态在它的五个步点上构造）；"
    "本臂没有步点也没有 durable store，两序无从构造，断言验证「确实不在场」，不要求实现。"
)
_R_DURABLE_DECLARED: dict[str, Verdict] = {
    "INV-R2": Verdict.UNSUPPORTED_DECLARED,
    "INV-R3": Verdict.UNSUPPORTED_DECLARED,
    "INV-R5": Verdict.UNSUPPORTED_DECLARED,
    "INV-R6": Verdict.UNSUPPORTED_DECLARED,
}
_R_DURABLE_NOTES: dict[str, str] = {
    "INV-R2": _R_DURABLE_NOT_APPLICABLE_ARM,
    "INV-R3": _R_DURABLE_NOT_APPLICABLE_ARM,
    "INV-R5": _R_INBOX_NOT_APPLICABLE_ARM,
    "INV-R6": _R_RACES_NOT_APPLICABLE_ARM,
}


@dataclass
class ScenarioRun:
    """一次后端驱动的产物：outcome + 会话（若有）+ 探针 + 后端实例。"""

    outcome: AgentOutcome
    session: object | None
    probe: ScenarioProbe
    runtime: object

    def close(self) -> None:
        if self.session is not None:
            close = getattr(self.session, "close", None)
            if callable(close):
                close()


class BackendDriver(Protocol):
    """把后端无关的场景脚本翻译成某个后端的真实驱动。"""

    def run(
        self,
        *,
        initial: Sequence[ScriptedTurn],
        repairs: Sequence[Sequence[ScriptedTurn]] = (),
        frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
        probe: ScenarioProbe,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> ScenarioRun: ...

    def start(
        self,
        *,
        initial: Sequence[ScriptedTurn],
        repairs: Sequence[Sequence[ScriptedTurn]] = (),
        frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
        probe: ScenarioProbe,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> ScenarioRun: ...


class ContinuousDriver:
    """continuous_glm：注入实现 ``AgentModelClient`` 协议的脚本化 client。"""

    name = "continuous_glm"

    def _runtime(
        self,
        initial: Sequence[ScriptedTurn],
        repairs: Sequence[Sequence[ScriptedTurn]],
        probe: ScenarioProbe,
        is_cancelled: Callable[[], bool] | None,
    ) -> GLMAgentRuntime:
        turns = list(initial)
        for repair in repairs:
            turns.extend(repair)
        return GLMAgentRuntime(
            client=ScriptedModelClient(turns, probe),
            is_cancelled=is_cancelled,
        )

    def run(
        self,
        *,
        initial: Sequence[ScriptedTurn],
        repairs: Sequence[Sequence[ScriptedTurn]] = (),
        frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
        probe: ScenarioProbe,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> ScenarioRun:
        runtime = self._runtime(initial, repairs, probe, is_cancelled)
        outcome = runtime.run(task_frame=frame, context=context, registry=registry)
        return ScenarioRun(outcome=outcome, session=None, probe=probe, runtime=runtime)

    def start(
        self,
        *,
        initial: Sequence[ScriptedTurn],
        repairs: Sequence[Sequence[ScriptedTurn]] = (),
        frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
        probe: ScenarioProbe,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> ScenarioRun:
        runtime = self._runtime(initial, repairs, probe, is_cancelled)
        session = runtime.start(frame, context=context, registry=registry)
        return ScenarioRun(
            outcome=session.outcome,
            session=session,
            probe=probe,
            runtime=runtime,
        )


class SdkDriver:
    """sdk_glm / sdk_gpt：注入 ``AgentsSdkRunner`` 协议的脚本化 runner。"""

    def __init__(self, backend: str) -> None:
        if backend not in {"sdk_glm", "sdk_gpt"}:
            raise ValueError("unsupported SDK backend for conformance driver")
        self.name = backend
        self._model_name = "glm-5.2" if backend == "sdk_glm" else "gpt-5.6-sol"

    def _runtime(
        self,
        initial: Sequence[ScriptedTurn],
        repairs: Sequence[Sequence[ScriptedTurn]],
        probe: ScenarioProbe,
        is_cancelled: Callable[[], bool] | None,
    ) -> OpenAIAgentsRuntime:
        scripts: list[Sequence[ScriptedTurn]] = [initial, *repairs]
        return OpenAIAgentsRuntime(
            runner=ScriptedSdkRunner(scripts, probe),
            backend=self.name,  # type: ignore[arg-type]
            model_name=self._model_name,
            is_cancelled=is_cancelled,
        )

    def run(
        self,
        *,
        initial: Sequence[ScriptedTurn],
        repairs: Sequence[Sequence[ScriptedTurn]] = (),
        frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
        probe: ScenarioProbe,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> ScenarioRun:
        runtime = self._runtime(initial, repairs, probe, is_cancelled)
        outcome = runtime.run(task_frame=frame, context=context, registry=registry)
        return ScenarioRun(outcome=outcome, session=None, probe=probe, runtime=runtime)

    def start(
        self,
        *,
        initial: Sequence[ScriptedTurn],
        repairs: Sequence[Sequence[ScriptedTurn]] = (),
        frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
        probe: ScenarioProbe,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> ScenarioRun:
        runtime = self._runtime(initial, repairs, probe, is_cancelled)
        session = runtime.start(frame, context=context, registry=registry)
        return ScenarioRun(
            outcome=session.outcome,
            session=session,
            probe=probe,
            runtime=runtime,
        )


class CodexDriver:
    """codex_headless：注入 ``HeadlessCommandRunner`` 协议的脚本化假 CLI。

    ``codex_bin`` 固定为一个不存在的占位路径：command_runner 已注入，真实
    CLI 永不该被执行；若有代码绕过注入去跑 args[0]，会立刻显式失败。
    """

    name = "codex_headless"

    def _runtime(
        self,
        initial: Sequence[ScriptedTurn],
        repairs: Sequence[Sequence[ScriptedTurn]],
        probe: ScenarioProbe,
        is_cancelled: Callable[[], bool] | None,
    ) -> CodexHeadlessRuntime:
        scripts: list[Sequence[ScriptedTurn]] = [initial, *repairs]
        return CodexHeadlessRuntime(
            command_runner=ScriptedFakeCodex(scripts, probe),
            codex_bin="/nonexistent/conformance-codex",
            is_cancelled=is_cancelled,
        )

    def run(
        self,
        *,
        initial: Sequence[ScriptedTurn],
        repairs: Sequence[Sequence[ScriptedTurn]] = (),
        frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
        probe: ScenarioProbe,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> ScenarioRun:
        runtime = self._runtime(initial, repairs, probe, is_cancelled)
        outcome = runtime.run(task_frame=frame, context=context, registry=registry)
        return ScenarioRun(outcome=outcome, session=None, probe=probe, runtime=runtime)

    def start(
        self,
        *,
        initial: Sequence[ScriptedTurn],
        repairs: Sequence[Sequence[ScriptedTurn]] = (),
        frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
        probe: ScenarioProbe,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> ScenarioRun:
        # codex_headless 没有会话接缝（只有 run()，见 runtime_handle.py 模块
        # docstring 的逐条裁定）。session=None 是如实陈述，由声明表消化。
        return self.run(
            initial=initial,
            repairs=repairs,
            frame=frame,
            context=context,
            registry=registry,
            probe=probe,
            is_cancelled=is_cancelled,
        )


class StubDriver:
    """dsh_stub：脚本动作只支持 tool_call + 一次 finish(draft)。"""

    name = "dsh_stub"

    @staticmethod
    def _script(turns: Sequence[ScriptedTurn]) -> tuple[ScriptedDshAction, ...]:
        actions: list[ScriptedDshAction] = []
        for turn in turns:
            for call in turn.tool_calls:
                actions.append(
                    ScriptedDshAction(
                        kind="tool_call",
                        tool=call.name,
                        query=call.query,
                    )
                )
            if turn.finish is not None or turn.content:
                draft = ""
                if turn.finish is not None:
                    draft = str(turn.finish.get("draft") or "")
                actions.append(
                    ScriptedDshAction(
                        kind="finish",
                        draft=draft or turn.content or "scripted stub finish",
                    )
                )
                # stub 协议：finish 只许一次且在末尾。场景脚本里给其他后端
                # 兜底用的后续轮（如 finalization 轮的第二个 finish）在此截断。
                break
        return tuple(actions)

    def run(
        self,
        *,
        initial: Sequence[ScriptedTurn],
        repairs: Sequence[Sequence[ScriptedTurn]] = (),
        frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
        probe: ScenarioProbe,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> ScenarioRun:
        del repairs  # stub 的修复轮是协议级 replace，不消费脚本
        runtime = DshStubRuntime(self._script(initial), is_cancelled=is_cancelled)
        outcome = runtime.run(task_frame=frame, context=context, registry=registry)
        return ScenarioRun(outcome=outcome, session=None, probe=probe, runtime=runtime)

    def start(
        self,
        *,
        initial: Sequence[ScriptedTurn],
        repairs: Sequence[Sequence[ScriptedTurn]] = (),
        frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
        probe: ScenarioProbe,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> ScenarioRun:
        del repairs
        runtime = DshStubRuntime(self._script(initial), is_cancelled=is_cancelled)
        session = runtime.start(frame, context=context, registry=registry)
        return ScenarioRun(
            outcome=session.outcome,
            session=session,
            probe=probe,
            runtime=runtime,
        )


@dataclass(frozen=True)
class BackendDescriptor:
    """一个后端在能力声明表里的一行。

    ``notes`` 给每个非 SUPPORTED 的声明写理由与代码出处；断言函数据此
    产生可读的失败信息与 skip 理由。
    """

    name: str
    factory_registered: bool
    has_session_seam: bool
    attaches_runtime_handle: bool
    attaches_scope: bool
    capabilities: Mapping[str, Verdict]
    notes: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        missing = [inv for inv in INVARIANT_IDS if inv not in self.capabilities]
        if missing:
            raise ValueError(f"{self.name} 能力声明表缺不变量：{missing}")
        undeclared = [
            inv
            for inv, verdict in self.capabilities.items()
            if verdict is not Verdict.SUPPORTED and inv not in self.notes
        ]
        if undeclared:
            raise ValueError(
                f"{self.name} 非 SUPPORTED 声明必须带理由（notes）：{undeclared}"
            )

    def verdict(self, invariant: str) -> Verdict:
        return self.capabilities[invariant]

    def note(self, invariant: str) -> str:
        return self.notes.get(invariant, "")

    def build_driver(self) -> BackendDriver:
        return _DRIVER_FACTORIES[self.name]()


_DRIVER_FACTORIES: dict[str, Callable[[], BackendDriver]] = {
    "continuous_glm": ContinuousDriver,
    "sdk_glm": lambda: SdkDriver("sdk_glm"),
    "sdk_gpt": lambda: SdkDriver("sdk_gpt"),
    "codex_headless": CodexDriver,
    "dsh_stub": StubDriver,
}


_SDK_CAPABILITIES: dict[str, Verdict] = {
    "INV-1": Verdict.SUPPORTED,
    "INV-2": Verdict.SUPPORTED,
    "INV-3": Verdict.REDUCED,
    "INV-4": Verdict.SUPPORTED,
    "INV-5": Verdict.SUPPORTED,
    "INV-6": Verdict.SUPPORTED,
    "INV-7": Verdict.SUPPORTED,
    "INV-8": Verdict.SUPPORTED,
    **_R_DURABLE_DECLARED,
    "INV-R4": Verdict.UNSUPPORTED_DECLARED,
}

_SDK_NOTES: dict[str, str] = {
    "INV-3": (
        "自带缩减版：runner 拿到的 request.timeout 已扣 verifier/delivery "
        "reserve（openai_agents_runtime 内部夹层，核查表 2026-08-29）；"
        "adapter 层内层合成保底给零（api/app.py _zero_inner_synthesis_reserve）。"
        "断言按缩减语义：request.timeout < 总窗，且合成保底不归 runtime 管。"
    ),
    **_R_DURABLE_NOTES,
    "INV-R4": _R_SERIES_NOT_APPLICABLE_ARM,
}


BACKENDS: tuple[BackendDescriptor, ...] = (
    BackendDescriptor(
        name="continuous_glm",
        factory_registered=True,
        has_session_seam=True,
        attaches_runtime_handle=True,
        attaches_scope=True,
        capabilities={inv: Verdict.SUPPORTED for inv in INVARIANT_IDS},
    ),
    BackendDescriptor(
        name="sdk_glm",
        factory_registered=True,
        has_session_seam=True,
        attaches_runtime_handle=True,
        attaches_scope=False,
        capabilities=dict(_SDK_CAPABILITIES),
        notes=dict(_SDK_NOTES),
    ),
    BackendDescriptor(
        name="sdk_gpt",
        factory_registered=True,
        has_session_seam=True,
        attaches_runtime_handle=True,
        attaches_scope=False,
        capabilities=dict(_SDK_CAPABILITIES),
        notes=dict(_SDK_NOTES),
    ),
    BackendDescriptor(
        name="codex_headless",
        factory_registered=True,
        has_session_seam=False,
        attaches_runtime_handle=False,
        attaches_scope=False,
        capabilities={
            "INV-1": Verdict.SUPPORTED,
            "INV-2": Verdict.SUPPORTED,
            "INV-3": Verdict.UNSUPPORTED_DECLARED,
            "INV-4": Verdict.SUPPORTED,
            "INV-5": Verdict.UNSUPPORTED_EXPLICIT,
            "INV-6": Verdict.REDUCED,
            "INV-7": Verdict.SUPPORTED,
            "INV-8": Verdict.UNSUPPORTED_DECLARED,
            **_R_DURABLE_DECLARED,
            "INV-R4": Verdict.UNSUPPORTED_DECLARED,
        },
        notes={
            **_R_DURABLE_NOTES,
            "INV-R4": _R_SERIES_NOT_APPLICABLE_ARM,
            "INV-3": (
                "契约传入但内部单发执行，无内层检索/合成分窗机制"
                "（codex_headless_runtime.run 一次 command；核查表 2026-08-29）。"
                "机制整体不在场 → 声明式不支持，断言验证「确实不在场」。"
            ),
            "INV-5": (
                "判官在 adapter 层照跑，但修复静默跳过：continuous_turn_adapter"
                "._resume_for_gap 对无 resume 的 session（codex 走 run() 单发，"
                "session=None）直接 return None，无任何收据（L1181-1184）。"
                "声明不支持 → 要求运行时显式报告不支持；静默即红。"
            ),
            "INV-6": (
                "事件成对/durable 对账照断言；RuntimeHandle 六态收据没有会话"
                "接缝可接（runtime_handle.py docstring 逐条裁定 a 条），"
                "该半边按声明跳过。"
            ),
            "INV-8": (
                "只有 run()（L588），没有 start()，不满足 ResumableAgentRuntime"
                "——设计决定：单发 run 上不造会话状态机（核查表 2026-08-29）。"
                "断言验证「确实不在场」。"
            ),
        },
    ),
    BackendDescriptor(
        name="dsh_stub",
        factory_registered=False,
        has_session_seam=True,
        attaches_runtime_handle=True,
        attaches_scope=True,
        capabilities={
            "INV-1": Verdict.SUPPORTED,
            "INV-2": Verdict.SUPPORTED,
            "INV-3": Verdict.NOT_APPLICABLE,
            "INV-4": Verdict.SUPPORTED,
            "INV-5": Verdict.SUPPORTED,
            "INV-6": Verdict.SUPPORTED,
            "INV-7": Verdict.NOT_APPLICABLE,
            "INV-8": Verdict.SUPPORTED,
            **_R_DURABLE_DECLARED,
            "INV-R4": Verdict.UNSUPPORTED_DECLARED,
        },
        notes={
            **_R_DURABLE_NOTES,
            "INV-R4": _R_SERIES_NOT_APPLICABLE_ARM,
            "INV-3": (
                "脚本化协议参照桩：无模型轮、无检索/合成窗语义"
                "（DshStubRuntime._play 顺序回放脚本），deadline 分窗不变量"
                "对它无从谈起。"
            ),
            "INV-7": (
                "stub 不产生模型 FINAL_JSON——draft 由脚本给定、bindings 由 "
                "_outcome_from_snapshot 从真实 snapshot 组装，悬空引用在构造"
                "上不可表达；AgentOutcome 构造器兜底其余形状。"
            ),
        },
    ),
)


BACKENDS_BY_NAME: dict[str, BackendDescriptor] = {
    descriptor.name: descriptor for descriptor in BACKENDS
}


__all__ = [
    "BACKENDS",
    "BACKENDS_BY_NAME",
    "BackendDescriptor",
    "BackendDriver",
    "INVARIANT_IDS",
    "ScenarioRun",
    "Verdict",
]
