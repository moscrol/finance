from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from intelligence.services.answer_model import ThemeResearchSpec, resolve_theme_research_spec


QUESTION_STOCK_DEEP_DIVE = "stock_deep_dive"
QUESTION_THEME_ANALYSIS = "theme_analysis"
QUESTION_MARKET_FORECAST = "market_forecast"
QUESTION_NEWS_IMPACT = "news_impact"
QUESTION_VALUATION = "valuation_estimate"
QUESTION_ANSWER_REVIEW = "answer_review"
QUESTION_METHODOLOGY = "methodology_discussion"
QUESTION_GENERAL = "general_finance_qa"

DEPTH_QUICK = "quick"
DEPTH_STANDARD = "standard"
DEPTH_DEEP = "deep"


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
    required_lenses: list[str] = field(default_factory=list)
    retrieval_plan: list[str] = field(default_factory=list)
    quality_gates: list[str] = field(default_factory=list)
    output_contract: list[str] = field(default_factory=list)
    missing_data_policy: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    research_spec: ThemeResearchSpec | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "question_type": self.question_type,
            "depth": self.depth,
            "confidence": self.confidence,
            "required_lenses": self.required_lenses,
            "retrieval_plan": self.retrieval_plan,
            "quality_gates": self.quality_gates,
            "output_contract": self.output_contract,
            "missing_data_policy": self.missing_data_policy,
            "warnings": self.warnings,
            "research_spec": self.research_spec.to_dict() if self.research_spec else None,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_prompt_block(self) -> str:
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
        if self.research_spec is not None:
            lines.extend(["", self.research_spec.to_prompt_block()])
        return "\n".join(lines)


def plan_answer_question(
    query: str,
    matched_theme: str | None = None,
) -> QuestionPlan:
    raw_query = str(query or "").strip()
    if not raw_query:
        return QuestionPlan(
            query=raw_query,
            question_type=QUESTION_GENERAL,
            depth=DEPTH_QUICK,
            confidence=0.1,
            required_lenses=["先要求用户补充题材、个股、日期或材料"],
            retrieval_plan=[],
            quality_gates=["不能在问题为空时编造分析对象"],
            output_contract=["请用户补充问题"],
            missing_data_policy=["问题为空，必须追问"],
            warnings=["empty query"],
        )

    q = _normalize(raw_query)
    question_type, confidence = _classify_question_type(raw_query, q)
    depth = _classify_depth(raw_query, q, question_type)
    required_lenses = _required_lenses(question_type, depth)
    retrieval_plan = _retrieval_plan(question_type, depth, q)
    quality_gates = _quality_gates(question_type, depth)
    output_contract = _output_contract(question_type, depth)
    missing_data_policy = _missing_data_policy(question_type)
    warnings = _warnings(raw_query, q, question_type, retrieval_plan)
    research_spec = (
        resolve_theme_research_spec(raw_query, matched_theme)
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
        required_lenses=required_lenses,
        retrieval_plan=retrieval_plan,
        quality_gates=quality_gates,
        output_contract=output_contract,
        missing_data_policy=missing_data_policy,
        warnings=warnings,
        research_spec=research_spec,
    )


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text.lower())


def _has_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(_normalize(token) in text for token in tokens)


def _classify_question_type(raw_query: str, q: str) -> tuple[str, float]:
    if _has_any(q, ("质检", "打分", "评分", "claude", "输出", "回答质量", "模板")):
        return QUESTION_ANSWER_REVIEW, 0.86
    # 强触发词优先于泛化关键词：深挖/复盘先验是明确的任务指令，
    # 即便问句里同时出现 产业链/公告/板块 等弱信号也不应被抢路由。
    if _has_any(q, ("深挖", "个股深挖", "深度分析个股")):
        return QUESTION_STOCK_DEEP_DIVE, 0.9
    if _has_any(q, ("复盘先验", "先验复盘", "行情前瞻", "明日研判", "次日研判", "前瞻研判")):
        return QUESTION_MARKET_FORECAST, 0.9
    if _has_any(q, ("拍估值", "估值带", "贵不贵", "隐含预期", "隐含增长", "值多少钱", "估值分位", "估值怎么看", "合理估值")):
        return QUESTION_VALUATION, 0.88
    if _has_any(q, ("公告", "新闻", "链接", "传导", "冲击", "影响")):
        return QUESTION_NEWS_IMPACT, 0.82
    if _has_any(q, ("行情", "大盘", "今天", "明天", "盘前", "收盘", "6.", "走势", "市场怎么看")):
        return QUESTION_MARKET_FORECAST, 0.8
    if _has_any(q, ("题材", "板块", "方向", "细分", "产业", "主线", "双红")):
        return QUESTION_THEME_ANALYSIS, 0.76
    if _has_any(q, ("深挖", "个股", "上涨空间", "怎么看", "还有空间", "能不能涨", "后续空间")):
        return QUESTION_STOCK_DEEP_DIVE, 0.78
    if _has_any(q, ("方法论", "框架", "怎么做", "路径", "编排层", "怎么实现", "原理")):
        return QUESTION_METHODOLOGY, 0.74
    if len(raw_query) <= 12:
        return QUESTION_THEME_ANALYSIS, 0.52
    return QUESTION_GENERAL, 0.45


