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
    # 缺口镜像：降级答案里「仍需核验：X」的 X 直接变成可点击的追问。
    # 不在 FOLLOWUP_TYPES 里——那五类是"围绕完整答案往深处问"的模板轮换，
    # gap 类只在契约有未满足必需输出时出现，数量由缺口数决定。
    "gap": "缺口补齐",
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
        Followup(f"{subject}最近 5 个交易日的板块双红 / 边际量 / 涨停热度表现如何？", "recheck",
                 "用盘面数据回检叙事是否被资金认可"),
        Followup(f"{subject}的资金和逻辑接下来最可能向哪个相邻题材迁移？", "migration",
                 "提前布局题材扩散的下一站"),
    ]


def gap_mirror_followups(
    subject: str,
    gaps: tuple[str, ...] | list[str],
    *,
    limit: int = 3,
) -> FollowupResult:
    """把结构化缺口镜像成「猜你想问」——确定性，零模型调用。

    形状来自 knevo q12 蒸馏（label 短入口 + full_prompt 替用户写好的完整问题）；
    动机来自 R15 对照 9:2:0：多题失分不在缺口本身（fail-closed 是对的），
    在缺口变成句号——「追问负担全在用户」（C1 判词原文）。缺口文案来自任务
    契约的必需输出描述，与公开降级声明同一口径，模型没机会顺嘴编数据。
    """
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
            )
        )
    return FollowupResult(followups=items, llm_used=False)


def _llm_followups(question: str, theme: str | None, answer_excerpt: str,
                   n: int, model: str | None, timeout: int) -> tuple[list[Followup], str | None, str]:
    system = (
        "你是 A 股主题研究助手。基于用户问题与刚生成的研究回答，生成后续追问。"
        "每条必须具体、可执行、可证伪，且只能属于以下类型之一："
        "evidence(证据加深)/counter(反证验证)/alternative(替代标的)/recheck(盘面回检)/migration(题材迁移)。"
        "每条同时给 label（按钮文案，最多20字）和 full_prompt（完整用户口吻问题）。"
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
    """生成 3-5 条追问卡片；LLM 不可用时优雅降级为五类模板。"""
    result = FollowupResult()
    if use_llm:
        followups, provider, warn = _llm_followups(
            question, matched_theme, answer_excerpt, n, llm_model, llm_timeout
        )
        if followups:
            result.followups = followups
            result.llm_used = True
            result.llm_provider = provider
            return result
        result.warnings.append(f"{warn}（已降级为模板追问）")
    result.followups = _template_followups(question, matched_theme)[:n]
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
