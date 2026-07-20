from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from intelligence.services.entity_anchor import EntityAnchor
from intelligence.services.market_analogs import parse_analog_intent
from intelligence.services.market_midterm import parse_midterm_intent
from intelligence.services.scenario_tree import parse_scenario_intent


SubjectKind = Literal[
    "company",
    "theme",
    "index",
    "market_pattern",
    "external_market",
    "unknown",
]
MatchedBy = Literal[
    "ticker",
    "entity",
    "candidate",
    "alias",
    "quoted",
    "explicit",
    "definition",
    "market_anchor",
    "generic",
]
ResearchMode = Literal[
    "deep_dive",
    "financial",
    "news_impact",
    "theme_research",
    "forecast",
    "definition",
    "market_cause",
    "methodology",
    "general",
]
TimeHorizon = Literal[
    "intraday",
    "short",
    "medium",
    "long",
    "3_to_6_months",
    "unspecified",
]
ResearchOperator = Literal[
    "history_analog",
    "scenario_tree",
    "counterevidence",
    "money_flow",
    "comparison",
    "relation",
    "company_mapping",
    "market_change",
    "cause_attribution",
]

THEME_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "theme_research_specs.json"
)
_DATE_RE = re.compile(
    r"(?<!\d)20\d{2}(?:"
    r"年(?:\d{1,2}(?:月(?:\d{1,2}日?)?)?)?"
    r"|[-/.]\d{1,2}(?:[-/.]\d{1,2}日?)?"
    r")(?!\d)"
)
_REVIEW_DATE_RE = (
    r"(?:20\d{2}(?:年\d{1,2}月\d{1,2}日?|"
    r"[-/.]\d{1,2}[-/.]\d{1,2})"
    r"|\d{1,2}(?:月\d{1,2}日?|[./]\d{1,2}(?![\d%个万亿千倍])))"
)
_DATED_MARKET_REVIEW_RE = re.compile(
    _REVIEW_DATE_RE
    + r".{0,24}(?:行情|盘面|市场).{0,12}(?:总结|复盘|回顾|梳理|分析)"
    r"|(?:总结|复盘|回顾|梳理|分析).{0,24}"
    + _REVIEW_DATE_RE
    + r".{0,12}(?:行情|盘面|市场)",
    re.IGNORECASE,
)
_FULL_DATE_RE = re.compile(
    r"(?<!\d)(20\d{2})(?:年|[-/.])(\d{1,2})(?:月|[-/.])(\d{1,2})日?(?!\d)"
)
_YEARLESS_DATE_RE = re.compile(
    r"(?<!\d)(\d{1,2})(?:月|[./])(\d{1,2})日?(?![\d%个万亿千倍])"
)
_QUOTED_RE = re.compile(r"[“《\"]([^”》\"]{2,40})[”》\"]")
_TICKER_RE = re.compile(
    r"(?<![A-Za-z0-9])\d{6}(?:\.(?:SH|SZ|BJ))?(?![A-Za-z0-9])",
    re.I,
)
_EXPLICIT_CUE_RE = re.compile(r"(?:研究|分析|看看|深挖)")
_EXPLICIT_TOPIC_RE = re.compile(
    r"([\u4e00-\u9fffA-Za-z0-9+.-]{2,16}?)(?:题材|板块|产业链|方向)"
)
_GENERIC_EXPLICIT_SUBJECTS = frozenset(
    {
        "这",
        "那",
        "某",
        "该",
        "一个",
        "这个",
        "那个",
        "某个",
        "某一",
        "这一",
        "这类",
        "该类",
    }
)
_GENERIC_EXPLICIT_PREFIXES = (
    "为什么",
    "这个",
    "那个",
    "某个",
    "一个",
    "某一",
    "这一",
    "这类",
    "该类",
    "该",
)
_MARKET_PATTERN_TERMS = (
    "连续上涨",
    "成交占比",
    "涨停家数",
    "指数上涨",
    "背离",
    "健康分歧",
    "行情高潮",
)
_EXTERNAL_MARKET_TERMS = (
    "美股",
    "美国股市",
    "道指",
    "道琼斯",
    "纳指",
    "纳斯达克",
    "标普500",
    "标普",
    "费半",
    "费城半导体",
    "soxx",
    "qqq",
    "海外指数",
)
_EXTERNAL_QUOTE_TERMS = (
    "昨天",
    "昨日",
    "隔夜",
    "收盘",
    "涨跌",
    "点位",
    "行情",
    "走势",
    "表现",
)
_RELATIVE_TIMEFRAMES = ("昨天", "昨日", "隔夜", "今天", "今日", "最新", "本周", "这一周", "这周", "近一周", "过去一周", "一周内")
_DEFINITION_PREFIX_RE = re.compile(
    r"^(?:请|帮我|介绍一下|解释一下|分析一下|研究一下)*什么是"
    r"([\u4e00-\u9fffA-Za-z0-9+.-]{2,24})"
)
_DEFINITION_SUFFIX_RE = re.compile(
    r"^(?:请|帮我|介绍一下|解释一下|分析一下|研究一下)*"
    r"([\u4e00-\u9fffA-Za-z0-9+.-]{2,24}?)"
    r"(?:是什么|的?技术原理|如何工作|的?产业链位置)"
)
_VALUATION_SUBJECT_RE = re.compile(
    r"^(?:请|帮我|麻烦)?(?:给我)?(?:拍估值[：:]?)?"
    r"([\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9·.&+-]{1,15}?)"
    r"(?:现在)?(?:估值怎么看|贵不贵|值多少钱|合理估值|估值分位)$"
)
_COMPANY_CUE_RES = (
    re.compile(
        r"(?:个股深挖|个股研究|深挖|研究|分析|看看)"
        r"([\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9·.&+-]{1,15}?)"
        r"(?=的|最新|财报|公告|消息|新闻|现在|还有|上涨空间|估值|$)"
    ),
    re.compile(
        r"^(?:请|帮我|麻烦)?"
        r"([\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9·.&+-]{1,15}?)"
        r"(?=最新(?:[\u4e00-\u9fffA-Za-z0-9·.&+-]{0,8})?"
        r"(?:财报|公告|消息|新闻)|还有上涨空间|上涨空间|"
        r"的(?:[\u4e00-\u9fffA-Za-z0-9·.&+-]{0,8})?(?:业务|财报|公告)|"
        r"现在(?:怎么样|怎么看|贵不贵|估值))"
    ),
)
_GENERIC_COMPANY_SUBJECTS = frozenset(
    {
        "公司",
        "个股",
        "股票",
        "题材",
        "板块",
        "行业",
        "市场",
        "固态电池",
        "液冷",
        "光刻胶",
        "商业航天",
        "AI眼镜",
        "AI 眼镜",
    }
)
_FINANCIAL_ANALYSIS_RE = re.compile(
    r"(财报|定期报告|业绩|营收|收入|利润|归母|毛利率|净利率)"
)
_NEWS_IMPACT_RE = re.compile(r"(公告|消息|新闻|原文|影响)")
_NEWS_IMPACT_TARGET_RE = re.compile(
    r"(?:发布|公告|消息|新闻|事件|政策|关税|制裁|降息|加息|中标|签约|落地)"
    r"[^。？！]*?"
    r"对([^。？！，,对]{1,24}?)(?:板块|行业|个股|公司|产业链)?的?"
    r"(?:影响|冲击|利好|利空)"
)
_RELATED_NEWS_TOPIC_RE = re.compile(
    r"^(?:请|帮我|麻烦)?(?:分析|研究|看看)?(?:一下)?"
    r"(?:近期|最近|最新|今日|今天)?"
    r"([\u4e00-\u9fffA-Za-z0-9+._-]{2,24}?)"
    r"相关(?:公告|消息|新闻|事件)"
)
_MARKET_WATCH_RE = re.compile(
    r"(?:今天|今日)(?:(?:的)?(?:A股|市场|行情|盘面|大盘)(?:上|里|中)?)?"
    r"(?:有什么|有哪些|哪些)?(?:值得关注|看点|主线|机会)"
    r"|(?:今天|今日)(?:的)?(?:市场|行情|盘面|大盘)(?:怎么样|如何|表现如何)"
    r"|(?:今天|今日)(?:的)?(?:A股|市场|行情|盘面|大盘)?复盘"
)
_MARKET_FORECAST_RE = re.compile(
    r"(?:展望|研判|预测)[^。？！]{0,16}(?:后市|市场|行情|大盘)"
    r"|(?:后市|后面市场|接下来市场|未来市场)[^。？！]{0,16}"
    r"(?:怎么|如何|演绎|走势|走)"
    r"|(?:市场|行情|大盘)[^。？！]{0,12}(?:后面|接下来|未来)"
    r"[^。？！]{0,8}(?:演绎|走势|怎么走|如何走)"
)
_MARKET_CAUSE_RE = re.compile(
    r"(?:(?:本周|这一周|这周|近一周|过去一周|一周内).{0,20}"
    r"(?:行情|大盘|市场|指数).{0,16}(?:下跌|上涨|回撤|走弱|走强).{0,16}"
    r"(?:主要原因|原因|为什么|驱动|归因))"
    r"|(?:(?:行情|大盘|市场|指数).{0,12}(?:下跌|上涨|回撤|走弱|走强).{0,12}"
    r"(?:主要原因|原因|为什么|驱动|归因))"
)
_MONTH_HORIZON_RE = re.compile(
    r"(?:未来|接下来)?\s*(\d{1,2})\s*(?:[-~—到至]\s*(\d{1,2})\s*)?个?月"
)
_COMPOSITIONAL_SUBJECT_CUE_RE = re.compile(r"(?:研究|分析|深挖|评估)")
_COMPOSITIONAL_SUBJECT_BOUNDARIES = (
    "未来",
    "接下来",
    "中期赔率",
    "中长期赔率",
    "历史类似",
    "历史类比",
    "历史相似",
    "情景树",
    "升级",
    "降级",
    "证伪",
)
_COUNTEREVIDENCE_RE = re.compile(r"(反证|证伪|降级条件|证伪条件|升级、降级)")
_MONEY_FLOW_RE = re.compile(r"(资金流|主买|净流入|大单)")
_COMPARISON_RE = re.compile(r"(比较|对比|相比|赔率排序)")
_RELATION_RE = re.compile(r"(上游|下游|供应|客户|产业链位置|处于.{0,8}环节|关系)")
_COMPANY_MAPPING_RE = re.compile(r"(有哪些公司|哪些公司|受益公司|公司映射|核心公司)")
_MARKET_CHANGE_RE = re.compile(r"(边际变化|最近变化|近期变化|预期差变化)")

