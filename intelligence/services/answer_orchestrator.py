from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from intelligence.services.answer_model import ThemeResearchSpec, resolve_theme_research_spec
from intelligence.services.entity_anchor import EntityAnchor
from intelligence.services.query_understanding import QueryEnvelope, understand_query
from intelligence.services.route_table import is_quick_fact_query


QUESTION_STOCK_DEEP_DIVE = "stock_deep_dive"
QUESTION_THEME_ANALYSIS = "theme_analysis"
QUESTION_MARKET_REVIEW = "market_review"
QUESTION_MARKET_FORECAST = "market_forecast"
QUESTION_NEWS_IMPACT = "news_impact"
QUESTION_VALUATION = "valuation_estimate"
QUESTION_FINANCIAL_ANALYSIS = "financial_analysis"
QUESTION_ANSWER_REVIEW = "answer_review"
QUESTION_METHODOLOGY = "methodology_discussion"
QUESTION_FACT_CHECK = "fact_check"
QUESTION_GENERAL = "general_finance_qa"
QUESTION_EXTERNAL_MARKET = "external_market"
QUESTION_CONCEPT_DEFINITION = "concept_definition"
QUESTION_MARKET_TECHNICAL = "market_technical"
QUESTION_MARKET_CAUSE = "market_cause"
QUESTION_EVENT_FORECAST = "event_forecast"
QUESTION_COMPARISON = "comparison"
# 与 route_table 的 quick_fact 路由、task_frame 的
# ("fact_value","as_of_date","evidence_boundary") 同名对齐。此前本分类器没有这一档，
# 于是「收盘价多少」这类取值查询落到下面的 market_forecast 兜底（"收盘" 是它的触发词）。
QUESTION_QUICK_FACT = "quick_fact"

QUESTION_TYPES = frozenset(
    {
        QUESTION_STOCK_DEEP_DIVE,
        QUESTION_THEME_ANALYSIS,
        QUESTION_MARKET_REVIEW,
        QUESTION_MARKET_FORECAST,
        QUESTION_NEWS_IMPACT,
        QUESTION_VALUATION,
        QUESTION_FINANCIAL_ANALYSIS,
        QUESTION_ANSWER_REVIEW,
        QUESTION_METHODOLOGY,
        QUESTION_FACT_CHECK,
        QUESTION_GENERAL,
        QUESTION_EXTERNAL_MARKET,
        QUESTION_CONCEPT_DEFINITION,
        QUESTION_MARKET_TECHNICAL,
        QUESTION_MARKET_CAUSE,
        QUESTION_EVENT_FORECAST,
        QUESTION_COMPARISON,
        QUESTION_QUICK_FACT,
    }
)

DEPTH_QUICK = "quick"
DEPTH_STANDARD = "standard"
DEPTH_DEEP = "deep"


@dataclass(frozen=True)
class BaseFinanceMode:
    """不依赖专项 Skill 的常驻金融检索与表达底线。"""

    require_market: bool
    require_memory: bool
    require_news: bool
    require_graph: bool
    require_financials: bool
    quick_answer: bool

    def to_dict(self) -> dict[str, bool]:
        return {
            "require_market": self.require_market,
            "require_memory": self.require_memory,
            "require_news": self.require_news,
            "require_graph": self.require_graph,
            "require_financials": self.require_financials,
            "quick_answer": self.quick_answer,
        }

    def to_prompt_block(self) -> str:
        required = [
            label
            for enabled, label in (
                (self.require_market, "行情"),
                (self.require_memory, "历史记忆"),
                (self.require_news, "近期新闻"),
                (self.require_graph, "产业链/关系"),
                (self.require_financials, "财务与估值"),
            )
            if enabled
        ]
        return "\n".join(
            (
                "## Base Finance Mode（始终生效）",
                f"- 检索底线：{'、'.join(required) or '通用金融证据'}；"
                "“快答”只缩短表达，不得跳过已触发的检索。",
                "- 内部先写核心矛盾句；正文结论必须覆盖：直接定性、最强证据、"
                "主要风险、条件边界（翻转条件）、下一步验证或替代路径。",
                "- 缺数按三档处理：先做标明假设的区间推断；再找替代锚点；"
                "仍不足时写“缺 X → 仍可判 Y → 验证窗口 Z”，禁止补造确定性。",
                "- 用户观点只作为待检验假设；允许明确纠正，而不是顺从用户预设。",
            )
        )


@dataclass(frozen=True)
class QuestionPlan:
    """Deterministic P0 planning layer before an answer is composed.

    It is intentionally lightweight: the plan does not execute tools by itself.
    It tells downstream retrieval/composition what kind of question this is,
    which lenses are mandatory, and which evidence sources should be preferred.
    """

    query: str
    question_type: str
    depth: str
    confidence: float
    query_envelope: QueryEnvelope
    required_lenses: list[str] = field(default_factory=list)
    retrieval_plan: list[str] = field(default_factory=list)
    quality_gates: list[str] = field(default_factory=list)
    output_contract: list[str] = field(default_factory=list)
    missing_data_policy: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    research_spec: ThemeResearchSpec | None = None
    base_finance_mode: BaseFinanceMode | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "question_type": self.question_type,
            "depth": self.depth,
            "confidence": self.confidence,
            "query_envelope": self.query_envelope.to_dict(),
            "required_lenses": self.required_lenses,
            "retrieval_plan": self.retrieval_plan,
            "quality_gates": self.quality_gates,
            "output_contract": self.output_contract,
            "missing_data_policy": self.missing_data_policy,
            "warnings": self.warnings,
            "research_spec": self.research_spec.to_dict() if self.research_spec else None,
            "base_finance_mode": (
                self.base_finance_mode.to_dict()
                if self.base_finance_mode is not None
                else None
            ),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_prompt_block(self, *, compact: bool = False) -> str:
        if compact:
            deep = self.depth == DEPTH_DEEP
            lens_limit = 5 if deep else 3
            source_limit = 5 if deep else 3
            gate_limit = 3
            output_limit = 4 if deep else 3
            lines = [
                "## 本轮任务边界",
                f"- 类型：{self.question_type}；深度：{self.depth}",
                "- 必要视角："
                + "；".join(self.required_lenses[:lens_limit]),
                "- 优先证据："
                + "；".join(self.retrieval_plan[:source_limit]),
                "- 完成条件："
                + "；".join(self.output_contract[:output_limit]),
                "- 事实门："
                + "；".join(self.quality_gates[:gate_limit]),
            ]
            if self.missing_data_policy:
                lines.append(
                    "- 缺数据：" + "；".join(self.missing_data_policy[:2])
                )
            if self.warnings:
                lines.append("- 边界提醒：" + "；".join(self.warnings[:2]))
            # Methodology/review/general questions should not inherit the
            # five-part finance-answer skeleton.  Their reliability comes from
            # the same fact verifier, not from forcing risk/trigger headings.
            if self.base_finance_mode is not None and self.question_type not in {
                QUESTION_METHODOLOGY,
                QUESTION_ANSWER_REVIEW,
                QUESTION_GENERAL,
            }:
                required = [
                    label
                    for enabled, label in (
                        (self.base_finance_mode.require_market, "行情"),
                        (self.base_finance_mode.require_memory, "历史记忆"),
                        (self.base_finance_mode.require_news, "近期新闻"),
                        (self.base_finance_mode.require_graph, "产业链/关系"),
                        (self.base_finance_mode.require_financials, "财务与估值"),
                    )
                    if enabled
                ]
                lines.append(
                    "- 金融检索底线：" + ("、".join(required) or "通用金融证据")
                )
            return "\n".join(line for line in lines if not line.endswith("："))
        lines = [
            "## 问答编排计划（回答前的结构化任务理解，不要机械复述）",
            f"- 问题类型：{self.question_type}",
            f"- 回答深度：{self.depth}",
            f"- 规划置信度：{self.confidence:.2f}",
            "- 必须动用的分析视角：",
        ]
        lines.extend(f"  - {item}" for item in self.required_lenses)
        lines.append("- 优先证据来源：")
        lines.extend(f"  - {item}" for item in self.retrieval_plan)
        lines.append("- 输出前质检门槛：")
        lines.extend(f"  - {item}" for item in self.quality_gates)
        lines.append("- 输出契约：")
        lines.extend(f"  - {item}" for item in self.output_contract)
        if self.missing_data_policy:
            lines.append("- 缺数据时的处理：")
            lines.extend(f"  - {item}" for item in self.missing_data_policy)
        if self.warnings:
            lines.append("- 编排警告：")
            lines.extend(f"  - {item}" for item in self.warnings)
        if self.base_finance_mode is not None:
            lines.extend(["", self.base_finance_mode.to_prompt_block()])
        if self.research_spec is not None:
            lines.extend(["", self.research_spec.to_prompt_block()])
        return "\n".join(lines)


