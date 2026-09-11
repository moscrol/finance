"""把用户贴进来的材料登记成本回合的证据，让计算工具算得了它。

**这补的是一个设计缺口，不是接线缺口。** 05 把材料做成了「身份」：id / 标题 / 表头 /
行数 / 材料内日期进提示词的身份表，模型看得见「有这么一份东西」。但材料的**内容**
从来没进过证据账本，而 ``derived_calculation`` 的第一道门恰恰是「本回合有没有已绑定
的证据」——于是「我给你数据，你帮我算」在结构上做不到：2026-09-11 的实测里，同一回合
21 次调用全部以 ``no_bound_evidence`` 被拒，模型最后只能手工心算，并如实写下「全部数字
为手工复算、未经工具核验」。系统是诚实的，只是交付不了。

三条设计约束，逐条都有它的反面教训：

1. **单独一个档位 ``user_supplied``，不冒充一手资料。** 材料里的数是材料自己的说法，
   不是市场事实（提示词里 ``_MATERIAL_RULE`` 已经这么写了，证据档位必须说同一句话）。
   它不在 ``_HARD_EVIDENCE_TIERS`` 里，所以拿它支撑的结论不会被判成「有硬证据」。
2. **不填 ``source_date``。** ``EvidenceLedger.append`` 会**静默丢弃**发布日晚于信息
   截止日的证据。材料里的日期是材料**内容**覆盖的时段，不是我们能背书的发布日；拿它
   当 ``source_date`` 会让「用户贴了一份比库还新的数据」这个完全正当的场景变成一次无声
   丢弃——正是本文件在修的那类 bug 的翻版。日期照常进 ``detail`` 与 observations 的
   ``as_of``，只是不参与截止日裁剪。
3. **表格正文走 ``observations``，不走 ``detail``。** ``detail`` 进沙箱时截到 600 字符、
   进模型视图时截到 240，一张 30 行的表两头都装不下。``StructuredObservation`` 是仓内
   既有的「机器可读形态」通道（"下游读它，不回头解析 detail 自由文本"），表格材料正该走它。

层次：本模块认识 ``user_task`` 的材料切分与 ``agent_research`` 的证据类型，两边都不认识
它——它只是把前者的产物翻译成后者的形状。表格判据不自己另写一套，直接用
``material_table_rows``，与身份表同源。
"""

from __future__ import annotations

import re
from dataclasses import replace

from intelligence.services.agent_research import (
    AgentEvidence,
    StructuredObservation,
    evidence_content_hash,
)
from intelligence.services.task_frame import TaskFrame
from intelligence.services.user_task import (
    MaterialRef,
    material_table_rows,
    materials_in_conversation,
    split_user_message,
)

MATERIAL_EVIDENCE_TOOL = "user_material"
MATERIAL_EVIDENCE_TIER = "user_supplied"
# 证据 detail 的模型视图只有 240 字符；给沙箱的 payload 是 600。取 560 留出固定句，
# 数本身不靠这段话传（表格走 observations），所以截断不丢可计算的信息。
_DETAIL_CHARS = 560
_MAX_OBSERVATIONS = 400

_NUMBER_RE = re.compile(r"^[+-]?\d{1,3}(?:,\d{3})*(?:\.\d+)?$|^[+-]?\d+(?:\.\d+)?$")
_UNIT_SUFFIXES = ("%", "亿元", "万元", "亿股", "万股", "亿", "万", "元", "股", "倍", "个", "家", "pct", "bp")


def _numeric_cell(cell: str) -> tuple[float, str] | None:
    """``"1,234.5亿"`` → ``(1234.5, "亿")``；不是数就 None。

    **不做单位换算。** ``12.3%`` 记成 12.3 而不是 0.123，单位原样挂进指标名——
    静默改写用户给的数字比读不出来危险得多，脚本看得见单位就自己决定怎么用。
    """

    text = str(cell or "").strip().replace(" ", "").replace(" ", "")
    if not text:
        return None
    unit = ""
    for suffix in _UNIT_SUFFIXES:
        if text.endswith(suffix) and len(text) > len(suffix):
            unit = suffix
            text = text[: -len(suffix)]
            break
    text = text.rstrip("+")
    if not _NUMBER_RE.match(text):
        return None
    try:
        return float(text.replace(",", "")), unit
    except ValueError:
        return None


