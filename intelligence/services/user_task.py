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
from dataclasses import dataclass, field
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
    "material_from_text",
    "material_id_for",
    "materials_in_conversation",
    "references_material",
    "resolve_nicknames",
    "split_user_message",
    "translate_market_feel",
]
