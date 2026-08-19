from __future__ import annotations

import dataclasses
import json
import os
from unittest import mock

import pytest

from intelligence.services.agent_research import AgentEvidence, AgentToolContext
from intelligence.services.agent_runtime import (
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    OutputEvidenceBinding,
)
from intelligence.services.episode_protocol import (
    ABSENT_REJECTION_CODE,
    EpisodeFinish,
    EpisodeFinishRejection,
    SYSTEM_PROMPT_DYNAMIC_BOUNDARY,
    build_episode_input,
    build_episode_instructions,
    cited_evidence_ordinals,
    evidence_ordinal_table,
    finish_json_schema,
    finish_rejection_fields,
    resolve_evidence_refs,
    split_episode_prompt,
    strip_hashes_for_model,
    validate_episode_finish,
)
from intelligence.services.episode_issues import IssueCode
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.evidence_capabilities import EvidencePlan
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    RequiredOutput,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
)
from intelligence.services.research_tool_registry import (
    ResearchToolRegistry,
    ToolSpec,
)
from intelligence.services.task_frame import TaskFrame


def _frame() -> TaskFrame:
    return TaskFrame(
        raw_question="目前市场怎么看",
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


def _context(frame: TaskFrame) -> ResearchRunContext:
    contract = ResearchTaskContract(
        task_id="episode-protocol-test",
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
        allowed_capabilities=("market_data",),
        research_tier="quick",
        freshness="current",
        timeframe=frame.timeframe,
        evidence_plan=EvidencePlan(),
        task_frame_hash=frame.task_frame_hash,
    )
    return ResearchRunContext(
        contract=contract,
        deadline=ResearchDeadline.from_timeout(30.0),
        policy=ResearchPolicy("quick", 3, 30.0, 0.0),
        trace_parent_id="episode-protocol-test",
        today="2026-07-25",
        latest_data_date="2026-07-24",
    )


def _registry() -> ResearchToolRegistry:
    def runner(_query: str, _context: AgentToolContext):
        return (
            [],
            "",
            ProviderTrace(
                provider="test:market",
                capability="market_data",
                status="empty",
            ),
        )

    return ResearchToolRegistry(
        (
            ToolSpec(
                name="market_data",
                capability="market_data",
                description="结构化行情与市场时序",
                cost="local",
                freshness="current",
                runner=runner,
            ),
        )
    )


def _evidence() -> tuple[AgentEvidence, ...]:
    return (
        AgentEvidence(
            tool="market_data",
            title="A股市场总览",
            detail="截至2026-07-24，上涨家数增加。",
            source="本地行情",
            source_date="2026-07-24",
            evidence_tier="L4",
            content_hash="market-hash",
        ),
    )


def _hex_evidence(*hashes: str) -> tuple[AgentEvidence, ...]:
    return tuple(
        AgentEvidence(
            tool="market_data",
            title="A股市场总览",
            detail="截至2026-07-24，上涨家数增加。",
            source="本地行情",
            source_date="2026-07-24",
            evidence_tier="L4",
            content_hash=content_hash,
        )
        for content_hash in hashes
    )


def _finish_with_hashes(*hashes: str) -> dict[str, object]:
    return {
        "status": "completed",
        "draft": "有内容的草稿。",
        "bindings": [
            {
                "output_id": "direct_assessment",
                "evidence_hashes": list(hashes),
                "basis": "evidence",
            }
        ],
    }


def test_finish_schema_is_closed_and_requires_all_fields() -> None:
    schema = finish_json_schema()

    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"status", "draft", "gaps", "bindings"}
    binding_schema = schema["properties"]["bindings"]["items"]
    assert "basis" in binding_schema["required"]
    assert binding_schema["properties"]["basis"]["enum"] == [
        "evidence",
        "user_premise",
        "model_reasoning",
    ]


def test_protocol_builds_task_bound_instructions_and_input() -> None:
    frame = _frame()
    context = dataclasses.replace(
        _context(frame),
        conversation_context=(
            "user: 昨天的反弹能持续多久\n"
            "assistant: 基准判断是短周期修复。"
        ),
    )

    instructions = build_episode_instructions(frame, context, _registry())
    task_input = json.loads(build_episode_input(frame, context, _registry()))

    assert frame.task_frame_hash not in instructions
    assert "market_data" not in instructions
    assert "不得在答案中暴露内部工具名、provider 或哈希" in instructions
    assert task_input["task_frame"]["task_frame_hash"] == frame.task_frame_hash
    assert task_input["task_frame_hash"] == frame.task_frame_hash
    assert task_input["research_contract"]["task_frame_hash"] == (
        frame.task_frame_hash
    )
    assert "market_data" in task_input["available_tools"]
    assert task_input["latest_data_date"] == "2026-07-24"
    assert task_input["information_cutoff"] == (
        context.information_cutoff.to_dict()
    )
    assert "information_cutoff" in task_input["date_rule"]
    assert "基准判断是短周期修复" in task_input["conversation_context"]
    assert task_input["conversation_context_rule"] == (
        "历史对话仅用于消解指代和延续用户目标，不得当作事实证据"
    )


def test_episode_input_carries_perspective_context_only_when_active() -> None:
    """视角块只在激活时进模型输入；neutral 不得出现任何新键。

    neutral 逐字节不变是注入原语的既有契约（ask_synthesis 侧同源）；
    激活时观点层/事实层的边界声明必须与内容同时到达。
    """
    frame = _frame()
    neutral_context = _context(frame)
    active_context = dataclasses.replace(
        neutral_context,
        perspective_context="只允许使用下方这一位 KOL 的画像与原文召回。",
    )

    neutral_input = json.loads(
        build_episode_input(frame, neutral_context, _registry())
    )
    active_input = json.loads(
        build_episode_input(frame, active_context, _registry())
    )

    assert "perspective_context" not in neutral_input
    assert "perspective_context_rule" not in neutral_input
    assert active_input["perspective_context"] == (
        "只允许使用下方这一位 KOL 的画像与原文召回。"
    )
    assert "不得当作事实证据" in active_input["perspective_context_rule"]


