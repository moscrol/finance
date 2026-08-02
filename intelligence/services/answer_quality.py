from __future__ import annotations

from dataclasses import dataclass, field


LAYER_L1 = "L1"
LAYER_L2 = "L2"
LAYER_L3 = "L3"
LAYER_L4 = "L4"


@dataclass(frozen=True)
class AnswerQualityContext:
    """A small, deterministic research-quality overlay for non-template answers.

    The LLM still writes the final prose. This context tells it what a mature
    A-share research answer must actively check before speaking.
    """

    stage: str
    layers: list[str]
    guidance: list[str] = field(default_factory=list)
    critic_questions: list[str] = field(default_factory=list)
    methodology_checks: list[str] = field(default_factory=list)
    market_review_checklist: list[str] = field(default_factory=list)
    daily_agent_reasoning: list[str] = field(default_factory=list)
    market_reverse_reasoning: list[str] = field(default_factory=list)
    sellside_winrate_reasoning: list[str] = field(default_factory=list)
    high_position_mainline_reasoning: list[str] = field(default_factory=list)
    stock_analysis_entrypoints: list[str] = field(default_factory=list)
    logic_lifecycle_questions: list[str] = field(default_factory=list)
    pre_output_quality_gate: list[str] = field(default_factory=list)
    shadow_user_critic: list[str] = field(default_factory=list)
    narrative_composer: list[str] = field(default_factory=list)
    prompt_profile: str = "full"

    def compact_for(self, question_type: str, research_tier: str = "standard") -> "AnswerQualityContext":
        """Project the full audit checklist into a small task-specific overlay.

        The complete checklist remains useful for offline review, but injecting
        it into every request spends attention on dimensions unrelated to the
        question.  This projection keeps the hard evidence/gap reminders and
        selects only the relevant reasoning blocks.
        """
        normalized = str(question_type or "general_finance_qa").lower()
        deep = research_tier == "deep"
        common = {
            "stage": self.stage,
            "layers": self.layers,
            "guidance": self.guidance[:2],
            "critic_questions": self.critic_questions[:3],
            "methodology_checks": self.methodology_checks[:2],
            "prompt_profile": normalized,
        }
        if "market_review" in normalized or normalized == "daily_review":
            return self
        if "method" in normalized or normalized in {
            "answer_review",
            "general",
            "general_finance_qa",
        }:
            return AnswerQualityContext(**common)
        if "stock" in normalized or "financial" in normalized:
            common.update(
                stock_analysis_entrypoints=self.stock_analysis_entrypoints[:6 if deep else 3],
                logic_lifecycle_questions=self.logic_lifecycle_questions[:4 if deep else 2],
                pre_output_quality_gate=self.pre_output_quality_gate[:4],
                narrative_composer=self.narrative_composer[:2],
            )
        elif "forecast" in normalized or "theme" in normalized:
            common.update(
                high_position_mainline_reasoning=self.high_position_mainline_reasoning[:4 if deep else 2],
                market_reverse_reasoning=self.market_reverse_reasoning[:4 if deep else 2],
                pre_output_quality_gate=self.pre_output_quality_gate[:4],
                narrative_composer=self.narrative_composer[:2],
            )
        else:
            common.update(
                market_reverse_reasoning=self.market_reverse_reasoning[:2],
                pre_output_quality_gate=self.pre_output_quality_gate[:3],
            )
        return AnswerQualityContext(**common)

    def to_prompt_block(self) -> str:
        lines = [
            "## 回答质量约束（内部研究审稿，不要机械复述为模板）",
            f"- 阶段判断：{self.stage}",
            f"- 证据层：{', '.join(self.layers) if self.layers else '未识别'}",
        ]
        if self.prompt_profile == "full":
            lines.extend(
                [
                    "- 写作要求：自然回答，不要按固定标题填空；把与本题相关的生命周期、盘面验证、反证和证据边界融进主线。",
                    "- 市场题底层逻辑：资金推动价格，量能影响周期；缺数据就明确缺口，不补造结论。",
                    "- 术语提示：不要出现“复盘会路径”，改称“市场结构推演路径”。",
                ]
            )
        elif "method" in self.prompt_profile or self.prompt_profile in {
            "answer_review",
            "general_finance_qa",
        }:
            lines.append(
                "- 只检查是否直接回答、事实是否有来源、未知项是否如实说明；不套用个股/题材/市场复盘骨架。"
            )
        else:
            lines.append(
                "- 只使用下列与本题相关的审稿提醒；结构与标题由问题本身决定。"
            )
        if self.daily_agent_reasoning:
            lines.append("- daily-agent 底层推理（必须内化为回答骨架，不要逐条硬列）：")
            lines.extend(f"  - {item}" for item in self.daily_agent_reasoning)
        if self.market_reverse_reasoning:
            lines.append("- 盘面反向解读（从全量盘面数据推导市场真实选择，不能只罗列数据）：")
            lines.extend(f"  - {item}" for item in self.market_reverse_reasoning)
        if self.sellside_winrate_reasoning:
            lines.append("- 晚间卖方/机构胜率发散（胜率不是买入信号，而是信息权重调节器）：")
            lines.extend(f"  - {item}" for item in self.sellside_winrate_reasoning)
        if self.high_position_mainline_reasoning:
            lines.append("- 高位主线反证与生命周期推理（学分析动作，不照搬观点）：")
            lines.extend(f"  - {item}" for item in self.high_position_mainline_reasoning)
        if self.stock_analysis_entrypoints:
            lines.append("- 个股/题材完整切入路径（视角要融进自然分析，不要机械列标题）：")
            lines.extend(f"  - {item}" for item in self.stock_analysis_entrypoints)
        if self.logic_lifecycle_questions:
            lines.append("- 逻辑生命周期四问（每天必须回答，缺数据要说缺口）：")
            lines.extend(f"  - {item}" for item in self.logic_lifecycle_questions)
        if self.pre_output_quality_gate:
            lines.append("- 输出前质检器（内部执行，不要把清单原样输出；若不通过，先补写再给最终回答）：")
            lines.extend(f"  - {item}" for item in self.pre_output_quality_gate)
        if self.shadow_user_critic:
            lines.append("- 用户影子反驳（模拟严格审稿人追问，内部反问后修正最终稿，不要输出审稿过程）：")
            lines.extend(f"  - {item}" for item in self.shadow_user_critic)
        if self.narrative_composer:
            lines.append("- 叙事编排器（内部执行，视角不是小标题，不要输出编排过程）：")
            lines.extend(f"  - {item}" for item in self.narrative_composer)
        if self.market_review_checklist:
            lines.append("- 硬性复盘视角（必须逐项思考，不能自行筛掉）：")
            lines.extend(f"  - {item}" for item in self.market_review_checklist)
        if self.methodology_checks:
            lines.append("- 市场结构推演路径：")
            lines.extend(f"  - {item}" for item in self.methodology_checks)
        if self.guidance:
            lines.append("- 阶段解释：")
            lines.extend(f"  - {item}" for item in self.guidance)
        if self.critic_questions:
            lines.append("- 反方审稿：")
            lines.extend(f"  - {item}" for item in self.critic_questions)
        return "\n".join(lines)


