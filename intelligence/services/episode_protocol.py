"""Shared prompt and finish contract for provider-neutral research runtimes."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
import json
import re
from typing import cast

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    EpisodeStatus,
    OutputEvidenceBinding,
)
from intelligence.services.episode_output_substance import (
    required_output_evidence_floor,
    required_outputs_without_substance,
)
from intelligence.services.research_contract import ResearchRunContext
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.task_frame import TaskFrame


_FINISH_STATUSES = frozenset({"completed", "partial"})
# A few OpenAI-compatible adapters append one unmatched quote after an
# otherwise exact fenced payload. Accept only that observed one-character
# suffix; arbitrary prose before/after the fence remains invalid.
_FINAL_JSON_RE = re.compile(
    r"```(?:json)?\s*(\{.*\})\s*```[ \t]*\"?",
    re.S | re.I,
)
_FINAL_JSON_BLOCK_RE = re.compile(
    r"```(?:json)?\s*(.*?)\s*```",
    re.S | re.I,
)


@dataclass(frozen=True)
class EpisodeFinish:
    status: EpisodeStatus
    draft: str
    gaps: tuple[str, ...]
    bindings: tuple[OutputEvidenceBinding, ...]


def finish_json_schema() -> dict[str, object]:
    """Return the closed provider-facing schema for a terminal episode."""

    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "status": {
                "type": "string",
                "enum": ["completed", "partial"],
            },
            "draft": {"type": "string"},
            "gaps": {
                "type": "array",
                "items": {"type": "string"},
            },
            "bindings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "output_id": {"type": "string"},
                        "evidence_hashes": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "basis": {
                            "type": "string",
                            "enum": [
                                "evidence",
                                "user_premise",
                                "model_reasoning",
                            ],
                        },
                        "gap": {"type": "string"},
                    },
                    "required": [
                        "output_id",
                        "evidence_hashes",
                        "basis",
                        "gap",
                    ],
                },
            },
        },
        "required": ["status", "draft", "gaps", "bindings"],
    }


def build_episode_instructions(
    task_frame: TaskFrame,
    context: ResearchRunContext,
    registry: ResearchToolRegistry,
) -> str:
    """Build one outcome-first instruction contract shared by all runtimes."""

    valuation_rule = (
        "估值题专用完成规则：scenario_range 必须给出保守、中性、乐观"
        "三种条件化情景中的实际估值倍数或市值区间，并写清方法/假设；不能把"
        "当前单一 PB、标题或空表当作情景区间。证据不足时应返回 partial，"
        "并在该 binding.gap 明确说明。financial_business_anchor 的 binding "
        "必须至少包含一个 financial_data 证据哈希；KB、公告或业务材料可以作为"
        "补充证据，但不能替代逐季财务硬锚。若 D5 已给出 PB 情景计算锚，优先"
        "逐字复用其保守/中性/乐观数值，模型只补条件与风险，不得另造倍数。"
        "情景条件优先只用 financial_data 已观察到的营收、净利、毛利率或净利率"
        "改善/恶化；没有直接 evidence 的项目、产能、客户和业务催化不得写入。"
        if task_frame.question_type == "valuation_estimate"
        else ""
    )
    # prior_recall 槽位专用规则：只在该格出现于契约时注入。
    #
    # 这条规则是**陈述性**的，不指定调用顺序。初版写的是「研究开始时必须优先调用
    # memory_lookup」，实测无效：`run_20260808_102708` 里槽位、授权、这行强制指令
    # 三样都在，模型仍在第一轮把 7 次工具预算全投给市场侧检索。
    #
    # 真正的缺口不在措辞而在契约结构——那时 prior_recall 的 evidence_types 是全量
    # 能力列表，模型读不出「哪个工具能填这格」。修法落在 `episode_factory` 把该格
    # 的 evidence_types 收窄成 `memory_lookup`；这里只需说明该格接受什么，让模型
    # 自主推理出要调用它。强制顺序会牺牲 agentic 的工具选择权，且已被证伪。
    prior_recall_rule = (
        "本任务包含 prior_recall 槽位（grounding_mode=user_premise）：该格只接受 "
        "memory_lookup 召回的用户历史判断与纠偏原则，市场侧工具返回的当前世界事实"
        "无法填充它；绑定时 basis 用 user_premise。若 memory_lookup 返回空命中，"
        "在该 binding.gap 注明「用户记忆无相关命中」。"
        if any(
            o.output_id == "prior_recall"
            for o in context.contract.required_outputs
        )
        else ""
    )
    # 只改形状，一个字不改：本函数的静态契约文本去掉全部空白后，sha256 与重排前
    # 逐字节相同（`test_episode_protocol` 里那条指纹测试锁住这一点）。所以下面新增
    # 的只有换行和六个分组标题，**约束的措辞与前后顺序都没动**。
    #
    # 重排前是 1,501 字符里一个换行都没有的连续段，24 条约束平铺：模型要回答
    # 「哪几条是关于证据绑定的」，只能在一条长串里线性扫。同类约束原本也散落在
    # 不同位置（证据绑定出现在开头、中段、末尾三处）。分组后每条独立成行、同类
    # 相邻，但因为顺序不能动（动了指纹就变），标题只插在原顺序本来就有的边界上。
    #
    # 为什么不顺手改措辞：这轮唯一想验证的是「结构是否影响模型表现」。同时改字，
    # 后续行为差异就分不清来自哪一边——这跟工具观察预算那轮坚持纯变换是同一条纪律。
    return (
        "你是连续运行的金融研究 Agent。始终回答最初的不可变任务。\n"
        "\n"
        "【任务与计划】\n"
        "第一轮可以先只输出一个 kind=PLAN 的 JSON 对象，字段为 task_summary、"
        "answer_elements、hypotheses、evidence_needs、candidate_actions、open_gaps、"
        "requested_mode(quick|deep)、revision，以及可选 branch_goals（最多 3 个可分离"
        "的只读研究目标）；也可以在任务简单时直接调用已授权工具。\n"
        "PLAN 只是可观察研究意图，不能授权工具、预算、证据或完成状态；候选动作不等于"
        "调用许可。branch_goals 只是申请，只有运行时批准 deep 后才能执行；它不能指定"
        "权限、预算或继续派生分支。计划修订必须保持原任务且 revision 严格递增。\n"
        "\n"
        "【工具与观察】\n"
        "每次看到工具原始观察后，自主决定继续查、改写查询或停止。只能调用本轮提供的"
        "只读工具，不能臆造工具结果。\n"
        "事实判断必须绑定工具返回的 evidence_hashes；"
        "缺数据要写 gap。\n"
        "观察事实与分析判断分开；不得编造精确数值阈值。\n"
        "\n"
        "【表达边界】\n"
        "不得在"
        "答案中暴露内部工具名、provider 或哈希，要改写成自然语言过程说明。\n"
        "数据中"
        "“阶段第N天”只是数据提供方的阶段标签，不等于连续N个上涨日。\n"
        "用户要求"
        "预测、空间、持续时间或估值时，必须给出一个明确标注的基准判断，并说明"
        "不确定性。\n"
        "\n"
        "【证据绑定】\n"
        "draft 中每个精确数字事实都必须由相应 required output 的"
        "binding 包含其直接 evidence_hash；不能绑定就省略该数字。\n"
        "公开网页中的"
        "预测或观点只能明确标作外部观点，不能冒充当前事实或历史概率。\n"
        "对于原因归因题，news_search 未返回同一时间窗口证据时，不得用普通 "
        "web_search 摘要补成已核验因果；应保留已核验盘面，把原因写为 gap "
        "或明确标注为外部观点候选。\n"
        "每条被正文使用的观察事实都必须把直接证据哈希加入对应 output binding；"
        "不得用同一次工具返回的相邻证据代替，也不得正文使用后漏绑。\n"
        "\n"
        "【何时停止】\n"
        "必需输出"
        "已有足够直接证据时应停止研究，不得为了耗尽步数调用非必需工具。\n"
        "不要套固定标题、行数或段落模板。终止时不要调用工具，"
        "为保证结构化终止完整，draft 控制在 1000 汉字以内，优先保留直接"
        "判断、决定性依据、继续条件和失效条件；这不要求固定标题或段数。\n"
        "\n"
        "【终局 JSON】\n"
        "只输出一个 JSON 对象：\n"
        '{"status":"completed|partial","draft":"自然语言回答",'
        '"gaps":["..."],"bindings":[{"output_id":"...",'
        '"evidence_hashes":["..."],"basis":"evidence|user_premise|model_reasoning",'
        '"gap":""}]}。\n'
        "每个 binding 的 basis 必须与对应 required output 的 grounding_mode 一致；"
        "evidence 表示当前世界事实，user_premise 表示只评估用户给出的条件，"
        "model_reasoning 表示方法论或推理框架，不得伪造证据哈希。\n"
        "binding.gap 只在该 required output 无法回答时填写；"
        "若 output 已由 evidence_hashes 支持并完成，binding.gap 必须为空，"
        "限制条件写入顶层 gaps 或 draft。\n"
        "completed 必须覆盖所有 required outputs；partial 必须明确缺口。\n"
        f"{prior_recall_rule}\n"
        f"{valuation_rule}\n"
        f"任务哈希：{task_frame.task_frame_hash}\n"
        f"可用工具：\n{registry.prompt_block(context.contract.allowed_capabilities)}"
    )


def build_episode_input(
    task_frame: TaskFrame,
    context: ResearchRunContext,
) -> str:
    """Serialize the immutable task and deterministic execution contract."""

    return json.dumps(
        {
            "task_frame": task_frame.to_dict(),
            "research_contract": context.contract.to_dict(),
            "today": context.today,
            "latest_data_date": context.latest_data_date,
            "information_cutoff": context.information_cutoff.to_dict(),
            "conversation_context": context.conversation_context,
            "conversation_context_rule": (
                "历史对话仅用于消解指代和延续用户目标，不得当作事实证据"
            ),
            "date_rule": (
                "today 不是行情日期；information_cutoff 是所有查询与引用事实的"
                "不可变日期上限；市场事实还须服从 latest_data_date 和证据日期"
            ),
        },
        ensure_ascii=False,
    )



class RejectionKind(str, Enum):
    """拒收的**类别**，决定上游该做什么——与具体病因（``code``）分开。

    分层出处：马书 ch06b 的三层漏斗（25+ 具体类型 → 4 类别 → 1 布尔），
    「诊断信息可以非常详细，而决策逻辑保持简洁，两个关注点完全解耦」。
    本文件此前是这个结构的反面：15 个病因共用一个 ``ValueError``，
    于是「格式滑一档」和「伪造证据哈希」得到同一个动作，收据里也留不下
    可归类的字段——那正是 ``synthesis_health`` 读出 59% 「口径未知」的上游。
    """

    FORMAT = "format"
    """模型把结构写错了。官方口径：作为 tool result **回灌**给模型让它换个写法，
    不是丢弃整份输出。"""

    SUBSTANCE = "substance"
    """结构合法但内容不足。harness-books 9.7：恢复的目标是继续工作，
    应降级并**保留草稿**，别把用户困在失败态里。"""

    INTEGRITY = "integrity"
    """证据体系的地基被破坏（伪造哈希、越界输出）。**硬拒，不可恢复。**"""


class EpisodeFinishRejection(ValueError):
    """带稳定分类的拒收。

    继承 ``ValueError`` 是刻意的：上游所有 ``except ValueError`` 原样继续工作，
    因此本次改动**不改变任何行为**，只让病因变得可归类。决策分流是下一个增量——
    按 ch06b 的顺序，classify → categorize → decide，没有命名就无法划分可恢复集合。
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.kind = REJECTION_KINDS[code]