# 认识论分流：这些问题要回答的是系统/方法本身，而不是某个金融标的的
# 当前事实。若把它们送进金融 RAG，检索器会因为词面命中“模板化/编排”等词
# 返回无关研报，最终用有证据但不相关的材料替代模型原生推理。
_METHODOLOGY_SUBJECT_RE = re.compile(
    r"(?:"
    r"(?:agent|rag|bm25|rerank|prompt|verifier|workflow)"
    r"|编排层|路由层|检索层|合成层|验证器|系统架构|工作台架构|"
    r"模型能力|工具调用|向量检索|混合检索|模板化回答|模板化|"
    r"深度研究(?:agent|代理)|研究代理"
    r")",
    re.IGNORECASE,
)
_METHODOLOGY_GOAL_RE = re.compile(
    r"(?:为什么|怎么(?:做|实现)?|如何(?:做|实现)?|原理|架构|设计|实现|"
    r"优化|权衡|取舍|导致|机制|区别|比较|路径)",
    re.IGNORECASE,
)

# 确定性技术位头部意图：指数别名 → 标准指数代码。
# 名称按长度降序匹配，避免「科创50」被「科创」类题材别名截胡。
INDEX_ALIASES: tuple[tuple[str, str, str], ...] = (
    ("科创50", "000688.SH", "科创50"),
    ("科创五十", "000688.SH", "科创50"),
    ("科创板50", "000688.SH", "科创50"),
    ("科创100", "000698.SH", "科创100"),
    ("上证50", "000016.SH", "上证50"),
    ("上证指数", "000001.SH", "上证指数"),
    ("上证综指", "000001.SH", "上证指数"),
    ("沪深300", "000300.SH", "沪深300"),
    ("中证500", "000905.SH", "中证500"),
    ("中证1000", "000852.SH", "中证1000"),
    ("中证2000", "932000.CSI", "中证2000"),
    ("深证成指", "399001.SZ", "深证成指"),
    ("创业板指", "399006.SZ", "创业板指"),
    ("创业板指数", "399006.SZ", "创业板指"),
    ("北证50", "899050.BJ", "北证50"),
    ("万得微盘", "8841431.WI", "万得微盘股"),
    ("微盘股指数", "8841431.WI", "万得微盘股"),
)
_TECHNICAL_LEVEL_RE = re.compile(
    r"支撑(?:位|点位|区|区域|在哪|位置)"
    r"|(?:压力|阻力)(?:位|点位|区|区域|在哪|位置)"
    r"|(?:突破|跌破)(?:位|点位|价位)"
    r"|均线(?:支撑|压力|位置|在哪)"
    r"|(?:回踩|回调)(?:到哪|支撑)"
    r"|技术(?:位|点位|支撑|压力)"
    r"|颈线|缺口(?:回补|支撑)"
)