def build_quality_context(
    *,
    evidence_lines: list[str],
    market_lines: list[str],
    gap_lines: list[str],
) -> AnswerQualityContext:
    layers = _detect_layers(evidence_lines=evidence_lines, market_lines=market_lines, gap_lines=gap_lines)
    market_tone = _detect_market_tone(market_lines)
    stage = classify_expectation_stage(layers, market_tone)
    joined = "\n".join([*evidence_lines, *market_lines, *gap_lines])
    return AnswerQualityContext(
        stage=stage,
        layers=sorted(layers),
        guidance=_stage_guidance(stage),
        critic_questions=_critic_questions(stage, layers, market_tone),
        methodology_checks=_methodology_checks(market_lines),
        market_review_checklist=_market_review_checklist(),
        daily_agent_reasoning=_daily_agent_reasoning(),
        market_reverse_reasoning=_market_reverse_reasoning(),
        sellside_winrate_reasoning=_sellside_winrate_reasoning(joined),
        high_position_mainline_reasoning=_high_position_mainline_reasoning(joined),
        stock_analysis_entrypoints=_stock_analysis_entrypoints(),
        logic_lifecycle_questions=_logic_lifecycle_questions(),
        pre_output_quality_gate=_pre_output_quality_gate(),
        shadow_user_critic=_shadow_user_critic(),
        narrative_composer=_narrative_composer(),
    )