def resolve_question_type(
    raw_query: str,
    query_envelope: Any,
    *,
    question_type_override: str | None = None,
) -> tuple[str, float]:
    """把「问题信封」定成最终问题类型。CLI 与会话两条路径必须共用这一处。

    信封（understand_query）擅长认出有明确主语的问题；主语是"大盘/市场"这类
    泛指时它给 general_finance_qa + confidence 0.4，需要 _classify_question_type
    的规则兜底才能升成 market_review。

    会话路径原先直接取 envelope.question_type，绕过了这层兜底，于是
    "今天大盘处于什么阶段？当前主线是哪几个方向？" 在 CLI 里是 market_review、
    在工作台里是 general_finance_qa——同一个问题两个答法，而工作台是用户实际
    用的那条。
    """
    q = _normalize(raw_query)
    # general_finance_qa 是「上游没认出来」的兜底值，不是「确定是通用问题」的判断，
    # 因此不作为权威 override。会话路径把 contract.question_type 原样传进来
    # （ask.py / conversation_orchestrator），信封对泛指主语只给得出这个兜底值，
    # 于是它会压掉本来认得出复盘类问题的规则——"今天大盘处于什么阶段？当前主线是
    # 哪几个方向？"因此走不到 _answer_market_review，主线数据块根本没被构建。
    if question_type_override is not None and question_type_override != QUESTION_GENERAL:
        return question_type_override, 1.0
    # 取值意图先于主语类型。下面几条分支都是按 subject_kind 派题型的——
    # 主语是公司就 stock_deep_dive、是题材就 theme_analysis——但主语说的是
    # 「问的是什么」，跟「想要什么」是两件事：「300750是哪家公司」主语是公司、
    # 「光刻胶板块今天成交额多少」主语是题材，两者要的都是一个确定的值。
    # 让主语压掉意图，这类问题就会被派去做深挖/题材分析，然后在任务契约里
    # 被要求写反证、在 rubric 里被追加前瞻维度——一个成交额数字满足不了。
    if is_quick_fact_query(raw_query):
        return QUESTION_QUICK_FACT, 0.85
    if query_envelope.question_type in {
        QUESTION_EXTERNAL_MARKET,
        QUESTION_CONCEPT_DEFINITION,
        QUESTION_MARKET_TECHNICAL,
    }:
        return query_envelope.question_type, query_envelope.confidence
    if query_envelope.question_type == "market_watch":
        classified_type, classified_confidence = _classify_question_type(raw_query, q)
        if classified_type == QUESTION_MARKET_REVIEW:
            return classified_type, classified_confidence
        return QUESTION_GENERAL, query_envelope.confidence
    if query_envelope.subject_kind == "market_pattern":
        return QUESTION_GENERAL, query_envelope.confidence
    if query_envelope.subject_kind == "company":
        return query_envelope.question_type, query_envelope.confidence
    classified_type, classified_confidence = _classify_question_type(raw_query, q)
    if (
        query_envelope.subject_kind == "theme"
        and classified_type != QUESTION_STOCK_DEEP_DIVE
    ):
        return query_envelope.question_type, query_envelope.confidence
    return classified_type, classified_confidence


def plan_answer_question(
    query: str,
    matched_theme: str | None = None,
    *,
    question_type_override: str | None = None,
    anchor: EntityAnchor | None = None,
) -> QuestionPlan:
    raw_query = str(query or "").strip()
    query_envelope = understand_query(
        raw_query,
        matched_theme=matched_theme,
        anchor=anchor,
    )
    if not raw_query:
        return QuestionPlan(
            query=raw_query,
            question_type=QUESTION_GENERAL,
            depth=DEPTH_QUICK,
            confidence=0.1,
            query_envelope=query_envelope,
            required_lenses=["先要求用户补充题材、个股、日期或材料"],
            retrieval_plan=[],
            quality_gates=["不能在问题为空时编造分析对象"],
            output_contract=["请用户补充问题"],
            missing_data_policy=["问题为空，必须追问"],
            warnings=["empty query"],
        )

    q = _normalize(raw_query)
    if (
        question_type_override is not None
        and question_type_override not in QUESTION_TYPES
    ):
        raise ValueError("unknown question type override")
    question_type, confidence = resolve_question_type(
        raw_query,
        query_envelope,
        question_type_override=question_type_override,
    )
    depth = _classify_depth(raw_query, q, question_type)
    required_lenses = _required_lenses(question_type, depth)
    retrieval_plan = _retrieval_plan(question_type, depth, q)
    quality_gates = _quality_gates(question_type, depth)
    output_contract = _output_contract(question_type, depth)
    missing_data_policy = _missing_data_policy(question_type)
    warnings = _warnings(raw_query, q, question_type, retrieval_plan)
    base_finance_mode = _base_finance_mode(raw_query, q, question_type, depth)
    research_spec = (
        resolve_theme_research_spec(raw_query, query_envelope.subject)
        if question_type
        in {
            QUESTION_THEME_ANALYSIS,
            QUESTION_NEWS_IMPACT,
            QUESTION_STOCK_DEEP_DIVE,
        }
        else None
    )
    return QuestionPlan(
        query=raw_query,
        question_type=question_type,
        depth=depth,
        confidence=confidence,
        query_envelope=query_envelope,
        required_lenses=required_lenses,
        retrieval_plan=retrieval_plan,
        quality_gates=quality_gates,
        output_contract=output_contract,
        missing_data_policy=missing_data_policy,
        warnings=warnings,
        research_spec=research_spec,
        base_finance_mode=base_finance_mode,
    )


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text.lower())


