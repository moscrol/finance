"""产业证据变化 vs 市场定价状态：两问分开答（Knevo q17 Q4 回灌，回灌清单 R5 的收窄版）。

背景（为什么要这个层）：
    「主线再确认」和「已经接近过热」可以同时成立。把两件事揉成一个多空结论，就会
    出现两种典型错答：拿新订单证明「还能追」（无视拥挤度），或拿高拥挤度否掉真实的
    产业增强（无视兑现路径）。用户要的是**两段分别成立的判断**——逻辑变强到什么
    程度、价格已经反映了多少、哪些还判断不了。

    初版 R5 写的是「共识兑现 vs 再确认六条件（催化性质/价格响应质量/资金主被动/
    拥挤度分位/产业链共振/领先者状态），≥4 判定」。2026-09-11 复核**不采纳投票
    阈值**：这六项彼此相关（价格响应、资金、拥挤度共享同一批成交数据），独立计票
    会把一个信号数三遍。另有两处口径修正——
    - 原清单「sellside-coverage-cross 现只有覆盖密度单维」与实际不符：该 skill 已在
      查库内已知信息、覆盖密度、盘面背离与观点冲突四问（规范源在知识库仓）。
    - ``event_pricing.reaction.CONSENSUS_GAP`` 至今是 ``"not_wired"``：**没有事前
      预期源**。所以「市场反映了多少」这一问在多数题上只能报价格状态，不能声称
      共识已经怎样——上涨本身不是「市场已相信」的证据。

设计（沿 scenario_tree / ranking_contract 的表达层惯例，零新数据源）：
    - **表达层模板**：注入 synthesis prompt（legacy）与 episode 指令，只约束输出
      组织方式，不新增证据、不改证据链。
    - **接线而非再造读数**（R1a 的教训）：拥挤度分位早就在 ``market_midterm``，
      排序题式当年却因为词面门控拿不到它，于是契约层被迫另造一个读数、底下那个照样
      不通。本单因此先放宽 D6 门控（:func:`is_pricing_state_query` 已并入
      ``market_midterm.midterm_intent_for``），让「已经反映多少」这一问真能看到
      相对分位；契约里只引用读数，不自造。
    - **程序核对 + 收据**：缺件只进收据（EVAL 与同题对照实验读），**不**并进
      ``missing_outputs``——那会触发修复轮、改预算行为，等实验量出效果再说。

验收（复核笔记给的判据，见 ``intelligence/tests/test_pricing_split.py``）：
    「新订单 + 高拥挤」与「旧消息重提 + 低拥挤」两组交叉样本，相同涨幅但信息增量
    不同，应产生不同解释；缺资金主动性数据时写未知而不是形容词。
"""

from __future__ import annotations

import re
from typing import Any

# ——————————————————————————————————————————— 意图
# 定价状态问句：问的是「这波涨/跌里，产业逻辑占多少、价格已经反映多少」。
_PRICING_CUE_RE = re.compile(
    r"还能不能追|还能追|还能买|还能上车|追高|接不接得住"
    r"|已经反映|反映了多少|是不是反映|price\s*in|priced\s*in|priced|定价了吗|计入了吗"
    r"|涨了这么多|涨这么多|涨幅这么大|还有多少空间|还有空间|透支|太贵了吗"
    r"|是不是炒完|炒到头|见顶了吗|过热|拥挤"
    r"|逻辑变强|逻辑更强|基本面还是情绪|情绪还是基本面|基本面还是资金|资金还是基本面"
    r"|预期差还在|兑现了吗|兑现到什么程度"
)
# 定义/算法题：问的是名词本身，不是某个标的的定价状态。
_DEFINITION_RE = re.compile(r"什么是|是什么意思|怎么算|如何计算|定义是|指标含义")
_EXCLUDED_QUESTION_TYPES = frozenset(
    {"concept_definition", "quick_fact", "methodology_discussion", "market_data"}
)