def test_episode_input_carries_reading_baseline_by_default() -> None:
    """判读基线默认进 continuous 输入，且能被 env 总开关整块关掉。

    与 perspective_context 的契约相反：视角是观点层、默认不注入；判读基线是领域
    方法层、**默认注入**——关掉它 agent 就退化成查数机器人。两个引擎都必须接，
    只接 legacy 会重演 2026-08-14「视角配置生效、模型没看到」那次事故。
    """
    frame = _frame()
    context = _context(frame)

    on = json.loads(build_episode_input(frame, context))
    assert "FY-A10" in on["reading_baseline"], "默认应注入判读基线"
    assert "以证据为准" in on["reading_baseline_rule"]

    # 总开关关掉后，payload 里两个键都不得出现（逐字节回到未内置状态）
    with mock.patch.dict(os.environ, {"FINANCE_READING_BASELINE": "0"}):
        off = json.loads(build_episode_input(frame, context))
    assert "reading_baseline" not in off
    assert "reading_baseline_rule" not in off


def _static_contract_text() -> str:
    """Return only the hard-coded contract literals of the instruction builder.

    Reads the source with ``ast`` instead of calling the builder. Per-turn
    hash, tool table, and question-type rules now live in
    ``build_episode_input``; this lock is the constitution only.
    """

    import ast
    import inspect
    import textwrap

    tree = ast.parse(
        textwrap.dedent(inspect.getsource(build_episode_instructions))
    )
    return "".join(
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        # Drop the docstring: it is not part of the model-facing contract.
        and not node.value.startswith("Build the static constitution")
        and not node.value.startswith("Build one outcome-first")
    )


# 宪法静态契约文本，扣掉 `【…】` 分组标题与全部空白后的指纹。
#
# 2026-08-22 L2 把题型规则 / hash / 工具表搬出本函数。基线从
# acb20a7df27a44c59f4febcff330d852ed78e70cf14a34f7c9fa3acc126efce8
# 更新为本值：措辞未动，只搬位置，不得为保旧指纹留副本。
#
# 它变红意味着有人动了约束的措辞或顺序。那可能是对的，但必须是**显式**的：
# 请连同这里的期望值一起更新，并在 commit 说明改了哪一条、为什么。
_CONTRACT_FINGERPRINT = (
    "a6f450a1d3ab387915d8a9693784d365785c866b451e78ea90dfbca6d9c7c44a"
)


def test_instruction_reshape_kept_every_constraint_verbatim() -> None:
    import hashlib
    import re

    stripped = re.sub(r"\s+", "", re.sub(r"【[^】]*】", "", _static_contract_text()))
    digest = hashlib.sha256(stripped.encode("utf-8")).hexdigest()

    assert digest == _CONTRACT_FINGERPRINT, (
        "静态契约的措辞或顺序变了（扣掉分组标题与空白后比较）。\n"
        f"  实际 {digest}\n"
        f"  期望 {_CONTRACT_FINGERPRINT}\n"
        "若这次确实要改约束内容，请显式更新 _CONTRACT_FINGERPRINT 并在 commit "
        "里说明改了哪一条；不要靠回退重排来让它变绿。"
    )


def test_instructions_are_grouped_not_one_flat_wall() -> None:
    """锁形状本身，否则「指纹没变」也可能是因为重排被整体回退了。

    阈值不是审美：重排前最长无换行段 1,501 字符、全文仅 4 个换行，模型要定位
    「哪几条是关于证据绑定的」只能线性扫一遍长串。这里用一个宽松上界（400）
    钉住「不能再退回单段墙」，而不是锁死当前的 210——留出后续增删约束的余量。
    """

    instructions = build_episode_instructions(_frame(), _context(_frame()), _registry())
    longest_run = max(len(line) for line in instructions.split("\n"))

    assert longest_run < 400, f"出现了 {longest_run} 字符的无换行段，契约正在退回单段墙"
    assert instructions.count("\n") >= 20
    for header in (
        "【任务与计划】",
        "【工具与观察】",
        "【表达边界】",
        "【证据绑定】",
        "【何时停止】",
        "【终局 JSON】",
    ):
        assert header in instructions


def test_system_instructions_are_byte_stable_across_task_frames() -> None:
    """L2 学会了 ①：两个不同 task_frame 的 system 消息逐字节相同。"""

    market = _frame()
    valuation = dataclasses.replace(
        _frame(),
        raw_question="瑞华泰的合理估值",
        question_type="valuation_estimate",
        subject="瑞华泰",
        subject_kind="company",
        required_outputs=("scenario_range",),
    )
    market_system, market_user = split_episode_prompt(
        market, _context(market), _registry()
    )
    valuation_system, valuation_user = split_episode_prompt(
        valuation, _context(valuation), _registry()
    )

    assert market_system == valuation_system
    assert market_user != valuation_user
    assert SYSTEM_PROMPT_DYNAMIC_BOUNDARY == "SYSTEM_PROMPT_DYNAMIC_BOUNDARY"


def test_episode_input_carries_hash_tools_rules_and_cutoff() -> None:
    """L2 学会了 ②：user JSON 含 hash、可用工具、题型规则、information_cutoff。"""

    frame = dataclasses.replace(
        _frame(),
        raw_question="瑞华泰的合理估值",
        question_type="valuation_estimate",
        subject="瑞华泰",
        subject_kind="company",
        required_outputs=("scenario_range",),
    )
    context = _context(frame)
    payload = json.loads(build_episode_input(frame, context, _registry()))

    assert payload["task_frame_hash"] == frame.task_frame_hash
    assert "market_data" in payload["available_tools"]
    assert "估值题专用完成规则" in payload["question_type_rules"]
    assert payload["information_cutoff"] == context.information_cutoff.to_dict()