def _classify_depth(raw_query: str, q: str, question_type: str) -> str:
    if _has_any(q, ("深挖", "完整", "详细", "hybrid", "对照模板", "打分", "质检", "第一性原理")):
        return DEPTH_DEEP
    if _has_any(q, ("简单", "一句话", "快答", "简短")):
        return DEPTH_QUICK
    if question_type in {QUESTION_STOCK_DEEP_DIVE, QUESTION_NEWS_IMPACT, QUESTION_ANSWER_REVIEW, QUESTION_VALUATION}:
        return DEPTH_DEEP
    if question_type in {QUESTION_THEME_ANALYSIS, QUESTION_MARKET_FORECAST}:
        return DEPTH_STANDARD
    return DEPTH_STANDARD


def _required_lenses(question_type: str, depth: str) -> list[str]:
    common = [
        "证据硬度：区分公告/年报/互动易/订单等硬证据，与研报推演、市场传闻、盘面标签",
        "反证视角：主动说明如果判断错，最可能错在哪里",
        "条件化结论：不要给单点结论，要写清升级、降级和证伪条件",
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
    if question_type in {QUESTION_STOCK_DEEP_DIVE, QUESTION_THEME_ANALYSIS}:
        gates.extend(
            [
                "必须判断逻辑生命周期，以及状态相对过去 N 天发生了什么变化",
                "必须回答这条逻辑是否真正产生过市场价值，而不是只讲故事",
                "必须说明市场正在奖励谁、抛弃谁、犹豫谁",
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
    if question_type == QUESTION_VALUATION:
        gates.extend(
            [
                "禁止输出单点目标价，只能给条件化的估值区间",
                "情景必须绑定可验证条件，不能只给乐观/悲观形容词",
                "未验鲜的财务/市值数据不得使用，缺口必须显式写出",
                "研报盈利预测只能作为 L1 参考，不能当作硬输入",
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
    if question_type == QUESTION_STOCK_DEEP_DIVE:
        base.append("缺公司收入结构/客户证据时，不得把题材标签当作基本面结论")
        base.append("缺 L3 硬证据时，应先通过 L3 evidence tools 补查公告/互动易；查不到则显式降权，而不是补脑")
    if question_type == QUESTION_MARKET_FORECAST:
        base.append("缺最新 DuckDB 盘面时，只能做方法论推演，不能伪装成当天判断")
        base.append("缺晚间卖方、晨汇或最新隔夜美股时，必须显式标记缺口并降低前瞻置信度")
        base.append("fupanhui 外盘若只返回昨日 source_trade_date，应用 web/finance search 补当晚美股涨跌幅")
        base.append("缺 daily-agent 策略候选时，可以基于策略底层方法论手工推演，但必须标注未读取候选池")
        base.append("daily-agent research_queue 存在今日该做 IMA / 今日该找公告或调研时，先补 DeepDive / L3 证据并 ingest；未补前只能生成带缺口标记的草稿")
    if question_type == QUESTION_NEWS_IMPACT:
        base.append("缺原文或公告时，先要求材料或实时查源，不能根据标题扩写")
    if question_type == QUESTION_VALUATION:
        base.append("缺财务/估值数据时只能做框架推演，不得伪装成当前估值判断")
        base.append("缺可比公司数据时，必须说明可比集缺口，不能用印象估值带补齐")
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