def match_index_subject(query: str) -> tuple[str, str] | None:
    """在问题中匹配指数别名，返回 (标准名, 指数代码)；未命中返回 None。"""
    text = re.sub(r"\s+", "", str(query or ""))
    for alias, ts_code, canonical in sorted(
        INDEX_ALIASES, key=lambda item: len(item[0]), reverse=True
    ):
        if alias in text:
            return canonical, ts_code
    return None


def is_market_technical_query(query: str) -> bool:
    """确定性识别「指数/股票 + 支撑位/压力位/均线/突破位」类技术位问题。"""
    text = re.sub(r"\s+", "", str(query or ""))
    if _TECHNICAL_LEVEL_RE.search(text) is None:
        return False
    return (
        match_index_subject(text) is not None
        or _TICKER_RE.search(text) is not None
    )


def is_methodology_query(query: str) -> bool:
    """识别系统/Agent 方法论问题，避免被金融知识检索的词面命中劫持。"""

    text = re.sub(r"\s+", "", str(query or ""))
    return bool(
        text
        and _METHODOLOGY_SUBJECT_RE.search(text)
        and _METHODOLOGY_GOAL_RE.search(text)
    )


@dataclass(frozen=True)
class QueryEnvelope:
    question_type: str
    subject_kind: SubjectKind
    subject: str | None
    decision_goal: str
    timeframe: str | None
    matched_by: MatchedBy
    confidence: float
    research_mode: ResearchMode = "general"
    time_horizon: TimeHorizon = "unspecified"
    operators: tuple[ResearchOperator, ...] = ()
    required_outputs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["operators"] = list(self.operators)
        payload["required_outputs"] = list(self.required_outputs)
        return payload


