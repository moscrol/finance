"""回答后的「猜你想问」追问卡片生成（第 2 步：foresight 追问闭环）。

与 ``foresight.py`` 同一套哲学，但目标不同：foresight 是"盘面驱动、每日主动发问"，
本模块是"回答驱动、围绕刚生成的这份答案往深处追问"。两者共用 ``llm_refine``
的 provider 链与降级机制。

设计取舍（教学）：
- **LLM 可选、模板兜底**：无 key 时按五类固定模板（证据加深/反证验证/替代标的/
  盘面回检/题材迁移）用 matched_theme 填充出可用追问；有 key 时让 LLM 基于答案
  正文生成更具体的问题，再落回同样的五类。保证"追问卡片"永远出现，机制可审。
- **类型即产品语义**：每张卡片带 type，UI 可按类型着色/分组；这五类来自
  产品设计稿 3.4 节，是研究方法论的一部分而非随机问题。
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field

from intelligence.services import answer_model, llm_refine

FOLLOWUP_TYPES = ["evidence", "counter", "alternative", "recheck", "migration"]
TYPE_LABELS = {
    "evidence": "证据加深",
    "counter": "反证验证",
    "alternative": "替代标的",
    "recheck": "盘面回检",
    "migration": "题材迁移",
}


@dataclass
class Followup:
    question: str
    type: str
    rationale: str = ""
    type_label: str = ""
    source: str = ""
    label: str = ""
    full_prompt: str = ""

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
                "followups": [asdict(f) for f in self.followups],
                "llm_used": self.llm_used,
                "llm_provider": self.llm_provider,
                "warnings": self.warnings,
            },
            ensure_ascii=False,
            indent=2,
        )


def _template_followups(question: str, theme: str | None) -> list[Followup]:
    subject = theme or question[:16]
    return [
        Followup(f"{subject}目前最硬的一条公司级证据是什么，出自哪份公告或研报？", "evidence",
                 "把结论锚到可核对的一手材料上"),
        Followup(f"如果{subject}的逻辑不成立，最先出现的反证信号会是什么？", "counter",
                 "预设可证伪条件，避免单边叙事"),
        Followup(f"除了当前提到的标的，{subject}产业链上还有哪些暴露度相近的替代标的？", "alternative",
                 "对比同链条标的的证据硬度与位置"),
        Followup(
            f"若{subject}当前阶段被证伪，哪一个盘面指标会最先翻面，对应什么动作分层？",
            "recheck",
            "二阶回检：不问近几日双红事实（数据块已覆盖），问证伪后的动作",
        ),
        Followup(f"{subject}的资金和逻辑接下来最可能向哪个相邻题材迁移？", "migration",
                 "提前布局题材扩散的下一站"),
    ]


def _llm_followups(question: str, theme: str | None, answer_excerpt: str,
                   n: int, model: str | None, timeout: int) -> tuple[list[Followup], str | None, str]:
    system = (
        "你是 A 股主题研究助手。基于用户问题与刚生成的研究回答，生成后续追问。"
        "每条必须具体、可执行、可证伪，且只能属于以下类型之一："
        "evidence(证据加深)/counter(反证验证)/alternative(替代标的)/recheck(盘面回检)/migration(题材迁移)。"
        "每条同时给 label（按钮文案，最多20字）和 full_prompt（完整用户口吻问题）。"
        "禁止生成本仓数据块已能直接回答的一阶问题：历史上类似情绪环境、题材生命周期阶段、"
        "近几日双红/边际量/涨停热度事实。追问必须是二阶——下一层后果、跨域传导、证伪后的动作分层。"
        '只输出 JSON：{"followups":[{"label":"...","full_prompt":"...",'
        '"type":"evidence","rationale":"..."}]}'
    )
    user = (
        f"用户问题：{question}\n匹配题材：{theme or '—'}\n\n回答摘录：\n{answer_excerpt[:2000]}\n\n"
        f"请生成 {n} 条覆盖不同类型的追问。"
    )
    content, provider, reason = llm_refine.complete(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        model_override=model, timeout=timeout, temperature=0.7,
    )
    provider_name = provider.name if provider else None
    if content is None:
        return [], provider_name, reason or "LLM 不可用"
    obj = llm_refine._extract_json(content)
    raw = obj.get("followups") if isinstance(obj, dict) else None
    if not isinstance(raw, list):
        return [], provider_name, 'LLM 返回无法解析为 {"followups":[...]}'
    out: list[Followup] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        q = str(item.get("full_prompt") or item.get("question") or "").strip()
        label = str(item.get("label") or "").strip()
        t = str(item.get("type") or "").strip()
        if q and t in FOLLOWUP_TYPES:
            out.append(
                Followup(
                    q,
                    t,
                    str(item.get("rationale") or "").strip(),
                    label=label,
                    full_prompt=q,
                )
            )
    return out[:n], provider_name, "" if out else "LLM 未给出任何有效追问"


def generate_followups(
    question: str,
    *,
    matched_theme: str | None = None,
    answer_excerpt: str = "",
    n: int = 5,
    llm_model: str | None = None,
    llm_timeout: int = 60,
    use_llm: bool = True,
) -> FollowupResult:
    """生成 3-5 条追问卡片；LLM 不可用时优雅降级为五类模板。

    跟踪类问题跳过 recheck：跟踪契约的「下期关注清单」已经覆盖盘面回检，
    再生成「近几日双红如何」是一阶重复。
    """
    from intelligence.services.track_contract import parse_track_intent

    skip_types: set[str] = set()
    if parse_track_intent(question):
        skip_types.add("recheck")
    result = FollowupResult()
    if use_llm:
        followups, provider, warn = _llm_followups(
            question, matched_theme, answer_excerpt, n, llm_model, llm_timeout
        )
        followups = [f for f in followups if f.type not in skip_types]
        if followups:
            result.followups = followups
            result.llm_used = True
            result.llm_provider = provider
            return result
        result.warnings.append(f"{warn}（已降级为模板追问）")
    templates = [f for f in _template_followups(question, matched_theme) if f.type not in skip_types]
    result.followups = templates[:n]
    return result


def generate_answer_spec_followups(
    answer_spec: answer_model.AnswerSpec,
    *,
    subject: str | None = None,
    n: int = 4,
) -> FollowupResult:
    """只从 AnswerSpec 的缺口、触发条件和验证动作生成可执行追问。"""
    limit = min(4, max(3, int(n)))
    anchor = (
        subject
        or answer_spec.research_spec.theme
        or answer_spec.presentation_title
        or "当前研究主题"
    )
    candidates: list[Followup] = []
    for gap in answer_spec.gaps:
        text = _sentence(gap.text)
        if text:
            candidates.append(
                Followup(
                    f"{anchor}的这个证据缺口应如何补齐并绑定可核验来源：{text}？",
                    "evidence",
                    "来自本轮 AnswerSpec 的 evidence gap",
                    source=f"gap:{gap.claim_id}",
                )
            )
    for action in answer_spec.next_actions:
        text = _sentence(action)
        if text:
            candidates.append(
                Followup(
                    f"下一步如何执行并核验：{text}？",
                    "recheck",
                    "来自本轮 AnswerSpec 的验证路径",
                    source="next_action",
                )
            )
    for trigger in answer_spec.triggers:
        text = _sentence(trigger.text)
        if text:
            candidates.append(
                Followup(
                    f"哪些数据能验证或证伪这个条件：{text}？",
                    "counter",
                    "来自本轮 AnswerSpec 的触发或降级条件",
                    source=f"trigger:{trigger.claim_id}",
                )
            )

    conservative = (
        Followup(
            f"{anchor}当前哪些关键结论仍缺公司级可核验来源？",
            "evidence",
            "保守补充：继续检查本轮证据边界",
            source="answer_spec_boundary",
        ),
        Followup(
            f"{anchor}下一验证窗口应优先核对哪些触发条件？",
            "recheck",
            "保守补充：落实本轮验证路径",
            source="answer_spec_boundary",
        ),
        Followup(
            f"出现哪些反证时，应下调对{anchor}的当前判断？",
            "counter",
            "保守补充：明确可证伪条件",
            source="answer_spec_boundary",
        ),
        Followup(
            f"{anchor}已有证据中，哪些需要更新到更近的数据日期？",
            "evidence",
            "保守补充：复核证据新鲜度",
            source="answer_spec_boundary",
        ),
    )
    candidates.extend(conservative)
    deduped: list[Followup] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = re.sub(r"\s+", "", candidate.question)
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(candidate)
        if len(deduped) == limit:
            break
    return FollowupResult(followups=deduped)


def _sentence(value: str) -> str:
    return str(value or "").strip().rstrip("。！？?!；;")


def _compact_label(value: str) -> str:
    cleaned = re.sub(r"\s+", "", str(value or "").strip())
    cleaned = cleaned.rstrip("。！？?!；;")
    return cleaned[:20] or "继续研究"
