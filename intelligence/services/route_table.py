"""Canonical 意图路由表：意图识别与派单的单一事实源。

每一行把一种用户意图映射到 lane / question_type / answer owner / 能力集。
LLM Turn Controller 只能在这张表里选一行（受约束选择），
`QUESTION_OWNER_SKILLS` 等下游契约由本表派生，不得另行维护。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

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
