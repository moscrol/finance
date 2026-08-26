"""Canonical 意图路由表：意图识别与派单的单一事实源。

每一行把一种用户意图映射到 lane / question_type / answer owner / 能力集。
LLM Turn Controller 只能在这张表里选一行（受约束选择），
`QUESTION_OWNER_SKILLS` 等下游契约由本表派生，不得另行维护。
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Literal, TypeAlias

# 快速事实（取值）查询的词面识别。放在本表而不是各分类器里，是因为本仓有两条
# 并行的题型判定链——turn_controller 决定任务契约的 required_outputs，
# answer_orchestrator.plan_answer_question 决定 rubric 用哪几个维度——两边各写一份
# 词表就会漂移：实测「宁德时代今天收盘多少」曾同时被判成 market_forecast，
# 于是被要求给出情景路径与失效条件，两头都判失败。
QUICK_FACT_PATTERN = re.compile(
    r"(?:(?<!\d)\d{6}(?!\d).{0,8}(?:是哪家公司|什么公司|代码对应)"
    r"|(?:股价|市盈率|市净率|股票代码).{0,10}"
    r"(?:多少|多少倍|是什么|是多少)"
    r"|(?:收盘|开盘|最高价|最低价|涨幅|跌幅|振幅|成交额|成交量|换手率|市值)"
    r"价?.{0,10}(?:多少|是多少|报多少|几个点)"
    r"|(?:涨|跌)了多少)"
)
# 要的是判断而不是数值：命中时不判快速事实。既包括前瞻（「明天收盘多少」问的是
# 预测），也包括分析请求（「市盈率多少倍，基本面怎么样」要的是研究，不是取值）。
JUDGMENT_REQUEST_PATTERN = re.compile(
    r"(?:明天|明日|次日|后市|未来|接下来|预测|展望|研判"
    r"|怎么看|如何看|怎么样|怎样|如何评价|值不值|贵不贵|会不会|能不能涨"
    r"|分析一下|深挖|逻辑|机会|风险)"
)


def is_quick_fact_query(query: str) -> bool:
    """这句话是不是在要一个确定的数值/代码，而不是要一个判断。

    这是**意图**判断，与主语无关：「光刻胶板块今天成交额多少」主语是题材、
    「300750是哪家公司」主语是公司，两者要的都是一个确定的值。上游 envelope
    按主语给题型（theme_analysis / stock_deep_dive），会把这层意图压掉。
    """
    text = str(query or "")
    return bool(QUICK_FACT_PATTERN.search(text)) and not JUDGMENT_REQUEST_PATTERN.search(text)


_DATED_METRIC_WORDS = re.compile(
    r"(成交额|成交量|收盘价|收盘|开盘价|涨幅|跌幅|涨了多少|跌了多少)"
)
_ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def is_dated_metric_query(query: str) -> bool:
    """带 ISO 日期的指标取值：仍是 quick_fact，但不得走 knowledge 车道。

    C4/C5 的失败形态是 ``knowledge_lane_answer``。题型保持取值，车道改 research。
    「茅台现在股价多少」没有日期锚，继续 knowledge。
    """

    text = str(query or "")
    if JUDGMENT_REQUEST_PATTERN.search(text):
        return False
    if not _ISO_DATE_RE.search(text):
        return False
    return bool(_DATED_METRIC_WORDS.search(text))


def research_lane_for_dated_quick_fact(
    row: RouteRow | None, query: str
) -> RouteRow | None:
    if row is None or row.route_id != "quick_fact":
        return row
    if is_dated_metric_query(query):
        return replace(row, lane="research")
    return row


RouteLane: TypeAlias = Literal[
    "chat",
    "meta",
    "knowledge",
    "research",
    "workflow",
    "clarify",
]


@dataclass(frozen=True)
class RouteRow:
    route_id: str
    description: str
    examples: tuple[str, ...]
    lane: RouteLane
    question_type: str | None
    answer_owner: str | None
    needs_retrieval: bool
    needs_template: bool
    capabilities: tuple[str, ...]


ROUTE_TABLE: tuple[RouteRow, ...] = (
    RouteRow(
        route_id="chat",
        description="寒暄、闲聊、对回答本身的反馈等与金融无关的普通对话",
        examples=("你好", "谢谢", "你觉得这个解释清楚吗"),
        lane="chat",
        question_type=None,
        answer_owner=None,
        needs_retrieval=False,
        needs_template=False,
        capabilities=(),
    ),
    RouteRow(
        route_id="meta",
        description="关于系统、模型、能力边界的元问题",
        examples=("你是什么模型", "你能做什么"),
        lane="meta",
        question_type=None,
        answer_owner=None,
        needs_retrieval=False,
        needs_template=False,
        capabilities=(),
    ),
    RouteRow(
        route_id="clarify",
        description="指代不明、信息不足，需要先向用户澄清",
        examples=("帮我看看", "那这个呢"),
        lane="clarify",
        question_type=None,
        answer_owner=None,
        needs_retrieval=False,
        needs_template=False,
        capabilities=(),
    ),
    RouteRow(
        route_id="concept_definition",
        description="概念定义或静态知识解释，不依赖时效数据",
        examples=("卫星互联网是什么", "什么是EV/EBITDA"),
        lane="knowledge",
        question_type="concept_definition",
        answer_owner=None,
        needs_retrieval=False,
        needs_template=False,
        capabilities=(),
    ),
    RouteRow(
        route_id="methodology_discussion",
        description="Agent、RAG、编排、检索或验证机制的方法论与工程取舍",
        examples=("RAG 怎么做", "编排层为什么会导致模板化"),
        lane="knowledge",
        question_type="methodology_discussion",
        answer_owner=None,
        needs_retrieval=False,
        needs_template=False,
        capabilities=(),
    ),
    RouteRow(
        route_id="fresh_knowledge",
        description="含时效词的一般知识问题（主体不是可验证的金融标的）",
        examples=("PQC最新消息", "量子计算最近有什么新闻"),
        lane="knowledge",
        question_type="general_knowledge",
        answer_owner=None,
        needs_retrieval=True,
        needs_template=False,
        capabilities=("web_search", "web_fetch", "market_news"),
    ),
    RouteRow(
        route_id="market_watch",
        description="询问当日盘面的关注点、看点或整体情况",
        examples=("今天有什么值得关注的", "今日盘面有哪些看点"),
        lane="workflow",
        question_type="market_watch",
        answer_owner=None,
        needs_retrieval=True,
        needs_template=True,
        capabilities=("memory", "market_quote", "graph"),
    ),
    RouteRow(
        route_id="watchlist_digest",
        description="按用户画像自选清单出当日接合简报（对着清单说话，不是全市场日报，也不是买卖建议）",
        examples=("按我的自选出今天的简报", "我的自选今天怎么样"),
        lane="workflow",
        question_type="watchlist_digest",
        answer_owner=None,
        needs_retrieval=True,
        needs_template=True,
        capabilities=("memory", "market_quote"),
    ),
    RouteRow(
        route_id="dated_market_review",
        description="指定日期的A股行情总结、复盘或分析",
        examples=("复盘7月16日的A股市场", "7.16的行情你分析一下"),
        lane="workflow",
        question_type="dated_market_review",
        answer_owner=None,
        needs_retrieval=True,
        needs_template=True,
        capabilities=("memory", "market_quote", "graph"),
    ),
    RouteRow(
        route_id="market_forecast",
        description="基于当前A股市场数据做后市展望、条件化推演与验证路径",
        examples=("基于目前市场数据，后面市场会怎么演绎", "展望一下A股后市"),
        lane="research",
        question_type="market_forecast",
        answer_owner=None,
        needs_retrieval=True,
        needs_template=True,
        capabilities=("memory", "market_quote", "graph"),
    ),
    RouteRow(
        route_id="market_cause",
        description="解释指定时间窗口内市场涨跌的主要原因，必须合并周内盘面变化与事件/资金证据；不能用单日复盘快照代答",
        examples=("这一周行情下跌的主要原因是什么", "近一周大盘为什么走弱"),
        lane="research",
        question_type="market_cause",
        answer_owner=None,
        needs_retrieval=True,
        needs_template=False,
        capabilities=("market_quote", "market_news", "web_search"),
    ),
    RouteRow(
        route_id="market_technical",
        description="指数或个股的技术位问题：支撑位、压力位、均线位置、突破/跌破点位，用结构化行情确定性计算，不做题材研究",
        examples=("科创50的支撑点位在哪", "沪深300压力位在哪里", "上证指数回踩到哪有支撑"),
        lane="research",
        question_type="market_technical",
        answer_owner=None,
        needs_retrieval=True,
        needs_template=False,
        capabilities=("market_quote",),
    ),
    RouteRow(
        route_id="external_market",
        description="海外或外部市场（美股、港股、汇率、大宗）的行情与走势",
        examples=("昨天美股的涨跌情况", "港股今天怎么样"),
        lane="research",
        question_type="external_market",
        answer_owner=None,
        needs_retrieval=True,
        needs_template=True,
        capabilities=("market_quote", "market_news", "web_search"),
    ),
    RouteRow(
        route_id="stock_deep_dive",
        description="针对具体公司的深度研究、观点或买卖判断",
        examples=("中际旭创怎么看", "深度分析宁德时代"),
        lane="research",
        question_type="stock_deep_dive",
        answer_owner="stock-deep-dive",
        needs_retrieval=True,
        needs_template=True,
        capabilities=("memory", "market_quote", "graph", "financials"),
    ),
    RouteRow(
        route_id="valuation_estimate",
        description="针对具体公司的估值高低或上涨空间判断",
        examples=("中际旭创估值贵不贵", "宁德时代还有多少上涨空间"),
        lane="research",
        question_type="valuation_estimate",
        answer_owner="stock-deep-dive",
        needs_retrieval=True,
        needs_template=True,
        capabilities=("memory", "market_quote", "graph", "financials"),
    ),
    RouteRow(
        route_id="disclosure_scan",
        description="板块/行业范围内，近期官方披露里哪些个股有偏利好公告的名单扫描",
        examples=(
            "医药和科技板块有哪些个股有比较利好的公告",
            "最近医药有哪些公司出了利好公告",
            "电子板块近一周中标或合同公告有哪些",
        ),
        lane="research",
        question_type="disclosure_scan",
        answer_owner=None,
        needs_retrieval=True,
        needs_template=True,
        capabilities=(),
    ),
    RouteRow(
        route_id="theme_analysis",
        description="针对题材、板块或产业链的进展、催化与投资逻辑",
        examples=("最近固态电池有什么新进展", "低空经济这个题材还能不能追"),
        lane="research",
        question_type="theme_analysis",
        answer_owner="theme-research",
        needs_retrieval=True,
        needs_template=True,
        capabilities=("memory", "market_quote", "graph"),
    ),
    RouteRow(
        route_id="news_impact",
        description="某个事件、公告或消息对公司/板块的影响判断",
        examples=(
            "英伟达GPU发布对光模块板块的影响",
            "宁德时代最新公告有什么影响",
        ),
        lane="research",
        question_type="news_impact",
        answer_owner="news-impact",
        needs_retrieval=True,
        needs_template=True,
        capabilities=("memory", "market_news", "graph", "web_search"),
    ),
    RouteRow(
        route_id="financial_analysis",
        description="针对具体公司财报、收入利润毛利率等财务数据的分析",
        examples=("宁德时代Q2财报怎么看", "分析一下中际旭创的毛利率"),
        lane="research",
        question_type="financial_analysis",
        answer_owner="financial-analysis",
        needs_retrieval=True,
        needs_template=True,
        capabilities=("memory", "financials", "filings", "graph"),
    ),
    RouteRow(
        route_id="quick_fact",
        description="要一个确定的数字/代码/日期的快速事实查询，先检索行情确认再短答，不派研究流程",
        examples=("茅台现在股价多少", "英伟达市盈率多少倍", "300750是哪家公司"),
        lane="knowledge",
        question_type="quick_fact",
        answer_owner=None,
        needs_retrieval=True,
        needs_template=False,
        capabilities=("market_quote", "memory"),
    ),
    RouteRow(
        route_id="theme_track",
        description="题材/行业的持续跟踪：近期边际变化、信号与进展（区别于一次性全景分析）",
        examples=("光伏最近一个月有什么新变化", "动力电池产业链近况跟踪一下"),
        lane="research",
        question_type="theme_track",
        answer_owner="theme-research",
        needs_retrieval=True,
        needs_template=True,
        capabilities=("memory", "market_quote", "market_news", "graph"),
    ),
    RouteRow(
        route_id="event_forecast",
        description="对未发生事件的概率判断、情景推演与price-in程度（区别于已发生消息的影响）",
        examples=("美联储9月降息25还是50bp", "苹果发AI功能能不能推动换机潮"),
        lane="research",
        question_type="event_forecast",
        answer_owner=None,
        needs_retrieval=True,
        needs_template=True,
        capabilities=("memory", "market_news", "web_search", "graph"),
    ),
    RouteRow(
        route_id="kol_review",
        description="对某个KOL观点、专家判断或研报的证据强度、立场与偏差的分析",
        examples=(
            "但斌说茅台到顶了逻辑有没有漏洞",
            "这份高盛AI算力研报核心假设站得住吗",
        ),
        lane="research",
        question_type="kol_review",
        answer_owner=None,
        needs_retrieval=True,
        needs_template=True,
        capabilities=("memory", "web_search", "market_news"),
    ),
    RouteRow(
        route_id="comparison_analog",
        description="跨行业/跨历史的类比、可比公司寻找与反方视角检验",
        examples=(
            "2015互联网泡沫和现在AI行情有什么异同",
            "液冷历史上有没有类似导入期行业可类比",
        ),
        lane="research",
        question_type="comparison_analog",
        answer_owner=None,
        needs_retrieval=True,
        needs_template=True,
        capabilities=("memory", "graph", "web_search"),
    ),
    RouteRow(
        route_id="comparison",
        description="同一问题中对两个或多个对象按统一维度比较",
        examples=(
            "液冷和风冷的优势分别是什么",
            "这三家公司的竞争优势如何比较",
        ),
        lane="research",
        question_type="comparison",
        answer_owner=None,
        needs_retrieval=True,
        needs_template=True,
        capabilities=("memory", "graph", "web_search"),
    ),
    RouteRow(
        route_id="fact_check",
        description="核验某个说法、数据或逻辑链条是否站得住脚，需给出来源与证据评级",
        examples=(
            "网传台积电砍了3nm订单有可靠来源吗",
            "这份研报说液冷市场500亿帮我核一下",
        ),
        lane="research",
        question_type="fact_check",
        answer_owner=None,
        needs_retrieval=True,
        needs_template=True,
        capabilities=("memory", "web_search", "market_news", "filings"),
    ),
    RouteRow(
        route_id="trade_advice",
        description="直接买卖/加减仓建议，降级为条件化thesis check（估值分位+催化+风险+时间框架），不输出确定性买卖结论",
        examples=("茅台现在该不该买", "宁德时代要不要止损"),
        lane="research",
        question_type="trade_advice",
        answer_owner="stock-deep-dive",
        needs_retrieval=True,
        needs_template=True,
        capabilities=("memory", "market_quote", "graph", "financials"),
    ),
)

ROUTE_INDEX: dict[str, RouteRow] = {row.route_id: row for row in ROUTE_TABLE}


def route_by_id(route_id: str) -> RouteRow | None:
    return ROUTE_INDEX.get(route_id)


def owner_skills_from_route_table() -> dict[str, str]:
    """由路由表派生 question_type → answer owner 契约（单一事实源）。"""
    return {
        row.question_type: row.answer_owner
        for row in ROUTE_TABLE
        if row.question_type is not None and row.answer_owner is not None
    }


def render_route_table_prompt() -> str:
    """把路由表渲染成 LLM 提示词里的受约束选项清单。"""
    lines = []
    for row in ROUTE_TABLE:
        examples = "；".join(row.examples)
        lines.append(f"- {row.route_id}：{row.description}（例：{examples}）")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 主车道 + overlay：不改 RouteRow / question_type，只追加证据 capabilities。
# resolve_evidence_plan 通吃整表；新混合形状加一行，不再在 plan 里堆 if。
# ---------------------------------------------------------------------------

# 隔夜 / 外盘前提。只用市场专名，不用单独的「今晚」——「今晚复盘」仍是纯 A 股预测。
# 与 query_understanding._EXTERNAL_MARKET_TERMS 对齐，并补上外盘/隔夜（那边把隔夜
# 放在报价词里，单独不够把混合预测改道到 external_market）。
_OVERNIGHT_EXTERNAL_MARKERS = (
    "美股",
    "纳指",
    "纳斯达克",
    "费半",
    "费城半导体",
    "道指",
    "标普",
    "外盘",
    "隔夜",
    "soxx",
    "qqq",
    "海外",
)

# 外部宏观事件词必须收紧：单独「新闻」「CPI」不触发。CPI 只认「同比」这种事件口径。
_EXTERNAL_MACRO_EVENT_MARKERS = (
    "美联储",
    "fomc",
    "非农",
    "cpi同比",
)

# 本地推演侧：必须问 A 股/板块/推演，纯「美联储会不会降息」走 event_forecast，不加 overlay。
_LOCAL_INFERENCE_MARKERS = (
    "a股",
    "板块",
    "推演",
)


def _normalize_query_markers(query: str) -> str:
    return re.sub(r"\s+", "", str(query or "")).casefold()


def _has_overnight_external_premise(query: str) -> bool:
    """隔夜/外盘专名是否出现。episode_tools 与组合表第一条共用此实现。"""
    normalized = _normalize_query_markers(query)
    return any(marker.casefold() in normalized for marker in _OVERNIGHT_EXTERNAL_MARKERS)


def _has_external_macro_event_local_inference(query: str) -> bool:
    """外部宏观事件 + 本地 A 股/板块推演。两翼都要，避免每条新闻题开火。"""
    normalized = _normalize_query_markers(query)
    has_event = any(
        marker.casefold() in normalized for marker in _EXTERNAL_MACRO_EVENT_MARKERS
    )
    has_local = any(
        marker.casefold() in normalized for marker in _LOCAL_INFERENCE_MARKERS
    )
    return has_event and has_local


@dataclass(frozen=True)
class LaneCompositionRule:
    """(谓词, 追加 capabilities, 规则名)。overlay 只追加、不删、不改主车道。"""

    predicate: Callable[[str], bool]
    extra_capabilities: tuple[str, ...]
    rule_name: str


LANE_COMPOSITION_RULES: tuple[LaneCompositionRule, ...] = (
    LaneCompositionRule(
        _has_overnight_external_premise,
        ("news_search", "web_search"),
        "overnight_external_premise",
    ),
    LaneCompositionRule(
        _has_external_macro_event_local_inference,
        ("news_search", "web_search"),
        "external_macro_event_local_inference",
    ),
)
