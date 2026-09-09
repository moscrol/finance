"""研究项目（ResearchProject）：会话级研究状态的只读投影（09 连续研究）。

它解决什么：同一个题材研究到第二天，系统要知道「已解决什么、还缺什么、上次哪条判断
被裁决成什么」，而不是让用户重贴背景。做法是把**已有对象**投影成一份状态：

- ``ConversationStore``：每轮的问句、``turn_intent``（对象 / 题型）、``citations``、
  ``followups``（带 kind / inherits）、用户消息上的 ``continuation``（本轮延续自哪张卡）。
- ``RunStore``：``run.json``（状态 / 数据截止 ``source_date`` / 产物 / degrades）、
  ``report.json``（``task_frame.subject`` 回退、``warnings``）。
- 判断轨台账：``checkpoints.jsonl`` + ``verdicts.jsonl``（按 ``session_id`` 关联本会话，
  再按对象召回；每条取最新裁决）。

三条纪律：
1. **不另开台账**——本模块零写入；写入者仍是各自模块。
2. **不摘抄聊天**——正文只取上轮结论标题（首行 ≤ 80 字）和计数；整段回答留在消息里。
3. **先验不是市场事实**——渲染块尾固定使用要求；易变项以本轮检索为准。

本模块只 import ``userspace`` 与 ``services``，不 import ``runtime``（layer_audit）。
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date as date_cls
from pathlib import Path
from typing import Any

from intelligence import userspace
from intelligence.services import checkpoints as checkpoints_svc
from intelligence.services.checkpoint_recall import (
    latest_verdicts,
    select_relevant_checkpoints,
)
from intelligence.services.conversation_store import ConversationStore, Message
from intelligence.services.followups import (
    KIND_LABELS,
    followup_kind,
    prior_kind_rank,
)
from intelligence.services.run_store import RunStore

HEADLINE_CHARS = 80
PROMPT_BLOCK_MAX_CHARS = 600
RELATED_CONVERSATION_SCAN = 40
TRIGGER_LIMIT = 5
OPEN_QUESTION_LIMIT = 5

TRIGGER_STATUS_LABEL = {
    "hit": "命中",
    "miss": "落空",
    "partial": "半对",
    "unverifiable": "暂无法判定",
    "due": "到期待判",
    "pending": "跟踪中",
}
_GAP_LABEL_PREFIX = "补齐："
# 缺口镜像卡的 full_prompt 形如「关于X，上一轮「<缺口>」未完成核验：…」；label 会被压到 20 字并去空格，
# 所以先从 full_prompt 取原文，label 只作回退。
_GAP_PROMPT_RE = re.compile(r"上一轮「(.+?)」未完成核验")
# 去掉行首的标题 / 引用 / 列表记号（含「1. 」「1）」这类编号），但不吃掉「1.6T」这类数字正文。
_MARKDOWN_LEAD = re.compile(r"^(?:[\s#>*•\-]+|\d+[.、)）]\s*(?=\D))+")
_WS = re.compile(r"\s+")


@dataclass(frozen=True)
class ResearchRound:
    index: int
    run_id: str
    question: str
    asked_at: str
    status: str
    as_of: str | None
    question_type: str
    subject: str
    answer_headline: str
    citations: int
    artifacts: tuple[str, ...]
    open_gaps: tuple[str, ...]
    followups: tuple[dict[str, Any], ...]
    continuation: dict[str, Any] | None
    warnings: tuple[str, ...] = ()
    # report.research_status：complete / partial / degraded…；partial 轮的首行是降级模板，
    # 不能当「上轮结论」喂给下一轮。
    research_status: str = ""

    @property
    def concluded(self) -> bool:
        """这一轮是否形成了可当先验的结论（完成 + 非降级 + 有标题）。"""
        return (
            self.status == "completed"
            and self.research_status in ("", "complete", "completed")
            and not any("降级" in text for text in self.warnings)
            and bool(self.answer_headline)
        )


@dataclass(frozen=True)
class ResearchTrigger:
    kind: str
    id: str
    claim: str
    due: str
    status: str
    checked_at: str | None
    source: str
    themes: tuple[str, ...]
    linked: str


@dataclass(frozen=True)
class ResearchProjectState:
    conversation_id: str
    user_id: str
    title: str
    subject: str
    question_type: str
    as_of: str | None
    updated_at: str
    rounds: tuple[ResearchRound, ...] = ()
    current_judgment: str = ""
    open_questions: tuple[str, ...] = ()
    materials_read: int = 0
    artifacts: tuple[str, ...] = ()
    triggers: tuple[ResearchTrigger, ...] = ()
    next_questions: tuple[dict[str, Any], ...] = ()
    prior_status: str | None = None
    prior_note: str = ""
    origin_conversation_id: str | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def completed_rounds(self) -> tuple[ResearchRound, ...]:
        return tuple(r for r in self.rounds if r.status == "completed")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["completed_rounds"] = len(self.completed_rounds)
        return payload

    def to_prompt_block(
        self,
        *,
        continuation: dict[str, Any] | None = None,
        max_chars: int = PROMPT_BLOCK_MAX_CHARS,
    ) -> str:
        """渲染成模型可见的先验块；无已完成轮次时返回空串（不追加块）。"""
        done = self.completed_rounds
        if not done:
            return ""
        last = done[-1]
        origin = (
            f"（来自早先会话「{_truncate(self.title, 20)}」）"
            if self.origin_conversation_id
            else ""
        )
        lines = [
            "## 研究项目状态（跨轮先验，非市场事实）" + origin,
            f"- 对象：{self.subject or '未识别'}；已研究 {len(done)} 轮，累计 {self.materials_read} 条引用；"
            f"上轮数据截止 {last.as_of or '未记录'}（{last.asked_at[:10]}）。",
        ]
        if last.concluded:
            lines.append(f"- 上轮结论标题：{_truncate(last.answer_headline, HEADLINE_CHARS)}")
        else:
            reason = "按证据边界降级" if last.warnings else "未形成结论"
            lines.append(f"- 上轮未形成可用结论（{reason}），不要把它当既有判断。")
            if self.current_judgment:
                lines.append(
                    f"- 更早一轮的结论标题：{_truncate(self.current_judgment, HEADLINE_CHARS)}"
                )
        if self.open_questions:
            lines.append(
                "- 未解问题："
                + "；".join(_truncate(q, 40) for q in self.open_questions[:3])
            )
        if self.triggers:
            rows = []
            for trigger in self.triggers[:3]:
                rows.append(
                    f"「{_truncate(trigger.claim, 32)}」到期 {trigger.due or '—'}"
                    f"→{TRIGGER_STATUS_LABEL.get(trigger.status, trigger.status)}"
                )
            lines.append("- 已登记可证伪点：" + "；".join(rows))
        if self.prior_note:
            lines.append(f"- 上次哪个判断让我这次这样查：{self.prior_note}")
        if continuation:
            kind = str(continuation.get("kind") or "")
            label = str(continuation.get("label") or continuation.get("source") or "")
            lines.append(
                f"- 本轮延续：{KIND_LABELS.get(kind, kind or '追问')}"
                + (f"「{_truncate(label, 24)}」" if label else "")
            )
        lines.append(
            "- 使用要求：以上是研究状态先验，不是市场事实；本轮只报相对上轮的变化与新增证据，"
            "不重跑全景；价格、订单、产能等易变项以本轮检索为准。"
        )
        return _fit(lines, max_chars)


def _truncate(text: Any, width: int) -> str:
    s = _WS.sub(" ", str(text or "")).strip()
    return s if len(s) <= width else s[: width - 1] + "…"


def _fit(lines: list[str], max_chars: int) -> str:
    """超预算时从中间的列表行开始砍，头（标题）尾（使用要求）保留。"""
    text = "\n".join(lines)
    while len(text) > max_chars and len(lines) > 3:
        del lines[-2]
        text = "\n".join(lines)
    return text


def headline_of(content: str) -> str:
    """回答首个非空行，去掉 Markdown 记号，≤ 80 字。只当「标题」，不当摘要。"""
    for raw in str(content or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        line = line.replace("**", "").replace("`", "")
        line = _MARKDOWN_LEAD.sub("", line).strip()
        if line:
            return _truncate(line, HEADLINE_CHARS)
    return ""


def gap_from_followup(item: dict[str, Any]) -> str | None:
    """从缺口镜像卡（type=gap）还原缺口原文：先 full_prompt 的「…」，再 label 的「补齐：」。"""
    if str(item.get("type") or "") != "gap":
        return None
    matched = _GAP_PROMPT_RE.search(str(item.get("full_prompt") or item.get("question") or ""))
    if matched and matched.group(1).strip():
        return matched.group(1).strip()
    label = str(item.get("label") or "")
    if label.startswith(_GAP_LABEL_PREFIX):
        text = label[len(_GAP_LABEL_PREFIX) :].strip().rstrip("…")
        return text or None
    return None


def _normalize_subject(value: Any) -> str:
    return _WS.sub("", str(value or "")).strip().lower()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _annotate_followup(item: dict[str, Any]) -> dict[str, Any]:
    """旧记录没有 kind：按 angle/type 补出，不改其它字段。"""
    payload = dict(item)
    if not payload.get("kind"):
        payload["kind"] = followup_kind(
            angle=str(payload.get("angle") or ""), type_=str(payload.get("type") or "")
        )
    if not payload.get("kind_label"):
        payload["kind_label"] = KIND_LABELS.get(str(payload["kind"]), str(payload["kind"]))
    return payload


def _rounds(
    messages: list[Message],
    run_store: RunStore,
    *,
    exclude_run_id: str | None,
) -> list[ResearchRound]:
    by_run: dict[str, dict[str, Message]] = {}
    order: list[str] = []
    for message in messages:
        run_id = message.run_id
        if not run_id or run_id == exclude_run_id:
            continue
        if run_id not in by_run:
            by_run[run_id] = {}
            order.append(run_id)
        if message.role in {"user", "assistant"} and message.role not in by_run[run_id]:
            by_run[run_id][message.role] = message
    rounds: list[ResearchRound] = []
    for index, run_id in enumerate(order, start=1):
        pair = by_run[run_id]
        user = pair.get("user")
        assistant = pair.get("assistant")
        run_payload: dict[str, Any] = {}
        report: dict[str, Any] = {}
        try:
            run = run_store.load_run(run_id)
        except (FileNotFoundError, ValueError):
            run = None
        else:
            run_payload = asdict(run)
            report = _load_json(run_store.run_dir(run_id) / "report.json")
        intent = (assistant.turn_intent if assistant else None) or {}
        frame = report.get("task_frame") if isinstance(report.get("task_frame"), dict) else {}
        subject = str(intent.get("primary_subject") or frame.get("subject") or "").strip()
        question_type = str(
            intent.get("question_type") or frame.get("question_type") or ""
        ).strip()
        status = str(
            run_payload.get("status") or (assistant.status if assistant else "") or ""
        )
        followups = tuple(
            _annotate_followup(item)
            for item in (assistant.followups if assistant else [])
            if isinstance(item, dict)
        )
        # 研究缺口只认缺口镜像卡（它就是 episode 报出的 open_gaps 的确定性镜像）；
        # run.degrades / report.warnings 是运行告警（降级声明、判官提示），另列 warnings，
        # 两者不混——否则「未解问题」里会长出「已按证据边界降级」这种不是问题的问题。
        gaps: list[str] = []
        seen_gap_keys: set[str] = set()
        for item in followups:
            gap = gap_from_followup(item)
            key = _WS.sub("", gap or "")
            if gap and key not in seen_gap_keys:
                seen_gap_keys.add(key)
                gaps.append(gap)
        round_warnings: list[str] = []
        report_warnings = report.get("warnings")
        for text in (
            *(run_payload.get("degrades") or ()),
            *(report_warnings if isinstance(report_warnings, list) else ()),
        ):
            cleaned = str(text).strip()
            if cleaned and cleaned not in round_warnings:
                round_warnings.append(cleaned)
        artifacts = tuple(
            str(a.get("title") or a.get("name") or "")
            for a in (run_payload.get("artifacts") or ())
            if isinstance(a, dict)
            and str(a.get("visibility") or "public") == "public"
            and (a.get("title") or a.get("name"))
        )
        rounds.append(
            ResearchRound(
                index=index,
                run_id=run_id,
                question=(user.content if user else str(run_payload.get("question") or "")),
                asked_at=(user.created_at if user else str(run_payload.get("created_at") or "")),
                status=status,
                as_of=run_payload.get("source_date"),
                question_type=question_type,
                subject=subject,
                answer_headline=headline_of(assistant.content) if assistant else "",
                citations=len(assistant.citations) if assistant else 0,
                artifacts=artifacts,
                open_gaps=tuple(gaps),
                warnings=tuple(round_warnings),
                followups=followups,
                continuation=(user.continuation if user else None),
                research_status=str(report.get("research_status") or ""),
            )
        )
    return rounds


def _trigger_status(record: dict[str, Any], verdict: dict[str, Any] | None, today: str) -> str:
    v = str((verdict or {}).get("verdict") or "").strip()
    if v in checkpoints_svc.TERMINAL_VERDICTS or v == "unverifiable":
        return v
    due = str(record.get("due") or "")
    return "due" if due and due <= today else "pending"


def _triggers(
    *,
    conversation_id: str,
    subject: str,
    query: str,
    checkpoints_path: Path,
    verdicts_path: Path,
    today: str,
) -> list[ResearchTrigger]:
    records, _ = checkpoints_svc.load_checkpoints(checkpoints_path)
    if not records:
        return []
    verdicts, _ = checkpoints_svc.load_verdicts(verdicts_path)
    latest = latest_verdicts(verdicts)
    linked: dict[str, tuple[dict[str, Any], str]] = {}
    for record in records:
        if str(record.get("session_id") or "") == conversation_id:
            linked[str(record.get("id") or "")] = (record, "conversation")
    if subject or query:
        for record in select_relevant_checkpoints(
            records, query or subject, theme=subject or None, limit=TRIGGER_LIMIT
        ):
            cid = str(record.get("id") or "")
            if cid and cid not in linked:
                linked[cid] = (record, "subject")
    triggers: list[ResearchTrigger] = []
    for cid, (record, link) in linked.items():
        verdict = latest.get(cid)
        triggers.append(
            ResearchTrigger(
                kind="checkpoint",
                id=cid,
                claim=str(record.get("claim") or ""),
                due=str(record.get("due") or ""),
                status=_trigger_status(record, verdict, today),
                checked_at=(str(verdict.get("checked_at")) if verdict else None),
                source=str(record.get("source") or ""),
                themes=tuple(str(t) for t in (record.get("themes") or ())),
                linked=link,
            )
        )
    # 会话直连的排前面；同类里到期/落空更需要被看见。
    weight = {"miss": 0, "partial": 1, "due": 2, "unverifiable": 3, "pending": 4, "hit": 5}
    triggers.sort(key=lambda t: (t.linked != "conversation", weight.get(t.status, 9), t.due))
    return triggers[: TRIGGER_LIMIT * 2]


def _prior(triggers: list[ResearchTrigger]) -> tuple[str | None, str]:
    """由裁决决定「本轮先做什么」：落空/半对 → 先检验条件；到期待判/暂无法判定 → 先补缺口。"""
    for status, action in (
        ("miss", "先检验条件，再补证据"),
        ("partial", "先检验条件，再补证据"),
        ("due", "先补齐到期未判的缺口，再谈新结论"),
        ("unverifiable", "先补齐机器判不了的缺口，再谈新结论"),
    ):
        hit = next((t for t in triggers if t.status == status), None)
        if hit is not None:
            label = TRIGGER_STATUS_LABEL.get(status, status)
            key = "pending" if status == "due" else status
            return key, f"上次「{_truncate(hit.claim, 32)}」到期裁决为{label}，本轮{action}"
    return None, ""


def _reorder(items: tuple[dict[str, Any], ...], prior_status: str | None) -> tuple[dict[str, Any], ...]:
    rank = prior_kind_rank(prior_status)
    if rank is None:
        return items
    return tuple(sorted(items, key=lambda item: rank.get(str(item.get("kind") or ""), len(rank))))


def load_project(
    conversation_store: ConversationStore,
    run_store: RunStore,
    conversation_id: str,
    *,
    exclude_run_id: str | None = None,
    today: str | None = None,
    checkpoints_path: str | Path | None = None,
    verdicts_path: str | Path | None = None,
) -> ResearchProjectState:
    """把一个会话投影成研究项目状态。``exclude_run_id`` 用于排除进行中的当前 run。"""
    conversation = conversation_store.load_conversation(conversation_id)
    messages = conversation_store.load_messages(conversation_id)
    rounds = _rounds(messages, run_store, exclude_run_id=exclude_run_id)
    done = [r for r in rounds if r.status == "completed"]
    subject = next((r.subject for r in reversed(rounds) if r.subject), "")
    question_type = next((r.question_type for r in reversed(rounds) if r.question_type), "")
    today_text = today or date_cls.today().isoformat()
    us = userspace.user_space(conversation.user_id)
    ck_path = Path(checkpoints_path) if checkpoints_path else us.checkpoints_path
    v_path = Path(verdicts_path) if verdicts_path else us.verdicts_path
    triggers = _triggers(
        conversation_id=conversation_id,
        subject=subject,
        query=subject or (done[-1].question if done else conversation.title),
        checkpoints_path=ck_path,
        verdicts_path=v_path,
        today=today_text,
    )
    prior_status, prior_note = _prior(triggers)
    latest = done[-1] if done else None
    open_questions: list[str] = []
    for r in reversed(done):
        for gap in r.open_gaps:
            if gap not in open_questions:
                open_questions.append(gap)
        if open_questions:
            break
    artifacts: list[str] = []
    for r in done:
        for name in r.artifacts:
            if name not in artifacts:
                artifacts.append(name)
    state_warnings: list[str] = []
    for r in done:
        for text in r.warnings:
            if text not in state_warnings:
                state_warnings.append(text)
    return ResearchProjectState(
        conversation_id=conversation_id,
        user_id=conversation.user_id,
        title=conversation.title,
        subject=subject,
        question_type=question_type,
        as_of=latest.as_of if latest else None,
        updated_at=conversation.updated_at,
        rounds=tuple(rounds),
        # 当前判断只取最近一轮**形成了结论**的标题；降级模板不是判断。
        current_judgment=next((r.answer_headline for r in reversed(done) if r.concluded), ""),
        open_questions=tuple(open_questions[:OPEN_QUESTION_LIMIT]),
        materials_read=sum(r.citations for r in done),
        artifacts=tuple(artifacts),
        triggers=tuple(triggers),
        next_questions=_reorder(latest.followups, prior_status) if latest else (),
        prior_status=prior_status,
        prior_note=prior_note,
        warnings=tuple(state_warnings),
    )


def find_related_conversation(
    conversation_store: ConversationStore,
    *,
    subject: str,
    exclude_conversation_id: str,
    scan_limit: int = RELATED_CONVERSATION_SCAN,
) -> str | None:
    """同一用户、同一对象、最近更新的另一个会话；找不到返回 None。

    只比对消息里已结构化的 ``turn_intent.primary_subject``，不读正文猜对象。
    """
    key = _normalize_subject(subject)
    if not key:
        return None
    conversations = sorted(
        conversation_store.list_conversations(),
        key=lambda c: c.updated_at,
        reverse=True,
    )
    for conversation in conversations[:scan_limit]:
        if conversation.conversation_id == exclude_conversation_id:
            continue
        if conversation.status != "active":
            continue
        for message in reversed(conversation_store.load_messages(conversation.conversation_id)):
            if message.role != "assistant" or message.status != "completed":
                continue
            intent = message.turn_intent or {}
            if _normalize_subject(intent.get("primary_subject")) == key:
                return conversation.conversation_id
            break
    return None


def continuation_for_run(messages: list[Message], run_id: str) -> dict[str, Any] | None:
    """当前 run 对应用户消息上的 continuation（由卡片点击带入）；没有则 None。"""
    for message in messages:
        if message.role == "user" and message.run_id == run_id:
            return message.continuation or None
    return None


def prior_block_for_turn(
    conversation_store: ConversationStore,
    run_store: RunStore,
    *,
    conversation_id: str,
    current_run_id: str,
    subject: str,
    continuation: dict[str, Any] | None = None,
    today: str | None = None,
    checkpoints_path: str | Path | None = None,
    verdicts_path: str | Path | None = None,
    max_chars: int = PROMPT_BLOCK_MAX_CHARS,
) -> str:
    """``prior_for_turn`` 的只取渲染块版本。"""
    block, _ = prior_for_turn(
        conversation_store,
        run_store,
        conversation_id=conversation_id,
        current_run_id=current_run_id,
        subject=subject,
        continuation=continuation,
        today=today,
        checkpoints_path=checkpoints_path,
        verdicts_path=verdicts_path,
        max_chars=max_chars,
    )
    return block


def prior_for_turn(
    conversation_store: ConversationStore,
    run_store: RunStore,
    *,
    conversation_id: str,
    current_run_id: str,
    subject: str,
    continuation: dict[str, Any] | None = None,
    today: str | None = None,
    checkpoints_path: str | Path | None = None,
    verdicts_path: str | Path | None = None,
    max_chars: int = PROMPT_BLOCK_MAX_CHARS,
) -> tuple[str, str | None]:
    """研究车道开工前的先验：``(渲染块, prior_status)``。

    三种情形返回 ``("", None)``（模型输入逐字节不变、卡片原序）：

    1. 本会话没有已完成轮次，且其他会话里也找不到同一对象；
    2. 本会话有轮次，但当前对象与项目对象都已识别且不同（用户换题），且本轮不是卡片延续；
    3. 渲染结果为空。
    """
    project = load_project(
        conversation_store,
        run_store,
        conversation_id,
        exclude_run_id=current_run_id,
        today=today,
        checkpoints_path=checkpoints_path,
        verdicts_path=verdicts_path,
    )
    if not project.completed_rounds:
        related = find_related_conversation(
            conversation_store,
            subject=subject,
            exclude_conversation_id=conversation_id,
        )
        if related is None:
            return "", None
        origin = load_project(
            conversation_store,
            run_store,
            related,
            today=today,
            checkpoints_path=checkpoints_path,
            verdicts_path=verdicts_path,
        )
        project = ResearchProjectState(
            **{**asdict_shallow(origin), "origin_conversation_id": related}
        )
    elif (
        not continuation
        and _normalize_subject(subject)
        and _normalize_subject(project.subject)
        and _normalize_subject(subject) != _normalize_subject(project.subject)
    ):
        return "", None
    block = project.to_prompt_block(continuation=continuation, max_chars=max_chars)
    return block, (project.prior_status if block else None)


def asdict_shallow(state: ResearchProjectState) -> dict[str, Any]:
    """dataclass 顶层字段（不递归展开嵌套 dataclass），用于带修改地重建状态。"""
    return {name: getattr(state, name) for name in state.__dataclass_fields__}


__all__ = [
    "ResearchProjectState",
    "ResearchRound",
    "ResearchTrigger",
    "continuation_for_run",
    "find_related_conversation",
    "gap_from_followup",
    "headline_of",
    "load_project",
    "prior_block_for_turn",
    "prior_for_turn",
]