def _has_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(_normalize(token) in text for token in tokens)


# 「问现状」判定用的三组词。拆成三组而不是一个大列表，是为了让「需要大盘主语」
# 这条约束可表达——否则题材问句会被抢进 market_review。
_MARKET_TIME_ANCHORS: tuple[str, ...] = (
    "今天",
    "今日",
    "现在",
    "当前",
    "目前",  # 与 _MARKET_WATCH_RE 对齐：现在/当前 都在，漏了同义的 目前
    "当下",
    "收盘",
    "盘后",
    "本轮",
)
_MARKET_SUBJECTS: tuple[str, ...] = ("大盘", "市场", "行情", "指数", "a股")
_MARKET_STATE_WORDS_NEEDING_SUBJECT: tuple[str, ...] = (
    "阶段",
    "结构",
    "状态",
    "强弱",
    "怎么样",
    "什么情况",
)
_MARKET_LEVEL_STATE_WORDS: tuple[str, ...] = (
    "主线",
    "赚钱效应",
    "涨跌家数",
    "涨停家数",
    "市场情绪",
)
_CLAUSE_SPLIT_RE = re.compile(r"[，。；？！、,;?!\s]+")


def _market_level_clause(q: str) -> bool:
    """有没有哪个分句是「在问全市场」。

    只做子串命中是不够的：「创新药板块当前主线是哪几个」命中了时间锚 当前 和
    市场级状态词 主线，于是被抢进 market_review，用户问一个板块的主线却拿到全市场
    复盘——而复盘的主线块和知识库锚点讲的是市场的题材（消费零售/半导体/AI算力），
    跟创新药没关系。「半导体设备市场当前强弱如何」同理。

    三条同时成立才算：
    1. 分句以时间锚或市场主语开头——点了具体题材/板块/公司的问句，主语占着最前面，
       因此不满足。这和 _MARKET_WATCH_RE 里 主线 那条分支用的分句边界是同一条判据。
    2. 分句里有时间锚——「大盘处于什么阶段」光有状态词不算问现状（既有约定）。
    3. 有市场级状态词，或者有需要主语的状态词且全句某处出现了市场主语。

    第 3 条里市场主语允许跨分句，是因为「今天什么阶段，明天大盘怎么看」的主语在
    后半句。但状态词和时间锚必须同分句，否则又会退回到跨分句拼凑。
    """
    has_subject_anywhere = _has_any(q, _MARKET_SUBJECTS)
    for clause in _CLAUSE_SPLIT_RE.split(q):
        clause = clause.strip()
        if not clause:
            continue
        if not clause.startswith(_MARKET_TIME_ANCHORS + _MARKET_SUBJECTS):
            continue
        if not _has_any(clause, _MARKET_TIME_ANCHORS):
            continue
        if _has_any(clause, _MARKET_LEVEL_STATE_WORDS):
            return True
        if has_subject_anywhere and _has_any(
            clause, _MARKET_STATE_WORDS_NEEDING_SUBJECT
        ):
            return True
    return False


def _base_finance_mode(
    raw_query: str,
    q: str,
    question_type: str,
    depth: str,
) -> BaseFinanceMode:
    if question_type in {
        QUESTION_EXTERNAL_MARKET,
        QUESTION_CONCEPT_DEFINITION,
        QUESTION_MARKET_TECHNICAL,
    }:
        return BaseFinanceMode(
            require_market=question_type == QUESTION_MARKET_TECHNICAL,
            require_memory=False,
            require_news=False,
            require_graph=False,
            require_financials=False,
            quick_answer=depth == DEPTH_QUICK,
        )
    has_specific_target = (
        question_type
        in {
            QUESTION_STOCK_DEEP_DIVE,
            QUESTION_VALUATION,
            QUESTION_FINANCIAL_ANALYSIS,
        }
        or bool(re.search(r"\b\d{6}(?:\.(?:SH|SZ|BJ))?\b", raw_query, re.I))
    )
    asks_recent_event = question_type == QUESTION_NEWS_IMPACT or _has_any(
        q,
        ("最近", "近期", "最新", "新闻", "消息", "公告", "事件", "催化", "进展"),
    )
    asks_chain = question_type in {
        QUESTION_THEME_ANALYSIS,
        QUESTION_STOCK_DEEP_DIVE,
        QUESTION_NEWS_IMPACT,
    } or _has_any(q, ("产业链", "上下游", "供应链", "关系", "受益链"))
    asks_financials = question_type in {
        QUESTION_VALUATION,
        QUESTION_FINANCIAL_ANALYSIS,
    } or _has_any(
        q,
        (
            "财报",
            "财务",
            "业绩",
            "营收",
            "净利",
            "毛利率",
            "估值",
            "贵不贵",
            "隐含增长",
        ),
    )
    return BaseFinanceMode(
        require_market=has_specific_target,
        require_memory=has_specific_target,
        require_news=asks_recent_event,
        require_graph=asks_chain,
        require_financials=asks_financials,
        quick_answer=depth == DEPTH_QUICK,
    )