# 病因 → 类别。**必须穷尽**：``test_every_rejection_code_is_classified``
# 钉住「每个 raise 出去的 code 都在这张表里」，对应 book1 ch06 那条不变量
# ``withheld_error ∈ {...}``——可恢复集合必须是明确枚举，不是「其余都算」。
REJECTION_KINDS: dict[str, RejectionKind] = {
    # 结构写错 → 回灌重写
    "not_json_object": RejectionKind.FORMAT,
    "bad_status": RejectionKind.FORMAT,
    "draft_not_string": RejectionKind.FORMAT,
    "bad_gaps": RejectionKind.FORMAT,
    "bindings_not_list": RejectionKind.FORMAT,
    "binding_not_object": RejectionKind.FORMAT,
    "hashes_not_list": RejectionKind.FORMAT,
    "basis_mismatch": RejectionKind.FORMAT,
    "duplicate_binding": RejectionKind.FORMAT,
    # 内容不足 → 降级保留草稿
    "empty_draft": RejectionKind.SUBSTANCE,
    "evidence_type_floor": RejectionKind.SUBSTANCE,
    "no_substantive_answer": RejectionKind.SUBSTANCE,
    "missing_evidence": RejectionKind.SUBSTANCE,
    # 地基破坏 → 硬拒
    "unknown_output": RejectionKind.INTEGRITY,
    "forged_hash": RejectionKind.INTEGRITY,
}


