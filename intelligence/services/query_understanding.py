from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, replace
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from intelligence.services.disclosure_scan_pack import (
    is_disclosure_scan_query,
    parse_disclosure_buckets,
)
from intelligence.services.entity_anchor import EntityAnchor
from intelligence.services.market_analogs import parse_analog_intent
from intelligence.services.market_regime_analogs import parse_regime_intent
from intelligence.services.market_midterm import parse_midterm_intent
from intelligence.services.scenario_tree import parse_scenario_intent
from intelligence.services.task_frame import TaskFrame, build_task_frame


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
    "suffix_window",
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
# 盘面复盘的**细分**话题词。
#
# 为什么需要它：上面那条 _DATED_MARKET_REVIEW_RE 要求「日期 + 行情/盘面/市场 +
# 总结/复盘/回顾/梳理/分析」三件齐全，对 A 组 10 道真实验收题**一条都不匹配**——
# 没人会说「2026-07-23 的盘面复盘一下双红」，用户说的是「2026-07-23 哪些板块是双红」。
# 实测后果（2026-08-01 A 组基线，见 docs/verification/2026-08-01-a-tier-baseline.md）：
# 7/10 题落到通用检索，用「特斯拉 Optimus 人形机器人」答双红、用外汇/期货/债券
# 新闻答市场情绪，另有两题谎称「该日期是未来」——而当天的 daily-review 导出就在磁盘上。
#
# 只收**盘面复盘专有**的词。刻意不收「题材」「板块」「资金流」：它们同时是题材研究
# 的常用词，收进来会把 theme-research 的问题抢走（over-routing 比 under-routing 更难
# 发现——答案看起来是有的，只是答错了层）。
_DATED_MARKET_TOPIC_RE = re.compile(
    r"双红|涨停|跌停|连板|梯队|断层|主线|新高|新低"
    r"|涨家数|跌家数|量能|缩量|放量|成交额|市场阶段|市场情绪|赚钱效应"
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
    r"|(?:目前|当前|现在)(?:的)?(?:A股|市场|行情|盘面|大盘)(?:的)?"
    r"(?:主线|结构|看点|机会)(?:是什么|有哪些|怎么样|如何)?"
    # 「今天大盘处于什么阶段」：market_stage 本身就是 fact_market_daily 的字段，
    # 这是最典型的当日盘面提问。市场名词必须在，否则会吞掉
    # 「固态电池现在处于什么阶段」这类题材问题。
    # 分句边界锚：不加的话「固态电池市场处于什么阶段」会命中中间的
    # 「市场处于什么阶段」，一个题材问句被送去跑全市场日报。
    r"|(?:(?<=^)|(?<=[，。；？！、,;?!]))(?:今天|今日|目前|当前|现在)(?:的)?(?:A股|市场|行情|盘面|大盘)"
    r"[^。？！]{0,6}?(?:处于|在)?(?:什么|哪个|哪一)?阶段"
    # 语序反过来的说法：「大盘目前在哪个阶段」。
    r"|(?:(?<=^)|(?<=[，。；？！、,;?!]))(?:A股|市场|行情|盘面|大盘)(?:目前|当前|现在|今天|今日)?(?:的)?"
    r"(?:处于|在)(?:什么|哪个|哪一)?阶段"
    # 「当前主线是哪几个方向」：主线在本项目里专指全市场主线，前面不需要再有主语。
    # 限定必须位于句首或分句首，避免「固态电池当前主线逻辑」被当成大盘提问。
    r"|(?:(?<=^)|(?<=[，。；？！、,;?!]))(?:目前|当前|现在|今天|今日)(?:的)?"
    r"主线(?:是|有)?(?:什么|哪些|哪几个|哪个)"
)
_MARKET_FORECAST_RE = re.compile(
    r"(?:展望|研判|预测)[^。？！]{0,16}(?:后市|市场|行情|大盘)"
    r"|(?:后市|后面市场|接下来市场|未来市场)[^。？！]{0,16}"
    r"(?:怎么|如何|演绎|走势|走)"
    r"|(?:市场|行情|大盘)[^。？！]{0,12}(?:后面|接下来|未来)"
    r"[^。？！]{0,8}(?:演绎|走势|怎么走|如何走)"
    # 动词表原先只有「走势」类，认不出日常最常说的「明天怎么看」。后果不是措辞
    # 问题：envelope 给不出 market_forecast，turn_controller 就按 general_finance_qa
    # 建 TaskFrame，required_outputs 只有 (direct_answer, evidence_boundary)——
    # 这道题从一开始就没被要求产出 direct_assessment / scenario_paths /
    # continuation_conditions / invalidation_conditions，后面的 partial 判定与
    # fail-closed 都只是在正确执行一个错误的契约。
    r"|(?:明天|明日|次日|下个交易日)[^。？！]{0,20}"
    r"(?:反弹|上涨|下跌|走弱|走势|怎么走|如何走|怎么看|如何看|怎么样|什么情况)"
    r"|(?:反弹|修复)[^。？！]{0,12}"
    r"(?:持续多久|能持续|持续性|延续多久|还能延续)"
    # 「站在 X 收盘/盘后……」是本项目里 point-in-time 前瞻提问的固定句式：
    # 无论后面接不接「市场/大盘」，问的都是下一个交易日的走向。
    r"|站在[^。？！]{0,24}(?:收盘|盘后|收市)"
    # 「给出对 07-22 的研判」——研判/展望在句尾、后面没有「市场/大盘」时，
    # 第一个分支匹配不到。
    r"|(?:给出|做|说说|谈谈)[^。？！]{0,14}(?:研判|展望|预判)"
)
# 无序合取：句尾「本周行情的展望」/「写一下本周展望」认不出有序支。
# 不并进 _MARKET_FORECAST_RE，避免把「怎么看」类题材题一并放宽。
_FORECAST_VERB_RE = re.compile(r"(?:展望|研判|预测|预判)")
_FORECAST_MARKET_SUBJECT_RE = re.compile(r"(?:后市|市场|行情|大盘|本周)")
_EVENT_FORECAST_RE = re.compile(
    r"(?:如果|若|假设)[^。？！]{0,48}"
    r"(?:会不会|能否|是否|可能|受益|影响|推动|证伪|落地)"
    r"|(?:下次|未来|后续)[^。？！]{0,12}"
    r"(?:降息|加息|政策|发布|推出|落地)[^。？！]{0,20}"
    r"(?:影响|受益|推动|证伪|可能)"
)
_CAUSE_VERB_RE = re.compile(r"为什么|原因|驱动|归因")
_CAUSE_MOVE_RE = re.compile(r"走强|走弱|上涨|下跌|回撤|涨|跌")
_CAUSE_MARKET_NOUN_RE = re.compile(r"行情|大盘|市场|指数")
_CAUSE_LAYER_TOKEN_RE = re.compile(r"板块|题材|行业")
_LAYER_NAME_SEPS = ("为什么", "为何", "研究", "分析一下", "分析", "请问", "帮我")
_GENERIC_LAYER_SUBJECTS = frozenset(
    {"哪些", "什么", "哪个", "哪种", "这种", "那种", "有些", "相关"}
)
_MONTH_HORIZON_RE = re.compile(
    r"(?:未来|接下来)?\s*(\d{1,2})\s*(?:[-~—到至]\s*(\d{1,2})\s*)?个?月"
)
_CHINESE_MONTH_HORIZON_RE = re.compile(
    r"(?:未来|接下来)?\s*(一|二|两)\s*个?月"
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
# 「比较」在中文里既是动词也是程度副词，「相比」还常只带时间参照。裸词命中
# 会把普通选股提问（「哪只个股比较有机会」）误判成 comparison，逼出一副
# 「A vs B」的骨架去回答一个根本没给出 B 的问题。程度副词用法的判别特征是
# 后面紧跟谓词（形容词或心理动词），下面这批做否定前瞻用。
_DEGREE_ADVERB_TAIL = (
    r"(?:有|没有|无|强|弱|高|低|多|少|好|差|大|小|贵|便宜|难|容易|快|慢|"
    r"危险|安全|重要|明显|乐观|悲观|谨慎|激进|极端|"
    r"关注|看好|看空|喜欢|担心|在意|倾向|偏好|认可|熟悉|了解|放心)"
)
_COMPARISON_RE = re.compile(
    # 动词化后缀：「比较一下」「对比一番」。
    r"(?:比较|对比)\s*(?:一下|一番)"
    r"|对比(?:分析|结果|来看|之下)"
    # 真实可比对象：「比较瑞华泰和中际旭创」，但排除「比较关注半导体和消费」。
    rf"|(?:比较|对比)(?!{_DEGREE_ADVERB_TAIL})"
    r"[\u4e00-\u9fffA-Za-z0-9+.·-]{2,12}(?:和|与|跟)"
    r"[\u4e00-\u9fffA-Za-z0-9+.·-]{2,12}"
    # 显式比较名词：「对比两家公司的优劣」。
    rf"|(?:比较|对比)(?!{_DEGREE_ADVERB_TAIL})"
    r"[^。？！\n]{0,12}(?:优劣|异同|差异|区别|竞争优势|谁更|哪个更)"
    # 「相比」要带得出结论的落点，「最近相比之前怎么样」不算。
    r"|(?:相比|相对于)[\u4e00-\u9fffA-Za-z0-9+.·-]{2,12}"
    r"[^。？！\n]{0,16}(?:更|优劣|差异|区别|强|弱|高|低)"
    r"|赔率排序"
    # 以下两支原样保留：它们已经要求真出现「A 和 B…差异/区别」结构。
    r"|[\u4e00-\u9fffA-Za-z0-9+.-]{2,12}(?:和|与)"
    r"[\u4e00-\u9fffA-Za-z0-9+.-]{2,12}.{0,16}"
    r"(?:分别|差异|区别|竞争优势|优劣)"
    r"|(?:和|与).{0,32}(?:哪个|哪一个|谁).{0,20}"
    r"(?:更|优先|胜出|主线)"
)
_RELATION_RE = re.compile(
    r"(上游|下游|供应|客户|合作|产业链位置|处于.{0,8}环节|关系)"
)
_COMPANY_CONFIRMATION_RE = re.compile(
    r"(?:是否|有无|有没有|已经|已)?(?:确认|官宣|披露)?"
    r"(?:合作|供货|供应|客户关系|订单|合同|认证|定点)"
    r"|(?:合作|供货|供应|客户关系|订单|合同|认证|定点)"
    r".{0,10}(?:是否|真假|属实|确认|官宣|披露)",
)
_COMPANY_MAPPING_RE = re.compile(
    r"(有哪些公司|哪些公司|受益公司|公司映射|核心公司"
    r"|哪些个股|观察哪些个股|关注哪些个股|个股有哪些|个股的反馈)"
)
_KEEP_XIA_COMPOUNDS = ("下游", "下跌", "下旬", "下修", "下一代")
_JOINT_BOARD_RE = re.compile(
    r"([\u4e00-\u9fff]{2,6})(?:和|与|、)([\u4e00-\u9fff]{2,6})$"
)
_JOINT_LEFT_PREFIXES = (
    "你认为",
    "我认为",
    "认为",
    "周一",
    "周二",
    "周三",
    "周四",
    "周五",
    "周六",
    "周日",
    "本周",
    "下周",
    "这周",
    "今日",
    "今天",
    "明日",
    "明天",
    "次日",
)
_JOINT_BOARD_SUFFIX_RE = re.compile(r"(?:板块|题材)")
# 前瞻观点词形（R-20260825-07）：接下来/后续/往后 × 怎么看/怎么走/走势。
# 只做词面在场判定；误放的代价由「板块|题材」后缀窗口与黑名单再过滤（先窄）。
_FORWARD_OPINION_CUE_RE = re.compile(r"(?:接下来|后续|往后)")
_FORWARD_OPINION_ASK_RE = re.compile(r"(?:怎么看|怎么走|走势)")
_SINGLE_BOARD_WINDOW_RE = re.compile(r"[\u4e00-\u9fff]{2,6}$")
_SINGLE_BOARD_PREFIXES = ("接下来", "后续", "往后", "的", "关注", "看好")
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
    r"|(?:反弹|上涨)(?:空间|高度)(?:有多(?:少|大))?"
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
    task_frame: TaskFrame | None = None

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["operators"] = list(self.operators)
        payload["required_outputs"] = list(self.required_outputs)
        payload["task_frame"] = (
            self.task_frame.to_dict() if self.task_frame is not None else None
        )
        return payload


def project_task_frame(
    frame: TaskFrame,
    template: QueryEnvelope,
) -> QueryEnvelope:
    """Project canonical semantics into the legacy routing adapter."""

    return replace(
        template,
        question_type=frame.question_type,
        subject_kind=frame.subject_kind,
        subject=frame.subject,
        decision_goal=frame.user_goal,
        timeframe=frame.timeframe,
        confidence=frame.confidence,
        required_outputs=frame.required_outputs,
        task_frame=frame,
    )


def envelope_from_task_frame(
    frame: TaskFrame,
    *,
    operators: tuple[ResearchOperator, ...] = (),
    time_horizon: TimeHorizon = "unspecified",
) -> QueryEnvelope:
    """Create a legacy adapter without re-interpreting the raw question."""

    return QueryEnvelope(
        question_type=frame.question_type,
        subject_kind=frame.subject_kind,  # type: ignore[arg-type]
        subject=frame.subject,
        decision_goal=frame.user_goal,
        timeframe=frame.timeframe,
        matched_by="explicit" if frame.subject is not None else "market_anchor",
        confidence=frame.confidence,
        research_mode=_research_mode(
            frame.question_type,
            frame.subject_kind,  # type: ignore[arg-type]
            operators=operators,
        ),
        time_horizon=time_horizon,
        operators=operators,
        required_outputs=frame.required_outputs,
        task_frame=frame,
    )


def is_dated_market_review(query: str, envelope: QueryEnvelope) -> bool:
    if envelope.question_type == "external_market":
        return False
    # 日期解析放在最前面：它是「有没有一份可读的当日导出」的充要前提。
    # 原来它被 and 在那条 0 命中的措辞正则后面，等于解析出来了也用不上——
    # 信息在系统里但没送到，而这次没送到的距离只有一个 and。
    if market_review_requested_date(query) is None:
        return False
    if _DATED_MARKET_REVIEW_RE.search(query) is not None:
        return True
    # 主题词这条支路要自己排除境外市场：「美股涨停情况怎么样」不带「行情/盘面」，
    # 分类器给的是 general_finance_qa 而不是 external_market，上面那道 question_type
    # 闸放它过去，而 daily-review 导出里只有 A 股。这条是加主题词时引入的真回归，
    # 被 test_dated_overseas_board_subtopic_still_excluded 当场抓住的。
    lowered = str(query or "").lower()
    if any(term in lowered for term in _EXTERNAL_MARKET_TERMS):
        return False
    return _DATED_MARKET_TOPIC_RE.search(query) is not None


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


def _decision_goal(query: str, *, matched_theme: str | None = None) -> str:
    if is_market_cause_query(query, matched_theme=matched_theme):
        return "解释指定时间窗口内市场涨跌的主要原因并形成可回查因果链"
    if _is_external_market_query(query):
        return "核对海外指数收盘点位与涨跌幅"
    if _definition_subject(query):
        return "解释定义、技术背景与产业链位置"
    if _COMPANY_CONFIRMATION_RE.search(query):
        return "核验公司与客户/合作方关系是否有公告、合同、认证等官方证据"
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


SIGNAL_MARKET_WATCH = "market_watch"
SIGNAL_DOUBLE_RED = "double_red"
SIGNAL_FERMENTATION = "fermentation"
SIGNAL_AGGREGATE = "aggregate"
SIGNAL_DETAIL = "detail"
SIGNAL_CROSS_TABLE = "cross_table"
SIGNAL_CONTRADICTION = "contradiction"
SIGNAL_SUBSTITUTE_OBSERVATION = "substitute_observation"
SIGNAL_STEP_TRAJECTORY = "step_trajectory"

_PROGRAM_AGGREGATE_RE = re.compile(r"(多少|几个|几家|家数|数量|有多少)")
_PROGRAM_DETAIL_RE = re.compile(r"(列出|名单|明细|哪些)")
_PROGRAM_CROSS_RE = re.compile(r"(交集|同时属于|既是.+又|既在.+又)")
_PROGRAM_CONTRADICTION_RE = re.compile(r"(矛盾|冲突|不一致)")
# 替补观察三词族：题材面 + 个股面 + 观察意图，三者齐才触发（勿放宽——
# 触发后的替补池以「主线题材无双红匹配」为准，单股深挖题进来只会是噪音）。
_SUBSTITUTE_THEME_RE = re.compile(r"(板块|题材|主线|行业)")
_SUBSTITUTE_STOCK_RE = re.compile(r"(个股|标的)")
_SUBSTITUTE_OBS_RE = re.compile(r"(观察|反馈|机会|对标|关注)")
# 台阶/资格两件共用一个信号：SPT 铁律「先定资格再谈板块」，台阶没有资格盘
# 垫底就没法读（spec 2026-08-25-step-trajectory-qualification-design §1.1）。
_TRAJECTORY_OUTLOOK_RE = re.compile(
    r"(走势|接下来|后续|趋势|怎么看|怎么走|台阶|量能)"
)


def surface_research_signals(
    query: str,
    *,
    question_class: str = "",
) -> frozenset[str]:
    """词面触发。只返回信号名，不写 ResearchProgram.operators。"""

    from intelligence.services.asof_prefetch import is_fermentation_query

    text = re.sub(r"\s+", "", str(query or "").strip())
    klass = str(question_class or "").strip()
    signals: set[str] = set()
    # 路由已经定了别的题型时，不再用盘面词面覆写。否则
    # market_forecast 夹具句「目前市场结构如何」会多出 catalog/双红槽。
    routed_watch = klass == "market_watch"
    inferred_watch = klass in {"", "general_finance_qa"} and is_market_watch_query(query)
    if routed_watch or inferred_watch:
        signals.add(SIGNAL_MARKET_WATCH)
        signals.add(SIGNAL_DOUBLE_RED)
    if "双红" in text:
        signals.add(SIGNAL_DOUBLE_RED)
    if is_fermentation_query(query):
        signals.add(SIGNAL_FERMENTATION)
        signals.add(SIGNAL_DOUBLE_RED)
    if _PROGRAM_AGGREGATE_RE.search(text):
        signals.add(SIGNAL_AGGREGATE)
    elif _PROGRAM_DETAIL_RE.search(text):
        signals.add(SIGNAL_DETAIL)
    if _PROGRAM_CROSS_RE.search(text):
        signals.add(SIGNAL_CROSS_TABLE)
    if _PROGRAM_CONTRADICTION_RE.search(text):
        signals.add(SIGNAL_CONTRADICTION)
    # 盘面题不发替补信号：market_watch 路径的替补池由四袋包的探针供给
    # （bind_market_watch_pack），此处再发会双份。
    if (
        not (routed_watch or inferred_watch)
        and _SUBSTITUTE_THEME_RE.search(text)
        and _SUBSTITUTE_STOCK_RE.search(text)
        and _SUBSTITUTE_OBS_RE.search(text)
    ):
        signals.add(SIGNAL_SUBSTITUTE_OBSERVATION)
    # 盘面题不发台阶/资格信号：market_watch 的锁格由四袋包供给，包路径的
    # 台阶/资格接入是 P1（spec §8 P1-a），此处再发会双份。
    if (
        not (routed_watch or inferred_watch)
        and _SUBSTITUTE_THEME_RE.search(text)
        and _TRAJECTORY_OUTLOOK_RE.search(text)
    ):
        signals.add(SIGNAL_STEP_TRAJECTORY)
    return frozenset(signals)


def is_market_forecast_query(query: str) -> bool:
    """识别明确的全市场后市展望；不把泛泛“市场怎么样”误当预测。"""

    text = re.sub(r"\s+", "", str(query or "").strip())
    if not text:
        return False
    if _MARKET_FORECAST_RE.search(text) is not None:
        return True
    return (
        _FORECAST_VERB_RE.search(text) is not None
        and _FORECAST_MARKET_SUBJECT_RE.search(text) is not None
    )


def is_event_forecast_query(query: str) -> bool:
    """识别尚未发生事件的条件化推演，交给通用研究 owner。"""
    text = re.sub(r"\s+", "", str(query or "").strip())
    return _EVENT_FORECAST_RE.search(text) is not None


def is_market_cause_query(
    query: str,
    *,
    matched_theme: str | None = None,
    anchor: EntityAnchor | None = None,
) -> bool:
    """无序合取：归因动词 ∧ 涨跌事件 ∧ 主语锚点。主语锚点含 matched_theme。"""
    return _market_cause_hit(
        query,
        matched_theme=matched_theme,
        anchor=anchor,
    ) is not None


def _theme_alias_in_query(text: str) -> str | None:
    folded = text.casefold()
    for alias in _theme_aliases():
        if alias.casefold() in folded:
            return alias
    return None


def _layer_subject(text: str) -> str | None:
    for match in _CAUSE_LAYER_TOKEN_RE.finditer(text):
        prefix = text[: match.start()]
        for sep in _LAYER_NAME_SEPS:
            if sep in prefix:
                prefix = prefix.rsplit(sep, 1)[-1]
        named = re.search(r"(?:A股|沪深)([\u4e00-\u9fff]{1,6})$", prefix)
        if named is None:
            named = re.search(r"([\u4e00-\u9fff]{1,6})$", prefix)
        if named is None:
            continue
        name = named.group(1).strip()
        if (
            not name
            or name in _GENERIC_EXPLICIT_SUBJECTS
            or name in _GENERIC_LAYER_SUBJECTS
            or name.startswith(_GENERIC_EXPLICIT_PREFIXES)
        ):
            continue
        return name
    return None


def _market_cause_hit(
    query: str,
    *,
    matched_theme: str | None = None,
    anchor: EntityAnchor | None = None,
) -> tuple[SubjectKind, str | None, MatchedBy] | None:
    text = re.sub(r"\s+", "", str(query or "").strip())
    if not text:
        return None
    if (
        anchor is not None
        or _TICKER_RE.search(text) is not None
        or _explicit_company_subject(text) is not None
    ):
        return None
    if _CAUSE_VERB_RE.search(text) is None or _CAUSE_MOVE_RE.search(text) is None:
        return None
    theme = str(matched_theme or "").strip()
    alias = _theme_alias_in_query(text)
    layer_name = _layer_subject(text)
    has_layer = _CAUSE_LAYER_TOKEN_RE.search(text) is not None
    has_market_noun = _CAUSE_MARKET_NOUN_RE.search(text) is not None
    if not (theme or alias or has_layer or has_market_noun):
        return None
    if theme:
        return ("theme", theme, "candidate")
    if alias:
        return ("theme", alias, "alias")
    if layer_name is not None:
        return ("theme", layer_name, "explicit")
    return ("market_pattern", None, "market_anchor")


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
    if _COMPANY_CONFIRMATION_RE.search(query):
        return "fact_check"
    if re.search(r"(?:估值|值多少钱|贵不贵|合理价值|目标价)", query):
        return "valuation_estimate"
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
    chinese_month_window = _CHINESE_MONTH_HORIZON_RE.search(text)
    if chinese_month_window is not None:
        return "short" if chinese_month_window.group(1) == "一" else "medium"
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


def _research_operators(
    query: str,
    *,
    matched_theme: str | None = None,
    anchor: EntityAnchor | None = None,
) -> tuple[ResearchOperator, ...]:
    operators: list[ResearchOperator] = []
    if parse_analog_intent(query) or parse_regime_intent(query):
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
    if is_market_cause_query(
        query,
        matched_theme=matched_theme,
        anchor=anchor,
    ):
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
    if question_type == "disclosure_scan":
        return "general"
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
    return _strip_spoken_xia_prefix(normalized)


def _strip_spoken_xia_prefix(text: str) -> str:
    """Cue 后的口语「下」可以剥；「下游 / 下跌」这类复合词必须整段保留。"""

    if any(text.startswith(compound) for compound in _KEEP_XIA_COMPOUNDS):
        return text
    if text.startswith("下"):
        return text[1:]
    return text


def _forward_opinion_shape(compact: str) -> bool:
    return bool(
        _FORWARD_OPINION_CUE_RE.search(compact)
        and _FORWARD_OPINION_ASK_RE.search(compact)
    )


def _joint_board_subject(
    query: str,
    *,
    operators: tuple[ResearchOperator, ...],
) -> str | None:
    """句式路：A和B板块。窄门二选一：两算子且含情景树，或前瞻观点词形在句。

    「会怎么样」带出 scenario_tree 走算子门；「怎么看/怎么走」不带算子，
    由词形门放行（R-20260825-07）。后缀窗口与黑名单过滤两门共用。
    """

    compact = re.sub(r"\s+", "", str(query or ""))
    scenario_gate = len(operators) >= 2 and "scenario_tree" in operators
    if not scenario_gate and not _forward_opinion_shape(compact):
        return None
    for suffix in _JOINT_BOARD_SUFFIX_RE.finditer(compact):
        window = compact[max(0, suffix.start() - 16) : suffix.start()]
        hit = _JOINT_BOARD_RE.search(window)
        if hit is None:
            continue
        left, right = hit.group(1), hit.group(2)
        left = _strip_joint_left_prefixes(left)
        if (
            len(left) < 2
            or len(right) < 2
            or left in _GENERIC_EXPLICIT_SUBJECTS
            or right in _GENERIC_EXPLICIT_SUBJECTS
            or left.startswith(_GENERIC_EXPLICIT_PREFIXES)
            or right.startswith(_GENERIC_EXPLICIT_PREFIXES)
        ):
            continue
        return f"{left}、{right}"
    return None


def _strip_joint_left_prefixes(text: str) -> str:
    prefixes = sorted(_JOINT_LEFT_PREFIXES, key=len, reverse=True)
    current = text
    changed = True
    while changed and current:
        changed = False
        for prefix in prefixes:
            if current.startswith(prefix):
                current = current[len(prefix) :]
                changed = True
                break
    return current


def _forward_opinion_board_subject(query: str) -> str | None:
    """单题材路：「X板块/题材」×前瞻观点词形才抽主语（R-20260825-07）。

    先窄：只认「板块|题材」后缀，不查题材词表、不做模糊匹配；联合句式由
    ``_joint_board_subject`` 先行，本函数只接单主语残局。窗口取后缀前
    紧邻的 2–6 个汉字，功能词前缀剥完再过黑名单。
    """

    compact = re.sub(r"\s+", "", str(query or ""))
    if not _forward_opinion_shape(compact):
        return None
    for suffix in _JOINT_BOARD_SUFFIX_RE.finditer(compact):
        window = compact[max(0, suffix.start() - 6) : suffix.start()]
        run = _SINGLE_BOARD_WINDOW_RE.search(window)
        if run is None:
            continue
        candidate = _strip_single_board_prefixes(run.group(0))
        if (
            len(candidate) < 2
            or candidate in _GENERIC_EXPLICIT_SUBJECTS
            or candidate.startswith(_GENERIC_EXPLICIT_PREFIXES)
        ):
            continue
        return candidate
    return None


def _strip_single_board_prefixes(text: str) -> str:
    prefixes = sorted(
        _JOINT_LEFT_PREFIXES + _SINGLE_BOARD_PREFIXES, key=len, reverse=True
    )
    current = text
    changed = True
    while changed and current:
        changed = False
        for prefix in prefixes:
            if current.startswith(prefix):
                current = current[len(prefix) :]
                changed = True
                break
    return current


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


_CJK_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")
_LEFT_FUNCTION_PREFIXES = (
    "最近",
    "近期",
    "最新",
    "今日",
    "今天",
    "昨天",
    "目前",
    "当前",
    "关于",
    "国内",
    "海外",
    "中国",
    "以及",
    "还有",
    "或者",
    "如果",
    "对于",
    "围绕",
    "包括",
    "看看",
    "分析",
    "研究",
    "关注",
    "提到",
    "涉及",
    "相关",
    "美股",
    "港股",
    "A股",
    "a股",
    "沪深",
    "大盘",
)


def has_clean_theme_occurrence(folded_query: str, folded_term: str) -> bool:
    """主题词在问句里是否有一次非后缀嵌入的出现（左邻不是 CJK 字符）。

    生产事故（2026-08-13 R13-A3）：「立新能源怎么看」问的是个股 001258，
    实体锚定因 wiki 未登记而落空后，主题词典把「新能源」从「立新能源」
    肚子里抠了出来——theme_analysis 路由、theme-research owner、零证据终局。
    同形状地雷不止一颗：国新能源、宝新能源、华润新能源全是「X+新能源」
    后缀嵌入。

    规则刻意不对称：只 veto **左邻 CJK**（后缀嵌入是公司名的形状），
    不 veto 右邻延伸（「新能源汽车」是主题短语的形状，且更长的别名按
    长度降序先匹配）。
    """

    if not folded_term:
        return False
    start = 0
    while True:
        index = folded_query.find(folded_term, start)
        if index < 0:
            return False
        if index == 0 or not _CJK_CHAR_RE.match(folded_query[index - 1]):
            return True
        start = index + 1


def cjk_span_embedding_term(query: str, term: str) -> str | None:
    """若 ``term`` 只作为更长 CJK 片段的后缀出现，返回该前缀+词片段。

    只向左扩张：公司名形状是「X+主题」；右边常是「怎么看」这类问句成分，
    不能并进候选名。
    """

    if not term:
        return None
    start = 0
    while True:
        index = query.find(term, start)
        if index < 0:
            return None
        if index > 0 and _CJK_CHAR_RE.match(query[index - 1]):
            left = index
            while left > 0 and _CJK_CHAR_RE.match(query[left - 1]):
                left -= 1
            token = _strip_function_prefix(query[left : index + len(term)])
            if token != term:
                return token
        start = index + 1
    return None


def _strip_function_prefix(text: str) -> str:
    remaining = text
    changed = True
    while changed and remaining:
        changed = False
        for prefix in _LEFT_FUNCTION_PREFIXES:
            if remaining.startswith(prefix):
                remaining = remaining[len(prefix) :]
                changed = True
                break
    return remaining


def understand_query(
    query: str,
    *,
    matched_theme: str | None = None,
    anchor: EntityAnchor | None = None,
) -> QueryEnvelope:
    text = str(query or "").strip()
    operators = _research_operators(
        text,
        matched_theme=matched_theme,
        anchor=anchor,
    )
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
        legacy = QueryEnvelope(
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
        frame = build_task_frame(text, legacy)
        # ``QueryEnvelope`` remains a backwards-compatible adapter.  Its
        # historical raw/date/operator fields stay byte-for-byte stable while
        # all new consumers use the attached canonical frame.
        return replace(legacy, task_frame=frame)

    timeframe_match = _DATE_RE.search(text)
    month_horizon_match = (
        _MONTH_HORIZON_RE.search(text)
        or _CHINESE_MONTH_HORIZON_RE.search(text)
    )
    timeframe = (
        timeframe_match.group(0)
        if timeframe_match
        else next(
            (term for term in _RELATIVE_TIMEFRAMES if term in text),
            month_horizon_match.group(0) if month_horizon_match else None,
        )
    )

    cause_hit = _market_cause_hit(
        text,
        matched_theme=matched_theme,
        anchor=anchor,
    )
    if cause_hit is not None:
        subject_kind, subject, matched_by = cause_hit
        return envelope(
            "market_cause",
            subject_kind,
            subject,
            "解释指定时间窗口内市场涨跌的主要原因并形成可回查因果链",
            timeframe,
            matched_by,
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

    if is_disclosure_scan_query(text):
        buckets = parse_disclosure_buckets(text)
        subject = "、".join(bucket.name for bucket in buckets) or None
        return envelope(
            "disclosure_scan",
            "theme",
            subject,
            "扫描点名板块近期官方披露里偏利好的个股名单",
            timeframe,
            "explicit",
            0.98,
        )

    if is_market_watch_query(text):
        return envelope(
            "market_watch",
            "market_pattern",
            None,
            "总结当前盘面主线、观察清单与验证信号",
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

    if "comparison" in operators and not any(
        term in text for term in ("什么是", "定义")
    ):
        return envelope(
            "comparison",
            "unknown",
            None,
            "比较对象、关键差异与证据边界",
            timeframe,
            "explicit",
            0.82,
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

    if is_event_forecast_query(text):
        return envelope(
            "event_forecast",
            "unknown",
            None,
            "围绕未发生事件形成条件化影响推演与证伪路径",
            timeframe,
            "explicit",
            0.88,
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

    joint = _joint_board_subject(text, operators=operators)
    if joint is not None:
        return envelope(
            "general_finance_qa",
            "theme",
            joint,
            _decision_goal(text),
            timeframe,
            "explicit",
            0.8,
        )

    forward_board = _forward_opinion_board_subject(text)
    if forward_board is not None:
        return envelope(
            "general_finance_qa",
            "theme",
            forward_board,
            _decision_goal(text),
            timeframe,
            "suffix_window",
            0.74,
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