def classify_expectation_stage(layers: set[str], market_tone: set[str]) -> str:
    has_l1 = LAYER_L1 in layers
    has_l2 = LAYER_L2 in layers
    has_l3 = LAYER_L3 in layers
    has_l4 = LAYER_L4 in layers
    weak_l4 = "weak_l4" in market_tone or "priced_in" in market_tone
    strong_l4 = "strong_l4" in market_tone

    if has_l3 and weak_l4:
        return "事实验证但兑现分歧"
    if has_l3 and strong_l4:
        return "事实验证并继续重估"
    if has_l1 and has_l2 and has_l4 and not has_l3:
        return "预期交易"
    if has_l1 and has_l2 and not has_l4:
        return "预期形成"
    if has_l4 and not (has_l1 or has_l2 or has_l3):
        return "情绪脉冲"
    if has_l3:
        return "事实验证待观察"
    if has_l1:
        return "叙事观察"
    return "证据不足"


def _detect_layers(
    *,
    evidence_lines: list[str],
    market_lines: list[str],
    gap_lines: list[str],
) -> set[str]:
    layers: set[str] = set()
    evidence_text = "\n".join(evidence_lines)
    market_text = "\n".join(market_lines)
    gap_text = "\n".join(gap_lines)

    if _has_any(evidence_text, ("研报", "产业链", "叙事", "逻辑", "需求", "趋势", "主题", "题材")):
        layers.add(LAYER_L1)
    if _has_any(evidence_text, ("核心层", "主营", "baseline", "F10", "年报", "产能", "客户", "L2")):
        layers.add(LAYER_L2)
    if _has_any(evidence_text, ("公告", "订单", "合同", "中标", "认证", "量产", "出货", "客户验证", "互动易", "调研", "L3")):
        layers.add(LAYER_L3)
    if market_lines and not _has_any(market_text, ("无盘面", "未命中")):
        layers.add(LAYER_L4)
    if _has_any(gap_text, ("缺 L3", "缺失证据层", "L3 官方验证")):
        layers.discard(LAYER_L3)
    return layers


def _detect_market_tone(market_lines: list[str]) -> set[str]:
    text = "\n".join(market_lines)
    tone: set[str] = set()
    if _has_any(text, ("双红", "涨停热度", "新高", "扩散", "强验证", "多信号", "放量", "继续重估")):
        tone.add("strong_l4")
    if _has_any(text, ("高开低走", "未扩散", "兑现", "分歧", "后排不跟", "弱验证", "盘面弱", "下跌")):
        tone.add("weak_l4")
    if _has_any(text, ("提前交易", "涨幅已大", "已涨", "兑现")):
        tone.add("priced_in")
    return tone


def _stage_guidance(stage: str) -> list[str]:
    if stage == "事实验证但兑现分歧":
        return [
            "事实层不降级：L3 出现说明逻辑有硬证据，但不要把盘面下跌直接等同于逻辑证伪。",
            "情绪层要降温：需要判断预期是否已经提前交易，短线可能是公告兑现而不是新一轮启动。",
        ]
    if stage == "预期交易":
        return [
            "这是 L1/L2/L4 驱动的预期交易，不是事实兑现；回答要说清缺哪个硬事实。",
            "重点不是证明故事正确，而是判断市场正在交易哪个预期，以及这个预期还能否被 L3 续命。",
        ]
    if stage == "事实验证并继续重估":
        return ["事实和盘面同向，优先检查是否有第二层扩散和后续财务科目兑现。"]
    if stage == "情绪脉冲":
        return ["只有盘面热度时，必须主动提示证据不足，不能倒推出产业逻辑成立。"]
    return ["区分事实、推导、情绪和待验证；不要把材料里的观点直接当成公司结论。"]


def _critic_questions(stage: str, layers: set[str], market_tone: set[str]) -> list[str]:
    questions = [
        "这条信息是新事实，还是市场早已知道的旧预期？",
        "一阶受益和二阶受益分别是谁，是否存在更直接的替代标的？",
        "公司有能力栈不等于有收入弹性，弹性是否足以改变报表预期？",
    ]
    if stage in {"事实验证但兑现分歧", "预期交易"}:
        questions.insert(0, "预期是否已经提前交易，盘面是在继续重估还是兑现分歧？")
    if LAYER_L3 not in layers:
        questions.append("缺哪个硬事实：订单、合同、中标、认证、量产、客户验证、收入占比还是毛利率？")
    if "weak_l4" in market_tone:
        questions.append("如果事实成立但后排不扩散，是否应把结论拆成研究保留、情绪降温？")
    return questions