def _classify_question_type(raw_query: str, q: str) -> tuple[str, float]:
    if _has_any(q, ("质检", "打分", "评分", "回答质量", "答案质量")) or (
        _has_any(q, ("输出", "模板", "claude"))
        and _has_any(q, ("这份回答", "这个回答", "这个答案", "上一版", "质量", "改写"))
    ):
        return QUESTION_ANSWER_REVIEW, 0.86
    # 强触发词优先于泛化关键词：深挖/复盘先验是明确的任务指令，
    # 即便问句里同时出现 产业链/公告/板块 等弱信号也不应被抢路由。
    if _has_any(q, ("深挖", "个股深挖", "深度分析个股")):
        return QUESTION_STOCK_DEEP_DIVE, 0.9
    if _has_any(q, ("复盘先验", "先验复盘", "行情前瞻", "明日研判", "次日研判", "前瞻研判")):
        return QUESTION_MARKET_FORECAST, 0.9
    if (
        _has_any(q, ("展望", "研判", "预测"))
        and _has_any(q, ("后市", "市场", "行情", "大盘"))
    ) or (
        _has_any(q, ("后市", "后面市场", "接下来市场", "未来市场"))
        and _has_any(q, ("怎么", "如何", "演绎", "走势"))
    ):
        return QUESTION_MARKET_FORECAST, 0.9
    if _has_any(
        q,
        (
            "今日复盘",
            "市场复盘",
            "市场总览",
            "最新交易日",
            "赚钱效应",
            "市场结构",
            "主要风险",
        ),
    ) or (
        "复盘" in q
        and _has_any(
            q,
            ("市场", "交易日", "大盘", "主线", "赚钱效应", "涨跌家数", "风险"),
        )
    ):
        return QUESTION_MARKET_REVIEW, 0.92
    # 「问现状」而非「问后市」：时间锚点 + 状态词。
    #
    # 原先 market_review 只认「复盘/市场总览/赚钱效应」这类行话，而下面那条兜底
    # 把含「今天」或「大盘」的问句一律判成 market_forecast，于是走 forecast-preflight
    # 要求先补齐 daily-agent 研究队列 —— 日常最高频的「今天大盘什么阶段」因此拒答，
    # 尽管本地盘面库是完整的（8799 canary run_20260730_153013_338430 实证）。
    #
    # 状态词分两类，为的是不把题材问题抢过来：
    #   需要大盘主语的（阶段/结构/状态/强弱）—— 否则「固态电池现在什么阶段」会被误抢；
    #   本身就是大盘级的（主线/赚钱效应/涨跌家数/涨停家数）—— 无需主语。
    # 两类都要求时间锚点，所以「固态电池的主线逻辑」（无锚点）仍归 theme_analysis。
    #
    # 明确指向未来的问法（展望/研判/预测/后市/明日研判…）在本规则之前已经返回，
    # 不会走到这里；同时问两头的「今天什么阶段、明天怎么看」按现状作答，因为盘面
    # 数据是现成的，后市部分可在答案里做条件化情景。
    if _market_level_clause(q):
        return QUESTION_MARKET_REVIEW, 0.88
    if _has_any(q, ("拍估值", "估值带", "贵不贵", "隐含预期", "隐含增长", "值多少钱", "估值分位", "估值怎么看", "合理估值")):
        return QUESTION_VALUATION, 0.88
    if _has_any(
        q,
        (
            "财报分析",
            "财报",
            "财务分析",
            "业绩分析",
            "业绩兑现",
            "营收",
            "净利润",
            "毛利率",
            "净利率",
            "季度业绩",
            "基本面",
        ),
    ):
        return QUESTION_FINANCIAL_ANALYSIS, 0.84
    if _has_any(q, ("公告", "新闻", "链接", "传导", "冲击", "影响")):
        return QUESTION_NEWS_IMPACT, 0.82
    # 取值查询必须挡在前瞻兜底之前：下面那行把「收盘」当前瞻触发词，于是
    # 「宁德时代今天收盘多少」这种纯粹问过去数字的问题被判成 market_forecast，
    # 进而在 rubric 里追加四源合议/策略状态映射等 5 个前瞻维度、在 task_frame 里
    # 被要求给出情景路径与失效条件——查一个收盘价满足不了其中任何一条。
    # 词面判定与 turn_controller 共用 route_table.is_quick_fact_query，避免两条
    # 并行判定链再次漂移。
    if is_quick_fact_query(raw_query):
        return QUESTION_QUICK_FACT, 0.85
    # 兜底：到这里说明既不是「问现状」也没有明确的后市措辞，按前瞻处理。
    # 移除了原有的 "6."——那是个会匹配任意含 "6." 文本的误留模式（例如
    # 「营收 6.2 亿」），与市场前瞻无关。
    if _has_any(q, ("行情", "大盘", "今天", "明天", "盘前", "收盘", "走势", "市场怎么看")):
        return QUESTION_MARKET_FORECAST, 0.8
    if _has_any(q, ("题材", "板块", "方向", "细分", "产业", "主线", "双红")):
        return QUESTION_THEME_ANALYSIS, 0.76
    if _has_any(
        q,
        (
            "个股",
            "这只股",
            "股票怎么看",
            "上涨空间",
            "还有空间",
            "能不能涨",
            "后续空间",
        ),
    ):
        return QUESTION_STOCK_DEEP_DIVE, 0.78
    if _has_any(q, ("方法论", "框架", "怎么做", "路径", "编排层", "怎么实现", "原理")):
        return QUESTION_METHODOLOGY, 0.74
    return QUESTION_GENERAL, 0.45


def _classify_depth(raw_query: str, q: str, question_type: str) -> str:
    if _has_any(q, ("深挖", "完整", "详细", "hybrid", "对照模板", "打分", "质检", "第一性原理")):
        return DEPTH_DEEP
    if _has_any(q, ("简单", "一句话", "快答", "简短")):
        return DEPTH_QUICK
    if question_type in {
        QUESTION_STOCK_DEEP_DIVE,
        QUESTION_NEWS_IMPACT,
        QUESTION_ANSWER_REVIEW,
        QUESTION_VALUATION,
        QUESTION_FINANCIAL_ANALYSIS,
    }:
        return DEPTH_DEEP
    if question_type in {
        QUESTION_EXTERNAL_MARKET,
        QUESTION_CONCEPT_DEFINITION,
    }:
        return DEPTH_STANDARD
    if question_type in {QUESTION_THEME_ANALYSIS, QUESTION_MARKET_REVIEW, QUESTION_MARKET_FORECAST}:
        return DEPTH_STANDARD
    return DEPTH_STANDARD