def test_episode_runtimes_mark_system_prompt_dynamic_boundary() -> None:
    """组消息处标出边界；本单不实现 cache_control。"""

    from pathlib import Path

    roots = (
        Path("intelligence/runtime/agent_episode.py"),
        Path("intelligence/runtime/openai_agents_runtime.py"),
        Path("intelligence/runtime/codex_headless_runtime.py"),
    )
    for path in roots:
        assert "SYSTEM_PROMPT_DYNAMIC_BOUNDARY" in path.read_text(
            encoding="utf-8"
        ), path


def test_track_questions_get_episode_track_contract() -> None:
    """跟踪题的 episode 指令必须带跟踪表达契约（knevo q8 回灌的 episode 版）。

    此前该契约只接在 legacy ask_synthesis 路径——生产主路径（episode）的
    跟踪题仍被答成一次性全景重跑。episode 版术语必须对齐本路径：基线来源
    是 memory_lookup / conversation_context，不是 legacy 的 [M]/[V] 检索块。
    """
    frame = dataclasses.replace(
        _frame(),
        raw_question="光伏自上次之后有什么新变化",
        question_type="theme_track",
    )
    payload = json.loads(build_episode_input(frame, _context(frame), _registry()))
    rules = payload["question_type_rules"]
    instructions = build_episode_instructions(frame, _context(frame), _registry())

    assert "跟踪表达契约" not in instructions
    assert "跟踪表达契约" in rules
    assert "无上期基线，本期建立基线" in rules
    assert "memory_lookup" in rules
    # legacy 检索块记号不得泄漏进 episode 指令——episode 里没有这些块。
    for legacy_marker in ("[M]", "[V]", "[D0]", "[D6]", "[W7]"):
        assert legacy_marker not in rules


def test_non_track_questions_keep_instructions_unchanged() -> None:
    frame = _frame()
    instructions = build_episode_instructions(frame, _context(frame), _registry())
    payload = json.loads(build_episode_input(frame, _context(frame), _registry()))
    assert "跟踪表达契约" not in instructions
    assert "跟踪表达契约" not in payload["question_type_rules"]


def test_forecast_episode_gets_causal_hypothesis_contract() -> None:
    """第五轮路径是 continuous episode，不是 ask_synthesis。

    scenario_tree 在预测题上被别名到 rebound_case，只改槽位描述到不了模型。
    因果假说必须像跟踪契约一样条件注入指令。
    """
    overnight = dataclasses.replace(
        _frame(),
        raw_question=(
            "基于周二的盘面数据，你认为主线是什么。"
            "今晚美股科技调整较多，你认为明天盘面会怎么走，哪个方向可能有机会"
        ),
    )
    local = dataclasses.replace(
        _frame(),
        raw_question="昨天的反弹能持续多久",
    )
    valuation = dataclasses.replace(
        _frame(),
        raw_question="深信服最近一期毛利率是多少",
        question_type="valuation",
    )

    overnight_rules = json.loads(
        build_episode_input(overnight, _context(overnight), _registry())
    )["question_type_rules"]
    local_rules = json.loads(
        build_episode_input(local, _context(local), _registry())
    )["question_type_rules"]
    valuation_rules = json.loads(
        build_episode_input(valuation, _context(valuation), _registry())
    )["question_type_rules"]

    assert "互斥因果假说" in overnight_rules
    assert "证据不足，两假说并立" in overnight_rules
    assert "领跌相对强弱" in overnight_rules
    assert "互斥因果假说" in local_rules
    assert "互斥因果假说" not in valuation_rules
    for legacy_marker in ("[M]", "[V]", "[D0]", "[D6]", "[W7]"):
        assert legacy_marker not in overnight_rules


def test_validate_finish_rejects_unknown_evidence_hash() -> None:
    frame = _frame()
    context = _context(frame)
    value = {
        "status": "completed",
        "draft": "当前判断有直接依据。",
        "gaps": [],
        "bindings": [
            {
                "output_id": "direct_assessment",
                "evidence_hashes": ["unknown-hash"],
                "gap": "",
            }
        ],
    }

    with pytest.raises(ValueError, match="unknown evidence hash"):
        validate_episode_finish(value, context=context, evidence=_evidence())