def _methodology_checks(market_lines: list[str]) -> list[str]:
    text = "\n".join(market_lines)
    if not market_lines or _has_any(text, ("无盘面", "未命中")):
        return ["盘面数据缺失：不能直接从公司逻辑外推上涨空间，需补市场量能、板块承接和个股确认。"]

    checks: list[str] = []
    if _has_any(text, ("成交", "total_amount", "volume_ratio", "量能", "放量", "缩量", "暴量")):
        checks.append("市场量能：用成交额、20日量能回归或放缩量状态判断有没有新增资金。")
    else:
        checks.append("市场量能缺口：未看到成交额/量能回归，结论需降置信。")

    if _has_any(text, ("涨停", "跌停", "涨跌家数", "advancers", "limit_up", "limit_down", "情绪")):
        checks.append("市场情绪：用涨跌家数、涨停/跌停和情绪扩散判断赚钱效应。")
    else:
        checks.append("市场情绪缺口：未看到涨跌家数或涨停跌停，难判断赚钱效应扩散。")

    if _has_any(text, ("容量前三", "top3", "top3_industry_ratio", "行业聚散度", "concentration")):
        checks.append("行业聚散度：用容量前三和 top3 成交占比判断资金主战场与拥挤度。")
    else:
        checks.append("行业聚散度缺口：未看到容量前三或 top3 占比，难判断流动性是否拥挤。")

    if _has_any(text, ("double_red", "双红", "边际量", "diff_ratio", "成交占比环比", "板块承接")):
        checks.append("板块承接：用双红、边际量和成交额确认题材是否真正获得资金承接。")
    else:
        checks.append("板块承接缺口：未看到双红/边际量/成交额组合，题材强度需谨慎。")

    if _has_any(text, ("new_high", "新高", "strong_stock", "强势股", "limit_heat", "涨停热度", "连板", "advance", "量价结构")):
        checks.append("个股确认：用新高、强势股、涨停热度、连板晋级和量价结构确认核心个股。")
    else:
        checks.append("个股确认缺口：未看到新高/强势股/涨停热度，个股空间判断需保守。")

    return checks


def _market_review_checklist() -> list[str]:
    return [
        "大盘阶段：说明当前是初步走强、主升、主升后分歧、反弹、反弹后兑现、探底、破位下跌还是冰点修复。",
        "量价与指数位置：说明成交额、相对20日均量/量能回归、放缩量、周均线偏离度、指数涨跌，判断增量资金还是存量拥挤。",
        "MA5情绪：说明涨家数MA5所在波峰/波谷/震荡区间；比较过去5日，推演未来5日MA5更可能拐头向上还是向下。",
        "市场风格：判断强度集中在大成交趋势、情绪连板、低位切换、高位抱团分化，还是防御/避险。",
        "申万一级映射：列出容量前三申万一级及占比、成交占比环比；说明目标个股所属申万一级，以及其题材如何映射到这些一级行业。",
        "题材映射：列出目标个股隶属题材；判断是否属于双红题材、涨停热度题材、新高方向，若不是也要说明。",
        "双红演变：说明相关双红题材是初次出现、连续加强、主升扩散、分歧衰减、二阶段回流还是高位兑现。",
        "同行/同题材新高：说明同申万一级、同题材的新高数量和代表个股，并判断它们与目标公司是同链核心、容量核心、补涨、替代还是二阶暴露。",
        "涨停结构：说明所属申万一级涨停多不多，涨停个股分别落在哪些细分题材，判断是板块主线扩散还是局部脉冲。",
        "个股流动性与相对强度：说明成交额、成交排名、加权涨幅、3/5/10日强度、新高/涨停状态，以及相对板块是领先、同步、补涨还是掉队。",
        "个股逻辑生命周期：说明该股从逻辑发现、预期发酵、加速确认、分歧承接、二阶段回流到兑现退潮中的哪一段；给出它当前更像启动核心、趋势延续、分歧承接、低位补涨、高低切承接还是高位兑现。",
    ]


