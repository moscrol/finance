"""判断增量筛材料（Knevo q17 Q8 回灌，回灌清单 R4 的收窄版）。

背景（为什么要这个层）：
    材料越多，答案越容易被「同一件利好的第 N 次转述」占满。真正稀缺的是**能改变
    判断的那一条**——足以推翻主判断的反证、尚未证实但一旦坐实就翻盘的消息、以及
    「下一份什么材料会裁决这场争论」。现有 :mod:`evidence_window` 已按相关性/硬度/
    新鲜度/独立性排序并砍窗口，但它**不认识反证**：十家媒体转述同一笔订单可以把
    唯一一条「订单终止」挤出窗口，模型连看都看不到。

    初版 R4 写的是「作战地图压缩层：主矛盾(1)+情绪扰动(≤3)+裁判变量(1-3) + 四条
    丢弃规则」。2026-09-11 复核收窄：**不做摘要引擎、不硬编码只能有一条主矛盾、
    不按「非主线」丢信息**——非主线常常正是新线索和反证的藏身处。留下的只有一条
    判据：保留的信息要能回答「它改变哪项判断，或帮助裁决哪个未解问题」。

设计（沿 scenario_tree / ranking_contract 的表达层惯例）：
    - **确定性分类**（:func:`classify_material`）：同一事件的多家报道合并成一条线索
      并保留全部出处；每条线索打一个判断增量角色（反证 / 新增事实 / 待证实 / 重复
      确认）。合并与排序是纯函数，零取数、零外呼，可单测。
    - **窗口保底**（:func:`counter_evidence_floor_order`）：给反证在模型可见窗口里
      留位——重复利好再多也挤不掉最后那几个反证槽。这是本单唯一改既有行为的地方。
    - **表达指导**：注入 synthesis prompt（legacy）与 episode 指令，提示证据取舍、
      待验证问题与下一步动作；按用户问题组织答案，不要求固定标题或前缀。
    - **收据**（:func:`judgment_delta_receipt`）：EVAL 可读，给同题对照实验用。
      只记录材料与显式章节观察，不把标题命中率当质量评估或完成门禁。

验收（复核笔记给的判据，见 ``intelligence/tests/test_judgment_delta.py``）：
    同一材料包灌入大量重复利好，保留的线索集合与待验证问题不变；加入一条有力反证，
    它必须进入模型可见窗口且排在确认性材料之前。
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Sequence

from intelligence.services.ranking_contract import NEXT_ACTION_LABELS

# ——————————————————————————————————————————— 判断增量角色
ROLE_COUNTER = "counter"  # 反证：与主判断反向，足以让结论降级或翻转
ROLE_NEW_FACT = "new_fact"  # 新增事实：公司级硬事实（公告/订单/中标/量产/带口径数字）
ROLE_UNVERIFIED = "unverified"  # 待证实：可能改判但当前无法证实 → 转成待验证问题
ROLE_REPEAT = "repeat"  # 重复确认：已知事实的再次转述，不单独占篇幅
ROLE_ORDER: tuple[str, ...] = (ROLE_COUNTER, ROLE_NEW_FACT, ROLE_UNVERIFIED, ROLE_REPEAT)

# 反证词面：与「利好被确认」反向的公开事实。刻意只收**可回查的事件**
# （终止/下修/处罚/流标…），不收「回调」「走弱」这类行情形容词——后者是价格状态，
# 属 pricing_split 的活，不是产业反证。
_COUNTER_MARKERS: tuple[str, ...] = (
    "不及预期", "低于预期", "下修", "下调", "终止", "取消", "中止", "解约", "撤回",
    "减产", "停产", "延期", "推迟", "流标", "废标", "失标", "落标",
    "诉讼", "处罚", "立案", "问询函", "关注函", "警示函", "违约", "退市风险",
    "减持", "清仓", "质疑", "证伪", "否认", "辟谣", "召回", "禁令", "制裁",
    "转亏", "亏损扩大", "商誉减值", "客户流失", "订单取消", "产能过剩",
)
# 新增事实词面：AGENTS.md 知识库回填口径的同一条线——公告、订单、中标、量产、
# 带金额或数量口径的公司级事实才算硬事实，研报提及不算。
_FACT_MARKERS: tuple[str, ...] = (
    "公告", "招标结果", "中标", "订单", "合同", "批复", "获批", "签约", "交付",
    "量产", "投产", "出货", "扩产", "并购", "收购", "定增", "季报", "年报", "中报",
)
_QUANTIFIED_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:亿元|万元|亿美元|万美元|亿|万|吨|万吨|GWh|MWh|台|套|片|颗|条|pct|%|个百分点)"
)
# 待证实词面：消息可能改判，但来源自己就说了「未经证实」。
_UNVERIFIED_MARKERS: tuple[str, ...] = (
    "传闻", "据悉", "市场传言", "传言", "知情人士", "小作文", "有消息称", "路边社",
    "未经证实", "待确认", "尚未公告", "口头", "有望", "预计将", "或将",
)
# 合并同一事件时，标题里要先打掉的媒体/体例噪声。
_TITLE_NOISE_RE = re.compile(
    r"[《》【】\[\]（）()「」“”\"'·、，,。.！!？?：:；;\-—_|/\\]+"
    r"|财联社|证券时报|上证报|中证报|新浪财经|东方财富|同花顺|界面新闻|第一财经|智通财经"
    r"|快讯|独家|重磅|深度|原创|要闻|头条"
)
_EVENT_KEY_CHARS = 24


def _text_of(item: object) -> str:
    title = str(getattr(item, "title", "") or "")
    detail = str(getattr(item, "detail", "") or "")
    return f"{title} {detail}"


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "")).lower()


def event_key(item: object) -> str:
    """同一事件的稳定键：独立源键优先，否则用去噪标题前缀 + 时点。

    十家媒体转述同一笔订单时标题措辞各异但主干相同；只取去噪后的前
    :data:`_EVENT_KEY_CHARS` 个字符，配上 ``source_date``，足以把它们并成一条，
    又不会把「同一天的另一则公告」误并（前缀不同）。
    """
    independent = _normalize(getattr(item, "independent_key", "") or "")
    if independent:
        return f"key:{independent}"
    title = _TITLE_NOISE_RE.sub("", str(getattr(item, "title", "") or ""))
    stem = _normalize(title)[:_EVENT_KEY_CHARS]
    if not stem:
        stem = _normalize(str(getattr(item, "detail", "") or ""))[:_EVENT_KEY_CHARS]
    day = str(getattr(item, "source_date", "") or "")[:10]
    return f"evt:{stem}|{day}"


def classify_role(item: object) -> str:
    """一条材料的判断增量角色。反证优先判定——它是最贵的一类，宁可多认不可漏认。"""
    if tuple(getattr(item, "contradicts", ()) or ()):
        return ROLE_COUNTER
    body = _normalize(_text_of(item))
    if any(marker in body for marker in _COUNTER_MARKERS):
        return ROLE_COUNTER
    if any(marker in body for marker in _UNVERIFIED_MARKERS):
        return ROLE_UNVERIFIED
    if any(marker in body for marker in _FACT_MARKERS) or _QUANTIFIED_RE.search(body):
        return ROLE_NEW_FACT
    return ROLE_REPEAT


@dataclass(frozen=True)
class MaterialLead:
    """一条合并后的线索：同一事件的全部报道并成一条，出处不丢。"""

    key: str
    role: str
    title: str
    detail: str
    sources: tuple[str, ...] = ()
    source_date: str | None = None
    duplicate_count: int = 1
    tool: str = ""
    evidence_tier: str = ""

    @property
    def merged(self) -> bool:
        return self.duplicate_count > 1

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["sources"] = list(self.sources)
        payload["merged"] = self.merged
        return payload


@dataclass(frozen=True)
class MaterialDigest:
    """材料包的判断增量视图。不丢信息：重复的并成一条，全部线索都在 ``leads`` 里。"""

    leads: tuple[MaterialLead, ...] = ()
    open_questions: tuple[str, ...] = ()
    input_count: int = 0
    merged_count: int = 0

    def by_role(self, role: str) -> tuple[MaterialLead, ...]:
        return tuple(lead for lead in self.leads if lead.role == role)

    @property
    def counter_count(self) -> int:
        return len(self.by_role(ROLE_COUNTER))

    def to_payload(self) -> dict[str, object]:
        return {
            "input_count": self.input_count,
            "lead_count": len(self.leads),
            "merged_count": self.merged_count,
            "role_counts": {
                role: len(self.by_role(role)) for role in ROLE_ORDER
            },
            "leads": [lead.to_payload() for lead in self.leads],
            "open_questions": list(self.open_questions),
        }

    def to_inline_note(self) -> str:
        """证据链末尾的一行合并说明。没有合并也没有反证时返回空串（行为不变）。

        窗口把同事件的转述稿并成一位（``evidence_window.select_agent_evidence``），
        被省掉的出处要在这里说出来——「合并」不写出来就是「丢了」。
        """
        if not self.merged_count and not self.counter_count:
            return ""
        parts = [
            f"【判断增量】{self.input_count} 条材料合并为 {len(self.leads)} 条独立线索"
        ]
        merged_leads = [lead for lead in self.leads if lead.merged]
        if merged_leads:
            detail = "；".join(
                f"{lead.title or lead.detail[:20]}（{lead.duplicate_count} 篇："
                + "、".join(lead.sources[:5])
                + "）"
                for lead in merged_leads[:3]
            )
            parts.append(f"重复报道已并，出处保留：{detail}")
        if self.counter_count:
            parts.append(f"反证 {self.counter_count} 条已置顶")
        return "；".join(parts) + "。"

    def to_prompt_block(self) -> str:
        """注入检索块的判断增量摘要。空材料返回空串（不注入，行为不变）。"""
        if not self.leads:
            return ""
        lines = [
            f"【判断增量摘要】{self.input_count} 条材料合并为 {len(self.leads)} 条独立线索"
            f"（合并重复 {self.merged_count} 条，出处已保留）：",
        ]
        for label, role in (
            ("反证（与主判断反向，优先裁决）", ROLE_COUNTER),
            ("新增事实", ROLE_NEW_FACT),
            ("待证实", ROLE_UNVERIFIED),
            ("重复确认", ROLE_REPEAT),
        ):
            leads = self.by_role(role)
            if not leads:
                continue
            lines.append(f"- {label}：{len(leads)} 条")
            for lead in leads[:4]:
                sources = "、".join(lead.sources[:4]) or "来源未标"
                suffix = f"（同源报道 {lead.duplicate_count} 篇：{sources}）" if lead.merged else f"（{sources}）"
                day = f"[{lead.source_date}] " if lead.source_date else ""
                lines.append(f"  · {day}{lead.title or lead.detail[:40]}{suffix}")
        if self.open_questions:
            lines.append("- 待验证问题（当前无法证实，但一旦坐实会改判）：")
            lines.extend(f"  · {item}" for item in self.open_questions)
        lines.append(
            "以上是材料的组织视图，不是新证据；引用仍用各条材料自己的证据编号。"
        )
        return "\n".join(lines)


def classify_material(
    items: Sequence[object] | Iterable[object],
    *,
    max_open_questions: int = 3,
) -> MaterialDigest:
    """把材料包合并成线索并打上判断增量角色。纯函数，不取数、不改输入。

    合并规则：同 :func:`event_key` 的多条并成一条，保留全部出处、取最早的
    ``source_date``、角色取最「贵」的那个（反证 > 新增事实 > 待证实 > 重复确认）——
    同一事件里只要有一条是反证，这条线索就是反证，不会被同事件的确认稿盖过去。
    """
    order: list[str] = []
    buckets: dict[str, list[object]] = {}
    total = 0
    for item in items or ():
        total += 1
        key = event_key(item)
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(item)

    leads: list[MaterialLead] = []
    for key in order:
        group = buckets[key]
        roles = [classify_role(item) for item in group]
        role = next((candidate for candidate in ROLE_ORDER if candidate in roles), ROLE_REPEAT)
        # 同一事件里挑出代表：优先那条定了角色的（反证稿而不是确认稿）。
        head = next(
            (item for item, item_role in zip(group, roles) if item_role == role),
            group[0],
        )
        dates = sorted(
            {
                str(getattr(item, "source_date", "") or "")[:10]
                for item in group
                if str(getattr(item, "source_date", "") or "").strip()
            }
        )
        sources = tuple(
            dict.fromkeys(
                str(getattr(item, "source", "") or "").strip()
                for item in group
                if str(getattr(item, "source", "") or "").strip()
            )
        )
        leads.append(
            MaterialLead(
                key=key,
                role=role,
                title=str(getattr(head, "title", "") or ""),
                detail=str(getattr(head, "detail", "") or ""),
                sources=sources,
                source_date=dates[0] if dates else None,
                duplicate_count=len(group),
                tool=str(getattr(head, "tool", "") or ""),
                evidence_tier=str(getattr(head, "evidence_tier", "") or ""),
            )
        )

    rank = {role: index for index, role in enumerate(ROLE_ORDER)}
    leads.sort(key=lambda lead: rank.get(lead.role, len(ROLE_ORDER)))
    open_questions = tuple(
        f"{lead.title or lead.detail[:40]} —— 等哪份公开材料能证实？"
        for lead in leads
        if lead.role == ROLE_UNVERIFIED
    )[:max_open_questions]
    return MaterialDigest(
        leads=tuple(leads),
        open_questions=open_questions,
        input_count=total,
        merged_count=total - len(leads),
    )


# ——————————————————————————————————————————— 窗口保底：反证不被重复利好挤掉
DEFAULT_COUNTER_FLOOR = 2


def counter_evidence_floor_order(
    ranked_items: Sequence[object],
    *,
    floor: int = DEFAULT_COUNTER_FLOOR,
) -> list[object]:
    """把最多 ``floor`` 条反证提到已排序序列最前，其余保持原相对次序。

    调用方（:func:`evidence_window.select_agent_evidence`）按本序列取窗口，于是
    「反证进不进模型视野」不再取决于它的相关性分排第几——**这正是重复利好淹没
    反证的机制**：转述稿各自独立、分数不低、数量却是反证的十倍。

    ``floor <= 0`` 时原样返回，调用方可以一键关掉本行为做 A/B 对照。
    """
    items = list(ranked_items or ())
    if floor <= 0 or len(items) <= 1:
        return items
    promoted: list[object] = []
    rest: list[object] = []
    for item in items:
        if len(promoted) < floor and classify_role(item) == ROLE_COUNTER:
            promoted.append(item)
        else:
            rest.append(item)
    return promoted + rest


# ——————————————————————————————————————————— 表达契约
_OPEN_QUESTION_HEADING = "待验证问题"
_DECIDER_HEADING = "裁判变量"


def _structure_lines(evidence_note: str) -> list[str]:
    return [
        "1. **保留判据**：写进答案的每条材料都要能回答「它改变哪项判断，或帮助裁决哪个"
        "未解问题」；答不上来的归入「重复确认」，与同事件的其它报道合并成一条"
        "（保留全部出处与最早时点），不单独占篇幅。禁止因为「不是主线」直接丢掉一条"
        "材料——新线索和反证常常就在非主线里。",
        f"2. **反证优先**：主动考虑足以削弱或推翻主判断的反证，带{evidence_note}与时点；"
        "说明它如何影响判断。未找到反证时如实界定检索范围，不把未找到当作不存在。",
        f"3. **{_OPEN_QUESTION_HEADING}**：无法证实但一旦坐实会改判的消息应保留为"
        "待核实问题，说明哪份公开材料或数据能证实；不得把传闻直接当事实并入结论。",
        f"4. **{_DECIDER_HEADING}**：有实际争论时说明下一份什么材料或数据可以裁决，"
        "包括观察时点及不同结果如何改变判断。",
        f"5. 有关键缺口时给出可执行的下一步，例如{NEXT_ACTION_LABELS[0]}、"
        f"{NEXT_ACTION_LABELS[1]}或{NEXT_ACTION_LABELS[2]}；证据已足够时不必额外扩写。",
        "6. 主矛盾可以不止一条：真有两条并行的争论就并列写出，不为了整齐压成一条。",
        "以上是按需使用的研究方法；答案按用户问题组织，不要求固定标题、顺序或套话。",
    ]


def build_judgment_delta_guidance() -> str:
    """判断增量表达契约（注入 synthesis prompt；legacy 证据记号）。"""
    return "\n".join(
        [
            "## 判断增量表达契约（材料要按「什么会改变判断」组织，不按「说了几遍」组织）",
            *_structure_lines("证据编号如 [D6]/[W7]/[L1-x]"),
        ]
    )


def build_judgment_delta_guidance_for_episode() -> str:
    """episode 主路径版——纪律同 :func:`build_judgment_delta_guidance`，证据记号换成 E1、E2…。"""
    return "\n".join(
        [
            "【判断增量表达契约】材料要按「什么会改变判断」组织，不按「说了几遍」组织"
            "（以下为按需使用的表达建议，不是可绑定的 output_id）：",
            *_structure_lines("证据序号 E1、E2…"),
        ]
    )


# 材料型问句：要在一堆材料上给判断的题。快事实、定义、估值口径题不进来——
# 它们的答案本来就短，注入这段只会稀释指令。
_MATERIAL_QUESTION_TYPES = frozenset(
    {
        "theme_analysis",
        "theme_track",
        "news_impact",
        "market_cause",
        "market_forecast",
        "event_forecast",
        "stock_deep_dive",
        "research",
    }
)
_EXCLUDED_QUESTION_TYPES = frozenset(
    {
        "quick_fact",
        "concept_definition",
        "market_data",
        "market_technical",
        "watchlist_digest",
        "dated_market_review",
        "methodology_discussion",
        "valuation_estimate",
    }
)
# 没给 question_type 时的兜底词面：只收「要判断」的问法，不收「要数据」的问法。
_MATERIAL_CUE_RE = re.compile(
    r"怎么看|如何看|怎么理解|影响有多大|有什么影响|梳理一下|逻辑是什么|还成立吗|"
    r"为什么涨|为什么跌|利好还是利空|靠谱吗|可信吗"
)


def parse_judgment_delta_intent(query: str, question_type: str | None = None) -> bool:
    """材料型判断题才注入。排除表优先——快事实/定义/估值题永远不进来。"""
    qtype = str(question_type or "").strip()
    if qtype in _EXCLUDED_QUESTION_TYPES:
        return False
    if qtype in _MATERIAL_QUESTION_TYPES:
        return True
    if qtype:
        return False
    text = re.sub(r"\s+", "", str(query or ""))
    return bool(text) and _MATERIAL_CUE_RE.search(text) is not None


def judgment_delta_guidance_for_query(query: str, question_type: str | None = None) -> str:
    """命中意图返回表达契约，否则空串（不注入，行为不变）。"""
    if not parse_judgment_delta_intent(query, question_type):
        return ""
    return build_judgment_delta_guidance()


def episode_judgment_delta_rule(query: str, question_type: str | None = None) -> str:
    """episode 指令的条件注入口：命中材料型判断题返回 episode 版契约，否则空串。"""
    if not parse_judgment_delta_intent(query, question_type):
        return ""
    return build_judgment_delta_guidance_for_episode()


# ——————————————————————————————————————————— 显式章节观察（不据此判定答案质量）
_HEADING_RE = re.compile(r"^\s*(?:#{1,6}\s*|\*\*|\d+[.)、）]\s*)?(.{1,24}?)(?:\*\*)?\s*[：:]?\s*$")
_BULLET_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)、）])\s*(.+)$")


def _section_items(text: str, heading: str) -> tuple[str, ...]:
    items: list[str] = []
    inside = False
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not inside:
            match = _HEADING_RE.match(line)
            if match and heading in re.sub(r"[*#\s]", "", match.group(1)):
                inside = True
                tail = line.split("：", 1)[1] if "：" in line else ""
                if tail.strip():
                    items.append(tail.strip())
            continue
        if not line:
            continue
        if line.startswith("#") or line.startswith("|"):
            break
        match = _HEADING_RE.match(line)
        if match and not _BULLET_RE.match(line) and line.endswith(("：", ":")):
            break
        bullet = _BULLET_RE.match(line)
        items.append(bullet.group(1).strip() if bullet else line)
    return tuple(item for item in items if item and item not in {"无", "None"})


def judgment_delta_receipt(
    answer: str,
    *,
    query: str = "",
    question_type: str | None = None,
    materials: Sequence[object] | None = None,
    as_of: str | None = None,
) -> dict[str, Any]:
    """EVAL 观察收据；未出现固定章节不代表缺少相应推理，质量须另评。"""
    intent = parse_judgment_delta_intent(query, question_type)
    digest = classify_material(materials or ()) if materials is not None else None
    return {
        "check": "judgment_delta",
        "judgment_delta_intent": intent,
        "quality_assessment": "not_evaluated",
        "open_questions": list(_section_items(str(answer or ""), _OPEN_QUESTION_HEADING)),
        "decider_variables": list(_section_items(str(answer or ""), _DECIDER_HEADING)),
        "material_digest": digest.to_payload() if digest else None,
        "as_of": as_of,
    }


__all__ = [
    "DEFAULT_COUNTER_FLOOR",
    "MaterialDigest",
    "MaterialLead",
    "ROLE_COUNTER",
    "ROLE_NEW_FACT",
    "ROLE_ORDER",
    "ROLE_REPEAT",
    "ROLE_UNVERIFIED",
    "build_judgment_delta_guidance",
    "build_judgment_delta_guidance_for_episode",
    "classify_material",
    "classify_role",
    "counter_evidence_floor_order",
    "episode_judgment_delta_rule",
    "event_key",
    "judgment_delta_guidance_for_query",
    "judgment_delta_receipt",
    "parse_judgment_delta_intent",
]