def test_validate_finish_returns_immutable_value() -> None:
    frame = _frame()
    context = _context(frame)
    finish = validate_episode_finish(
        {
            "status": "completed",
            "draft": "当前更接近条件化修复。",
            "gaps": [],
            "bindings": [
                {
                    "output_id": "direct_assessment",
                    "evidence_hashes": ["market-hash"],
                    "gap": "",
                }
            ],
        },
        context=context,
        evidence=_evidence(),
    )

    assert finish == EpisodeFinish(
        status="completed",
        draft="当前更接近条件化修复。",
        gaps=(),
        bindings=finish.bindings,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        finish.status = "partial"  # type: ignore[misc]


def test_validate_finish_accepts_model_reasoning_without_fake_evidence() -> None:
    frame = _frame()
    context = _context(frame)
    context = dataclasses.replace(
        context,
        contract=dataclasses.replace(
            context.contract,
            required_outputs=(
                RequiredOutput(
                    "direct_assessment",
                    "直接判断",
                    (),
                    True,
                    grounding_mode="model_reasoning",
                ),
            ),
            allowed_capabilities=(),
        ),
    )

    finish = validate_episode_finish(
        {
            "status": "completed",
            "draft": "判断新题材时，应先定义可证伪条件，再观察资金接力。",
            "gaps": [],
            "bindings": [
                {
                    "output_id": "direct_assessment",
                    "evidence_hashes": [],
                    "basis": "model_reasoning",
                    "gap": "",
                }
            ],
        },
        context=context,
        evidence=(),
    )

    assert finish.bindings == (
        OutputEvidenceBinding(
            "direct_assessment",
            (),
            basis="model_reasoning",
        ),
    )


def _context_with_evidence_boundary(frame: TaskFrame) -> ResearchRunContext:
    """两格必需输出的契约，复刻 2026-08-10 live 里真实作废的那份 FINAL_JSON。"""

    context = _context(frame)
    return dataclasses.replace(
        context,
        contract=dataclasses.replace(
            context.contract,
            required_outputs=(
                RequiredOutput("direct_assessment", "直接判断", ("market_data",), True),
                RequiredOutput("evidence_boundary", "证据边界", ("market_data",), True),
            ),
        ),
    )


def test_validate_finish_keeps_answer_when_supported_output_adds_a_caveat() -> None:
    """有证据支撑的附带 gap 不得作废整份答案，限制挪到顶层 gaps。

    2026-08-10 live 实测：``evidence_boundary`` 带证据哈希、顶层 gaps 已写同一
    条限制，模型又在 ``binding.gap`` 里抄了一份。契约要求这种限制只写顶层，
    所以这是格式滑档。08-10 先锁住「不要因此作废整份 FINAL_JSON」。
    08-15 补完第二步：把附带限制挪到顶层 ``gaps`` 并清空 ``binding.gap``，
    否则全格滑档时 verifier 会把已绑 hashes 全部丢掉，交付证据=0。
    """

    frame = _frame()
    context = _context_with_evidence_boundary(frame)

    finish = validate_episode_finish(
        {
            "status": "completed",
            "draft": "基准判断：偏强震荡，冲高回落风险同步上升。",
            "gaps": ["缺少同一时间窗口的新闻证据。"],
            "bindings": [
                {
                    "output_id": "direct_assessment",
                    "evidence_hashes": ["market-hash"],
                    "gap": "",
                },
                {
                    "output_id": "evidence_boundary",
                    "evidence_hashes": ["market-hash"],
                    "gap": "缺少同一时间窗口的新闻证据。",
                },
            ],
        },
        context=context,
        evidence=_evidence(),
    )

    assert finish.status == "completed"
    assert finish.draft == "基准判断：偏强震荡，冲高回落风险同步上升。"
    boundary = next(
        item for item in finish.bindings if item.output_id == "evidence_boundary"
    )
    assert boundary.gap == ""
    assert boundary.evidence_hashes == ("market-hash",)
    assert "缺少同一时间窗口的新闻证据。" in finish.gaps
    assert finish.caveat_slips == 1


def test_validate_finish_relocates_all_slot_caveats_so_verifier_can_fulfill() -> None:
    """R7-A7 形状：两格都是 hashes+gap 时，normalize 后 verifier 能 fulfilled。"""

    frame = _frame()
    context = _context_with_evidence_boundary(frame)
    finish = validate_episode_finish(
        {
            "status": "partial",
            "draft": "基准判断：偏强震荡。证据边界：同日盘面可核验，新闻缺口另列。",
            "gaps": [],
            "bindings": [
                {
                    "output_id": "direct_assessment",
                    "evidence_hashes": ["market-hash"],
                    "gap": "技术定义检索超时，盘面判断仍有同日数据。",
                },
                {
                    "output_id": "evidence_boundary",
                    "evidence_hashes": ["market-hash"],
                    "gap": "没有同日新闻证据。",
                },
            ],
        },
        context=context,
        evidence=_evidence(),
    )

    assert all(not item.gap for item in finish.bindings)
    assert "技术定义检索超时，盘面判断仍有同日数据。" in finish.gaps
    assert "没有同日新闻证据。" in finish.gaps
    assert finish.caveat_slips == 2

    outcome = AgentOutcome(
        task_frame_hash=context.contract.task_frame_hash,
        status="partial",
        draft=finish.draft,
        evidence=_evidence(),
        traces=(),
        gaps=finish.gaps,
        stop_reason="repair_model_stop",
        events=(EpisodeEvent(1, "task", {"task_frame_hash": context.contract.task_frame_hash}),),
        bindings=finish.bindings,
        usage=AgentUsage(llm_calls=1, tool_calls=1),
    )
    verified = verify_episode_outcome(context.contract, outcome)
    assert {item.status for item in verified.completion.outputs} == {"fulfilled"}
    assert not any(
        item.code == IssueCode.REQUIRED_OUTPUT_GAP for item in verified.issue_items
    )


def test_validate_finish_still_rejects_gap_without_any_evidence() -> None:
    """放宽的边界是「有没有直接证据」，不是「有没有写 gap」。

    没有证据哈希的 gap 是真缺口，仍须判必需输出缺失——否则上一条测试就会把
    「模型什么都没查到」一起放行，等于用取消校验来换取答案不丢。
    """

    frame = _frame()
    context = _context_with_evidence_boundary(frame)

    with pytest.raises(ValueError, match="required output lacks evidence"):
        validate_episode_finish(
            {
                "status": "completed",
                "draft": "基准判断：偏强震荡。",
                "gaps": ["没有查到证据边界所需数据。"],
                "bindings": [
                    {
                        "output_id": "direct_assessment",
                        "evidence_hashes": ["market-hash"],
                        "gap": "",
                    },
                    {
                        "output_id": "evidence_boundary",
                        "evidence_hashes": [],
                        "gap": "没有查到证据边界所需数据。",
                    },
                ],
            },
            context=context,
            evidence=_evidence(),
        )


def test_validate_finish_rejects_basis_that_weakens_evidence_contract() -> None:
    frame = _frame()
    context = _context(frame)

    with pytest.raises(ValueError, match="grounding basis"):
        validate_episode_finish(
            {
                "status": "completed",
                "draft": "当前市场已经转强。",
                "gaps": [],
                "bindings": [
                    {
                        "output_id": "direct_assessment",
                        "evidence_hashes": [],
                        "basis": "model_reasoning",
                        "gap": "",
                    }
                ],
            },
            context=context,
            evidence=(),
        )


def test_every_rejection_code_is_classified() -> None:
    """每个 raise 出去的 code 都必须在分类表里——可恢复集合是明确枚举。

    对应 book1 ch06 那条不变量 ``withheld_error ∈ {prompt_too_long, ...}``：
    恢复集合必须是显式枚举，不能是「其余都算」。

    **code 清单从源码 AST 解析，不手抄。** 手抄的清单会和源码分叉，
    而分叉时这条测试仍然发绿——那就成了 [[gate-assertion-granularity]] 里
    「只钉文件名的审计保不住符号」的同一个形状。
    """

    import ast
    import pathlib

    from intelligence.services import episode_protocol as mod

    source = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    raised = {
        node.args[0].value
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_reject"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }

    assert raised, "AST 没解析到任何 _reject 调用——解析器坏了，不是代码干净了"
    unclassified = raised - set(mod.REJECTION_KINDS)
    assert not unclassified, f"这些病因没有类别: {sorted(unclassified)}"
    unused = set(mod.REJECTION_KINDS) - raised
    assert not unused, f"分类表里有已不再抛出的病因，应删除: {sorted(unused)}"


def test_forged_hash_is_integrity_not_format() -> None:
    """伪造证据哈希是地基破坏，与「格式写错」必须落在不同类别。

    这两件事此前共用一个 ``ValueError``，因此得到同一个动作。分类的意义
    就在于让上游能对它们做不同处置：格式回灌重写，地基破坏硬拒。
    """

    from intelligence.services.episode_protocol import (
        EpisodeFinishRejection,
        RejectionKind,
    )

    context = _context(_frame())
    with pytest.raises(EpisodeFinishRejection) as forged:
        validate_episode_finish(
            {
                "status": "completed",
                "draft": "有内容的草稿。",
                "bindings": [
                    {
                        "output_id": "direct_assessment",
                        "evidence_hashes": ["hash-that-was-never-collected"],
                        "basis": "evidence",
                    }
                ],
            },
            context=context,
            evidence=(),
        )
    assert forged.value.code == "forged_hash"
    assert forged.value.kind is RejectionKind.INTEGRITY

    with pytest.raises(EpisodeFinishRejection) as bad_shape:
        validate_episode_finish(
            {"status": "completed", "draft": "有内容。", "bindings": "not-a-list"},
            context=context,
            evidence=(),
        )
    assert bad_shape.value.code == "bindings_not_list"
    assert bad_shape.value.kind is RejectionKind.FORMAT


def test_unique_one_char_truncated_hash_is_format_not_integrity() -> None:
    """生产 A4 形状：模型抄了 15/16 位。这是截断不是伪造。

    唯一前缀且只少 1 位 → FORMAT（可回灌重写）。
    回灌文案不得带出完整哈希，否则等于把白名单提示给模型。
    """

    from intelligence.services.episode_protocol import (
        EpisodeFinishRejection,
        RejectionKind,
        rejection_response,
    )

    full = "54a5b453de9366b0"
    truncated = full[:-1]
    context = _context(_frame())
    with pytest.raises(EpisodeFinishRejection) as err:
        validate_episode_finish(
            _finish_with_hashes(truncated),
            context=context,
            evidence=_hex_evidence(full),
        )
    assert err.value.code == "truncated_hash"
    assert err.value.kind is RejectionKind.FORMAT
    assert truncated in str(err.value)
    assert full not in str(err.value)

    response = rejection_response(err.value)
    assert response.reinject is True
    assert response.allow_recovery is True
    assert response.stop_reason == "invalid_model_finish"


def test_truncated_hash_stays_integrity_when_prefix_is_ambiguous_or_too_short() -> None:
    """少 2 位、或 15 位对上两条证据，仍是伪造——不能把 INTEGRITY 闸门凿开。"""

    from intelligence.services.episode_protocol import (
        EpisodeFinishRejection,
        RejectionKind,
    )

    context = _context(_frame())
    full_a = "54a5b453de9366b0"
    full_b = "54a5b453de9366b1"

    with pytest.raises(EpisodeFinishRejection) as ambiguous:
        validate_episode_finish(
            _finish_with_hashes("54a5b453de9366b"),
            context=context,
            evidence=_hex_evidence(full_a, full_b),
        )
    assert ambiguous.value.code == "forged_hash"
    assert ambiguous.value.kind is RejectionKind.INTEGRITY

    with pytest.raises(EpisodeFinishRejection) as too_short:
        validate_episode_finish(
            _finish_with_hashes(full_a[:-2]),
            context=context,
            evidence=_hex_evidence(full_a),
        )
    assert too_short.value.code == "forged_hash"
    assert too_short.value.kind is RejectionKind.INTEGRITY


def test_mixed_truncated_and_forged_hash_fails_closed_as_integrity() -> None:
    """一笔绑定里混进真伪造，不能因为另一条只是抄漏就给 FORMAT 回灌。"""

    from intelligence.services.episode_protocol import (
        EpisodeFinishRejection,
        RejectionKind,
    )

    full = "54a5b453de9366b0"
    context = _context(_frame())
    with pytest.raises(EpisodeFinishRejection) as err:
        validate_episode_finish(
            _finish_with_hashes(full[:-1], "deadbeefdeadbeef"),
            context=context,
            evidence=_hex_evidence(full),
        )
    assert err.value.code == "forged_hash"
    assert err.value.kind is RejectionKind.INTEGRITY


def test_exact_hash_still_accepts_after_truncation_gate() -> None:
    """截断口子不能误伤完整哈希。"""

    full = "54a5b453de9366b0"
    finish = validate_episode_finish(
        _finish_with_hashes(full),
        context=_context(_frame()),
        evidence=_hex_evidence(full),
    )
    assert finish.bindings[0].evidence_hashes == (full,)


def test_every_rejection_kind_has_a_disposition() -> None:
    """每个类别都必须有明确处置——不允许「其余都算」。

    对应 book1 ch06 那条熔断不变量 ``withheld_error ∈ {...}``：可恢复集合必须是
    明确枚举。少一格不会报错，只会在运行时落进某个默认分支——那正是本轮要消除
    的形状，所以用测试把穷尽性钉死，而不是靠 review 看出来。
    """

    from intelligence.services.episode_protocol import (
        REJECTION_RESPONSES,
        RejectionKind,
    )

    assert set(REJECTION_RESPONSES) == set(RejectionKind), (
        "有类别没有登记处置，或登记了不存在的类别: "
        f"{set(RejectionKind) ^ set(REJECTION_RESPONSES)}"
    )


def test_integrity_alone_is_denied_reinjection_and_recovery() -> None:
    """伪造证据哈希不得获得重写机会——本轮唯一的行为变更，必须钉住。

    改动前：``forged_hash`` 与「JSON 少个括号」走同一条路，都能拿到一次回灌。
    而回灌的内容是「你给的哈希不在白名单里」——这等于在提示一个编造了证据的
    模型「换个哈希再试」。格式滑档该给第二次机会，地基破坏不该。

    这条也顺带钉住**另外两类仍然可回灌**：分流不是「全都变严」，
    否则会牺牲 FORMAT/SUBSTANCE 本来正确的宽容度。
    """

    from intelligence.services.episode_protocol import (
        EpisodeFinishRejection,
        rejection_response,
    )

    integrity = rejection_response(EpisodeFinishRejection("forged_hash", "x"))
    assert integrity.reinject is False
    assert integrity.allow_recovery is False
    # 单独命名：否则地基破坏在收据统计里与普通格式错混为一谈。
    assert integrity.stop_reason == "integrity_violation"

    for code in ("bindings_not_list", "missing_evidence", "truncated_hash"):
        response = rejection_response(EpisodeFinishRejection(code, "x"))
        assert response.reinject is True, f"{code} 应保留回灌"
        assert response.allow_recovery is True, f"{code} 应保留收尾恢复"
        assert response.stop_reason == "invalid_model_finish"

    # 非本模块抛出的 ValueError 按 FORMAT 兜底 = 沿用旧行为。刻意不按 INTEGRITY
    # 兜底：一次分类遗漏不该表现成线上突然变严，那种回归极难归因。
    fallback = rejection_response(ValueError("来自下游第三方代码"))
    assert fallback.reinject is True
    assert fallback.allow_recovery is True
    assert rejection_response(ValueError("x")) is rejection_response(
        EpisodeFinishRejection("bad_status", "x")
    ), "未分类异常必须与 FORMAT 得到同一处置对象"


def _qa_context(frame: TaskFrame, *output_ids: str) -> ResearchRunContext:
    """B 组 / A6 冻结形状用的两格契约（direct_answer + evidence_boundary）。"""

    context = _context(frame)
    return dataclasses.replace(
        context,
        contract=dataclasses.replace(
            context.contract,
            required_outputs=tuple(
                RequiredOutput(output_id, output_id, ("market_data",), True)
                for output_id in output_ids
            ),
        ),
    )


def _definition_context(frame: TaskFrame) -> ResearchRunContext:
    """R7-A7 冻结主 case 的两格契约。"""

    return _qa_context(frame, "direct_definition", "evidence_boundary")


def _slip_binding(output_id: str, hashes: list[str], gap: str) -> dict[str, object]:
    return {
        "output_id": output_id,
        "evidence_hashes": hashes,
        "gap": gap,
        "basis": "evidence",
    }


def test_caveat_slips_replays_r7_a7_frozen_finish() -> None:
    """R-22 断言 1：重放 R7-A7 冻结 FINAL_JSON 形状，计数 = 被搬运格数。

    源 run ``run_20260813_034211_544672``：两格 hashes+gap（6/7），
    哈希用合成值，只钉形状。
    """

    frame = _frame()
    context = _definition_context(frame)
    definition_hashes = [f"a7-def-{index:02d}" for index in range(6)]
    boundary_hashes = [f"a7-bnd-{index:02d}" for index in range(7)]
    evidence = _hex_evidence(*definition_hashes, *boundary_hashes)
    finish = validate_episode_finish(
        {
            "status": "partial",
            "draft": "直接定义：该概念按公开口径解释。证据边界：同日盘面可核验。",
            "gaps": [],
            "bindings": [
                _slip_binding(
                    "direct_definition",
                    definition_hashes,
                    "技术定义检索超时，盘面判断仍有同日数据。",
                ),
                _slip_binding(
                    "evidence_boundary",
                    boundary_hashes,
                    "没有同日新闻证据。",
                ),
            ],
        },
        context=context,
        evidence=evidence,
    )

    assert finish.caveat_slips == 2
    assert all(not item.gap for item in finish.bindings)
    verified = verify_episode_outcome(
        context.contract,
        AgentOutcome(
            task_frame_hash=context.contract.task_frame_hash,
            status="partial",
            draft=finish.draft,
            evidence=evidence,
            traces=(),
            gaps=finish.gaps,
            stop_reason="repair_model_stop",
            events=(
                EpisodeEvent(
                    1, "task", {"task_frame_hash": context.contract.task_frame_hash}
                ),
            ),
            bindings=finish.bindings,
            usage=AgentUsage(llm_calls=1, tool_calls=1),
        ),
    )
    assert {item.status for item in verified.completion.outputs} == {"fulfilled"}


def test_caveat_slips_zero_on_clean_finish() -> None:
    """R-22 断言 2：无 gap、或 gap 已在顶层时，计数为 0 且字段在场。"""

    frame = _frame()
    context = _context(frame)
    clean = validate_episode_finish(
        {
            "status": "completed",
            "draft": "当前更接近条件化修复。",
            "gaps": [],
            "bindings": [
                {
                    "output_id": "direct_assessment",
                    "evidence_hashes": ["market-hash"],
                    "gap": "",
                }
            ],
        },
        context=context,
        evidence=_evidence(),
    )
    assert clean.caveat_slips == 0

    top_level_only = validate_episode_finish(
        {
            "status": "partial",
            "draft": "当前更接近条件化修复。",
            "gaps": ["新闻窗口未覆盖，限制已写在顶层。"],
            "bindings": [
                {
                    "output_id": "direct_assessment",
                    "evidence_hashes": ["market-hash"],
                    "gap": "",
                }
            ],
        },
        context=context,
        evidence=_evidence(),
    )
    assert top_level_only.caveat_slips == 0
    assert "新闻窗口未覆盖，限制已写在顶层。" in top_level_only.gaps


def test_caveat_slips_not_emitted_on_true_gap_reject() -> None:
    """R-22 断言 3：无哈希 gap 的拒绝路径不产生搬运计数，拒绝语义不变。"""

    frame = _frame()
    context = _context_with_evidence_boundary(frame)
    with pytest.raises(ValueError, match="required output lacks evidence") as caught:
        validate_episode_finish(
            {
                "status": "completed",
                "draft": "基准判断：偏强震荡。证据边界：尚未取得。",
                "gaps": ["没有查到证据边界所需数据。"],
                "bindings": [
                    {
                        "output_id": "direct_assessment",
                        "evidence_hashes": ["market-hash"],
                        "gap": "",
                    },
                    {
                        "output_id": "evidence_boundary",
                        "evidence_hashes": [],
                        "gap": "没有查到证据边界所需数据。",
                    },
                ],
            },
            context=context,
            evidence=_evidence(),
        )
    assert not isinstance(caught.value, EpisodeFinish)
    assert not hasattr(caught.value, "caveat_slips")


def test_r001_fixture_b5_all_slot_slip() -> None:
    """R-001 跨组夹具：B5 ``run_20260814_022902_659281`` 全格滑档 15/18。"""

    frame = _frame()
    context = _qa_context(frame, "direct_answer", "evidence_boundary")
    hashes = [f"b5-h{index:02d}" for index in range(18)]
    evidence = _hex_evidence(*hashes)
    finish = validate_episode_finish(
        {
            "status": "partial",
            "draft": "直接回答：该指标按公开口径解释。证据边界：同日盘面可核验。",
            "gaps": [],
            "bindings": [
                _slip_binding("direct_answer", hashes[:15], "附带限制：新闻窗口未对齐。"),
                _slip_binding("evidence_boundary", hashes, "附带限制：缺少同日新闻。"),
            ],
        },
        context=context,
        evidence=evidence,
    )
    assert finish.caveat_slips == 2
    assert all(not item.gap for item in finish.bindings)
    verified = verify_episode_outcome(
        context.contract,
        AgentOutcome(
            task_frame_hash=context.contract.task_frame_hash,
            status="partial",
            draft=finish.draft,
            evidence=evidence,
            traces=(),
            gaps=finish.gaps,
            stop_reason="repair_model_stop",
            events=(
                EpisodeEvent(
                    1, "task", {"task_frame_hash": context.contract.task_frame_hash}
                ),
            ),
            bindings=finish.bindings,
            usage=AgentUsage(llm_calls=1, tool_calls=1),
        ),
    )
    assert {item.status for item in verified.completion.outputs} == {"fulfilled"}


def test_r001_fixture_b7_mixed_true_gap_still_missing() -> None:
    """R-001 核心夹具：B7 ``run_20260814_023030_100048`` 混合形。

    ``direct_answer`` 0 hash 真缺口必须仍不满足；``evidence_boundary`` 13 hashes
    搬运后 fulfilled。证明修复没有放宽真缺口。
    """

    frame = _frame()
    context = _qa_context(frame, "direct_answer", "evidence_boundary")
    hashes = [f"b7-h{index:02d}" for index in range(13)]
    evidence = _hex_evidence(*hashes)
    finish = validate_episode_finish(
        {
            "status": "partial",
            "draft": "直接回答：该格仍缺可绑定证据。证据边界：同日盘面可核验。",
            "gaps": [],
            "bindings": [
                _slip_binding("direct_answer", [], "没有查到可直接回答的证据。"),
                _slip_binding(
                    "evidence_boundary",
                    hashes,
                    "附带限制：新闻窗口未覆盖。",
                ),
            ],
        },
        context=context,
        evidence=evidence,
    )
    assert finish.caveat_slips == 1
    by_id = {item.output_id: item for item in finish.bindings}
    assert by_id["direct_answer"].gap
    assert not by_id["direct_answer"].evidence_hashes
    assert by_id["evidence_boundary"].gap == ""
    assert by_id["evidence_boundary"].evidence_hashes == tuple(hashes)

    verified = verify_episode_outcome(
        context.contract,
        AgentOutcome(
            task_frame_hash=context.contract.task_frame_hash,
            status="partial",
            draft=finish.draft,
            evidence=evidence,
            traces=(),
            gaps=finish.gaps,
            stop_reason="repair_model_finish",
            events=(
                EpisodeEvent(
                    1, "task", {"task_frame_hash": context.contract.task_frame_hash}
                ),
            ),
            bindings=finish.bindings,
            usage=AgentUsage(llm_calls=1, tool_calls=1),
        ),
    )
    status_by_id = {
        item.output_id: item.status for item in verified.completion.outputs
    }
    assert status_by_id["direct_answer"] == "missing"
    assert status_by_id["evidence_boundary"] == "fulfilled"
    assert any(
        item.code == IssueCode.REQUIRED_OUTPUT_GAP and item.subject == "direct_answer"
        for item in verified.issue_items
    )


def test_r001_fixture_a6_all_slot_slip() -> None:
    """R-001 跨组夹具：A6 ``run_20260814_021218_897744`` 全格滑档 1/1。

    终态 ``repair_model_finish`` 也在射程内：搬运后两格 fulfilled。
    """

    frame = _frame()
    context = _qa_context(frame, "direct_answer", "evidence_boundary")
    evidence = _hex_evidence("a6-h00")
    finish = validate_episode_finish(
        {
            "status": "partial",
            "draft": "直接回答：该指标按公开口径解释。证据边界：同日盘面可核验。",
            "gaps": [],
            "bindings": [
                _slip_binding("direct_answer", ["a6-h00"], "附带限制：样本偏少。"),
                _slip_binding("evidence_boundary", ["a6-h00"], "附带限制：缺新闻。"),
            ],
        },
        context=context,
        evidence=evidence,
    )
    assert finish.caveat_slips == 2
    assert all(not item.gap for item in finish.bindings)
    verified = verify_episode_outcome(
        context.contract,
        AgentOutcome(
            task_frame_hash=context.contract.task_frame_hash,
            status="partial",
            draft=finish.draft,
            evidence=evidence,
            traces=(),
            gaps=finish.gaps,
            stop_reason="repair_model_finish",
            events=(
                EpisodeEvent(
                    1, "task", {"task_frame_hash": context.contract.task_frame_hash}
                ),
            ),
            bindings=finish.bindings,
            usage=AgentUsage(llm_calls=1, tool_calls=1),
        ),
    )
    assert {item.status for item in verified.completion.outputs} == {"fulfilled"}


def test_evidence_ordinals_resolve_and_unknown_ordinal_rejects() -> None:
    """E1/E2 解析回 hash；E99 越界硬拒。精确 hash 仍接受。"""

    frame = _frame()
    context = _context(frame)
    evidence = _hex_evidence("aaa111aaa111aaa1", "bbb222bbb222bbb2")
    table = evidence_ordinal_table(evidence)
    assert table == {"aaa111aaa111aaa1": "E1", "bbb222bbb222bbb2": "E2"}
    assert resolve_evidence_refs(["E1", "e2"], evidence) == (
        "aaa111aaa111aaa1",
        "bbb222bbb222bbb2",
    )
    assert resolve_evidence_refs(["aaa111aaa111aaa1"], evidence) == (
        "aaa111aaa111aaa1",
    )
    with pytest.raises(EpisodeFinishRejection) as err:
        resolve_evidence_refs(["E99"], evidence)
    assert err.value.code == "unknown_evidence_ref"

    finish = validate_episode_finish(
        {
            "status": "completed",
            "draft": "当前更接近条件化修复。",
            "gaps": [],
            "bindings": [
                {
                    "output_id": "direct_assessment",
                    "evidence_hashes": ["E1"],
                    "gap": "",
                }
            ],
        },
        context=context,
        evidence=evidence,
    )
    assert finish.bindings[0].evidence_hashes == ("aaa111aaa111aaa1",)


def test_hash_transcription_specimens_stay_rejected() -> None:
    """B1/B7 四个誊抄标本：换位/插入/删除/拼接，全部 fail-closed，不做模糊纠正。"""

    frame = _frame()
    context = _context(frame)
    real_b1_a = "3b0893e5a338d58f"
    real_b1_b = "8b9fcfe85c43d0d0"
    written_transpose = "3b0895e3a338d58f"
    written_concat = "8b9fcfe85a338d58f"
    real_b7_insert = "20eea1861410bd4d"
    written_insert = "20eea1861410bd4d5"
    real_b7_delete = "e82eaa545eafa11a"
    written_delete = "e82eaa545eafa11"

    def _reject_code(*hashes: str, known: tuple[str, ...]) -> str:
        with pytest.raises(EpisodeFinishRejection) as err:
            validate_episode_finish(
                _finish_with_hashes(*hashes),
                context=context,
                evidence=_hex_evidence(*known),
            )
        return err.value.code

    assert (
        _reject_code(written_transpose, known=(real_b1_a, real_b1_b)) == "forged_hash"
    )
    with pytest.raises(EpisodeFinishRejection) as concat_err:
        validate_episode_finish(
            _finish_with_hashes(written_concat),
            context=context,
            evidence=_hex_evidence(real_b1_a, real_b1_b),
        )
    assert concat_err.value.code == "forged_hash"
    assert (
        _reject_code(written_insert, known=(real_b7_insert, real_b7_delete))
        == "forged_hash"
    )
    assert (
        _reject_code(written_delete, known=(real_b7_insert, real_b7_delete))
        == "truncated_hash"
    )
    assert (
        _reject_code(
            written_insert,
            written_delete,
            known=(real_b7_insert, real_b7_delete),
        )
        == "forged_hash"
    )


def test_strip_hashes_for_model_keeps_ordinals_only() -> None:
    facing = strip_hashes_for_model(
        {
            "evidence": [
                {
                    "title": "t",
                    "content_hash": "aaa111aaa111aaa1",
                    "evidence_id": "E1",
                }
            ],
            "evidence_hashes": ["aaa111aaa111aaa1"],
            "evidence_ids": ["E1"],
        }
    )
    assert facing["evidence_ids"] == ["E1"]
    assert "evidence_hashes" not in facing
    assert "content_hash" not in facing["evidence"][0]
    assert facing["evidence"][0]["evidence_id"] == "E1"


def test_cited_evidence_ordinals_extracts_prose_refs_in_order() -> None:
    # R-20260821-06：正文 E 引用是答案对依赖的显式声明。识别语法与
    # _EVIDENCE_ORDINAL_RE 同一套（E1..E999、无前导零），首现顺序去重。
    assert cited_evidence_ordinals("结论（E3）成立；E1 与 e12 支持，E3 重复。") == (
        "E3",
        "E1",
        "E12",
    )


def test_cited_evidence_ordinals_rejects_lookalike_tokens() -> None:
    # 左界排除字母数字：PE10 是估值倍数、1.5E8 是科学计数、CE4 是认证名，
    # 都不是证据引用。右界排除续位数字：E41 不得拆成 E4。
    assert cited_evidence_ordinals("PE10 高估；市值 1.5E8；CE4 认证；E41 有效。") == (
        "E41",
    )
    assert cited_evidence_ordinals("") == ()
    assert cited_evidence_ordinals("E0 与 E1000 越格式") == ()


def test_finish_rejection_fields_present_when_absent() -> None:
    empty = finish_rejection_fields()
    assert empty["rejection_code"] == ABSENT_REJECTION_CODE
    assert empty["rejection_reason"] == ""
    filled = finish_rejection_fields(
        EpisodeFinishRejection("forged_hash", "binding contains unknown evidence hash")
    )
    assert filled["rejection_code"] == "forged_hash"
    assert "unknown evidence hash" in filled["rejection_reason"]