def _table_observations(ref: MaterialRef, text: str) -> tuple[StructuredObservation, ...]:
    grid = material_table_rows(text)
    if not grid:
        return ()
    headers = grid[0]
    # 单一日期才当 as_of：一张表里出现多个日期时，哪个属于哪一行是猜的，宁可留空。
    as_of = ref.dates[0] if len(ref.dates) == 1 else ""
    out: list[StructuredObservation] = []
    for row_index, row in enumerate(grid[1:], start=1):
        if not row:
            continue
        label = row[0].strip()
        # 首列本身是数（纯数字矩阵）时它不是行标签，用行号顶上，免得把一个数当主体名。
        subject = label if _numeric_cell(label) is None and label else f"第{row_index}行"
        for column_index, cell in enumerate(row):
            if column_index == 0 and subject == label:
                continue
            parsed = _numeric_cell(cell)
            if parsed is None:
                continue
            value, unit = parsed
            header = (
                headers[column_index].strip()
                if column_index < len(headers) and headers[column_index].strip()
                else f"第{column_index + 1}列"
            )
            out.append(
                StructuredObservation(
                    subject=subject,
                    as_of=as_of,
                    metric=f"{header}·{unit}" if unit else header,
                    value=value,
                )
            )
            if len(out) >= _MAX_OBSERVATIONS:
                return tuple(out)
    return tuple(out)


def _detail(ref: MaterialRef, text: str) -> str:
    head = re.sub(r"\n{2,}", "\n", str(text or "").strip())
    body = head[:_DETAIL_CHARS] + ("…（材料共 %d 字，全文见对话）" % ref.char_count if len(head) > _DETAIL_CHARS else "")
    dates = f"｜材料内日期：{'、'.join(ref.dates)}" if ref.dates else ""
    return f"[用户提供·{ref.material_id}]{dates}\n{body}"


def material_evidence(ref: MaterialRef, text: str) -> AgentEvidence | None:
    """一份材料 → 一条本回合证据。正文为空时返回 None（宁可没有，不造空壳）。"""

    if not str(text or "").strip():
        return None
    item = AgentEvidence(
        tool=MATERIAL_EVIDENCE_TOOL,
        title=ref.title or ref.material_id,
        detail=_detail(ref, text),
        source=f"用户提供的材料 {ref.material_id}",
        # 档位与来源族都点名「用户提供」：交叉验证时它与任何一个取数源都不同族，
        # 不会替真实数据源凑出一个「多源独立」的假象。
        evidence_tier=MATERIAL_EVIDENCE_TIER,
        independent_key=f"user_material:{ref.material_id}",
        freshness="user_supplied",
        observations=_table_observations(ref, text),
    )
    # content_hash 是账本主键，也是 ``input_evidence_hashes`` 的元素：空值会让
    # ``derived_calculation`` 直接把这条证据滤掉（见 run_derived_calculation 的 inputs）。
    return replace(item, content_hash=evidence_content_hash(item))


def materials_as_evidence(
    frame: TaskFrame,
    conversation_context: str | None = None,
) -> tuple[AgentEvidence, ...]:
    """本回合应当可计算的材料证据，按「本轮贴的 → 本轮点名引用的」顺序。

    两类各有理由，合起来正好覆盖用户说得出口的两种话：

    - ``frame.materials``：这条消息自己贴的（「这是三家的毛利率，帮我算…」）。正文按
      ``split_user_message(frame.raw_question)`` 重切——与 ``build_task_frame`` 同一个
      函数、同一份输入，结果必然一致；**再按 id 核对一次**，对不上就不发（对齐模型
      改写过 ``raw_question`` 时宁可没有材料证据，也不能把张三的正文挂到李四的 id 上）。
    - ``frame.referenced_material_ids``：这轮说「用上面那张表算」，正文在对话块里。

    只在对话里出现过、这轮没被点名的材料**不入账**：身份表带着它们是为了让模型认得
    「这篇」，不代表用户要拿它算数。证据账本是「本回合可引用的东西」，宽进会让上一个
    话题的表被算进这一轮。
    """

    bodies: dict[str, str] = {}
    own_ids = {item.material_id for item in frame.materials}
    if own_ids:
        parts = split_user_message(str(frame.raw_question or ""))
        for ref, body in zip(parts.materials, parts.material_texts):
            if ref.material_id in own_ids:
                bodies.setdefault(ref.material_id, body)
    wanted = [item for item in frame.materials]
    if frame.referenced_material_ids:
        earlier = dict(
            (ref.material_id, (ref, body))
            for ref, body in materials_in_conversation(conversation_context)
        )
        for material_id in frame.referenced_material_ids:
            found = earlier.get(material_id)
            if found is None or any(item.material_id == material_id for item in wanted):
                continue
            wanted.append(found[0])
            bodies.setdefault(material_id, found[1])
    out: list[AgentEvidence] = []
    for ref in wanted:
        body = bodies.get(ref.material_id)
        if not body:
            continue
        item = material_evidence(ref, body)
        if item is not None:
            out.append(item)
    return tuple(out)


__all__ = [
    "MATERIAL_EVIDENCE_TIER",
    "MATERIAL_EVIDENCE_TOOL",
    "material_evidence",
    "materials_as_evidence",
]