def _required_lenses(question_type: str, depth: str) -> list[str]:
    common = [
        "证据硬度：区分公告/年报/互动易/订单等硬证据，与研报推演、市场传闻、盘面标签",
        "反证视角：主动说明如果判断错，最可能错在哪里",
        "条件化结论：不要给单点结论，要写清升级、降级和证伪条件",
    ]
    if question_type == QUESTION_EXTERNAL_MARKET:
        return [
            "行情口径：指数名称、收盘点位、涨跌幅和 source_trade_date 必须来自结构化行情或 finance quote",
            "双源校验：优先结构化 global-market，滞后、缺失或缺少指数时再用 finance quote",
            "来源隔离：新闻标题只能补方向与事件，不得替代精确点位或涨跌幅",
            "失败可见：provider 失败时明确写数据缺口，不用本地 A 股资料代答",
        ]
    if question_type == QUESTION_MARKET_TECHNICAL:
        return [
            "行情口径：支撑/压力必须来自结构化 OHLCV 日线的确定性计算（均线、摆动低点、区间低点、缺口）",
            "计算透明：每个支撑区标注计算依据与数据截止日",
            "失效条件：给出跌破哪个价位判断失效",
            "来源隔离：不用 Wiki/题材结构/公司公告代替行情计算；取不到行情只报数据缺口",
        ]
    if question_type == QUESTION_MARKET_CAUSE:
        return [
            "时间窗口：先确认本周/近一周的起止交易日，不能把最后一个交易日当成整周",
            "盘面变化：指数、成交额、涨跌家数、涨停/跌停和行业扩散的周内变化",
            "因果链：把可核验的宏观/事件/资金证据与盘面变化逐条对应，区分事实与推断",
            "反证视角：说明哪些原因仍只是候选、什么数据会推翻当前归因",
        ]
    if question_type == QUESTION_CONCEPT_DEFINITION:
        return [
            "先解释定义、核心技术原理和产业链位置",
            "本地知识库未命中时受控升级到通用 Web Search",
            "Web 摘要只作为外部来源线索，保留来源链接和证据边界",
        ]
    if question_type == QUESTION_STOCK_DEEP_DIVE:
        return [
            "公司本体：主营、收入结构、产业链位置、客户/竞争格局",
            "市场结构：大盘阶段、量能、涨跌家数、MA5、行业聚散度和市场风格",
            "板块生命周期：主线/分支/补涨/高低切/高位分歧/反弹兑现",
            "个股相对强度：新高、成交承接、回撤半衰期、是否被市场选择",
            "逻辑生命周期：新出现/旧逻辑唤醒/升温验证/加速定价/高位分歧/衰退观察/证伪退出",
            "二阶导：产业瓶颈、替代表达、同题材更强标的",
            *common,
        ]
    if question_type == QUESTION_THEME_ANALYSIS:
        return [
            "市场阶段：当前是扩散、主升、第一次分歧、反弹还是兑现",
            "题材结构：双红、涨停扩散、新高集群、容量行业和边际量",
            "强势股队列：领先核心、同步确认、后排补涨和被抛弃方向",
            "产业链分层：上游瓶颈、中游制造、下游需求和二阶受益",
            "逻辑生命周期：题材有没有产生过真实市场价值，CAR/相对强度/半衰期如何",
            *common,
        ]
    if question_type == QUESTION_MARKET_REVIEW:
        return [
            "数据边界：先确认最新交易日，并分别检查题材级汇总与核心板块明细的日期",
            "市场结构：指数、成交额、涨跌家数、涨停跌停、行业聚散度和风格",
            "主线与赚钱效应：回答资金集中在哪里、扩散到哪里、哪些方向承压",
            "主要风险：只保留会改变当前市场判断的风险和数据缺口",
            "验证信号：给出下一交易日最少且可核验的升级/降级条件",
        ]
    if question_type == QUESTION_MARKET_FORECAST:
        return [
            "四源合议：全量盘面复盘、晚间卖方/机构胜率、隔夜美股/海外映射、晨汇/早间材料要先合并再判断",
            "大盘阶段：指数位置、量价关系、周均线偏离度和风险区间",
            "情绪阶段：涨家数、MA5、涨停/跌停、赚钱效应扩散或收缩",
            "风格判断：大成交抱团、情绪连板、低位切换、高位分化或防御轮动",
            "全量复盘硬字段：容量前三申万一级、双红题材、单红/缩量上涨题材、涨停热度、新高集群、开根加权强度都必须进入推理",
            "板块平行关系：主线、支线、补涨、高低切和双红演变；没有双红时要说明是存量修复/缩量抱团还是低位启动失败",
            "策略状态映射：分歧时比较策略三主线强势股回流与策略二流动性切换，上涨时区分普涨/结构性并映射策略一/策略四",
            "策略选择器：基于 daily-agent 生成的策略一二三四候选，结合当前市场阶段优选策略组合、题材和个股，并说明选择理由",
            "外生变量映射：区分复盘会外盘底座与 web/finance 最新隔夜美股，纳指、费半、AI硬件链、美股科技龙头和风险资产变化只能作为 A 股题材映射的辅助证据",
            "假设验证：盘前/前瞻推论必须能在盘后验证",
            *common,
        ]
    if question_type == QUESTION_NEWS_IMPACT:
        return [
            "事实抽取：先拆新事实、旧事实、观点和传闻",
            "产业链传导：需求变化 -> 财务科目 -> 公司弹性 -> 市场误分类",
            "受益/受损分层：一阶、二阶、替代、被挤压环节",
            "证据升级路径：从 L1 产业翻译到 L3 官方验证",
            "盘面映射：消息是否已经被交易，是否出现兑现分歧",
            *common,
        ]
    if question_type == QUESTION_VALUATION:
        return [
            "估值现状：当前 PE/PS/EV-EBITDA 历史分位与同业横截面位置",
            "可比公司估值带：同链/同商业模式 3-5 家，给区间不给点位",
            "隐含增长率反推：当前市值隐含了什么增速/份额假设，市场已经 price in 了多少",
            "情景估值表：悲观/中性/乐观三情景，每个情景绑定可验证条件（公告/订单/产能口径）",
            "证据审计：区分硬数据、研报推断（L1 降权）与缺口",
            *common,
        ]
    if question_type == QUESTION_FINANCIAL_ANALYSIS:
        return [
            "财务验鲜：确认报告期、披露日期和累计/单季口径",
            "增长质量：营收、归母净利、毛利率、净利率及其变化方向",
            "兑现与分歧：区分收入增长、利润弹性和非经常性因素",
            "公司证据：公告、定期报告、订单、产能和客户验证",
            "反证条件：增长失速、利润率恶化、现金流或订单不及预期",
            *common,
        ]
    if question_type == QUESTION_ANSWER_REVIEW:
        return [
            "覆盖率：是否覆盖公司本体、市场、板块、个股、生命周期、二阶导和反证",
            "证据边界：有没有编造、有没有把弱证据当硬事实",
            "推理质量：是否从第一性原理推导，而不是套模板",
            "市场融合：有没有把大盘、情绪、板块和相对强度融入判断",
            "可改进项：指出缺口并给出可直接重写的方向",
        ]
    if question_type == QUESTION_METHODOLOGY:
        return [
            "目标拆解：先区分用户要方法论、工程实现还是使用路径",
            "工程闭环：输入、编排、检索、生成、质检、沉淀、验证",
            "替代方案：规则、LLM planner、混合编排的取舍",
            "可迁移性：说明这套方法能迁移到哪些 agent 场景",
        ]
    return common


