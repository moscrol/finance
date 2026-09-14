"""Thin, immutable user semantics for the adaptive research runtime.

Besides ``UserTask`` this module owns the **input understanding** primitives
that turn one raw user message into user semantics before routing:

- ``split_user_message``: separate the question from pasted materials (report
  text, tables, URLs, quoted passages) and give each material a content-derived
  identity, so "这篇" in the next turn can bind to the same material without any
  storage.
- ``extract_user_premises``: the user's own beliefs / observations / references
  to their past judgement — premises to test, never facts.
- ``extract_method_candidates``: a described rule of thumb as
  条件 → 预期 → 适用环境 → 反例, always ``candidate_unverified`` on extraction.
- ``translate_market_feel``: 盘感 ("龙头不涨是不是退潮") into competing
  explanations plus the observables that discriminate them.
- ``resolve_nicknames``: market slang for companies (宁王 / 迪王).

All of it is deterministic and pure; ``task_frame.build_task_frame`` composes
the results into the canonical frame and ``query_understanding`` routes on the
question part only.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace, field
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from intelligence.services.task_frame import TaskFrame


RESOLUTION_SOURCES = frozenset(
    {"explicit", "inherited", "product_default", "inferred"}
)


def _trimmed_strings(values: object, *, field_name: str) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"{field_name} must contain strings")
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str):
            raise ValueError(f"{field_name} must contain strings")
        item = value.strip()
        if item and item not in normalized:
            normalized.append(item)
    return tuple(normalized)


def _freeze_json(value: object, *, path: str = "time_window") -> object:
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} must be JSON-safe")
        return value
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        return tuple(
            _freeze_json(item, path=f"{path}[]")
            for item in value
        )
    if isinstance(value, Mapping):
        frozen: dict[str, object] = {}
        for raw_key, item in value.items():
            if not isinstance(raw_key, str) or not raw_key.strip():
                raise ValueError(f"{path} must be JSON-safe")
            key = raw_key.strip()
            if key in frozen:
                raise ValueError(f"{path} contains duplicate keys")
            frozen[key] = _freeze_json(item, path=f"{path}.{key}")
        return MappingProxyType(frozen)
    raise ValueError(f"{path} must be JSON-safe")


def _thaw_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


@dataclass(frozen=True)
class ResolvedValue:
    value: str
    source: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise ValueError("resolved value must be a string")
        value = self.value.strip()
        if not value:
            raise ValueError("resolved value must be non-empty")
        if not isinstance(self.source, str):
            raise ValueError("unsupported resolution source")
        source = self.source.strip()
        if source not in RESOLUTION_SOURCES:
            raise ValueError("unsupported resolution source")
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "source", source)

    def to_dict(self) -> dict[str, str]:
        return {"value": self.value, "source": self.source}


@dataclass(frozen=True)
class UserTask:
    raw_question: str
    conversation_context: str
    subjects: tuple[ResolvedValue, ...]
    market_scope: ResolvedValue | None
    time_window: Mapping[str, object] | None
    assumptions: tuple[str, ...]
    ambiguities: tuple[str, ...]
    user_premises: tuple[str, ...]
    task_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.raw_question, str) or not self.raw_question.strip():
            raise ValueError("raw_question must be non-empty")
        if not isinstance(self.conversation_context, str):
            raise ValueError("conversation_context must be a string")
        if not isinstance(self.task_id, str) or not self.task_id.strip():
            raise ValueError("task_id must be non-empty")
        if not isinstance(self.subjects, (list, tuple)) or any(
            not isinstance(item, ResolvedValue) for item in self.subjects
        ):
            raise ValueError("subjects must contain ResolvedValue values")
        if self.market_scope is not None and not isinstance(
            self.market_scope, ResolvedValue
        ):
            raise ValueError("market_scope must be a ResolvedValue")
        if self.time_window is not None and not isinstance(
            self.time_window, Mapping
        ):
            raise ValueError("time_window must be a JSON-safe mapping")

        subjects: list[ResolvedValue] = []
        seen_subjects: set[str] = set()
        for subject in self.subjects:
            key = subject.value.casefold()
            if key in seen_subjects:
                continue
            seen_subjects.add(key)
            subjects.append(subject)

        object.__setattr__(
            self,
            "conversation_context",
            self.conversation_context.strip(),
        )
        object.__setattr__(self, "subjects", tuple(subjects))
        object.__setattr__(
            self,
            "time_window",
            (
                _freeze_json(self.time_window)
                if self.time_window is not None
                else None
            ),
        )
        object.__setattr__(
            self,
            "assumptions",
            _trimmed_strings(self.assumptions, field_name="assumptions"),
        )
        object.__setattr__(
            self,
            "ambiguities",
            _trimmed_strings(self.ambiguities, field_name="ambiguities"),
        )
        object.__setattr__(
            self,
            "user_premises",
            _trimmed_strings(self.user_premises, field_name="user_premises"),
        )
        object.__setattr__(self, "task_id", self.task_id.strip())

    def to_dict(self) -> dict[str, object]:
        return {
            "raw_question": self.raw_question,
            "conversation_context": self.conversation_context,
            "subjects": [item.to_dict() for item in self.subjects],
            "market_scope": (
                self.market_scope.to_dict()
                if self.market_scope is not None
                else None
            ),
            "time_window": (
                _thaw_json(self.time_window)
                if self.time_window is not None
                else None
            ),
            "assumptions": list(self.assumptions),
            "ambiguities": list(self.ambiguities),
            "user_premises": list(self.user_premises),
            "task_id": self.task_id,
        }

    @classmethod
    def from_task_frame(
        cls,
        frame: TaskFrame,
        context: Mapping[str, object] | str | None = None,
    ) -> UserTask:
        if context is None:
            values: Mapping[str, object] = {}
        elif isinstance(context, str):
            values = {"conversation_context": context}
        elif isinstance(context, Mapping):
            values = context
        else:
            raise ValueError("context must be a mapping or string")

        def resolution_source(field: str, default: str) -> str:
            raw = values.get(f"{field}_source", default)
            if not isinstance(raw, str):
                raise ValueError("unsupported resolution source")
            return raw

        assumptions = tuple(frame.assumptions)
        market_is_product_default = (
            frame.market_scope == "A股"
            and any("用户未明确市场范围" in item for item in assumptions)
        )
        subject_source = resolution_source("subject", "inferred")
        subjects = (
            (ResolvedValue(frame.subject, subject_source),)
            if frame.subject and frame.subject.strip()
            else ()
        )
        market_scope = (
            ResolvedValue(
                frame.market_scope,
                resolution_source(
                    "market_scope",
                    "product_default" if market_is_product_default else "inferred",
                ),
            )
            if frame.market_scope and frame.market_scope.strip()
            else None
        )
        time_window = (
            {
                "value": frame.timeframe,
                "source": resolution_source("time_window", "inferred"),
            }
            if frame.timeframe and frame.timeframe.strip()
            else None
        )
        conversation = values.get("conversation_context", "")
        if not isinstance(conversation, str):
            raise ValueError("conversation_context must be a string")
        # 调用方没给 user_premises 时取 frame 自己抽出来的用户假设；此前这一格
        # 只能由外部 context 填，生产唯一调用方（research_harness）从不填，于是
        # 「用户已有假设」在 UserTask 上永远是空的。
        raw_premises = values.get("user_premises", getattr(frame, "user_premises", ()))
        if not isinstance(raw_premises, (list, tuple)):
            raise ValueError("user_premises must contain strings")
        task_id = values.get("task_id", frame.task_frame_hash)
        if not isinstance(task_id, str):
            raise ValueError("task_id must be a string")
        return cls(
            raw_question=frame.raw_question,
            conversation_context=conversation,
            subjects=subjects,
            market_scope=market_scope,
            time_window=time_window,
            assumptions=assumptions,
            ambiguities=tuple(frame.ambiguities),
            user_premises=tuple(raw_premises),
            task_id=task_id,
        )


# --------------------------------------------------------------------------- #
# 输入理解：材料 / 假设 / 方法 / 盘感 / 代称（纯函数，无 IO）
# --------------------------------------------------------------------------- #


def _strings(values: object) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        return ()
    return tuple(
        text
        for item in values
        if isinstance(item, str) and (text := item.strip())
    )


@dataclass(frozen=True)
class MaterialRef:
    """One user-provided material with a content-derived identity.

    ``material_id`` is ``m-`` + sha1 of the whitespace-normalised text, so the
    same pasted text yields the same id in every turn and every process: the
    identity needs no store, and "这篇" can be bound by recomputing it from the
    conversation history.  The text itself is not carried here — it already
    lives in ``raw_question`` (this turn) or the conversation context (later
    turns); the ref carries what a citation needs: kind, title, headers, dates.
    """

    material_id: str
    kind: str  # pasted_text | table | url | quoted
    title: str
    char_count: int
    headers: tuple[str, ...] = ()
    dates: tuple[str, ...] = ()
    paragraphs: int = 0
    rows: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "material_id": self.material_id,
            "kind": self.kind,
            "title": self.title,
            "char_count": self.char_count,
            "headers": list(self.headers),
            "dates": list(self.dates),
            "paragraphs": self.paragraphs,
            "rows": self.rows,
        }

    @classmethod
    def from_dict(cls, value: object) -> MaterialRef | None:
        if not isinstance(value, Mapping):
            return None
        try:
            material_id = str(value["material_id"]).strip()
            kind = str(value.get("kind") or "pasted_text").strip()
            if not material_id:
                return None
            return cls(
                material_id=material_id,
                kind=kind,
                title=str(value.get("title") or "").strip(),
                char_count=int(value.get("char_count") or 0),
                headers=_strings(value.get("headers")),
                dates=_strings(value.get("dates")),
                paragraphs=int(value.get("paragraphs") or 0),
                rows=int(value.get("rows") or 0),
            )
        except (KeyError, TypeError, ValueError):
            return None


@dataclass(frozen=True)
class Hypothesis:
    """One competing explanation and the observables that would tell it apart."""

    label: str
    claim: str
    observables: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "claim": self.claim,
            "observables": list(self.observables),
        }

    @classmethod
    def from_dict(cls, value: object) -> Hypothesis | None:
        if not isinstance(value, Mapping):
            return None
        label = str(value.get("label") or "").strip()
        claim = str(value.get("claim") or "").strip()
        if not label or not claim:
            return None
        return cls(label=label, claim=claim, observables=_strings(value.get("observables")))


METHOD_STATUS_UNVERIFIED = "candidate_unverified"


@dataclass(frozen=True)
class MethodCandidate:
    """A user-described rule of thumb, shaped for 07's validation loop.

    条件 → 预期 → 适用环境 → 反例.  Extraction never verifies anything: the
    status is fixed to ``candidate_unverified`` and only the methodology backtest
    (``methodology_backtest`` / 07) may change it.
    """

    condition: str
    expectation: str
    applicability: str
    counterexamples: tuple[str, ...] = ()
    status: str = METHOD_STATUS_UNVERIFIED
    source_text: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "condition": self.condition,
            "expectation": self.expectation,
            "applicability": self.applicability,
            "counterexamples": list(self.counterexamples),
            "status": self.status,
            "source_text": self.source_text,
        }

    @classmethod
    def from_dict(cls, value: object) -> MethodCandidate | None:
        if not isinstance(value, Mapping):
            return None
        condition = str(value.get("condition") or "").strip()
        expectation = str(value.get("expectation") or "").strip()
        if not condition or not expectation:
            return None
        return cls(
            condition=condition,
            expectation=expectation,
            applicability=str(value.get("applicability") or "未说明").strip() or "未说明",
            counterexamples=_strings(value.get("counterexamples")),
            # 外来（模型 / 反序列化）候选一律回到未验证：验证状态只能由回测收据推出。
            status=METHOD_STATUS_UNVERIFIED,
            source_text=str(value.get("source_text") or "").strip()[:160],
        )


@dataclass(frozen=True)
class MessageParts:
    """Result of ``split_user_message``: the question part and the materials."""

    question: str
    materials: tuple[MaterialRef, ...] = ()
    material_texts: tuple[str, ...] = field(default=(), repr=False)
    # E2/P1：顶层三分区结果（classify_top_level_regions）。默认 None 时与旧行为
    # 完全一致；消费方（两轴/继承/冻结点）在后续阶段接线。
    regions: "TopLevelRegions | None" = None

    # ── E2 消费 API（P2+ 的消费方从这里读；P1 先定义，保证字段写读同仓）──
    @property
    def classification(self) -> str:
        """三态分类；未启用三分区时等同 no_constraint_confirmed。"""
        if self.regions is None:
            return "no_constraint_confirmed"
        return self.regions.classification

    @property
    def sub_questions(self) -> tuple[str, ...]:
        """编号题组（question_id = 用户原编号序）；无题组返回空。"""
        if self.regions is None:
            return ()
        return self.regions.sub_questions

    @property
    def uncertain_reasons(self) -> tuple[str, ...]:
        """boundary_uncertain 的确定性原因码（供澄清提问与审计）。"""
        if self.regions is None:
            return ()
        return self.regions.uncertain_reasons

    @property
    def boundary_uncertain(self) -> bool:
        """True = 任何后续状态操作前必须先澄清（设计稿 v10 §3.1 三态）。"""
        return self.classification == "boundary_uncertain"


# ── E2 材料题边界（设计稿 v10，docs/learning/knevo-distill/recheck/
# 2026-09-12-t23-nogrok/E2-DESIGN-material-contract-2026-09-13.md）─────────────
#
# 两类状态操作共用词表与共用探测器（QC 守则 1 + 退修 R3：第 1 步内容复核与第 2
# 步指令识别不仅共用词表，还必须共用同一个句级识别函数 find_state_ops）。
# ① 轴值更新（B 轴 / A 轴 / 显式放宽）：
_B_MATERIAL_ONLY_PHRASES: tuple[str, ...] = (
    "只依据", "仅根据", "不读取任何材料外", "不读取材料外",
)
_B_LOCAL_ONLY_PHRASES: tuple[str, ...] = (
    "不要联网", "不联网", "别查实时", "不读外部",
)
_B_RELAX_PHRASES: tuple[str, ...] = ("可以查真实数据", "结合最新行情", "结合当前行情")
# ② 基底继承（续轮声明）：
_CONTINUATION_HEAD_PHRASES: tuple[str, ...] = ("继续", "接着", "同上")

# 同一句逗号两侧可以分别声明 A 前提和 B 权限，偏移仍对应原文。
_SENT_SPLIT_RE = re.compile(r"[。！？；，,\n]")
# 虚构前提声明：「以下是完全虚构的研究案例」「均为虚构」「纯属虚构」等（句中即算，
# 这类措辞极少出现在叙述句里；出现在复核块里时走 boundary_uncertain 保守分支）。
_FICTIONAL_SENT_RE = re.compile(
    r"以下\s*[是为][^。；，]{0,12}虚构|均为虚构|纯属虚构|完全虚构|虚构案例|[是为]虚构的?"
)
# A8 的「假设 X，结合当前行情」不要求额外的「成立」。是否顶层由区域复核决定，
# 而不是把明确假设漏成无约束；材料内同形态仍走 uncertain，强保护内不可见。
_HYPOTHESIS_STRONG_RE = re.compile(r"^(?:假设|如果)\S.{1,}")
# 题内假设：句首 假设/如果 即算（题上下文消歧，scope=q{n}）。
_HYPOTHESIS_IN_QUESTION_RE = re.compile(r"^(?:假设|如果)\S{2,}")

_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_QUOTE_PAIRS: tuple[tuple[str, str], ...] = (
    ("「", "」"), ("『", "』"), ("“", "”"), ("‘", "’"), ('"', '"'), ("'", "'"),
)
_LEADIN_RE = re.compile(
    r"(?:材料|材料内容|报告原文|报告|原文|案例|资料)"
    r"(?:如下|全文)?[^\n]{0,24}[:：]\s*$"
)
_QUESTION_LEAD_RE = re.compile(r"按以下|逐项|回答以下|以下\s*\d+\s*题")
_NUMBERED_ITEM_RE = re.compile(r"^\s*(\d{1,2})[.、\)）]\s*(\S.*)$")
# 题/请求形态（区别于「1. 行业概览」式研报小节标题）。
_QUESTIONISH_RE = re.compile(
    r"[？?]|吗\b|什么|怎么|多少|哪些|如何|为何|是否|请|如果|假设|选哪|排序|指出|说明"
)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT_RE.split(text) if s.strip()]


def _sentence_spans(text: str) -> list[tuple[int, int, str]]:
    """按句边界切分，返回 (start, end, stripped_sentence)；start/end 为原文偏移。

    掩码是按字符等长替换的，掩码文本上算出的偏移可直接切回原始行取原文。
    """
    out: list[tuple[int, int, str]] = []
    pos = 0
    for m in _SENT_SPLIT_RE.finditer(text):
        seg = text[pos : m.start()]
        if seg.strip():
            lead = len(seg) - len(seg.lstrip())
            out.append((pos + lead, m.start(), seg.strip()))
        pos = m.end()
    seg = text[pos:]
    if seg.strip():
        lead = len(seg) - len(seg.lstrip())
        out.append((pos + lead, len(text), seg.strip()))
    return out


def _state_op_in_sentence(sent: str) -> str | None:
    """句级状态操作识别（内容复核与指令识别共用的唯一入口，退修 R3）。

    返回 "constraint_b" | "premise_declaration" | "continuation" | None。
    """
    s = sent.strip()
    if not s:
        return None
    head = re.sub(r"^(?:请|麻烦|烦请)\s*", "", s)
    if head.startswith(_B_MATERIAL_ONLY_PHRASES + _B_LOCAL_ONLY_PHRASES + _B_RELAX_PHRASES):
        return "constraint_b"
    if head.startswith(_CONTINUATION_HEAD_PHRASES) or "其余条件不变" in s:
        return "continuation"
    if _FICTIONAL_SENT_RE.search(s):
        return "premise_declaration"
    if _HYPOTHESIS_STRONG_RE.match(s):
        return "premise_declaration"
    return None


def find_state_ops(text: str) -> tuple[tuple[str, str], ...]:
    """对一段（已按强保护掩码的）文本做句级状态操作扫描，返回 (kind, 原句) 列表。"""
    out: list[tuple[str, str]] = []
    for sent in _sentences(text):
        kind = _state_op_in_sentence(sent)
        if kind:
            out.append((kind, sent))
    return tuple(out)


def _visible_lines(lines: list[str]) -> tuple[list[str], list[str]]:
    """强保护掩码：围栏整行、闭合引号按字符区间置空格（退修 R2/R5）。

    返回 (掩码后行列表, 保护失败原因)。闭合引号只掩码引用区间本身，同一行引用
    之外的指令文字仍然可见；未闭合构造按设计落 boundary_uncertain。
    """
    masked = list(lines)
    uncertain: list[str] = []
    fence_open: int | None = None
    fence_mark = ""
    for li, line in enumerate(lines):
        m = _FENCE_RE.match(line)
        if not m:
            continue
        if fence_open is None:
            fence_open, fence_mark = li, m.group(1)
        elif m.group(1) == fence_mark:
            for j in range(fence_open, li + 1):
                masked[j] = " " * len(masked[j])
            fence_open = None
    if fence_open is not None:
        uncertain.append("unclosed_fence")

    # 先只在围栏之外配对；每个闭合围栏都是配对屏障。按文本次序冻结最外层
    # 引用，不能按引号类型逐轮重扫原文（内层未闭合符号会泄漏到外层）。
    visible = "\n".join(masked)
    chars = list(visible)
    barriers: set[int] = set()
    offset = 0
    for original, line in zip(lines, masked):
        if original != line:
            barriers.add(offset)
        offset += len(line) + 1
    pairs: dict[int, int] = {}
    openers: set[int] = set()
    for opener, closer in _QUOTE_PAIRS:
        stack: list[int] = []
        backslashes = 0
        for pos, ch in enumerate(visible):
            if pos in barriers:
                stack.clear()
            escaped = backslashes % 2 == 1
            backslashes = backslashes + 1 if ch == "\\" else 0
            if escaped:
                continue
            if ch == opener and (opener != closer or not stack):
                stack.append(pos)
                openers.add(pos)
            elif ch == closer and stack:
                pairs[stack.pop()] = pos
    unclosed: list[int] = []
    pos = 0
    while pos < len(chars):
        if pos in pairs:
            end = pairs[pos] + 1
            for index in range(pos, end):
                if chars[index] != "\n":
                    chars[index] = " "
            pos = end
        else:
            if pos in openers:
                unclosed.append(pos)
            pos += 1
    visible = "".join(chars)
    for pos in unclosed:
        # 检测从开引号之后开始；已冻结内容仍不可见，不能误报内部状态操作。
        end = min((b for b in barriers if b > pos), default=len(visible))
        if find_state_ops(visible[pos + 1 : end]):
            uncertain.append("unclosed_quote_with_state_op")
    return visible.split("\n"), uncertain


@dataclass(frozen=True)
class InstructionSpan:
    """指令区片段（D1）：行为指令 / 前提声明 / 续轮声明。

    scope="message" 为消息级；题内检出的状态操作 scope="q{用户原编号}"（退修 R6）。
    """

    kind: str  # "constraint_b" | "premise_declaration" | "continuation"
    text: str
    line_index: int
    scope: str = "message"


@dataclass(frozen=True)
class TopLevelRegions:
    """D1 顶层三分区 + 三态分类结果（设计稿 v10 §3.1）。"""

    classification: str  # constraint_confirmed | no_constraint_confirmed | boundary_uncertain
    instructions: tuple[InstructionSpan, ...] = ()
    sub_questions: tuple[str, ...] = ()
    uncertain_reasons: tuple[str, ...] = ()


def classify_top_level_regions(text: str) -> TopLevelRegions:
    """E2 设计稿 v10 §3.1：先保护、后解释、三态分类（全部确定性）。

    有序步骤：①强保护掩码（围栏整行 / 闭合引号字符区间；未闭合→uncertain）
    ②引导块/缩进块/长文块内容复核（掩码后文本，命中状态操作→uncertain）
    ③题组区识别（编号连续、保留原文续行；题内状态操作 scope=qN）
    ④指令区识别（句级，行内第二句也算，退修 R1）⑤邻接规则（与叙述无空行相连
    的疑似指令→uncertain，退修 R4）⑥三态分类。
    """
    raw = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    if not raw.strip():
        return TopLevelRegions(classification="no_constraint_confirmed")
    lines = raw.split("\n")
    n = len(lines)
    masked, uncertain = _visible_lines(lines)
    claimed = [False] * n  # 已归材料区（保护/复核通过块）或题组区

    # 第 2 步：引导块 / 缩进块（内容复核类；复核在掩码后文本上做，R5）
    li = 0
    while li < n:
        if claimed[li] or not masked[li].strip():
            li += 1
            continue
        begin, end, why = -1, -1, ""
        body_from = begin
        if _LEADIN_RE.search(masked[li]):
            begin = li
            end = n
            for j in range(li + 1, n):
                if not lines[j].strip():
                    nxt = j + 1
                    while nxt < n and not lines[nxt].strip():
                        nxt += 1
                    if nxt < n and (
                        _NUMBERED_ITEM_RE.match(masked[nxt])
                        or _QUESTION_LEAD_RE.search(masked[nxt])
                        or _looks_like_question(masked[nxt])
                        or find_state_ops(masked[nxt])
                    ):
                        end = j
                        break
            why = "leadin_block_with_state_op"
            body_from = begin + 1  # 引导行本身不进复核，其状态操作走第 4 步指令区
        elif lines[li].startswith("  ") and masked[li].strip():
            begin, end = li, li
            while end < n and lines[end].startswith("  ") and masked[end].strip():
                end += 1
            why = "indent_block_with_state_op"
            body_from = begin
        if begin >= 0:
            if find_state_ops("\n".join(masked[body_from:end])):
                uncertain.append(why)
            # 复核失败的候选也不可被后续题组/指令扫描重新认领为已确认。
            for j in range(body_from, end):
                claimed[j] = True
            li = max(end, li + 1)
            continue
        li += 1

    # 长文候选先于题组认领。仅从叙述起点进入：已确认题首的长限定不因长度
    # 变材料；但「叙述+编号小节」不能先认成题组免检。逐片段检查整行角色，
    # 一行含状态操作不代表其余叙述也变成指令。
    li = 0
    while li < n:
        visible = masked[li].strip()
        fragments = _sentences(visible)
        state_only = bool(fragments) and all(_state_op_in_sentence(s) for s in fragments)
        numbered = _NUMBERED_ITEM_RE.match(visible)
        if not claimed[li] and numbered and _QUESTIONISH_RE.search(numbered.group(2)):
            # 题首已经具备请求句法，其紧邻续行是同一候选，不能从第二行另起
            # 长文候选抢走限定条件；真正题组是否连续仍由后续题组步骤验证。
            li += 1
            while li < n and lines[li].strip() and not _NUMBERED_ITEM_RE.match(masked[li]):
                li += 1
            continue
        if (
            claimed[li] or not visible or state_only
            or _QUESTION_LEAD_RE.search(visible)
            or _looks_like_question(visible)
        ):
            li += 1
            continue
        end = li + 1
        while end < n and lines[end].strip() and not claimed[end]:
            candidate = masked[end].strip()
            # 编号小节即使含「说明」也不是独立短问句；留在候选共同复核。
            if not _NUMBERED_ITEM_RE.match(candidate) and (
                _QUESTION_LEAD_RE.search(candidate)
                or (not find_state_ops(candidate) and _looks_like_question(candidate))
            ):
                break
            end += 1
        if end - li > 1 and len("\n".join(lines[li:end])) >= _MATERIAL_MIN_CHARS:
            if find_state_ops("\n".join(masked[li:end])):
                uncertain.extend(("long_block_with_state_op", "adjacent_state_op"))
            for j in range(li, end):
                claimed[j] = True
        li = end

    # 第 3 步：题组区。检测看可见文本，段落边界和存储看原文。
    # 已认定题体的长续行/全引用续行不是材料阈值或空行。
    sub_questions: list[str] = []
    q_spans: list[InstructionSpan] = []
    expected = 1
    li = 0
    while li < n:
        m = None if claimed[li] else _NUMBERED_ITEM_RE.match(masked[li])
        if m and int(m.group(1)) == expected:
            j = li + 1
            while (
                j < n
                and lines[j].strip()
                and not claimed[j]
                and not _NUMBERED_ITEM_RE.match(masked[j])
            ):
                j += 1
            # j = 题体之后首个空行/编号/已占行；向前看下一个非空行
            nxt = j
            while nxt < n and not lines[nxt].strip():
                nxt += 1
            followed_by_next_item = (
                nxt < n
                and _NUMBERED_ITEM_RE.match(masked[nxt]) is not None
                and int(_NUMBERED_ITEM_RE.match(masked[nxt]).group(1)) == expected + 1
            )
            body = "\n".join(
                [m.group(2).strip(), *(masked[k].strip() for k in range(li + 1, j))]
            ).strip()
            # 组在文末结束 或 紧随下一编号项 → 题；题间夹叙述正文 → 小节标题
            if _QUESTIONISH_RE.search(body) and (nxt >= n or followed_by_next_item):
                # 存储用原文（掩码仅供检测），保留题内引号内容
                original_body = "\n".join(
                    [
                        _NUMBERED_ITEM_RE.match(lines[li]).group(2).strip(),
                        *(lines[k].strip() for k in range(li + 1, j)),
                    ]
                ).strip()
                sub_questions.append(original_body)
                for k in range(li, j):
                    claimed[k] = True
                    # 题内状态操作：检测在掩码句上做，文本按同偏移切回原文（R6）；
                    # 首行跳过编号前缀，否则「8. 如果…」的句首形态被编号挡住
                    base = m.start(2) if k == li else 0
                    for s_off, e_off, sent in _sentence_spans(masked[k][base:]):
                        kind = _state_op_in_sentence(sent)
                        if kind is None and _HYPOTHESIS_IN_QUESTION_RE.match(sent):
                            kind = "premise_declaration"
                        if kind:
                            q_spans.append(
                                InstructionSpan(
                                    kind,
                                    lines[k][base + s_off : base + e_off].strip(),
                                    k,
                                    scope=f"q{expected}",
                                )
                            )
                expected += 1
        li += 1

    # 第 4 步：指令区识别（句级；未占行；行内第二句同样检出，R1；
    # 检测在掩码句上做，span 文本按同偏移切回原文，保留引用内容）
    instructions: list[InstructionSpan] = []
    instruction_lines: set[int] = set()
    for li in range(n):
        if claimed[li] or not masked[li].strip():
            continue
        for s_off, e_off, sent in _sentence_spans(masked[li]):
            kind = _state_op_in_sentence(sent)
            if kind:
                instructions.append(
                    InstructionSpan(kind, lines[li][s_off:e_off].strip(), li)
                )
                instruction_lines.add(li)

    # 第 5 步：邻接规则——疑似指令行与叙述行无空行相连 → 归属不明 → uncertain
    # （长研报里混入的禁令字样不升级为指令，R4；顶层消息首行/空行分隔不受影响）
    for span in instructions:
        li = span.line_index
        for neighbor in (li - 1, li + 1):
            if (
                0 <= neighbor < n
                and not claimed[neighbor]
                and neighbor not in instruction_lines
                and masked[neighbor].strip()
                and not _LEADIN_RE.search(masked[neighbor])
            ):
                uncertain.append("adjacent_state_op")
                break

    # 第 6 步：三态分类
    if uncertain:
        classification = "boundary_uncertain"
    elif instructions or q_spans:
        classification = "constraint_confirmed"
    else:
        classification = "no_constraint_confirmed"
    return TopLevelRegions(
        classification=classification,
        instructions=tuple(instructions) + tuple(q_spans),
        sub_questions=tuple(sub_questions),
        uncertain_reasons=tuple(dict.fromkeys(uncertain)),
    )


_URL_RE = re.compile(r"https?://[^\s<>\"'）)】\]]+", re.IGNORECASE)
_MATERIAL_DATE_RE = re.compile(
    r"(?<!\d)(20\d{2})\s*[-/.年]\s*(\d{1,2})(?:\s*[-/.月]\s*(\d{1,2})\s*日?)?(?!\d)"
)
_QUOTED_MATERIAL_RE = re.compile(r"[「“\"『]([^」”\"』]{40,})[」”\"』]")
_TABLE_SPLIT_RE = re.compile(r"\t|\s*\|\s*|\s{2,}")
# 问句标记只认真正的疑问 / 请求形状。「分析」「判断」「解读」这类词在研报正文里
# 到处都是（「三、我们的判断」），不能当问句标记，否则材料的末段会被当成问题。
_QUESTION_MARKER_RE = re.compile(
    r"(?:[？?]|吗|呢|怎么|如何|哪些|哪个|哪条|哪家|是不是|是否|能不能|能否|会不会|"
    r"该不该|要不要|值不值|站得住|靠谱|怎么看|怎么办|怎么操作|"
    r"^(?:帮我|请|麻烦|看看|分析一下|判断一下|解读一下|提纯一下|拆一下|挑出|区分一下|对比一下|比较一下))"
)
_MATERIAL_MARKER_RE = re.compile(
    r"(?:【|】|研报|摘要|纪要|公告|要点|核心观点|风险提示|来源[:：]|作者[:：]|"
    r"^[一二三四五六七八九十]+[、.．]|^\d+[、.．]|^第[一二三四五六七八九十]+[章节部分])",
    re.MULTILINE,
)
_MATERIAL_REFERENCE_RE = re.compile(
    r"(?:这篇|这份|这段|这张(?:表|图)?|上面(?:这|的)?(?:段|篇|份|表|材料|文章|研报)?|"
    r"刚(?:贴|发|给)的?|附件|该(?:材料|研报|文档|文章|表格|报告|纪要)|"
    r"这(?:个|篇|份)?(?:材料|研报|文档|文章|表格|报告|纪要|摘要|截图|链接))"
)
_LONG_SINGLE_LINE_MIN = 160
_MATERIAL_MIN_CHARS = 40
_QUESTION_MAX_CHARS = 120


def material_id_for(text: str) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    return "m-" + hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:10]


def _material_dates(text: str) -> tuple[str, ...]:
    found: list[str] = []
    for year, month, day in _MATERIAL_DATE_RE.findall(text):
        try:
            m = int(month)
            if not 1 <= m <= 12:
                continue
            if day:
                d = int(day)
                if not 1 <= d <= 31:
                    continue
                token = f"{int(year):04d}-{m:02d}-{d:02d}"
            else:
                token = f"{int(year):04d}-{m:02d}"
        except ValueError:
            continue
        if token not in found:
            found.append(token)
    return tuple(found[:8])


def _cells(line: str) -> tuple[str, ...]:
    stripped = line.strip().strip("|")
    if not stripped:
        return ()
    return tuple(cell.strip() for cell in _TABLE_SPLIT_RE.split(stripped) if cell.strip())


def _is_table_line(line: str) -> bool:
    return len(_cells(line)) >= 2 and ("\t" in line or "|" in line or re.search(r"\s{2,}", line.strip()) is not None)


def _title_for(text: str, kind: str, headers: tuple[str, ...]) -> str:
    if kind == "table" and headers:
        return "表格：" + "/".join(headers[:4])
    first = next((line.strip() for line in text.splitlines() if line.strip()), "")
    first = re.sub(r"\s+", " ", re.sub(r"[【】\[\]]", " ", first)).strip()
    if len(first) <= 40:
        return first
    return first[:30] + "…"


def material_from_text(text: str, *, kind: str = "pasted_text") -> MaterialRef | None:
    """Build a material ref for a whole text (used when the text IS the material)."""

    body = str(text or "").strip()
    if not body:
        return None
    lines = [line for line in body.splitlines() if line.strip()]
    table_lines = [line for line in lines if _is_table_line(line)]
    headers: tuple[str, ...] = ()
    rows = 0
    if kind == "table" or (len(table_lines) >= 2 and len(table_lines) >= len(lines) - 1):
        kind = "table"
        headers = _cells(table_lines[0]) if table_lines else ()
        rows = max(0, len(table_lines) - 1)
    paragraphs = len([block for block in re.split(r"\n\s*\n", body) if block.strip()])
    return MaterialRef(
        material_id=material_id_for(body),
        kind=kind,
        title=_title_for(body, kind, headers),
        char_count=len(body),
        headers=headers,
        dates=_material_dates(body),
        paragraphs=paragraphs,
        rows=rows,
    )


def _looks_like_question(text: str) -> bool:
    if "\n" in text.strip():
        # 问题是一行话；多行的块是材料（哪怕末行里有个「吗」）。
        return False
    compact = re.sub(r"\s+", "", text)
    return bool(compact) and len(compact) <= _QUESTION_MAX_CHARS and _QUESTION_MARKER_RE.search(compact) is not None


def split_user_message(text: str) -> MessageParts:
    """Separate the question from pasted materials in one user message.

    E2/P1：返回值附带顶层三分区结果（classify_top_level_regions），旧抽取行为
    不变；两轴/继承/冻结点等消费方在后续阶段接线。
    """
    parts = _split_user_message_core(text)
    return replace(parts, regions=classify_top_level_regions(text))


def _split_user_message_core(text: str) -> MessageParts:
    """Separate the question from pasted materials in one user message.

    Shapes handled (all deterministic):

    - table lines (tab / ``|`` / wide-space separated, ≥ 2 consecutive rows) →
      one ``table`` material with headers and row count;
    - multi-paragraph text where the first or last short paragraph is the
      question and the rest reads like a document → one ``pasted_text`` material;
    - a long single line ending in a short question sentence → head is material;
    - URLs → ``url`` materials (the question text keeps a ``该链接`` placeholder
      so routing regexes do not chew on the address);
    - long quoted passages → ``quoted`` materials.

    A message that is only a material (no question sentence) returns an empty
    ``question`` and the whole text as one material; callers fall back to the
    raw text for anything that needs a question.
    """

    raw = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not raw:
        return MessageParts(question="")

    materials: list[MaterialRef] = []
    texts: list[str] = []

    def add(body: str, kind: str) -> None:
        ref = material_from_text(body, kind=kind)
        if ref is None or any(item.material_id == ref.material_id for item in materials):
            return
        materials.append(ref)
        texts.append(body.strip())

    working = raw
    for url in _URL_RE.findall(working):
        add(url, "url")
        working = working.replace(url, "该链接")
    for quoted in _QUOTED_MATERIAL_RE.findall(working):
        add(quoted, "quoted")
        working = working.replace(quoted, "该材料")

    lines = working.split("\n")
    # 1. 表格行：连续 ≥ 2 行、每行 ≥ 2 个单元格。
    table_blocks: list[tuple[int, int]] = []
    start = None
    for index, line in enumerate(lines + [""]):
        if line.strip() and _is_table_line(line):
            if start is None:
                start = index
            continue
        if start is not None and index - start >= 2:
            table_blocks.append((start, index))
        start = None
    consumed: set[int] = set()
    for begin, end in table_blocks:
        add("\n".join(lines[begin:end]), "table")
        consumed.update(range(begin, end))
    remaining_lines = [line for index, line in enumerate(lines) if index not in consumed]
    rest = "\n".join(remaining_lines).strip()

    # 2. 段落：空行分块；首/末短问句是问题，其余长文是材料。
    blocks = [block.strip() for block in re.split(r"\n\s*\n", rest) if block.strip()]
    question = rest
    if len(blocks) >= 2:
        if _looks_like_question(blocks[-1]):
            question, body = blocks[-1], "\n\n".join(blocks[:-1])
        elif _looks_like_question(blocks[0]):
            question, body = blocks[0], "\n\n".join(blocks[1:])
        else:
            question, body = "", rest
        if body and (len(body) >= _MATERIAL_MIN_CHARS or _MATERIAL_MARKER_RE.search(body)):
            add(body, "pasted_text")
        else:
            question = rest
    elif len(blocks) == 1:
        block = blocks[0]
        if table_blocks and _looks_like_question(block):
            question = block
        elif "\n" in block and len(block) >= _MATERIAL_MIN_CHARS:
            # 多行但无空行：末行是短问句 → 前面是材料；整块像文档且没有问句 → 全是材料。
            block_lines = [line.strip() for line in block.split("\n") if line.strip()]
            if len(block_lines) >= 2 and _looks_like_question(block_lines[-1]) and not _looks_like_question("\n".join(block_lines[:-1])):
                question = block_lines[-1]
                add("\n".join(block_lines[:-1]), "pasted_text")
            elif _MATERIAL_MARKER_RE.search(block) and not _looks_like_question(block_lines[-1]):
                question = ""
                add(block, "pasted_text")
            else:
                question = block
        elif "\n" not in block and len(block) >= _LONG_SINGLE_LINE_MIN:
            # 单行长文 + 句尾短问句。
            sentences = [part for part in re.split(r"(?<=[。！？!?])", block) if part.strip()]
            if len(sentences) >= 2 and _looks_like_question(sentences[-1]) and len("".join(sentences[:-1])) >= 100:
                question = sentences[-1].strip()
                add("".join(sentences[:-1]), "pasted_text")
            else:
                question = block
        else:
            question = block
    elif not blocks and table_blocks:
        question = ""

    if not question.strip() and not materials:
        return MessageParts(question=raw)
    return MessageParts(
        question=question.strip(),
        materials=tuple(materials),
        material_texts=tuple(texts),
    )


def references_material(text: str) -> bool:
    """「这篇 / 这份材料 / 上面这段 / 附件」——题面引用了一份材料。"""

    compact = re.sub(r"\s+", "", str(text or ""))
    return bool(compact) and _MATERIAL_REFERENCE_RE.search(compact) is not None


_PROMPT_BLOCK_ROLE_RE = re.compile(r"^(user|assistant|system)[:：]\s?", re.MULTILINE)


def materials_in_conversation(conversation_context: str | None) -> tuple[tuple[MaterialRef, str], ...]:
    """Recover materials pasted in earlier **user** messages of a prompt block.

    ``ConversationContext.to_prompt_block`` renders ``role: content`` lines; the
    content may span lines, so a message runs until the next role marker or a
    ``## `` header.  Returns ``(ref, text)`` pairs oldest → newest.  Identities are
    recomputed from content, so they match the refs the earlier turn produced.
    """

    block = str(conversation_context or "")
    if not block.strip():
        return ()
    messages: list[tuple[str, str]] = []
    current_role: str | None = None
    current: list[str] = []
    for line in block.split("\n"):
        if line.startswith("## "):
            if current_role is not None:
                messages.append((current_role, "\n".join(current)))
            current_role, current = None, []
            continue
        marker = _PROMPT_BLOCK_ROLE_RE.match(line)
        if marker is not None:
            if current_role is not None:
                messages.append((current_role, "\n".join(current)))
            current_role = marker.group(1)
            current = [line[marker.end():]]
            continue
        if current_role is not None:
            current.append(line)
    if current_role is not None:
        messages.append((current_role, "\n".join(current)))

    found: list[tuple[MaterialRef, str]] = []
    seen: set[str] = set()
    for role, content in messages:
        if role != "user":
            continue
        parts = split_user_message(content)
        for ref, body in zip(parts.materials, parts.material_texts):
            if ref.material_id in seen:
                continue
            seen.add(ref.material_id)
            found.append((ref, body))
    return tuple(found)


_TRUNCATION_MARKER_RE = re.compile(r"^（前 \d+ 字符已省略，共 \d+ 条较早消息）")


def conversation_context_material_unrecoverable(conversation_context: str | None) -> bool:
    """对话块已知、且被截断时返回 True：「这篇」无法按现有会话内容找回身份。

    I2 接线层：长材料超出最近消息窗口后进入被截断的「较早消息」区，此时
    ``materials_in_conversation`` 返回空不是「没有材料」，而是「有过但正文丢了」。
    区分两者的唯一信号是截断标记（``ConversationContext.to_prompt_block`` 自带的
    如实自述行）。保留该信号的原始行号，便于审计，不要把它当作无材料的同义词。
    """

    block = str(conversation_context or "")
    for line in block.splitlines():
        if _TRUNCATION_MARKER_RE.match(line.strip()):
            return True
    return False


def rebind_material_from_text(
    raw_question: str,
    message_materials: tuple[MaterialRef, ...],
    *,
    identity_table: str | None = None,
) -> tuple[tuple[str, ...], str | None]:
    """从**本条消息自身粘贴的正文**里重建「这篇」的绑定，返回 (ids, 登记行)。

    适用场景：对话块已截断（身份表本身不在），但用户在新一条消息里**重贴了**原文。
    按内容哈希重算身份——与上一轮在完整对话里得到的 ``material_id`` 完全一致，
    且不需要任何持久化存储。登记行携带「按重贴内容重建」的来源说明，供审计区分
    「本轮新贴」与「跨轮同一份」。

    ``identity_table`` 传入时优先使用其中已列出的 material_id（对话块未截断的
    正常车道）；但内容哈希仍然按本条消息正文重算，不接受身份表里没有的伪装 id。
    """

    text = str(raw_question or "").strip()
    if not text or not message_materials:
        return (), None
    if not references_material(text):
        return (), None
    parts = split_user_message(text)
    ids: list[str] = []
    for ref, body in zip(parts.materials, parts.material_texts):
        # 按内容哈希重算身份，比 message_materials 里现成的 ref 更稳——后者
        # 是调用方按同一正文构造的，但重算能抵抗「调用方未来把材料正文换了」的漂移。
        rebound = material_from_text(body, kind=ref.kind)
        if rebound is None:
            continue
        if rebound.material_id not in ids:
            ids.append(rebound.material_id)
    if not ids:
        return (), None
    source_note = "本条消息重贴内容重建"
    if identity_table:
        source_note = f"{source_note}（身份表：{identity_table}）"
    return tuple(ids), f"「这篇 / 这份 / 这张表」按{source_note}绑定：{ids[-1]}"


def detect_reposted_material_gap(raw_question: str, conversation_context: str | None) -> str | None:
    """本轮题面引用了材料，正文既不在本轮消息里、对话块又已截断时返回缺口描述。

    供澄清层在「无法重新绑定」与「根本没贴过」之间分流：前者提示用户重贴原文，
    后者维持既有「缺材料」语义。返回 None 表示没有进入该缺口（可以走正常
    绑定/澄清路径）。不改变澄清本身的措辞，只给调用方一个可判定的分支。
    """

    if conversation_context is None:
        return None
    if not conversation_context_material_unrecoverable(conversation_context):
        return None
    if not references_material(str(raw_question or "")):
        return None
    if split_user_message(str(raw_question or "")).materials:
        return None
    return "「这篇」所指材料超出最近完整消息窗口，且本轮未重贴原文，无法按内容哈希恢复身份"


# --- 用户已有假设 ----------------------------------------------------------------
_BELIEF_RE = re.compile(
    r"(?:我(?:个人)?(?:觉得|认为|判断|感觉|预计|估计|倾向于认为|的看法是|的理解是|的经验是|"
    r"一直认为|一般认为|的方法是|的做法是|的规律是)|在我看来|按我的经验|经验上看?)"
    r"[，,:：]?(?P<body>[^。？！?\n]{4,80})"
)
_OBSERVATION_RE = re.compile(
    r"^(?P<body>[^，,。？！?\n]{2,24}?(?:不涨|滞涨|涨不动|走弱|走强|缩量|放量|分歧|退潮|"
    r"新高|新低|涨停|跌停|断板|断了|掉队|回流|补涨|大跌|大涨|翻绿|冲高回落|放巨量|跌了|涨了)"
    r"[^，,。？！?\n]{0,12})[，,]"
)
_PRIOR_REFERENCE_RE = re.compile(
    r"(?:我(?:之前|此前|过去|原来|先前|上次|当初)(?:的)?(?:判断|看法|观点|结论|逻辑|说过)|"
    r"跟我(?:上次|之前)说过|结合我之前(?:跟你)?说过|我之前跟你说过)"
)
PRIOR_JUDGEMENT_PREMISE = "引用此前判断（需从个人台账取回，不在本轮问句里）"
_QUESTION_CLAUSE_RE = re.compile(
    r"(?:吗|呢|[？?]|是不是|会不会|能不能|该不该|要不要|^这次|^那么|^那|^所以|怎么|如何|哪)"
)


def _trim_question_clauses(body: str) -> str:
    """「…板块一般还有一次回流，这次固态电池也会这样吗」→ 去掉句尾的提问分句。"""

    segments = [seg for seg in re.split(r"[，,]", body) if seg.strip()]
    while len(segments) > 1 and _QUESTION_CLAUSE_RE.search(segments[-1]):
        segments.pop()
    return "，".join(segments).strip()


def extract_user_premises(text: str) -> tuple[str, ...]:
    """The user's own beliefs / observations / references to a past judgement.

    Premises are what the user holds to be true going in.  They are recorded so
    the answer can test them explicitly instead of silently adopting or ignoring
    them; the frame never treats them as market facts.
    """

    compact = re.sub(r"[ \t]+", "", str(text or "")).strip()
    if not compact:
        return ()
    premises: list[str] = []

    def add(item: str) -> None:
        cleaned = item.strip(" ，,。：:；;")
        if cleaned and cleaned not in premises:
            premises.append(cleaned[:80])

    for match in _BELIEF_RE.finditer(compact):
        body = _trim_question_clauses(match.group("body"))
        if len(body) >= 4:
            add(body)
    observation = _OBSERVATION_RE.match(compact)
    if observation is not None and not _BELIEF_RE.match(compact):
        add(observation.group("body") + "（用户观察）")
    if _PRIOR_REFERENCE_RE.search(compact):
        add(PRIOR_JUDGEMENT_PREMISE)
    return tuple(premises)


# --- 方法候选 ----------------------------------------------------------------------
_METHOD_CUE_RE = re.compile(
    r"(?:我的(?:经验|方法|做法|习惯|规律|观察)是|按我的经验|经验上|一般来说|通常来说|"
    r"规律是|历史上看|我一般|我通常|每当|只要|一旦)"
)
_GENERALIZER_RE = re.compile(r"(?:一般|通常|往往|大概率|大多|基本|总会|就会|多半)")
_CONDITION_EXPECTATION_RES = (
    re.compile(
        r"(?:每当|只要|一旦|如果|若)(?P<cond>[^，,。；;？！\n]{2,40}?)[，,]?"
        r"(?:就|都会|一般|通常|往往|大概率|多半)(?P<exp>[^。；;？！\n]{2,60})"
    ),
    re.compile(
        r"(?P<cond>[^，,。；;？！\n]{2,40}?)(?:之后|以后|后|时|的时候)[，,]?"
        r"(?P<exp>[^。；;？！\n]{0,20}?(?:一般|通常|往往|大概率|大多|基本|总会|就会|多半)[^。；;？！\n]{1,60})"
    ),
    re.compile(
        r"(?P<cond>[^，,。；;？！\n]{2,30})(?:是|意味着|说明|代表)"
        r"(?P<exp>[^。；;？！\n]{2,40}?(?:信号|前兆|标志|开始|结束|见顶|见底|退潮|回流)[^。；;？！\n]{0,20})"
    ),
)
_APPLICABILITY_RE = re.compile(
    r"(?:主升(?:期|阶段)?|退潮(?:期|阶段)?|震荡(?:市|期)?|反弹(?:期|阶段)?|牛市|熊市|"
    r"情绪(?:高位|低位|冰点|高潮)|(?:大盘|指数)(?:强势|弱势|上行|下行)|题材(?:期|行情)|连板潮|"
    r"高位|低位|放量期|缩量期)"
)
_COUNTEREXAMPLE_RE = re.compile(r"(?:除了|除非|但是|但|不过|例外是|反例是)(?P<ce>[^。；;？！\n]{2,60})")
_QUESTION_TAIL_RE = re.compile(r"(?:这次|那么|所以|那|这回)?[^，,。；;？！\n]{0,20}(?:也会这样吗|会不会|是不是|能不能|吗|呢|？|\?)")


def extract_method_candidates(text: str) -> tuple[MethodCandidate, ...]:
    """A described rule of thumb → 条件 → 预期 → 适用环境 → 反例, unverified."""

    compact = re.sub(r"[ \t]+", "", str(text or "")).strip()
    if not compact:
        return ()
    if _METHOD_CUE_RE.search(compact) is None and _GENERALIZER_RE.search(compact) is None:
        return ()
    # 去掉句尾的提问，只在陈述部分里找规律。
    statement = compact
    cue = _METHOD_CUE_RE.search(statement)
    if cue is not None:
        statement = statement[cue.end():] if cue.group(0).endswith("是") else statement[cue.start():]
    statement = statement.strip("，,：:")
    sentences = [part for part in re.split(r"[。；;？！?\n]", statement) if part.strip()]
    candidates: list[MethodCandidate] = []
    applicability_hits = tuple(dict.fromkeys(_APPLICABILITY_RE.findall(compact)))
    applicability = "、".join(applicability_hits) if applicability_hits else "未说明（首次提取）"
    counterexamples = tuple(
        dict.fromkeys(match.group("ce").strip("，,") for match in _COUNTEREXAMPLE_RE.finditer(compact))
    )
    for sentence in sentences:
        body = _QUESTION_TAIL_RE.sub("", sentence) if _QUESTION_TAIL_RE.search(sentence) and "，" in sentence else sentence
        for pattern in _CONDITION_EXPECTATION_RES:
            match = pattern.search(body)
            if match is None:
                continue
            condition = match.group("cond").strip("，,")
            expectation = match.group("exp").strip("，,")
            expectation = _QUESTION_TAIL_RE.sub("", expectation).strip("，,") or expectation
            if len(condition) < 2 or len(expectation) < 2:
                continue
            candidate = MethodCandidate(
                condition=condition,
                expectation=expectation,
                applicability=applicability,
                counterexamples=counterexamples,
                status=METHOD_STATUS_UNVERIFIED,
                source_text=sentence[:160],
            )
            if candidate not in candidates:
                candidates.append(candidate)
            break
    return tuple(candidates)


# --- 盘感 → 竞争解释 ---------------------------------------------------------------
_MARKET_FEEL_TABLE: tuple[tuple[re.Pattern[str], tuple[Hypothesis, ...]], ...] = (
    # 先判「回流 / 二波」：「龙头连板断了以后板块还有一次回流吗」问的是分歧之后走哪条路，
    # 不是「龙头为什么不涨」；龙头模式放在它后面，免得先抢走。
    (
        re.compile(r"分歧.{0,8}(?:回流|二波|再来|加速|还能|之后|以后)|(?:回流|二波|再来一波).{0,16}(?:吗|会不会|能不能|也会这样|会这样)"),
        (
            Hypothesis("分歧后回流", "分歧日换手充分，次日资金回流形成二波", ("分歧日成交额", "龙头是否守住关键位", "次日双红是否回归", "指数量能")),
            Hypothesis("分歧转退潮", "分歧演变成一致走弱，回流不出现", ("连续无双红天数", "涨停家数下台阶", "板块成交额环比")),
        ),
    ),
    (
        re.compile(r"龙头.{0,8}(?:不涨|滞涨|涨不动|掉队|歇|不动|断板|断了|翻绿|走弱)|(?:不涨|滞涨|断板).{0,6}龙头"),
        (
            Hypothesis(
                "主线退潮",
                "龙头停涨是板块整体资金撤离的一部分：宽度收缩、双红消失、成交额下降",
                ("板块涨停家数与双红是否连续消失", "板块成交额环比", "跟风股是否同步走弱", "市场阶段标签"),
            ),
            Hypothesis(
                "高低切 / 内部轮动",
                "龙头休整、二线补涨，板块宽度与成交额不减，主线仍在",
                ("板块宽度（上涨家数、涨停家数）是否维持", "补涨股换手与涨幅", "板块成交额是否持平或放大"),
            ),
            Hypothesis(
                "龙头个股自身事件",
                "龙头停涨来自个股层面：巨量换手、减持、停牌核查、龙虎榜席位变化，与板块无关",
                ("龙头换手率与成交额", "个股公告 / 龙虎榜", "同板块其他核心股是否照常"),
            ),
            Hypothesis(
                "大盘阶段拖累",
                "全市场进入分歧或缩量阶段，龙头只是随大盘歇火",
                ("全市场涨跌家数与成交额环比", "指数分歧日标记", "其他主线是否同步走弱"),
            ),
        ),
    ),
    (
        re.compile(r"(?:主线|板块|题材|这条线|这个方向|线).{0,10}(?:退潮|走弱|结束|凉了|不行了|要完|见顶|到头)|(?:退潮|走弱|结束|见顶).{0,6}(?:了吗|没有|吗)"),
        (
            Hypothesis("退潮", "主线进入退潮：双红连续消失、涨停家数下台阶、龙头不再新高", ("连续无双红天数", "涨停家数逐日变化", "龙头是否创新高", "板块成交额环比")),
            Hypothesis("分歧后强轮动", "主升后的第一次分歧，资金在板块内部换手，宽度未收缩", ("分歧日成交额是否放大", "次日双红是否回归", "梯队是否完整")),
            Hypothesis("弱轮动 / 缩量休整", "板块缩量横盘，既未退潮也未加速，等待新催化", ("成交额环比", "涨跌家数比", "是否有新催化事件")),
        ),
    ),
    (
        re.compile(r"缩量.{0,6}(?:涨|新高|上涨|拉升|反弹)|(?:涨|新高).{0,4}缩量"),
        (
            Hypothesis("惜售式缩量（健康）", "筹码锁定、卖压小，缩量上涨可延续", ("涨家数是否同步扩大", "涨停家数", "换手率下降但价格稳", "主线连续性")),
            Hypothesis("承接不足（危险）", "买盘退坡而卖盘尚未出现，缩量是需求消失的前兆", ("成交额环比连续下降", "跌停家数与炸板率", "龙头封板质量", "指数量能")),
        ),
    ),
    (
        re.compile(r"放量.{0,6}(?:滞涨|不涨|大阴|上影|回落|下跌)|(?:滞涨|大阴).{0,4}放量"),
        (
            Hypothesis("高位换手分歧（可延续）", "新增资金接力、老资金兑现，分歧后可再度一致", ("次日承接与双红是否回归", "成交额环比", "龙头封板 / 换手")),
            Hypothesis("出货 / 阶段见顶", "放量是资金撤离，随后宽度与成交额一起收缩", ("此后成交额是否连续下降", "涨停家数是否下台阶", "跟风股是否补跌")),
        ),
    ),
    (
        re.compile(r"补涨|高低切"),
        (
            Hypothesis("高低切承接（主线延续）", "低位补涨股承接，主线借高低切延续", ("龙头是否只是休整", "补涨股换手与持续性", "板块宽度是否扩大")),
            Hypothesis("补涨即尾声", "补涨是最后一轮扩散，随后整体退潮", ("龙头是否已放量走弱", "市场成交额环比", "板块双红是否消失")),
        ),
    ),
    (
        re.compile(r"(?:情绪|市场).{0,6}(?:冰点|见底|极端|要反弹|反转)"),
        (
            Hypothesis("情绪冰点反转", "跌停 / 炸板极端值后出现修复", ("涨停与跌停家数比", "连板高度", "成交额是否止跌", "涨跌家数")),
            Hypothesis("弱势延续", "极端值后仍无新主线，继续缩量下行", ("是否出现新主线双红", "成交额环比", "涨停家数是否回升")),
        ),
    ),
    (
        re.compile(r"不对劲|氛围不对|感觉要出问题|有点问题|不太对|哪里不对"),
        (
            Hypothesis("阶段切换", "市场从一致进入分歧或退潮阶段", ("涨跌家数", "成交额环比", "市场阶段标签")),
            Hypothesis("结构分化", "指数与个股、主线与跟风背离，整体没变但结构在变", ("指数涨跌 vs 涨跌家数", "主线双红 vs 跟风股表现")),
            Hypothesis("事件性扰动", "外盘 / 消息 / 个股事件的一次性冲击", ("隔夜外盘", "当日新闻事件", "受影响板块是否局限")),
        ),
    ),
)


def translate_market_feel(text: str) -> tuple[Hypothesis, ...]:
    """盘感 → competing explanations + discriminating observables.

    Returns the hypotheses of the first matching market-feel pattern, or ``()``.
    The point is to stop the system from merely rephrasing "龙头不涨是不是退潮":
    the frame then carries what would actually decide the question.
    """

    compact = re.sub(r"\s+", "", str(text or ""))
    if not compact:
        return ()
    for pattern, hypotheses in _MARKET_FEEL_TABLE:
        if pattern.search(compact) is not None:
            return hypotheses
    return ()


# --- 公司代称 -----------------------------------------------------------------------
COMPANY_NICKNAMES: Mapping[str, str] = MappingProxyType(
    {
        "宁王": "宁德时代",
        "迪王": "比亚迪",
        "茅王": "贵州茅台",
        "寒王": "寒武纪",
        "药明": "药明康德",
        "东财": "东方财富",
        "立讯": "立讯精密",
        "汇川": "汇川技术",
        "隆基": "隆基绿能",
        "旭创": "中际旭创",
        "海光": "海光信息",
        "中芯": "中芯国际",
    }
)
_NICKNAME_RE = re.compile("|".join(sorted(map(re.escape, COMPANY_NICKNAMES), key=len, reverse=True)))
_NAME_FORMING_PREFIXES = frozenset("上东南西北中新大小老华国长金")


def resolve_nicknames(text: str) -> tuple[tuple[str, str], ...]:
    """Market slang → canonical company names, in order of appearance, deduped.

    An alias that is just the head of its own canonical name in the text
    (「隆基绿能」contains「隆基」) resolves to the same canonical and is deduped;
    aliases embedded in an unrelated longer CJK run are skipped.
    """

    compact = re.sub(r"\s+", "", str(text or ""))
    if not compact:
        return ()
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for match in _NICKNAME_RE.finditer(compact):
        alias = match.group(0)
        canonical = COMPANY_NICKNAMES[alias]
        tail = compact[match.end():]
        if canonical.startswith(alias) and tail.startswith(canonical[len(alias):]):
            alias_text = canonical
        else:
            alias_text = alias
            # 「东财」嵌在「东财转债」里仍是同一家；但「上海光…」里的「海光」不是海光信息。
            # 中文没有词边界，只拦常见的构名前缀，不拦「和迪王」这类连词。
            if match.start() > 0 and compact[match.start() - 1] in _NAME_FORMING_PREFIXES:
                continue
        if canonical in seen:
            continue
        seen.add(canonical)
        pairs.append((alias_text, canonical))
    return tuple(pairs)


__all__ = [
    "COMPANY_NICKNAMES",
    "Hypothesis",
    "METHOD_STATUS_UNVERIFIED",
    "MaterialRef",
    "MessageParts",
    "MethodCandidate",
    "PRIOR_JUDGEMENT_PREMISE",
    "RESOLUTION_SOURCES",
    "ResolvedValue",
    "UserTask",
    "extract_method_candidates",
    "extract_user_premises",
    "conversation_context_material_unrecoverable",
    "detect_reposted_material_gap",
    "material_from_text",
    "material_id_for",
    "materials_in_conversation",
    "rebind_material_from_text",
    "references_material",
    "resolve_nicknames",
    "split_user_message",
    "translate_market_feel",
]
