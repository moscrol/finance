from __future__ import annotations

import dataclasses
import json

import pytest

from intelligence.services.agent_research import AgentEvidence, AgentToolContext
from intelligence.services.agent_runtime import OutputEvidenceBinding
from intelligence.services.episode_protocol import (
    EpisodeFinish,
    build_episode_input,
    build_episode_instructions,
    finish_json_schema,
    validate_episode_finish,
)
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
    task_input = json.loads(build_episode_input(frame, context))

    assert frame.task_frame_hash in instructions
    assert "market_data" in instructions
    assert "不得在答案中暴露内部工具名、provider 或哈希" in instructions
    assert task_input["task_frame"]["task_frame_hash"] == frame.task_frame_hash
    assert task_input["research_contract"]["task_frame_hash"] == (
        frame.task_frame_hash
    )
    assert task_input["latest_data_date"] == "2026-07-24"
    assert task_input["information_cutoff"] == (
        context.information_cutoff.to_dict()
    )
    assert "information_cutoff" in task_input["date_rule"]
    assert "基准判断是短周期修复" in task_input["conversation_context"]
    assert task_input["conversation_context_rule"] == (
        "历史对话仅用于消解指代和延续用户目标，不得当作事实证据"
    )


def _static_contract_text() -> str:
    """Return only the hard-coded contract literals of the instruction builder.

    Reads the source with ``ast`` instead of calling the builder: the returned
    string also carries a task hash, the valuation rule and the registry block,
    all of which change per task and would drown out the one thing this locks.
    Plain ``Constant`` strings are the contract; ``JoinedStr`` (f-string) parts
    are the dynamic tail and are skipped.
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
        and not node.value.startswith("Build one outcome-first")
    )


# 重排后的静态契约文本，扣掉 `【…】` 分组标题与全部空白后的指纹。
#
# 这条测试存在的唯一理由：`2026-08-07` 那次把 1,501 字符的单段契约拆成 26 行并
# 插入 6 个分组标题，前提是**一个字不改**——只有措辞与顺序都没动，后续观察到的
# 行为差异才能归因于结构。指纹是这个前提唯一的可检验形式。
#
# 它变红意味着有人动了约束的措辞或顺序。那可能是对的，但必须是**显式**的：
# 请连同这里的期望值一起更新，并在 commit 说明改了哪一条、为什么。别为了让它
# 变绿而回退重排。
_CONTRACT_FINGERPRINT = (
    "f953cb34172874f948476283d68b2c725bfcef80128881c2e35e901a758323ad"
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
    """有证据支撑的附带 gap 不得作废整份答案。

    2026-08-10 live 实测：``evidence_boundary`` 带 2 条证据哈希、顶层 gaps 已写同一
    条限制，模型又在 ``binding.gap`` 里抄了一份。契约（``episode_protocol`` 第
    204-206 行）确实要求这种限制只写顶层，所以模型是**格式滑档**——但旧判定把它
    等同于「必需输出缺失」，��是 508 字符、5 格全绑证据的答案连续两轮整份作废，
    收据里只剩 ``draft_chars=0``。

    同一个事实在 ``episode_verifier.py:115`` 只降级为 partial 且保留草稿。这里锁住
    更宽松的那一侧：答案保住，gap 原样留在 binding 里继续供下游降级。
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
    # 留痕不可省：下游 verifier 靠这条 gap 把该格判 missing 并降级为 partial。
    boundary = next(
        item for item in finish.bindings if item.output_id == "evidence_boundary"
    )
    assert boundary.gap == "缺少同一时间窗口的新闻证据。"


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