def _retrieval_plan(question_type: str, depth: str, q: str) -> list[str]:
    if question_type == QUESTION_MARKET_TECHNICAL:
        return [
            "结构化指数/个股日线 OHLCV：唯一必需数据源，成功即停",
            "确定性技术位计算器：MA5/10/20/60、摆动低点、20/60日低点、跳空缺口",
            "跳过 Wiki RAG、知识图谱、agent web loop：该题型不需要文本证据",
        ]
    if question_type == QUESTION_MARKET_CAUSE:
        return [
            "DuckDB 周内市场窗口：指数、成交额、涨跌结构和行业集中度逐日变化",
            "财经新闻/网页：只检索与该周市场波动时间对齐的宏观、政策、外盘和资金事件",
            "因果核验：至少一条周内盘面证据 + 一条事件/资金证据；不足时明确报缺口",
        ]
    if question_type == QUESTION_EXTERNAL_MARKET:
        return [
            "fupanhui /reviews/global-market：结构化海外指数底座与 source_trade_date",
            "finance chart quote：结构化底座滞后、缺失或缺少指数时补精确收盘",
            "Bing News：仅在需要方向性事件补充时使用，不作为精确行情",
        ]
    if question_type == QUESTION_CONCEPT_DEFINITION:
        return [
            "本地 Wiki/RAG：先查已有定义和产业链资料",
            "Bing Web Search via Web Access：本地未命中时补外部定义与技术背景",
        ]
    common = ["experience_cards：召回历史纠偏和优秀样板", "answer_quality：加载通用多视角质检"]
    if question_type == QUESTION_STOCK_DEEP_DIVE:
        plan = [
            "DuckDB：个股走势、成交、相对强度、新高、同题材强势替代队列",
            "wiki entity：公司本体、收入结构、产业链暴露、证据缺口",
            "wiki hybrid RAG：召回研报、概念页、同链条替代标的",
            "evidence_index：客户/订单/量产/互动易/公告证据硬度",
            "L3 evidence tools：本地证据缺客户/订单/量产/产能/问询函时，运行时调用公告/互动易 CLI 补查",
            *common,
        ]
        if depth == DEPTH_DEEP:
            plan.append("D1/D2/D3/D4 数据块：市场价值、客户证据硬度、二阶导研究队列、主线题材结构")
        return plan
    if question_type == QUESTION_THEME_ANALYSIS:
        return [
            "DuckDB/theme candidates：双红、涨停热度、新高集群、容量行业、边际量",
            "DuckDB mainline sectors：每日主线题材、核心板块、cycle_status、启动日和新高/临近突破状态",
            "wiki concept + hybrid RAG：产业链结构、概念页、研报页",
            "同题材强势股队列：领先核心、补涨、替代方向",
            *common,
        ]
    if question_type == QUESTION_MARKET_REVIEW:
        return [
            "DuckDB market context：核对指数、成交额、上涨家数、涨停和跌停",
            "Daily Review：读取最新交易日的市场核心、主要方向、风险和数据说明",
            "DuckDB mainline sectors：核对主线连续性、核心板块、周期状态和量价状态",
            "experience_cards：召回用户对复盘表达和数据边界的纠偏",
        ]
    if question_type == QUESTION_MARKET_FORECAST:
        return [
            "DuckDB market context：大盘阶段、成交额、量能回归、涨跌家数、MA5、涨停跌停",
            "行业容量与风格：申万一级成交占比、top3 聚散度、强势题材",
            "主线结构：fact_mainline_sector_daily 的主线题材、核心板块、cycle_status 和启动/分歧/消亡状态",
            "全量复盘数据块：双红题材、边际量 diff_ratio、题材成交额、涨停热度、新高集群、开根加权强度和行业发动机",
            "theme candidates：双红演变、新高方向、涨停热度和强势股",
            "晚间卖方/机构胜率：按机构胜率、覆盖密度、证据硬度和盘面位置判断新 alpha、共识确认或兑现风险",
            "晨汇/早间材料：抽取隔夜新增产业变量、事件催化、风险提示和需要盘中验证的方向",
            "外盘双源：先读 fupanhui /reviews/global-market 作为可对齐底座；若 source_trade_date 滞后或需要当晚美股收盘，用 web/finance search 补最新纳指、费半、SOXX/QQQ、AI硬件链和核心股涨跌幅",
            "策略一二三四方法论：把策略看成市场状态语言，而不是静态股票池标签",
            "daily-agent 策略候选：读取策略一/二/三/四生成的题材和个股候选，做策略组合优选与次日验证",
            "forecast_preflight：读取 daily-agent research_queue，先检查旧逻辑唤醒 / 新逻辑候选 / DeepDive / L3 官方验证缺口；未通过时先让用户补材料并 ingest，再生成正式复盘",
            "hypothesis ledger：记录前瞻假设，盘后验证",
            *common,
        ]
    if question_type == QUESTION_NEWS_IMPACT:
        return [
            "source text：先抽取新闻/公告/研报里的事实、观点和传闻",
            "wiki concept/entity：产业链位置和公司暴露",
            "hybrid RAG：相邻概念、历史研报、替代表达",
            "disclosure/interaction API：需要最新公告、互动易、问询函时实时查询",
            "evidence_index：把 L3 级事实沉淀为可复用证据",
            *common,
        ]
    if question_type == QUESTION_VALUATION:
        return [
            "DuckDB：市值、区间涨幅、相对强度、同题材替代队列",
            "iFinD：财务口径（营收/利润/毛利率）与估值指标历史分位",
            "wiki entity：业务结构、产业链位置、可比公司候选",
            "evidence_index：订单/产能/客户等硬证据，支撑情景条件",
            "L3 evidence tools：情景条件缺公告级证据时运行时补查",
            *common,
        ]
    if question_type == QUESTION_FINANCIAL_ANALYSIS:
        return [
            "逐季财报：营收、归母净利、毛利率、净利率及同比方向",
            "定期报告与公告：核对业绩变动原因、订单、产能和客户口径",
            "公司本体与同业：业务结构、产业链位置和可比兑现节奏",
            "盘面与估值：判断业绩是否已被交易、市场仍在定价什么",
            *common,
        ]
    if question_type == QUESTION_ANSWER_REVIEW:
        return [
            "answer rubric：按固定评分项打分",
            "experience_cards：对照历史优秀样板和用户纠偏",
            "local-source check：核对回答是否真实使用本地 DuckDB/wiki/RAG",
        ]
    return common