def _daily_agent_reasoning() -> list[str]:
    return [
        "逻辑-盘面匹配：先判断当前对象更像 old_logic_wakeup（旧逻辑被盘面重新唤醒）、new_logic_candidate（盘面先动但知识沉淀不足）、data_gap（缺概念/公司暴露/证据/来源回溯）还是 noise_or_unconfirmed（噪音或占位题材）。",
        "生命周期判断：用 新出现 → 旧逻辑唤醒 → 升温验证 → 加速定价 → 高位分歧 → 衰退观察 → 证伪退出 这条链定位；理由必须来自连续出现天数、priority变化、强势股变化、触发信号变化、旧材料命中、证据裁判状态。",
        "盘面验证判断：用 强验证 / 中等验证 / 弱验证 / 无盘面验证 表达 L4 强度；核心观察 priority、触发信号数、涨停数、新高数、强势股数、板块涨幅、边际量、成交额、是否容量前三。",
        "量化强弱要服务于推理：加权涨幅、成交额、新高、涨停、3/5/10日相对强度、分歧日抗跌，不是罗列数据，而是判断它是领先核心、同步确认、后排补涨、二阶段回流还是高位兑现。",
        "研究队列落点：如果是旧逻辑唤醒，优先检查 L2/L3 缺口；如果是新逻辑候选，先定题材边界和产业链暴露；如果盘面强但证据弱，结论要写成预期交易而非事实验证；如果事实强但盘面弱，要拆成研究保留、情绪降温。",
        "历史有效性意识：若已有多窗口成绩单，要看 3/5/7/10 日收益、达峰天数、峰后回撤、相对基准超额和半衰期；若证据中没有这些数据，要明确“本轮未取到历史有效性数据”，不能假装判断过。",
    ]


def _stock_analysis_entrypoints() -> list[str]:
    return [
        "公司本体：先回答它到底是什么公司，主营、产品、客户、收入结构、毛利率、产业链上下游位置和报表传导是什么，禁止先贴题材标签。",
        "产业链暴露：判断它暴露在需求增长、涨价、国产替代、扩产、缺货、技术路线变化中的哪一类；是一阶受益还是二阶/三阶受益，是否是真瓶颈或只是题材标签。",
        "证据层：把逻辑拆成 L1观点叙事、L2公司基本面、L3公告/订单/认证/量产/客户验证、L4盘面强度；明确是预期交易还是事实验证。",
        "高位主线反证：若属于 AI硬件/CPO/PCB/半导体/存储等高位主线，必须问产业正确是否已被价格反映，新增利润预期和事件锚点是否还没兑现。",
        "大盘与流动性：先看大盘阶段、成交额、20日量能回归、指数/周均线偏离、涨家数、涨停跌停和涨家数MA5，判断市场有没有支持扩散的水位。",
        "市场风格：判断资金偏好是大成交趋势、情绪连板、低位切换、高位抱团、防御避险、小票修复还是容量核心虹吸。",
        "行业容量：看容量前三申万一级、目标所属申万一级、成交占比环比、所属行业涨停结构，判断它是否站在资金主战场。",
        "题材结构：看目标所属题材、是否双红、双红演变、新高集群、涨停热度、同题材前排是谁，判断方向强弱和目标股是否核心表达。",
        "个股相对强度：看成交额、流动性、加权涨幅、3/5/10日相对强度、新高/涨停、分歧日抗跌、回流日领先和强势股榜位置。",
        "逻辑生命周期：用四问判断它是新出现、旧逻辑唤醒、升温验证、加速定价、高位分歧、衰退观察还是证伪退出。",
        "二阶导发散：从目标股反推出真正瓶颈和更优表达，比较上游材料、设备、零部件、封测、测试、洁净室、供电、散热等环节的证据硬度和盘面强度。",
        "条件化结论：不要只给涨跌，必须给当前身份、置信度、升级条件、降级/证伪条件和后续跟踪指标。",
    ]


def _logic_lifecycle_questions() -> list[str]:
    return [
        "第一问：这条逻辑处在生命周期哪一段：新出现 / 旧逻辑唤醒 / 升温验证 / 加速定价 / 高位分歧 / 衰退观察 / 证伪退出；必须给理由。",
        "第二问：状态相比昨天或过去 N 天发生了什么变化：证据层是否升级，盘面强度是否增强，强势股是否扩散，叙事是否升温，旧材料是否被重新验证。",
        "第三问：这条逻辑有没有真正产生过市场价值：看 CAR、相对强度、成交额边际、强势股扩散、涨停扩散、回撤与半衰期；没有数据要明确缺口，不能用故事好听代替市场价值。",
        "第四问：后续怎么升级、降级或证伪：什么信号让它进入加速定价，什么信号让它降级为衰退观察，什么信号触发证伪退出。",
    ]