@dataclass(frozen=True)
class RejectionResponse:
    """一个拒收类别对应的**处置**——「诊断/决策解耦」里决策那一半。

    上一个增量只做了分类（code → kind），三类在运行时仍走同一条路。本结构把
    「怎么处置」也变成数据，于是分流规则可被单条测试钉住，而不是散在
    ``agent_episode`` 的 except 分支里靠读代码推断。
    """

    reinject: bool
    """是否把错误回灌给模型让它重写（族 A/C 一致：拒绝理由当工具结果进轨迹）。"""

    allow_recovery: bool
    """是否允许走 ``_recover_finalization``（另起一次收尾调用）。"""

    stop_reason: str
    """停下时记进收据的原因。INTEGRITY 单独命名，否则它在统计里和格式错混为一谈。"""


# 类别 → 处置。**必须穷尽**，理由同 ``REJECTION_KINDS``：
# book1 ch06 那条 ``withheld_error ∈ {...}`` 要求可恢复集合是明确枚举。
#
# INTEGRITY 不回灌、不恢复，是本表唯一与旧行为不同的一格：伪造证据哈希
# （``forged_hash``）此前和「JSON 少个括号」一样能拿到一次重写机会。给一个
# 编造了证据的模型第二次机会，等于把地基问题当格式问题处理——而回灌的内容
# 就是「你编的哈希不在白名单里」，这恰好是在告诉它哪个哈希需要换。
REJECTION_RESPONSES: dict[RejectionKind, RejectionResponse] = {
    RejectionKind.FORMAT: RejectionResponse(
        reinject=True, allow_recovery=True, stop_reason="invalid_model_finish"
    ),
    RejectionKind.SUBSTANCE: RejectionResponse(
        reinject=True, allow_recovery=True, stop_reason="invalid_model_finish"
    ),
    RejectionKind.INTEGRITY: RejectionResponse(
        reinject=False, allow_recovery=False, stop_reason="integrity_violation"
    ),
}