def _quality_gates(question_type: str, depth: str) -> list[str]:
    gates = [
        "不能只给结论，必须说明关键推理链和证据边界",
        "必须主动写反证和证伪条件",
        "缺数据时要说明缺口，不能用常识或印象补齐",
    ]
    if question_type == QUESTION_MARKET_TECHNICAL:
        gates.extend(
            [
                "支撑/压力数字必须来自确定性计算，不得由 LLM 生成或改写",
                "必须标注数据截止日与每个支撑区的计算依据",
                "取不到 OHLCV 时只报数据缺口短答，禁止用题材结构、公司公告、知识图谱模板代答",
            ]
        )
    if question_type == QUESTION_MARKET_CAUSE:
        gates.extend(
            [
                "必须回答指定周窗口，不得只复述最后一个交易日",
                "每个主要原因都要绑定可回查证据；盘面现象不能自动冒充外部因果",
                "没有足够事件/资金证据时，必须把原因写成候选并报告缺口",
                "用户未询问交易策略时，不追加买卖、仓位或防御建议",
            ]
        )
    if question_type == QUESTION_EXTERNAL_MARKET:
        gates.extend(
            [
                "不得把 Bing News 标题或新闻描述换算成精确涨跌幅",
                "必须展示 source_trade_date 和 provider 状态",
                "外部 provider 失败时不得用无关 A 股证据替代",
            ]
        )
    if question_type == QUESTION_CONCEPT_DEFINITION:
        gates.extend(
            [
                "本地知识命中与 Web 外部来源必须分开标注",
                "没有可靠来源时保留未知，不把 A 股题材标签当技术定义",
            ]
        )
    if question_type in {QUESTION_STOCK_DEEP_DIVE, QUESTION_THEME_ANALYSIS}:
        gates.extend(
            [
                "必须判断逻辑生命周期，以及状态相对过去 N 天发生了什么变化",
                "必须回答这条逻辑是否真正产生过市场价值，而不是只讲故事",
                "必须说明市场正在奖励谁、抛弃谁、犹豫谁",
            ]
        )
    if question_type == QUESTION_MARKET_REVIEW:
        gates.extend(
            [
                "必须直接回答市场结构、主线、赚钱效应和主要风险，不扩展成个股深挖",
                "当日市场数据与较旧主线快照必须分开表述，不能把历史主线当成当日事实",
                "没有当日题材数据时应保留未知，不用公司线索、产业链或二阶导填补",
            ]
        )
    if question_type == QUESTION_MARKET_FORECAST:
        gates.extend(
            [
                "不能只由全量盘面外推，必须说明晚间卖方、晨汇、外盘双源三类外生信息是否可得、支持什么、反证什么",
                "外盘必须标注口径：fupanhui 的 source_trade_date，或 web/finance search 的最新收盘日期，不能把昨日外盘当成最新隔夜",
                "必须把行情阶段映射到策略思路：分歧看主线强势股回流/流动性切换，上涨区分结构性上涨与普涨，高位看拥挤和兑现",
                "必须输出策略选择结果：优先策略/备选策略、对应题材、核心个股、选择理由和次日验证字段",
                "必须先通过复盘前置查漏门 forecast_preflight；若 daily-agent 提示今日该做 IMA 或今日该找公告/调研/订单，正式复盘应暂停，先输出 DeepDive / ingest 查漏清单",
                "必须判断双红题材：列出真正双红、涨但边际量为负的缩量强修复、以及涨停/新高强但非双红的方向，并据此调整追高/切换权重",
                "必须输出可验证假设，盘后能逐条验证",
                "必须区分大盘、情绪、板块、风格和个股机会，不可混为一谈",
            ]
        )
    if question_type == QUESTION_MARKET_REVIEW:
        gates.extend(
            [
                "开头三句话内回答当天市场是什么状态、钱去了哪里、主要风险是什么",
                "主答案不得出现内部表名、字段名、证据层编号、状态机或检索管线名称",
                "双红、偏离度等专业词必须改写成普通用户能直接理解的中文",
                "不得把整段问题当作题材名，也不得追加无关概念和公司列表",
            ]
        )
    if question_type == QUESTION_VALUATION:
        gates.extend(
            [
                "禁止输出单点目标价，只能给条件化的估值区间",
                "情景必须绑定可验证条件，不能只给乐观/悲观形容词",
                "未验鲜的财务/市值数据不得使用，缺口必须显式写出",
                "研报盈利预测只能作为 L1 参考，不能当作硬输入",
            ]
        )
    if question_type == QUESTION_FINANCIAL_ANALYSIS:
        gates.extend(
            [
                "必须标注财报报告期、披露日期和累计/单季口径",
                "缺逐季硬数据时不得用市场印象补齐增长率或利润率",
                "必须区分收入增长、利润增长、利润率变化和非经常性因素",
                "必须给出下一报告期可验证的升级、降级和证伪条件",
            ]
        )
    if question_type == QUESTION_NEWS_IMPACT:
        gates.extend(
            [
                "必须先拆事实层，再做产业链传导，不能直接跳到受益股",
                "必须区分一阶受益、二阶受益和反向受损",
            ]
        )
    if depth == DEPTH_DEEP:
        gates.append("深度回答必须经过影子用户反驳后重写，避免模板化和孤立分析")
    return gates