def _pre_output_quality_gate() -> list[str]:
    return [
        "覆盖率门槛：公司本体、产业链暴露、证据层、高位主线反证、大盘流动性、市场风格、行业容量、题材结构、个股相对强度、生命周期、二阶导、条件化结论至少都要被思考；缺数据要写明缺口。",
        "第一性原理门槛：不能只贴标签或罗列数据，必须解释资金为什么选择/不选择它，产业事实如何传导到收入、毛利率、订单、产能或估值预期。",
        "盘面融合门槛：大盘阶段、成交额/20日量能、涨家数/MA5、容量前三、双红/新高/涨停、个股相对强度要形成一条推理链；不能孤立看个股。",
        "证据分层门槛：明确 L1观点、L2基本面、L3订单/认证/量产/客户验证/反证、L4盘面强度；不得把观点研报或题材标签当成硬事实。",
        "生命周期门槛：必须回答阶段、相对过去N天变化、是否产生过市场价值、升级/降级/证伪条件；缺 CAR/半衰期/回撤数据时要说明未取到。",
        "二阶导门槛：必须从目标股反推真实产业瓶颈和更优表达，至少比较一阶受益、二阶暴露、替代标的或同链更硬证据方向。",
        "可读性门槛：最终回答要自然成文，不按清单机械分段；但关键结论、反证、条件和跟踪指标要清楚。",
    ]


def _shadow_user_critic() -> list[str]:
    return [
        "你是不是又在套模板，而没有从第一性原理解释为什么资金会买/卖、为什么这条逻辑能或不能继续定价？",
        "你是不是只看了个股，没有把它放到大盘阶段、整体情绪、板块容量、双红题材、同题材强势股和平行题材竞争里？",
        "你说它受益，证据够硬吗？有没有订单、认证、量产、客户验证、收入占比、毛利率，还是只有 L1 观点和题材标签？",
        "它是不是这条产业链的最优表达？如果不是，市场更可能奖励谁、抛弃谁、犹豫谁？",
        "这条逻辑生命周期到底在哪里？是新出现、旧逻辑唤醒、升温验证、加速定价、高位分歧、衰退观察，还是已经被反证降级？",
        "有没有把上涨空间和逻辑生命周期分开？上涨不重要，重要的是预期是否还在升级、盘面是否继续验证、证据是否能续命。",
        "有没有主动寻找反证：公司否认、收入占比很低、仍在研发/送样、客户未确认、扩产但需求不足、涨过后强度掉队？",
        "有没有二阶导到更好的投资机会或研究队列，而不是停留在目标公司的单点故事？",
    ]


def _narrative_composer() -> list[str]:
    return [
        "先在内部写出核心矛盾句：这家公司真实业务是什么，市场正在交易什么预期，最大的证据缺口或反证是什么。",
        "视角不是小标题：公司本体、收入结构、客户证据、盘面、生命周期、二阶导和反证，都必须服务核心矛盾句，而不是分块填空。",
        "每段都要回答：这个事实改变了我对空间、生命周期、资金选择或证据硬度的什么判断；不能只罗列事实。",
        "用资金选择串联全文：解释资金为什么选择/放弃/犹豫，哪些前排或替代表达更受奖励，目标股处于领先、同步、补涨、分歧承接还是掉队。",
        "输出时禁止按“公司本体/盘面/二阶导/反证”机械分标题；可以自然分段，但段落之间必须有因果推进。",
    ]


def _market_reverse_reasoning() -> list[str]:
    return [
        "先从第一性原理解释数据：资金推动价格、量能决定周期；成交额/20日量能回归决定有没有新增资金，涨家数MA5和涨跌停决定赚钱效应，容量前三和成交占比环比决定资金主战场，双红/新高/涨停决定板块是否被持续重定价。",
        "每个盘面指标都要做正反两面推导：它支持什么结论，也否定什么结论。例如板块 priority 上升但目标股不进强势股榜，说明市场在交易该题材，但没有把目标股选为前排核心。",
        "必须解释“强板块、弱个股”的含义：同题材新高/涨停/加权强度集中在其他公司时，目标股更可能是旧逻辑跟随、分歧承接或后排补涨，而不是主升核心；除非后续出现相对强度反转。",
        "必须解释“个股反弹、板块缩量/情绪回落”的含义：这更可能是分歧后的技术修复或存量资金承接，不等同于新一轮主升；只有放量、扩散、新高和涨停结构重新同步，才能升级判断。",
        "必须把大盘阶段和个股生命周期连接起来：顶部横盘/主升后分歧阶段里，前期涨过且证据未升级的个股更容易被兑现；底部修复/初步走强阶段里，低位新启动和率先新高的个股优先级更高。",
        "结论必须回答市场正在奖励谁、抛弃谁、犹豫谁：奖励的是容量核心/新高核心/涨停发动机，抛弃的是涨过但证据未升级且相对强度掉队的票，犹豫的是基本面有逻辑但 L4 未重新确认的票。",
    ]