def is_dated_market_review(query: str, envelope: QueryEnvelope) -> bool:
    return (
        envelope.question_type != "external_market"
        and _DATED_MARKET_REVIEW_RE.search(query) is not None
        and market_review_requested_date(query) is not None
    )


def market_review_requested_date(
    query: str,
    *,
    today: date | None = None,
) -> str | None:
    """确定性解析问题中的复盘日期，返回 ISO 日期。

    无年份写法（7.16 / 7月16日）映射为不晚于今天的最近一个同月同日，
    不交给 LLM 猜年份；无法构成合法日期时返回 None。
    """
    match = _FULL_DATE_RE.search(query)
    if match is not None:
        try:
            return date(
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3)),
            ).isoformat()
        except ValueError:
            return None
    match = _YEARLESS_DATE_RE.search(query)
    if match is None:
        return None
    month = int(match.group(1))
    day = int(match.group(2))
    anchor = today or date.today()
    for year in (anchor.year, anchor.year - 1):
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if candidate <= anchor:
            return candidate.isoformat()
    return None


@lru_cache(maxsize=1)
def _theme_aliases() -> tuple[str, ...]:
    try:
        doc = json.loads(THEME_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    if not isinstance(doc, dict):
        return ()
    packs = doc.get("packs")
    if not isinstance(packs, list):
        return ()
    aliases: list[str] = []
    for pack in packs:
        if not isinstance(pack, dict):
            continue
        pack_aliases = pack.get("aliases")
        if not isinstance(pack_aliases, list):
            continue
        aliases.extend(
            alias.strip()
            for alias in pack_aliases
            if isinstance(alias, str) and alias.strip()
        )
    return tuple(sorted(dict.fromkeys(aliases), key=len, reverse=True))


def _decision_goal(query: str) -> str:
    if is_market_cause_query(query):
        return "解释指定时间窗口内市场涨跌的主要原因并形成可回查因果链"
    if _is_external_market_query(query):
        return "核对海外指数收盘点位与涨跌幅"
    if _definition_subject(query):
        return "解释定义、技术背景与产业链位置"
    if "健康分歧" in query or "行情高潮" in query:
        return "区分健康分歧与行情高潮"
    if "背离" in query:
        return "解释市场背离"
    return "形成条件化判断"


def _is_external_market_query(query: str) -> bool:
    folded = str(query or "").casefold()
    return any(term in folded for term in _EXTERNAL_MARKET_TERMS) and any(
        term in folded for term in _EXTERNAL_QUOTE_TERMS
    )


def _definition_subject(query: str) -> str | None:
    text = re.sub(r"\s+", "", str(query or "").strip())
    if not text or re.search(r"(?:你|模型|model)", text, re.IGNORECASE):
        return None
    for pattern in (_DEFINITION_PREFIX_RE, _DEFINITION_SUFFIX_RE):
        match = pattern.search(text)
        if match is not None:
            subject = match.group(1).strip()
            if subject.endswith(("题材", "板块", "方向", "产业链")):
                return None
            return subject
    return None


def _news_impact_target(query: str) -> str | None:
    text = re.sub(r"\s+", "", str(query or "").strip())
    match = _RELATED_NEWS_TOPIC_RE.search(text)
    if match is None:
        match = _NEWS_IMPACT_TARGET_RE.search(text)
    if match is None:
        return None
    subject = match.group(1).strip()
    if not subject or subject.startswith(("这个", "那个", "该", "某")):
        return None
    return subject


def is_market_watch_query(query: str) -> bool:
    """确定性识别「今天有什么值得关注的 / 今日行情怎么样」类当日盘面提问。"""
    text = re.sub(r"\s+", "", str(query or "").strip())
    return _MARKET_WATCH_RE.search(text) is not None


def is_market_forecast_query(query: str) -> bool:
    """识别明确的全市场后市展望；不把泛泛“市场怎么样”误当预测。"""

    text = re.sub(r"\s+", "", str(query or "").strip())
    return _MARKET_FORECAST_RE.search(text) is not None


def is_market_cause_query(query: str) -> bool:
    """确定性识别「市场涨跌 + 时间窗口 + 原因/驱动」归因问题。"""
    text = re.sub(r"\s+", "", str(query or "").strip())
    return bool(text and _MARKET_CAUSE_RE.search(text))


def _valuation_subject(query: str) -> str | None:
    text = re.sub(r"\s+", "", str(query or "").strip())
    match = _VALUATION_SUBJECT_RE.search(text)
    if match is None:
        return None
    subject = match.group(1).strip()
    if (
        not subject
        or subject.startswith(("某公司", "某个", "某一", "这个", "那个", "该"))
        or subject.endswith(("题材", "板块", "行业", "产业", "赛道", "方向", "产业链"))
        or any(subject.casefold() == alias.casefold() for alias in _theme_aliases())
    ):
        return None
    return subject


def _explicit_company_subject(query: str) -> str | None:
    text = re.sub(r"\s+", "", str(query or "").strip())
    for pattern in _COMPANY_CUE_RES:
        match = pattern.search(text)
        if match is None:
            continue
        subject = match.group(1).strip()
        if (
            subject in _GENERIC_COMPANY_SUBJECTS
            or subject.startswith(
                ("某公司", "某个", "某一", "这个", "那个", "该", "截至", "为什么", "一下", "一些")
            )
            or any(
                generic in subject
                for generic in (
                    "题材",
                    "板块",
                    "行业",
                    "产业",
                    "赛道",
                    "方向",
                    "连续",
                    "成交",
                )
            )
            or re.search(r"\d{4}年|\d{1,2}月|\d{1,2}日|\d{1,2}[./-]\d{1,2}", subject)
            or subject.endswith(
                ("题材", "板块", "行业", "产业", "赛道", "方向", "产业链")
            )
            or any(subject.casefold() == alias.casefold() for alias in _theme_aliases())
        ):
            continue
        return subject
    return None


def _company_question_type(query: str) -> str:
    if re.search(r"(个股深挖|个股研究|深挖|深度分析个股)", query):
        return "stock_deep_dive"
    if _FINANCIAL_ANALYSIS_RE.search(query):
        return "financial_analysis"
    if _NEWS_IMPACT_RE.search(query):
        return "news_impact"
    return "stock_deep_dive"


def _time_horizon(query: str) -> TimeHorizon:
    text = re.sub(r"\s+", "", str(query or ""))
    month_window = _MONTH_HORIZON_RE.search(text)
    if month_window is not None:
        start = int(month_window.group(1))
        end = int(month_window.group(2) or start)
        if start == 3 and end == 6:
            return "3_to_6_months"
        if end <= 1:
            return "short"
        if end <= 6:
            return "medium"
        return "long"
    if any(term in text for term in ("盘中", "日内", "今天", "今日")):
        return "intraday"
    if any(term in text for term in ("短期", "短线", "未来几周")):
        return "short"
    if any(term in text for term in ("本周", "这一周", "这周", "近一周", "过去一周", "一周内")):
        return "short"
    if any(term in text for term in ("中期", "中线", "季度维度")):
        return "medium"
    if any(term in text for term in ("长期", "长线", "未来几年")):
        return "long"
    return "unspecified"


def _research_operators(query: str) -> tuple[ResearchOperator, ...]:
    operators: list[ResearchOperator] = []
    if parse_analog_intent(query):
        operators.append("history_analog")
    if parse_scenario_intent(query):
        operators.append("scenario_tree")
    if _COUNTEREVIDENCE_RE.search(query):
        operators.append("counterevidence")
    if _MONEY_FLOW_RE.search(query):
        operators.append("money_flow")
    if _COMPARISON_RE.search(query):
        operators.append("comparison")
    if _RELATION_RE.search(query):
        operators.append("relation")
    if _COMPANY_MAPPING_RE.search(query):
        operators.append("company_mapping")
    if _MARKET_CHANGE_RE.search(query):
        operators.append("market_change")
    if is_market_cause_query(query):
        operators.append("cause_attribution")
    return tuple(operators)


def _required_outputs(
    operators: tuple[ResearchOperator, ...],
) -> tuple[str, ...]:
    output_by_operator = {
        "history_analog": "historical_analogs",
        "scenario_tree": "scenario_tree",
        "counterevidence": "falsification_conditions",
        "money_flow": "money_flow",
        "comparison": "comparison",
        "relation": "relation_map",
        "company_mapping": "company_mapping",
        "market_change": "market_change",
        "cause_attribution": "cause_attribution",
    }
    return tuple(output_by_operator[operator] for operator in operators)


def _research_mode(
    question_type: str,
    subject_kind: SubjectKind,
    *,
    operators: tuple[ResearchOperator, ...],
) -> ResearchMode:
    if question_type == "concept_definition":
        return "definition"
    if question_type == "financial_analysis":
        return "financial"
    if question_type == "news_impact":
        return "news_impact"
    if question_type == "market_cause":
        return "market_cause"
    if question_type == "methodology_discussion":
        return "methodology"
    if question_type in {"stock_deep_dive", "valuation_estimate"}:
        return "deep_dive"
    if subject_kind == "theme":
        return "theme_research"
    if "scenario_tree" in operators:
        return "forecast"
    return "general"


def _compositional_theme_subject(
    query: str,
    *,
    operators: tuple[ResearchOperator, ...],
) -> str | None:
    if (
        parse_midterm_intent(query) is None
        or len(operators) < 2
        or "scenario_tree" not in operators
    ):
        return None
    cue = _COMPOSITIONAL_SUBJECT_CUE_RE.search(query)
    if cue is None:
        return None
    tail = query[cue.end() :].strip()
    boundaries = [
        index
        for term in _COMPOSITIONAL_SUBJECT_BOUNDARIES
        if (index := tail.find(term)) > 0
    ]
    month_window = _MONTH_HORIZON_RE.search(tail)
    if month_window is not None and month_window.start() > 0:
        boundaries.append(month_window.start())
    if not boundaries:
        return None
    subject = re.sub(r"\s+", "", tail[: min(boundaries)]).strip("，,：:")
    if (
        len(subject) < 2
        or len(subject) > 24
        or subject in _GENERIC_EXPLICIT_SUBJECTS
        or subject.startswith(_GENERIC_EXPLICIT_PREFIXES)
    ):
        return None
    return subject


def _normalize_explicit_tail(tail: str, timeframe: str | None) -> str:
    prefixes = ["我想了解", "什么是", "一下子", "一下", "A股"]
    if timeframe:
        prefixes.extend(
            (
                f"截至{timeframe}的",
                f"截至{timeframe}",
                f"{timeframe}的",
                timeframe,
            )
        )
    prefixes.sort(key=len, reverse=True)

    normalized = tail.strip()
    while normalized:
        for prefix in prefixes:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix) :].strip()
                break
        else:
            break
    return normalized