def rejection_response(error: BaseException) -> RejectionResponse:
    """把一个异常映射成处置。

    非 ``EpisodeFinishRejection`` 的 ``ValueError``（来自本函数下游的第三方代码）
    按 **FORMAT** 处理，即保持既有行为。刻意不按 INTEGRITY 兜底：未分类的东西
    应当沿用旧路径，不该因为「不认识」就悄悄变得更严——那会让一次分类遗漏
    表现成线上行为突变，且很难归因。
    """

    kind = getattr(error, "kind", None)
    if isinstance(kind, RejectionKind):
        return REJECTION_RESPONSES[kind]
    return REJECTION_RESPONSES[RejectionKind.FORMAT]


def _reject(code: str, message: str) -> EpisodeFinishRejection:
    return EpisodeFinishRejection(code, message)


def validate_episode_finish(
    value: object,
    *,
    context: ResearchRunContext,
    evidence: tuple[AgentEvidence, ...],
) -> EpisodeFinish:
    """Validate one provider result against the shared evidence contract."""

    evidence_by_hash = {
        item.content_hash: item for item in evidence if item.content_hash
    }
    evidence_hashes = set(evidence_by_hash)
    decoded = _finish_object(value)
    if decoded is None:
        raise _reject("not_json_object", "finish must be one JSON object")
    status = decoded.get("status")
    if status not in _FINISH_STATUSES:
        raise _reject("bad_status", "finish status must be completed or partial")
    draft = decoded.get("draft")
    if not isinstance(draft, str):
        raise _reject("draft_not_string", "finish draft must be a string")
    draft = _normalize_natural_language_layout(draft)
    if status == "completed" and not draft.strip():
        raise _reject("empty_draft", "completed finish draft must be non-empty")
    raw_gaps = decoded.get("gaps", [])
    if not isinstance(raw_gaps, list) or any(
        not isinstance(item, str) for item in raw_gaps
    ):
        raise _reject("bad_gaps", "finish gaps must be a string list")
    gaps = tuple(dict.fromkeys(item.strip() for item in raw_gaps if item.strip()))
    raw_bindings = decoded.get("bindings")
    if not isinstance(raw_bindings, list):
        raise _reject("bindings_not_list", "finish bindings must be a list")
    bindings: list[OutputEvidenceBinding] = []
    allowed_outputs = {item.output_id for item in context.contract.required_outputs}
    for raw in raw_bindings:
        if not isinstance(raw, Mapping):
            raise _reject("binding_not_object", "each finish binding must be an object")
        raw_hashes = raw.get("evidence_hashes", [])
        if not isinstance(raw_hashes, list):
            raise _reject("hashes_not_list", "binding evidence_hashes must be a list")
        binding = OutputEvidenceBinding(
            output_id=str(raw.get("output_id") or ""),
            evidence_hashes=tuple(raw_hashes),
            gap=str(raw.get("gap") or ""),
            basis=str(raw.get("basis") or "evidence"),
        )
        if binding.output_id not in allowed_outputs:
            raise _reject(
                "unknown_output",
                f"unknown required output: {binding.output_id}",
            )
        required = next(
            item
            for item in context.contract.required_outputs
            if item.output_id == binding.output_id
        )
        if binding.basis != required.grounding_mode:
            raise _reject(
                "basis_mismatch",
                f"grounding basis mismatch for {binding.output_id}: "
                f"expected {required.grounding_mode}, got {binding.basis}",
            )
        unknown = set(binding.evidence_hashes) - evidence_hashes
        if unknown:
            raise _reject(
                "forged_hash",
                "binding contains unknown evidence hash: "
                + ",".join(sorted(unknown)),
            )
        bindings.append(binding)

    if len({item.output_id for item in bindings}) != len(bindings):
        raise _reject("duplicate_binding", "duplicate output binding")
    for binding in bindings:
        bound_tools = tuple(
            evidence_by_hash[evidence_hash].tool
            for evidence_hash in binding.evidence_hashes
        )
        missing_floor = tuple(
            tool
            for tool in required_output_evidence_floor(binding.output_id)
            if tool not in bound_tools
        )
        if binding.evidence_hashes and missing_floor:
            raise _reject(
                "evidence_type_floor",
                f"required output lacks evidence type {binding.output_id}: "
                + ",".join(missing_floor),
            )

    binding_map = {item.output_id: item for item in bindings}
    empty_outputs = tuple(
        output_id
        for output_id in required_outputs_without_substance(
            context.contract,
            draft,
        )
        if output_id in binding_map and not binding_map[output_id].gap
    )
    if empty_outputs:
        raise _reject(
            "no_substantive_answer",
            "required output lacks substantive answer: "
            + ",".join(empty_outputs),
        )
    # ``binding.gap`` 与 ``evidence_hashes`` 同时非空，是模型的**格式滑档**，
    # 不是必需输出缺失：该 output 已有直接证据支撑，gap 里写的是附带限制条件。
    # 本函数上游的契约（第 204-206 行）要求这种限制写进顶层 ``gaps`` 或 ``draft``，
    # 而 2026-08-10 的 live 实测里模型**三处都写了**——``evidence_boundary``
    # 带 2 条证据哈希、顶层 gaps 有该条、binding.gap 又抄了一份。
    #
    # 把这种滑档判成「缺失」，代价与过失不成比例：整份 FINAL_JSON 作废，
    # 连同已绑好的证据一起丢，最终 ``draft_chars=0``（实测 508 字符答案被丢弃两轮）。
    # 而同一个事实在 ``episode_verifier.py:115`` 只降级为 partial 且**保留草稿**。
    # 两条路径对同一输入严厉度不同，更严厉的那条丢掉的恰是用户唯一能看到的东西。
    #
    # 这里只放宽「有证据支撑时的附带 gap」这一种组合：gap 而**无**证据哈希，
    # 仍然是缺口，仍然判缺失。放宽的边界就是「有没有直接证据」，不是「有没有写 gap」。
    if status == "completed":
        missing = []
        for required in context.contract.required_outputs:
            if not required.required:
                continue
            binding = binding_map.get(required.output_id)
            if binding is None:
                missing.append(required.output_id)
                continue
            if binding.gap and not binding.evidence_hashes:
                missing.append(required.output_id)
                continue
            if required.grounding_mode == "evidence" and not binding.evidence_hashes:
                missing.append(required.output_id)
        if missing:
            raise _reject(
                "missing_evidence",
                "required output lacks evidence: " + ",".join(missing),
            )
    # 放宽不等于把痕迹放掉：被容忍的 gap 原样留在 ``binding.gap`` 里，
    # ``episode_verifier.py:115`` 读到它照旧把这一格判 missing 并降级为 partial。
    # 于是「有答案」与「这一格有保留意见」两件事都成立——这正是本轮要的差别：
    # 失败留痕，但不再连答案一起销毁。
    return EpisodeFinish(
        status=cast(EpisodeStatus, status),
        draft=draft,
        gaps=gaps,
        bindings=tuple(bindings),
    )