def is_pricing_state_query(query: str) -> bool:
    """问句是否在问「产业逻辑 vs 已定价程度」。

    这是 D6 门控的第三个放宽入口（前两个是视角模式与方向排序题式，见
    ``market_midterm.midterm_intent_for``）。失败形状与 AB-002 同构：这类问句一个
    中期词都不带（「液冷还能追吗」），词面门全部拦下 → 拥挤度分位从未进入上下文 →
    「已经反映多少」只能靠当日绝对涨幅回答，而绝对涨幅恰恰答不了这一问。
    """
    text = re.sub(r"\s+", "", str(query or ""))
    if not text or _DEFINITION_RE.search(text):
        return False
    return _PRICING_CUE_RE.search(text) is not None


def parse_pricing_split_intent(query: str, question_type: str | None = None) -> bool:
    """契约注入门：定价状态词面命中且不是定义/快事实题。"""
    if str(question_type or "").strip() in _EXCLUDED_QUESTION_TYPES:
        return False
    return is_pricing_state_query(query)


# ——————————————————————————————————————————— 契约文本
EVIDENCE_HEADING = "产业证据变化"
PRICING_HEADING = "定价状态"
NO_CONSENSUS_DECLARATION = "无事前预期来源，本段只报告价格状态"


def _structure_lines(evidence_note: str, crowding_note: str) -> list[str]:
    return [
        f"1. **{EVIDENCE_HEADING}**（标题逐字）：新公告、订单、产能、经营数据有没有强化"
        f"原来的收入/利润兑现路径？逐条写「事实（{evidence_note}）+ 日期 + 口径 → 它把"
        f"兑现路径的哪一环变强/变弱」。本期没有新增产业证据就逐字写「本期无新增产业"
        f"证据」，不拿旧闻和研报观点充数。段末写「未知项」：还缺哪份材料才能判兑现。",
        f"2. **{PRICING_HEADING}**（标题逐字）：对照事前预期（若有）、已经发生的价格反应、"
        f"以及拥挤度分位，市场已经反映了多少？哪些部分仍然无法判断？"
        f"{crowding_note}拥挤度用**相对分位**表述，不用绝对成交额；取不到就写"
        f"「拥挤度未取到」，不许用「放量」「情绪高涨」这类绝对量词替代。",
        f"3. **没有事前预期来源时，本段只报告价格状态**：逐字写「{NO_CONSENSUS_DECLARATION}」，"
        f"并且不得把「已经涨了很多」当成「市场已经相信」的证据——涨幅是价格事实，"
        f"共识是另一件需要独立来源（卖方一致预期、指引、事前调研）才能说的事。",
        "4. 两段**分别给结论**，不合并成一个多空判断：允许「产业证据确实增强，但价格已较"
        "拥挤」同时成立，也允许反过来；不得用其中一段的结论否掉另一段的事实。",
        "5. 禁止投票式判定（「六项里满足四项所以…」这类阈值）：价格反应、资金、拥挤度"
        "共享同一批成交数据，彼此相关，独立计票等于把一个信号数三遍。",
        "6. 不把融资余额、龙虎榜席位、北向口径直接解释成某类投资者的意图或情绪；"
        "只报可观察的量与口径，动机写成待验证问题。缺资金主动性数据就写「未知」，"
        "不用形容词补位。",
        "7. 历史日期的问题只使用**截至提问日已知**的数据；事件之后的收益只能用于事后"
        "评价，不得当作当时的定价证据回填进判断。",
    ]


def build_pricing_split_guidance() -> str:
    """逻辑/定价二分表达契约（注入 synthesis prompt；legacy 检索块记号）。"""
    return "\n".join(
        [
            "## 产业证据 / 定价状态二分契约（本题在问「逻辑变强了还是已经反映了」，"
            "两问必须分开答）",
            *_structure_lines(
                "证据编号如 [D6]/[W7]/[L1-x]",
                "[D6] 块若在场，拥挤度分位逐字引用其读数；",
            ),
        ]
    )