def _sellside_winrate_reasoning(text: str) -> list[str]:
    if not _has_any(
        text,
        (
            "卖方",
            "晚间研报",
            "晚卖研汇",
            "机构胜率",
            "胜率榜",
            "覆盖密度",
            "T+5",
            "T+10",
            "opinion-store",
            "opinion_cross",
        ),
    ):
        return []
    return [
        "第一性原理：卖方观点本质是信息扩散节点；机构历史胜率只调节信息权重，不等于结论，更不能替代盘面和证据验证。",
        "先拆窗口有效性：T+5 强但 T+10 衰减，通常是短催化/情绪点火；T+5 和 T+10 都强，才更像可延续的产业趋势或中短期重估。",
        "再叠覆盖密度：高胜率机构推低覆盖方向，可能是新 alpha 入口；高胜率机构推高覆盖扎堆方向，更多是共识确认甚至兑现风险。",
        "证据硬度要分层：央视/公告/订单/涨价函/交期/客户认证/扩产属于更硬信号；框架性周观点、纯估值修复、泛主线复述只能当 L1/L4 线索。",
        "发散时沿产业瓶颈走，不沿研报标题走：从涨价/缺货/交期/扩产/客户认证反推最受约束的设备、材料、零部件、封测、供电或上游耗材环节。",
        "最终必须落回盘面：方向是否进入双红、容量行业、新高集群、涨停热度或强势股榜；若方向强但标的不强，要判断是后排跟随、旧逻辑承接还是尚未被市场选择。",
        "输出应分成优先发散、只作确认、反向谨慎三类：优先发散=高胜率+低覆盖+硬事实+盘面未充分反映；只作确认=逻辑真但已拥挤；反向谨慎=卖方密集唱多且盘面已兑现。",
    ]


def _high_position_mainline_reasoning(text: str) -> list[str]:
    if not _has_any(
        text,
        (
            "高位",
            "主线",
            "AI",
            "CPO",
            "PCB",
            "半导体",
            "存储",
            "光模块",
            "缩量",
            "拥挤",
            "兑现",
            "分歧",
            "玻璃桥",
            "长鑫",
            "海力士",
            "事件锚点",
        ),
    ):
        return []
    return [
        "第一性原理：高位主线继续上涨，不取决于长期产业确定性本身，而取决于边际预期、流动性、证据硬度和位置约束是否还能同时改善。",
        "外部约束不是泛宏观复述：只讨论会不会改变风险偏好、成交额、估值倍数和高估值题材定价的变量；已被市场定价的冲击要考虑边际递减或靴子落地。",
        "拆主线基本面时先问预期差：当前价格是否已经反映产业确定性，后续新增预期来自收入、毛利率、订单、涨价、产能、客户验证还是纯估值叙事。",
        "新概念必须做产业瑕疵审查：它处于实验室、样品、小批量还是量产；替代什么环节；是否解决真实瓶颈；是否只替代一部分；时间上能否赶上主线出货节奏。",
        "事件锚点要放进生命周期：区分发酵窗口、定价窗口、兑现窗口和二次验证窗口；事件越近越要问是继续验证，还是预期兑现。",
        "中观资金关系必须反向推导：总量不扩张时，题材之间是竞争关系；主线成交占比过高意味着拥挤，方向上涨可能来自旧主线资金切换，不等于增量资金健康扩散。",
        "板块阶段不要二元看多看空：顺势、主升后第一次分歧、分歧后的强轮动、弱轮动、日线做顶、高位僵持、缩量兑现和退潮是不同状态，不能混成一个涨跌结论。",
        "回答要区分产业变化、盘面资金切换、机构风格漂移、事件兑现和情绪周期；不要把所有涨跌都解释成基本面变化。",
    ]


def _has_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle.lower() in text.lower() for needle in needles)