def expand_episode_snapshot_bindings(
    *,
    bindings: tuple[OutputEvidenceBinding, ...],
    evidence: tuple[AgentEvidence, ...],
    registry: ResearchToolRegistry,
) -> tuple[OutputEvidenceBinding, ...]:
    """Expand a selected turn-scoped snapshot into one atomic private binding."""

    tool_by_hash = {
        item.content_hash: item.tool for item in evidence if item.content_hash
    }
    snapshot_hashes: dict[str, list[str]] = {}
    for item in evidence:
        if not item.content_hash:
            continue
        try:
            spec = registry.resolve(item.tool)
        except ValueError:
            continue
        if spec.query_scope == "episode":
            snapshot_hashes.setdefault(item.tool, []).append(item.content_hash)

    expanded: list[OutputEvidenceBinding] = []
    for binding in bindings:
        selected_snapshot_tools = {
            tool_by_hash[evidence_hash]
            for evidence_hash in binding.evidence_hashes
            if evidence_hash in tool_by_hash
            and tool_by_hash[evidence_hash] in snapshot_hashes
        }
        hashes = list(binding.evidence_hashes)
        for tool, tool_hashes in snapshot_hashes.items():
            if tool in selected_snapshot_tools:
                hashes.extend(tool_hashes)
        expanded.append(
            OutputEvidenceBinding(
                output_id=binding.output_id,
                evidence_hashes=tuple(dict.fromkeys(hashes)),
                gap=binding.gap,
                basis=binding.basis,
            )
        )
    return tuple(expanded)