def _output_contract(question_type: str, depth: str) -> list[str]:
    if question_type == QUESTION_MARKET_TECHNICAL:
        return [
            "先给当前收盘价与数据截止日，再列支撑区（数字区间 + 计算依据）",
            "给出压力区与失效条件（跌破哪个价位需要重新计算）",
            "取数失败时直接给数据缺口短答，不延伸任何题材或个股判断",
        ]
    if question_type == QUESTION_MARKET_CAUSE:
        return [
            "先给周窗口和市场结果，再列 1-3 个有证据支持的主要原因",
            "每个原因说明：证据是什么、如何传导到指数/成交/行业、置信度和反证",
            "区分已核验原因、盘面推断与仍缺的事件/资金证据",
            "结尾只写因果验证缺口，不输出用户未要求的交易策略或仓位建议",
        ]
    if question_type == QUESTION_EXTERNAL_MARKET:
        return [
            "先给 source_trade_date，再逐项列指数收盘点位与涨跌幅",
            "明确标注结构化行情或 finance quote 来源",
            "如有新闻补充，单列为方向性材料且不与行情数字混写",
            "取数失败时直接给 provider 缺口，不延伸无关 A 股题材",
        ]
    if question_type == QUESTION_CONCEPT_DEFINITION:
        return [
            "用简洁语言回答是什么、如何工作、位于产业链哪里",
            "列出本地知识或 Web 来源，区分事实与推导",
            "不自动扩展无关公司名单或 A 股盘面判断",
        ]
    if question_type == QUESTION_STOCK_DEEP_DIVE:
        return [
            "开头先给定位和核心矛盾",
            "把公司本体、市场结构、板块生命周期、个股相对强度和二阶导融成自然分析",
            "结尾给条件化结论与验证点，不输出买卖指令",
        ]
    if question_type == QUESTION_MARKET_FORECAST:
        return [
            "从前一交易日和过去 N 天视角推导下一交易日可能性",
            "先写市场状态，再写四源合议，再推导最可能路径与策略状态映射",
            "必须复用个股深挖里的盘面视角：市场阶段、容量行业、双红题材、涨停热度、新高集群、相对强度、开根加权、生命周期和反证",
            "必须给出结论型策略组合：当前优先用策略一/二/三/四中的哪些，为什么，选哪些板块/题材/个股",
            "输出 3-6 条可盘后验证的假设",
            "每条假设要标明支持/反证来源：全量盘面、晚间卖方、晨汇、fupanhui 外盘、web 最新美股或缺数据",
            "盘后应能回填验证结果和纠偏经验",
        ]
    if question_type == QUESTION_MARKET_REVIEW:
        return [
            "先用一句话给出直接结论，再说明整体数据截止日和局部数据缺口",
            "围绕用户问题组织为市场结构、主线与赚钱效应、主要风险、后续验证，使用少量自然小标题",
            "最多使用 5 个二级标题；数据边界放在开头，强势股动能并入市场结构或风险，不单独拆章",
            "默认只写支撑结论的关键数据；不要机械覆盖公司本体、产业链、客户证据、二阶导、完整生命周期或策略矩阵",
            "按数据粒度表述主线缺口：题材级汇总同日时可写当前题材名；核心板块明细滞后时，板块、周期和标的必须写未知",
            "标题和正文只用用户语言；不要出现反方审稿、第一性原理、质检、证据硬度等内部研究口吻",
            "技术诊断和内部字段只放到运行详情，不写入用户正文",
            "结尾给 2-4 个可核验信号，不输出买卖指令",
        ]
    if question_type == QUESTION_NEWS_IMPACT:
        return [
            "先复述事实，不扩写无证据信息",
            "再推导产业链冲击、受益/受损分层和观察指标",
            "最后给出需要入库沉淀的 L3 候选事实",
        ]
    if question_type == QUESTION_VALUATION:
        return [
            "先给估值现状和核心矛盾（市场已 price in 什么）",
            "再给可比估值带与隐含增长率反推",
            "情景估值表每行带可验证条件",
            "结尾给证据审计与升级/降级/证伪条件，不输出买卖指令",
        ]
    if question_type == QUESTION_FINANCIAL_ANALYSIS:
        return [
            "先给业绩兑现结论和最关键的增长质量变化",
            "再拆营收、利润、利润率及其持续性",
            "明确报告期、数据口径、异常项和仍缺的公司证据",
            "结尾给下一报告期的升级、降级和证伪条件",
        ]
    if question_type == QUESTION_ANSWER_REVIEW:
        return [
            "先给总分和核心缺口",
            "再按模板覆盖率、证据硬度、推理质量、市场融合、二阶导反证打分",
            "最后给出可执行重写建议",
        ]
    return ["自然回答，但必须显式区分事实、推导、反证和后续验证"]


def _missing_data_policy(question_type: str) -> list[str]:
    base = [
        "本地没有命中时，先声明缺口，再决定是否需要 web/API 补查",
        "外部实时查询只补最新事实，不替代知识库/金融库的结构化底座",
    ]
    if question_type == QUESTION_MARKET_TECHNICAL:
        base.append("OHLCV 取数失败时只报明确数据缺口，禁止用全市场题材结构或图谱代答")
    if question_type == QUESTION_MARKET_CAUSE:
        base.extend(
            [
                "周内市场数据不足时不得降级为单日复盘模板",
                "缺事件/资金证据时只能输出盘面事实与候选解释，并明确因果缺口",
            ]
        )
    if question_type == QUESTION_EXTERNAL_MARKET:
        base.extend(
            [
                "结构化 global-market 缺失、日期滞后或缺少指数时必须尝试 finance quote",
                "finance quote 仍失败时明确列出 provider 状态与缺口",
                "新闻搜索结果不能替代收盘点位和涨跌幅",
            ]
        )
    if question_type == QUESTION_CONCEPT_DEFINITION:
        base.append("本地 Wiki/RAG 未命中时才升级到通用 Web Search")
    if question_type == QUESTION_STOCK_DEEP_DIVE:
        base.append("缺公司收入结构/客户证据时，不得把题材标签当作基本面结论")
        base.append("缺 L3 硬证据时，应先通过 L3 evidence tools 补查公告/互动易；查不到则显式降权，而不是补脑")
    if question_type == QUESTION_MARKET_FORECAST:
        base.append("缺最新 DuckDB 盘面时，只能做方法论推演，不能伪装成当天判断")
        base.append("缺晚间卖方、晨汇或最新隔夜美股时，必须显式标记缺口并降低前瞻置信度")
        base.append("fupanhui 外盘若只返回昨日 source_trade_date，应用 web/finance search 补当晚美股涨跌幅")
        base.append("缺 daily-agent 策略候选时，可以基于策略底层方法论手工推演，但必须标注未读取候选池")
        base.append("daily-agent research_queue 存在今日该做 IMA / 今日该找公告或调研时，先补 DeepDive / L3 证据并 ingest；未补前只能生成带缺口标记的草稿")
    if question_type == QUESTION_MARKET_REVIEW:
        base.append("缺本地复盘报告或最新 DuckDB 市场总览时，不能伪装成最新交易日复盘")
        base.append("行业数据使用替代口径时，只判断方向，不把精确值表述为官方行业指数")
        base.append("主线表滞后时只能描述历史基线，并把当日主线标为未知")
    if question_type == QUESTION_NEWS_IMPACT:
        base.append("缺原文或公告时，先要求材料或实时查源，不能根据标题扩写")
    if question_type == QUESTION_VALUATION:
        base.append("缺财务/估值数据时只能做框架推演，不得伪装成当前估值判断")
        base.append("缺可比公司数据时，必须说明可比集缺口，不能用印象估值带补齐")
    if question_type == QUESTION_FINANCIAL_ANALYSIS:
        base.append("缺逐季财务数据时只能给核验框架，不能编造营收、利润或利润率")
        base.append("累计口径与单季口径不能混用；无法还原单季时必须显式说明")
    return base


def _warnings(raw_query: str, q: str, question_type: str, retrieval_plan: list[str]) -> list[str]:
    warnings: list[str] = []
    if question_type == QUESTION_GENERAL and len(raw_query) > 20:
        warnings.append("未高置信识别问题类型，建议先按通用金融问答处理并显式说明假设")
    if "web" in q or "搜索" in q:
        warnings.append("用户提到搜索时，应优先说明本地知识库/金融库与外部搜索的分工")
    if question_type == QUESTION_STOCK_DEEP_DIVE and not any("DuckDB" in item for item in retrieval_plan):
        warnings.append("个股深挖缺 DuckDB 取数计划，结论需降置信")
    return warnings