def _explicit_theme(text: str, timeframe: str | None) -> str | None:
    for cue in reversed(tuple(_EXPLICIT_CUE_RE.finditer(text))):
        tail = _normalize_explicit_tail(text[cue.end() :], timeframe)
        match = _EXPLICIT_TOPIC_RE.match(tail)
        if match is None:
            continue
        subject = match.group(1).strip()
        if (
            not subject
            or subject in _GENERIC_EXPLICIT_SUBJECTS
            or subject.startswith(_GENERIC_EXPLICIT_PREFIXES)
        ):
            continue
        return subject
    return None


def understand_query(
    query: str,
    *,
    matched_theme: str | None = None,
    anchor: EntityAnchor | None = None,
) -> QueryEnvelope:
    text = str(query or "").strip()
    operators = _research_operators(text)
    time_horizon = _time_horizon(text)
    required_outputs = _required_outputs(operators)

    def envelope(
        question_type: str,
        subject_kind: SubjectKind,
        subject: str | None,
        decision_goal: str,
        timeframe: str | None,
        matched_by: MatchedBy,
        confidence: float,
    ) -> QueryEnvelope:
        return QueryEnvelope(
            question_type,
            subject_kind,
            subject,
            decision_goal,
            timeframe,
            matched_by,
            confidence,
            research_mode=_research_mode(
                question_type,
                subject_kind,
                operators=operators,
            ),
            time_horizon=time_horizon,
            operators=operators,
            required_outputs=required_outputs,
        )

    timeframe_match = _DATE_RE.search(text)
    timeframe = (
        timeframe_match.group(0)
        if timeframe_match
        else next((term for term in _RELATIVE_TIMEFRAMES if term in text), None)
    )

    if is_market_cause_query(text):
        return envelope(
            "market_cause",
            "market_pattern",
            None,
            "解释指定时间窗口内市场涨跌的主要原因并形成可回查因果链",
            timeframe,
            "market_anchor",
            0.96,
        )

    if is_methodology_query(text):
        return envelope(
            "methodology_discussion",
            "unknown",
            None,
            "解释系统/Agent 方法、机制与工程取舍，不把无关金融资料当作答案",
            timeframe,
            "explicit",
            0.96,
        )

    if is_market_technical_query(text):
        index_hit = match_index_subject(text)
        ticker_hit = _TICKER_RE.search(text)
        if index_hit is not None:
            subject_name, _index_code = index_hit
            return envelope(
                "market_technical",
                "index",
                subject_name,
                "基于结构化行情确定性计算支撑/压力技术位",
                timeframe,
                "market_anchor",
                0.97,
            )
        if ticker_hit is not None:
            return envelope(
                "market_technical",
                "company",
                ticker_hit.group(0),
                "基于结构化行情确定性计算支撑/压力技术位",
                timeframe,
                "ticker",
                0.95,
            )

    if _is_external_market_query(text):
        return envelope(
            "external_market",
            "external_market",
            "美国股市",
            _decision_goal(text),
            timeframe,
            "market_anchor",
            0.98,
        )

    if anchor is None:
        news_target = _news_impact_target(text)
        if news_target is not None:
            return envelope(
                "news_impact",
                "theme",
                news_target,
                _decision_goal(text),
                timeframe,
                "explicit",
                0.9,
            )

    definition_subject = _definition_subject(text)
    if definition_subject is not None:
        return envelope(
            "concept_definition",
            "theme",
            definition_subject,
            _decision_goal(text),
            timeframe,
            "definition",
            0.9,
        )

    if anchor is not None:
        return envelope(
            _company_question_type(text),
            "company",
            anchor.entity,
            _decision_goal(text),
            timeframe,
            "ticker" if anchor.matched_by == "code" else "entity",
            1.0,
        )

    ticker = _TICKER_RE.search(text)
    if ticker:
        return envelope(
            "stock_deep_dive",
            "company",
            ticker.group(0),
            _decision_goal(text),
            timeframe,
            "ticker",
            0.82,
        )

    valuation_subject = _valuation_subject(text)
    if valuation_subject is not None:
        return envelope(
            "valuation_estimate",
            "company",
            valuation_subject,
            _decision_goal(text),
            timeframe,
            "explicit",
            0.84,
        )

    compositional_theme = _compositional_theme_subject(
        text,
        operators=operators,
    )
    if compositional_theme is not None:
        return envelope(
            "theme_analysis",
            "theme",
            compositional_theme,
            _decision_goal(text),
            timeframe,
            "explicit",
            0.88,
        )

    explicit_company = _explicit_company_subject(text)
    if explicit_company is not None:
        return envelope(
            _company_question_type(text),
            "company",
            explicit_company,
            _decision_goal(text),
            timeframe,
            "explicit",
            0.86,
        )

    if is_market_forecast_query(text):
        return envelope(
            "market_forecast",
            "unknown",
            None,
            "基于当前市场数据形成条件化后市推演",
            timeframe,
            "market_anchor",
            0.92,
        )

    normalized_theme = str(matched_theme or "").strip()
    if normalized_theme:
        return envelope(
            "theme_analysis",
            "theme",
            normalized_theme,
            _decision_goal(text),
            timeframe,
            "candidate",
            0.98,
        )

    folded_text = text.casefold()
    for alias in _theme_aliases():
        if alias.casefold() in folded_text:
            return envelope(
                "theme_analysis",
                "theme",
                alias,
                _decision_goal(text),
                timeframe,
                "alias",
                0.92,
            )

    quoted = _QUOTED_RE.search(text)
    if quoted:
        return envelope(
            "theme_analysis",
            "theme",
            quoted.group(1).strip(),
            _decision_goal(text),
            timeframe,
            "quoted",
            0.72,
        )

    explicit = _explicit_theme(text, timeframe)
    if explicit:
        return envelope(
            "theme_analysis",
            "theme",
            explicit,
            _decision_goal(text),
            timeframe,
            "explicit",
            0.8,
        )

    if sum(term in text for term in _MARKET_PATTERN_TERMS) >= 2:
        return envelope(
            "general_finance_qa",
            "market_pattern",
            None,
            _decision_goal(text),
            timeframe,
            "generic",
            0.9,
        )

    return envelope(
        "general_finance_qa",
        "unknown",
        None,
        _decision_goal(text),
        timeframe,
        "generic",
        0.4 if text else 0.1,
    )
