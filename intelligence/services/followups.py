"""回答后的「猜你想问」追问卡片（KC-12 / 选角设计稿）。

foresight 是盘面每日主动发问；本模块是回答驱动的下一问。编排只读
``FollowupState``：先选角、再填槽，模型只润色措辞。不吸收 Knevo 的
``suggest_options`` 工具，不把 D3 二阶导写进芯片。
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Protocol

from intelligence.services import answer_model, llm_refine
from intelligence.services.track_contract import parse_track_intent

FOLLOWUP_TYPES = ["evidence", "counter", "alternative", "recheck", "migration"]
TYPE_LABELS = {
    "evidence": "证据加深",
    "counter": "反证验证",
    "alternative": "替代标的",
    "recheck": "盘面回检",
    "migration": "题材迁移",
    "gap": "缺口补齐",
    "continue": "同一条件再对",
}

FETCH_ENV_FLAG = "FINANCE_FOLLOWUPS"
_METHODOLOGY_TERMS = (
    "错因",
    "归因分类",
    "检索规则",
    "五维排序",
    "四分类判据",
    "框架怎么回测",
)
_WAITING_PREFIXES = ("等待", "需等", "待验证")
_CODE_RE = re.compile(r"\d{6}")
_FIRST_ORDER_BANNED = ("双红", "近几日涨停热度")


@dataclass
class Followup:
    question: str
    type: str
    rationale: str = ""
    type_label: str = ""
    source: str = ""
    label: str = ""
    full_prompt: str = ""
    angle: str = ""

    def __post_init__(self) -> None:
        if not self.type_label:
            self.type_label = TYPE_LABELS.get(self.type, self.type)
        if not self.full_prompt:
            self.full_prompt = self.question
        if not self.question:
            self.question = self.full_prompt
        self.label = _compact_label(self.label or self.full_prompt)


@dataclass
class FollowupResult:
    followups: list[Followup] = field(default_factory=list)
    llm_used: bool = False
    llm_provider: str | None = None
    warnings: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(
            {
                "followups": [asdict(item) for item in self.followups],
                "llm_used": self.llm_used,
                "llm_provider": self.llm_provider,
                "warnings": self.warnings,
            },
            ensure_ascii=False,
            indent=2,
        )


@dataclass(frozen=True)
class AlternativeItem:
    name: str
    reason: str = ""
    source: str = "none"


@dataclass(frozen=True)
class FollowupState:
    subject: str = ""
    question: str = ""
    question_kind: str = "other"
    open_gaps: tuple[str, ...] = ()
    spec_gaps: tuple[str, ...] = ()
    spec_triggers: tuple[str, ...] = ()
    spec_next_actions: tuple[str, ...] = ()
    alternatives: tuple[AlternativeItem, ...] = ()
    bottlenecks: tuple[str, ...] = ()
    status: str = "completed"
    no_action_room: bool = False
    produced_framework: bool = False
    listed_names: frozenset[str] = field(default_factory=frozenset)
    skip_types: frozenset[str] = field(default_factory=frozenset)
    parent_followup_prompt: str | None = None
    same_bind: bool = False
    standing_date: str = ""
    question_type: str = ""
    market_watch_pack_present: bool = False


class FollowupComposer(Protocol):
    def compose(self, state: FollowupState, *, polish: bool = False) -> FollowupResult: ...


class AngleComposer:
    def compose(self, state: FollowupState, *, polish: bool = False) -> FollowupResult:
        return compose_followups(state, polish=polish)


class NullComposer:
    def compose(self, state: FollowupState, *, polish: bool = False) -> FollowupResult:
        _ = (state.subject, state.question, polish)
        return FollowupResult()


def active_composer() -> FollowupComposer:
    if os.environ.get(FETCH_ENV_FLAG, "1") == "0":
        return NullComposer()
    return AngleComposer()


def compute_no_action_room(
    *,
    open_gaps: tuple[str, ...] = (),
    spec_gaps: tuple[str, ...] = (),
    status: str = "completed",
    spec_next_actions: tuple[str, ...] = (),
) -> bool:
    if any(str(item).strip() for item in (*open_gaps, *spec_gaps)):
        return True
    if status in {"partial", "degraded"}:
        return True
    return any(str(action).startswith(_WAITING_PREFIXES) for action in spec_next_actions)


def infer_question_kind(
    question: str,
    subject: str,
    *,
    subject_kind: str = "",
    enable_methodology: bool = False,
) -> str:
    if parse_track_intent(question):
        return "track"
    text = str(subject or "").strip()
    if text:
        blob = f"{text}{question}"
        if subject_kind in {"company", "stock"} or _CODE_RE.search(blob):
            return "stock"
        return "theme"
    if enable_methodology and any(term in str(question or "") for term in _METHODOLOGY_TERMS):
        return "methodology"
    return "other"


def project_continuous_state(
    *,
    subject: str,
    question: str,
    open_gaps: tuple[str, ...] = (),
    status: str = "completed",
    subject_kind: str = "",
    parent_followup_prompt: str | None = None,
    same_bind: bool = False,
    standing_date: str = "",
    question_type: str = "",
    market_watch_pack_present: bool = False,
) -> FollowupState:
    kind = infer_question_kind(
        question, subject, subject_kind=subject_kind, enable_methodology=False
    )
    skip = frozenset({"recheck"} if parse_track_intent(question) else ())
    cleaned = tuple(str(gap).strip() for gap in open_gaps if str(gap).strip())
    mapped_status = status if status in {"completed", "partial", "degraded"} else "degraded"
    return FollowupState(
        subject=str(subject or "").strip(),
        question=str(question or "").strip(),
        question_kind=kind,
        open_gaps=cleaned,
        status=mapped_status,
        no_action_room=compute_no_action_room(
            open_gaps=cleaned, status=mapped_status
        ),
        skip_types=skip,
        parent_followup_prompt=parent_followup_prompt,
        same_bind=same_bind,
        standing_date=str(standing_date or "").strip(),
        question_type=str(question_type or "").strip(),
        market_watch_pack_present=market_watch_pack_present,
    )


def project_answer_spec_state(
    answer_spec: answer_model.AnswerSpec,
    *,
    subject: str | None = None,
    question: str = "",
) -> FollowupState:
    anchor = (
        str(subject or "").strip()
        or str(answer_spec.research_spec.theme or "").strip()
        or str(answer_spec.presentation_title or "").strip()
        or "当前研究主题"
    )
    spec_gaps = tuple(_sentence(gap.text) for gap in answer_spec.gaps if _sentence(gap.text))
    spec_triggers = tuple(
        _sentence(trigger.text) for trigger in answer_spec.triggers if _sentence(trigger.text)
    )
    spec_next_actions = tuple(
        _sentence(action) for action in answer_spec.next_actions if _sentence(action)
    )
    alternatives: list[AlternativeItem] = []
    listed: set[str] = set()
    for company in answer_spec.company_table:
        name = str(company.company or "").strip()
        if not name or name == anchor:
            continue
        alternatives.append(
            AlternativeItem(name=name, reason=str(company.chain_stage or ""), source="company_table")
        )
        listed.add(name)
    kind = infer_question_kind(question, anchor, enable_methodology=True)
    skip = frozenset({"recheck"} if parse_track_intent(question) or kind == "track" else ())
    return FollowupState(
        subject=anchor,
        question=str(question or "").strip(),
        question_kind=kind,
        spec_gaps=spec_gaps,
        spec_triggers=spec_triggers,
        spec_next_actions=spec_next_actions,
        alternatives=tuple(alternatives),
        status="completed",
        no_action_room=compute_no_action_room(
            spec_gaps=spec_gaps,
            spec_next_actions=spec_next_actions,
        ),
        produced_framework=kind == "methodology",
        listed_names=frozenset(listed),
        skip_types=skip,
    )


def project_ask_state(
    question: str,
    *,
    subject: str | None = None,
    open_gaps: tuple[str, ...] = (),
    parent_followup_prompt: str | None = None,
    alternatives: tuple[tuple[str, str], ...] = (),
    bottlenecks: tuple[str, ...] = (),
) -> FollowupState:
    """``alternatives``/``bottlenecks`` 来自 ask 的 D3 结构对象（AskResult.d3_*）。

    spec 2026-08-17 §5：P0 行进 alternatives(source=d3_p0)，P2 词进 bottlenecks，
    公司名进 listed_names——B 槽由此点名下一跳，且不得把已列名单当新发现。
    """

    # 分类与展示分离：主语未知时让 infer 看到空主语（否则永远判不出
    # methodology/other），展示兜底用「该问题」。不切原句——[:16] 曾把
    # 「…2026-08-18…」拦腰切成「2026-08-1」直接进用户可见的追问。
    subject_clean = str(subject or "").strip()
    kind = infer_question_kind(question, subject_clean, enable_methodology=True)
    anchor = subject_clean or "该问题"
    skip = frozenset({"recheck"} if kind == "track" or parse_track_intent(question) else ())
    cleaned = tuple(str(gap).strip() for gap in open_gaps if str(gap).strip())
    alt_items = tuple(
        AlternativeItem(
            name=str(name).strip(),
            reason=str(note or "").strip(),
            source="d3_p0",
        )
        for name, note in alternatives
        if str(name).strip()
    )
    cleaned_bottlenecks = tuple(
        str(term).strip() for term in bottlenecks if str(term).strip()
    )
    return FollowupState(
        subject=anchor,
        question=str(question or "").strip(),
        question_kind=kind,
        open_gaps=cleaned,
        alternatives=alt_items,
        bottlenecks=cleaned_bottlenecks,
        no_action_room=compute_no_action_room(open_gaps=cleaned),
        produced_framework=kind == "methodology",
        listed_names=frozenset(item.name for item in alt_items),
        skip_types=skip,
        parent_followup_prompt=parent_followup_prompt,
    )


def _gaps(state: FollowupState) -> tuple[str, ...]:
    return tuple(
        str(item).strip()
        for item in (*state.open_gaps, *state.spec_gaps)
        if str(item).strip()
    )


def select_angles(state: FollowupState) -> tuple[str, ...]:
    """只返回有序角度，长度 2–4，不生成文案。"""
    gaps = _gaps(state)
    has_gaps = bool(gaps)
    kind = state.question_kind
    skip_a = (kind == "methodology" or state.produced_framework) and not has_gaps
    slots: list[str] = []
    if has_gaps:
        slots.extend(["A"] * min(2, len(gaps)))
    elif not skip_a:
        slots.append("A")
    if kind != "methodology" and (
        state.alternatives or state.bottlenecks or kind in {"stock", "theme"}
    ):
        slots.append("B")
    if state.no_action_room:
        slots.append("C")
    want_d_multi = (kind == "methodology" or state.produced_framework) and not has_gaps
    want_d_one = bool(state.spec_triggers) or (
        kind in {"stock", "theme", "other"} and not has_gaps
    )
    if want_d_multi:
        slots.extend(["D", "D"])
        if len(slots) < 3:
            slots.append("D")
    elif want_d_one and not state.no_action_room:
        slots.append("D")
    while len(slots) < 2:
        padded = False
        for extra in ("B", "D", "C"):
            if extra == "B" and kind == "methodology":
                continue
            slots.append(extra)
            padded = True
            break
        if not padded:
            slots.append("D")
    return tuple(slots[:4])


def _subject(state: FollowupState) -> str:
    return state.subject.strip() or "该问题"


def _is_echo(state: FollowupState, prompt: str) -> bool:
    parent = re.sub(r"\s+", "", str(state.parent_followup_prompt or ""))
    return bool(parent) and parent == re.sub(r"\s+", "", prompt)


def _contains_banned(prompt: str) -> bool:
    return any(term in prompt for term in _FIRST_ORDER_BANNED)


def _followup(
    *,
    prompt: str,
    type_: str,
    angle: str,
    label: str,
    rationale: str,
    source: str = "",
) -> Followup | None:
    if not prompt.strip() or _contains_banned(prompt):
        return None
    return Followup(
        prompt,
        type_,
        rationale,
        source=source,
        label=label,
        full_prompt=prompt,
        angle=angle,
    )


def fill_slots(state: FollowupState, angles: tuple[str, ...]) -> list[Followup]:
    subject = _subject(state)
    gaps = list(_gaps(state))
    alts = list(state.alternatives)
    bottlenecks = [str(item).strip() for item in state.bottlenecks if str(item).strip()]
    triggers = [str(item).strip() for item in state.spec_triggers if str(item).strip()]
    actions = [str(item).strip() for item in state.spec_next_actions if str(item).strip()]
    executable = [item for item in actions if not item.startswith(_WAITING_PREFIXES)]
    d_index = 0
    items: list[Followup] = []
    for angle in angles:
        built = _fill_one(
            state,
            angle,
            subject,
            gaps=gaps,
            alts=alts,
            bottlenecks=bottlenecks,
            triggers=triggers,
            executable=executable,
            d_index=d_index,
        )
        if angle == "D":
            d_index += 1
        if built is None or _is_echo(state, built.full_prompt):
            built = _conservative(state, angle, subject, used_types={item.type for item in items})
        if built is None or _is_echo(state, built.full_prompt):
            continue
        if built.type in state.skip_types:
            if built.type == "recheck":
                built.type = "counter"
                built.type_label = TYPE_LABELS["counter"]
            else:
                continue
        items.append(built)
    return items


def _fill_one(
    state: FollowupState,
    angle: str,
    subject: str,
    *,
    gaps: list[str],
    alts: list[AlternativeItem],
    bottlenecks: list[str],
    triggers: list[str],
    executable: list[str],
    d_index: int = 0,
) -> Followup | None:
    if angle == "A":
        if gaps:
            text = gaps.pop(0)
            prompt = (
                f"关于{subject}，上一轮「{text}」未完成核验：请只针对这一项"
                "补齐证据，给出可核对的来源与数据日期。"
            )
            return _followup(
                prompt=prompt,
                type_="gap",
                angle="A",
                label=f"补齐：{text}",
                rationale="上一轮降级缺口的直接回补",
                source="gap",
            )
        return _followup(
            prompt=f"{subject}目前最硬的一条公司级证据是什么，出自哪份公告或研报？",
            type_="evidence",
            angle="A",
            label="核对最硬证据",
            rationale="完整结论也打最薄一层证据核验",
        )
    if angle == "B":
        if state.question_kind == "methodology":
            return None
        if alts:
            item = alts.pop(0)
            reason = item.reason or item.source
            prompt = (
                f"除了{subject}，下一跳应先核{item.name}的哪条订单/认证/产能证据？"
                "不要重复列出已有替代名单。"
            )
            return _followup(
                prompt=prompt,
                type_="alternative",
                angle="B",
                label=f"下一跳：{item.name}",
                rationale=f"去核已选出的下一跳（{reason}），不是发现新票",
                source=item.source,
            )
        if bottlenecks:
            word = bottlenecks.pop(0)
            prompt = (
                f"{subject}若不是最优表达，{word}这一环谁更接近订单或产能约束？"
            )
            return _followup(
                prompt=prompt,
                type_="alternative",
                angle="B",
                label=f"瓶颈：{word}",
                rationale="芯片只问瓶颈下一跳，不重念 D3 名单",
            )
        listed = "、".join(sorted(state.listed_names)) if state.listed_names else ""
        prompt = f"除了当前已点名的标的，{subject}同链暴露度相近的下一跳应先核谁的订单或认证？不要把已有名单当成新发现。"
        if listed:
            prompt += f"已出现、不得当作新发现：{listed}。"
        return _followup(
            prompt=prompt,
            type_="alternative",
            angle="B",
            label="同链下一跳",
            rationale="连续对话第一期无 D3 结构，只问下一跳不点新票",
        )
    if angle == "C":
        type_ = "counter" if "recheck" in state.skip_types else "recheck"
        if executable:
            action = executable.pop(0)
            return _followup(
                prompt=f"下一步如何执行并核验：{action}？",
                type_=type_,
                angle="C",
                label=action,
                rationale="落实本轮验证路径",
                source="next_action",
            )
        return _followup(
            prompt=f"若{subject}现在不能动手，哪个可观察信号出现后才进入可执行窗口？",
            type_=type_,
            angle="C",
            label="等到什么信号",
            rationale="无操作空间时只问窗口，不问现在该买吗",
        )
    if angle == "D":
        if triggers:
            trigger = triggers.pop(0)
            return _followup(
                prompt=f"哪些数据能验证或证伪这个条件：{trigger}？",
                type_="counter",
                angle="D",
                label="证伪条件",
                rationale="来自本轮触发或降级条件",
                source="trigger",
            )
        variants = (
            f"出现哪些反证应下调对{subject}的判断？",
            f"哪个失效条件成立后应停用对{subject}的这套判断？",
            f"回测时哪些样本外窗口会推翻对{subject}的当前规则？",
        )
        return _followup(
            prompt=variants[d_index % len(variants)],
            type_="counter",
            angle="D",
            label="证伪条件",
            rationale="完整答案的默认证伪件",
        )
    return None


def _conservative(
    state: FollowupState,
    angle: str,
    subject: str,
    *,
    used_types: set[str],
) -> Followup | None:
    if angle == "B" and state.question_kind == "methodology":
        angle = "D"
    if angle == "C":
        return _followup(
            prompt=f"若{subject}现在不能动手，哪个可观察信号出现后才进入可执行窗口？",
            type_="counter" if "recheck" in state.skip_types else "recheck",
            angle="C",
            label="等到什么信号",
            rationale="conservative 窗口",
        )
    if angle == "A" and "gap" not in used_types:
        return _followup(
            prompt=f"{subject}目前最硬的一条公司级证据是什么，出自哪份公告或研报？",
            type_="evidence",
            angle="A",
            label="核对最硬证据",
            rationale="conservative 证据",
        )
    return _followup(
        prompt=f"出现哪些反证应下调对{subject}的判断？",
        type_="counter",
        angle="D",
        label="证伪条件",
        rationale="conservative 证伪",
    )


def should_emit_same_bind(state: FollowupState) -> bool:
    subject = _subject(state)
    if not subject or subject == "该问题":
        return False
    standing = str(state.standing_date or "").strip()
    if state.same_bind and standing:
        return True
    qtype = str(state.question_type or "").strip()
    if qtype == "market_watch":
        return bool(state.market_watch_pack_present and standing)
    if qtype in {"theme_track", "trade_advice"} and standing:
        return True
    return False


def build_same_bind_followup(state: FollowupState) -> Followup | None:
    if not should_emit_same_bind(state):
        return None
    subject = _subject(state)
    standing = str(state.standing_date or "").strip()
    qtype = str(state.question_type or "").strip()
    if qtype == "theme_track":
        prompt = (
            f"自 {standing} 之后，{subject}只报变化和四态对照，不要重跑全景。"
        )
    elif qtype == "market_watch":
        prompt = f"同一天盘面用四袋再对一次，只报相对 {standing} 的变化。"
    else:
        prompt = (
            f"按我刚才的{subject}条件，用最新价再对一次，只报相对 {standing} 的变化。"
        )
    if _is_echo(state, prompt):
        return None
    from intelligence.services.stance_pack import bind_id_for

    return Followup(
        question=prompt,
        type="continue",
        rationale="同一绑定换时刻或刷新现价",
        label="同一条件再对",
        full_prompt=prompt,
        angle="",
        source=f"same_bind:{bind_id_for(qtype or state.question_kind, subject, standing)}",
    )


def compose_followups(
    state: FollowupState,
    *,
    polish: bool = False,
    llm_model: str | None = None,
    llm_timeout: int = 60,
) -> FollowupResult:
    if state.status == "failed":
        return FollowupResult(warnings=["followup_skipped_failed_turn"])
    result = FollowupResult()
    try:
        angles = select_angles(state)
        items = fill_slots(state, angles)
        if len(items) < 2:
            subject = _subject(state)
            for extra in ("A", "D"):
                pad = _conservative(state, extra, subject, used_types={item.type for item in items})
                if pad is None or _is_echo(state, pad.full_prompt):
                    continue
                if pad.type in state.skip_types and pad.type != "recheck":
                    continue
                items.append(pad)
                if len(items) >= 2:
                    break
        chip = build_same_bind_followup(state)
        if chip is not None and not _is_echo(state, chip.full_prompt):
            items = [chip, *[item for item in items if item.type != "continue"]]
        result.followups = items[:4]
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(f"followup_compose_failed:{exc}")
        return result
    if polish and result.followups:
        polished, provider, warn = _polish_followups(
            result.followups, llm_model, llm_timeout
        )
        if polished:
            result.followups = polished
            result.llm_used = True
            result.llm_provider = provider
        elif warn:
            result.warnings.append(warn)
    return result


def _polish_followups(
    items: list[Followup],
    model: str | None,
    timeout: int,
) -> tuple[list[Followup], str | None, str]:
    payload = {
        "followups": [
            {"label": item.label, "full_prompt": item.full_prompt, "type": item.type, "angle": item.angle}
            for item in items
        ]
    }
    system = (
        "你只改措辞。每条保持原 type 与 angle，不得增删条数。"
        "label 最多 20 字，full_prompt 保持用户口吻。"
        '只输出 JSON：{"followups":[{"label":"...","full_prompt":"...","type":"...","angle":"..."}]}'
    )
    content, provider, reason = llm_refine.complete(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        model_override=model,
        timeout=timeout,
        temperature=0.3,
    )
    provider_name = provider.name if provider else None
    warn = f"followup_polish_dropped:{reason or 'LLM 不可用'}"
    if content is None:
        return [], provider_name, warn
    obj = llm_refine._extract_json(content)
    raw = obj.get("followups") if isinstance(obj, dict) else None
    if not isinstance(raw, list) or len(raw) != len(items):
        return [], provider_name, warn
    out: list[Followup] = []
    for original, item in zip(items, raw):
        if not isinstance(item, dict):
            return [], provider_name, warn
        if str(item.get("type") or original.type).strip() != original.type:
            return [], provider_name, warn
        if str(item.get("angle") or original.angle).strip() != original.angle:
            return [], provider_name, warn
        prompt = str(item.get("full_prompt") or item.get("question") or original.full_prompt).strip()
        label = str(item.get("label") or original.label).strip()
        if not prompt:
            return [], provider_name, warn
        out.append(
            Followup(
                prompt,
                original.type,
                original.rationale,
                source=original.source,
                label=label,
                full_prompt=prompt,
                angle=original.angle,
            )
        )
    return out, provider_name, ""


def gap_mirror_followups(
    subject: str,
    gaps: tuple[str, ...] | list[str],
    *,
    limit: int = 3,
) -> FollowupResult:
    """A 槽填充器：结构化缺口镜像。行为与既有单测兼容。"""
    subject = (subject or "").strip() or "该问题"
    cleaned = [str(gap).strip() for gap in gaps]
    items: list[Followup] = []
    for text in [gap for gap in cleaned if gap][: max(0, limit)]:
        items.append(
            Followup(
                question=(
                    f"关于{subject}，上一轮「{text}」未完成核验：请只针对这一项"
                    "补齐证据，给出可核对的来源与数据日期。"
                ),
                type="gap",
                rationale="上一轮降级缺口的直接回补",
                label=f"补齐：{text}",
                angle="A",
                source="gap",
            )
        )
    return FollowupResult(followups=items, llm_used=False)


def generate_followups(
    question: str,
    *,
    matched_theme: str | None = None,
    answer_excerpt: str = "",
    n: int = 4,
    llm_model: str | None = None,
    llm_timeout: int = 60,
    use_llm: bool = False,
    open_gaps: tuple[str, ...] = (),
    parent_followup_prompt: str | None = None,
    alternatives: tuple[tuple[str, str], ...] = (),
    bottlenecks: tuple[str, ...] = (),
) -> FollowupResult:
    """选题走 compose；默认不润色。显式 ``use_llm=True`` 时 LLM 只改措辞。条数合同 2–4。"""
    _ = answer_excerpt
    state = project_ask_state(
        question,
        subject=matched_theme,
        open_gaps=open_gaps,
        parent_followup_prompt=parent_followup_prompt,
        alternatives=alternatives,
        bottlenecks=bottlenecks,
    )
    if os.environ.get(FETCH_ENV_FLAG, "1") == "0":
        return NullComposer().compose(state, polish=False)
    result = compose_followups(
        state,
        polish=use_llm,
        llm_model=llm_model,
        llm_timeout=llm_timeout,
    )
    cap = 4 if n > 4 else n
    if cap >= 2:
        result.followups = result.followups[:cap]
    return result


def generate_answer_spec_followups(
    answer_spec: answer_model.AnswerSpec,
    *,
    subject: str | None = None,
    n: int = 4,
    question: str = "",
) -> FollowupResult:
    state = project_answer_spec_state(answer_spec, subject=subject, question=question)
    result = active_composer().compose(state, polish=False)
    gap_by_text = {
        _sentence(gap.text): f"gap:{gap.claim_id}" for gap in answer_spec.gaps
    }
    trigger_by_text = {
        _sentence(trigger.text): f"trigger:{trigger.claim_id}"
        for trigger in answer_spec.triggers
    }
    for item in result.followups:
        for text, source in gap_by_text.items():
            if text and text in item.full_prompt:
                item.source = source
                break
        else:
            for text, source in trigger_by_text.items():
                if text and text in item.full_prompt:
                    item.source = source
                    break
    cap = 4 if n > 4 else n
    if cap >= 2:
        result.followups = result.followups[:cap]
    return result


def _sentence(value: str) -> str:
    return str(value or "").strip().rstrip("。！？?!；;")


def _compact_label(value: str) -> str:
    cleaned = re.sub(r"\s+", "", str(value or "").strip())
    cleaned = cleaned.rstrip("。！？?!；;")
    return cleaned[:20] or "继续研究"