def build_pricing_split_guidance_for_episode() -> str:
    """episode 主路径版——纪律同 :func:`build_pricing_split_guidance`，证据记号换成 E1、E2…。"""
    return "\n".join(
        [
            "【产业证据 / 定价状态二分契约】本题在问「逻辑变强了还是已经反映了」，"
            "draft 必须把两问分开答（这些是正文表达要求，不是可绑定的 output_id）：",
            *_structure_lines(
                "证据序号 E1、E2…",
                "盘面工具返回拥挤度分位时逐字引用；",
            ),
        ]
    )


def pricing_split_guidance_for_query(query: str, question_type: str | None = None) -> str:
    """命中意图返回表达契约，否则空串（不注入，行为不变）。"""
    if not parse_pricing_split_intent(query, question_type):
        return ""
    return build_pricing_split_guidance()


def episode_pricing_split_rule(query: str, question_type: str | None = None) -> str:
    """episode 指令的条件注入口：命中定价状态意图返回 episode 版契约，否则空串。"""
    if not parse_pricing_split_intent(query, question_type):
        return ""
    return build_pricing_split_guidance_for_episode()


# ——————————————————————————————————————————— 程序核对（只进收据）
_NO_NEW_EVIDENCE_RE = re.compile(r"本期无新增产业证据|无新增产业证据")
_CROWDING_RE = re.compile(r"拥挤度")
_VOTE_RE = re.compile(r"(?:六|6|五|5|四|4)项(?:里|中)?(?:满足|命中|符合)|满足\s*\d\s*项")
_CONSENSUS_CLAIM_RE = re.compile(r"涨(?:了)?(?:这么多|很多|幅巨大).{0,12}(?:说明|证明|意味着).{0,12}(?:共识|市场已经相信|已被认可)")


def missing_pricing_split_elements(answer: str) -> tuple[str, ...]:
    """答案缺了契约的哪几件。非定价题的调用方应先自己判断要不要查。"""
    text = str(answer or "")
    missing: list[str] = []
    if EVIDENCE_HEADING not in text and not _NO_NEW_EVIDENCE_RE.search(text):
        missing.append("industrial_evidence_section")
    if PRICING_HEADING not in text:
        missing.append("pricing_state_section")
    if not _CROWDING_RE.search(text):
        missing.append("crowding_reading")
    return tuple(missing)


def pricing_split_violations(answer: str) -> tuple[str, ...]:
    """答案踩了哪几条明确禁令。命中即为反例，同题对照实验读它。"""
    text = str(answer or "")
    violations: list[str] = []
    if _VOTE_RE.search(text):
        violations.append("vote_threshold")
    if _CONSENSUS_CLAIM_RE.search(text):
        violations.append("price_as_consensus_proof")
    return tuple(violations)


def pricing_split_receipt(
    answer: str,
    *,
    query: str = "",
    question_type: str | None = None,
    as_of: str | None = None,
) -> dict[str, Any]:
    """EVAL 可读收据：意图、缺件、禁令命中。同题对照实验读它。"""
    intent = parse_pricing_split_intent(query, question_type)
    return {
        "check": "pricing_split",
        "pricing_split_intent": intent,
        "missing_elements": list(missing_pricing_split_elements(answer)) if intent else [],
        "violations": list(pricing_split_violations(answer)) if intent else [],
        "declared_no_consensus_source": NO_CONSENSUS_DECLARATION in str(answer or ""),
        "as_of": as_of,
    }


__all__ = [
    "EVIDENCE_HEADING",
    "NO_CONSENSUS_DECLARATION",
    "PRICING_HEADING",
    "build_pricing_split_guidance",
    "build_pricing_split_guidance_for_episode",
    "episode_pricing_split_rule",
    "is_pricing_state_query",
    "missing_pricing_split_elements",
    "parse_pricing_split_intent",
    "pricing_split_guidance_for_query",
    "pricing_split_receipt",
    "pricing_split_violations",
]