def _finish_object(value: object) -> dict[str, object] | None:
    if isinstance(value, str):
        return _parse_json_object(value)
    if not isinstance(value, Mapping) or any(
        not isinstance(key, str) for key in value
    ):
        return None
    return dict(value)


def _parse_json_object(content: str) -> dict[str, object] | None:
    raw = str(content or "").strip()
    fenced = _FINAL_JSON_RE.fullmatch(raw)
    if fenced is not None:
        value = _decode_finish_json(fenced.group(1))
        if value is not None:
            return value
    for block in reversed(tuple(_FINAL_JSON_BLOCK_RE.finditer(raw))):
        value = _decode_finish_json(block.group(1))
        if value is not None and _looks_like_finish_envelope(value):
            return value
    return _decode_finish_json(raw)


def _decode_finish_json(text: str) -> dict[str, object] | None:
    candidate = str(text or "").strip().removesuffix('"').rstrip()
    if not candidate.startswith("{") or not candidate.endswith("}"):
        return None
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        value = _recover_finish_with_raw_draft(candidate)
    return value if isinstance(value, dict) else None


def _looks_like_finish_envelope(value: dict[str, object]) -> bool:
    return {"status", "draft", "gaps", "bindings"}.issubset(value)


def _normalize_natural_language_layout(value: str) -> str:
    """Decode double-escaped newline literals in natural-language drafts."""

    return value.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")


def _recover_finish_with_raw_draft(text: str) -> dict[str, object] | None:
    """Recover the fixed envelope when a provider leaves draft prose raw."""

    prefix = re.match(
        r'^\{\s*"status"\s*:\s*"(completed|partial)"\s*,\s*'
        r'"draft"\s*:\s*"',
        text,
    )
    if prefix is None:
        return None
    separators = list(re.finditer(r'"\s*,\s*(?="gaps"\s*:)', text))
    if not separators:
        return None
    separator = separators[-1]
    if separator.start() < prefix.end():
        return None
    try:
        tail = json.loads("{" + text[separator.end() :])
    except json.JSONDecodeError:
        return None
    if not isinstance(tail, dict) or set(tail) != {"gaps", "bindings"}:
        return None
    return {
        "status": prefix.group(1),
        "draft": text[prefix.end() : separator.start()],
        "gaps": tail["gaps"],
        "bindings": tail["bindings"],
    }


__all__ = [
    "EpisodeFinish",
    "EpisodeFinishRejection",
    "RejectionKind",
    "RejectionResponse",
    "build_episode_input",
    "build_episode_instructions",
    "expand_episode_snapshot_bindings",
    "finish_json_schema",
    "rejection_response",
    "validate_episode_finish",
]
