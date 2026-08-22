"""判读基线：专家 knowhow 里「怎么读数据」那一半，默认生效。

与 perspective_lab 的分工（2026-08-19 用户对齐）：

- **本模块 = 判读方法**：这份数据该怎么读。关掉它，agent 退化成查数机器人，
  所以它是领域基线——默认生效、不需要用户显式选视角。
- **perspective_lab = 判断倾向**：怎么下注（不接飞刀、不追第一波…）。关掉只是
  少一个观点，所以留在可开关、可并列、可归因的 persona 层。

规则来源与裁定见 ``docs/learning/reading-rules-inventory-2026-08-19.md``：从
SPT-Molmansk 与风远两份画像里切出，用户 2026-08-19 逐组勾选确认，共 25 条 A 类。
本模块按数据依赖分三档存放：

- ``_BATCH1_RULES``：无数据依赖的全局元规则，进两个引擎的系统提示词；
- ``_BLOCK_RULES``：贴具体数据块，检索到哪块才带哪条；
- ``_PENDING_RULES``：已裁定采纳但本地缺数据源，**不注入**，与缺口 id 同处存放。

三条设计约束（同一文件 §7「三批共同要求」）：

1. 每条规则带 id，答案里引用得到，出问题能定位到是哪条判读在起作用；
2. 只装**结构性判读**，不装未回测的数字阈值——数字走 ``evolution/`` 回测队列，
   标定后才允许升格（用户自评：外部框架「结构可信，单点阈值没有回测支撑」）；
3. 留一个 env 总开关做 A/B——没有它就永远无法回答「内置判读到底有没有让答案变好」。

⚠ 顺序不是随意的：``FY-A10``（框架自身可被证伪）排第一是刻意的。它是唯一一条
**约束其他内置规则**的规则；先装自限阀再装规则，反过来会有一段时间里所有判读
不带失效条件地生效。

⚠⚠ **与 ``intelligence/foresight_methodology.md`` 有已知重叠**（2026-08-19 发现）。

那份 76 行的「思考宪法」只注入 foresight（盘面主动发问）一条路，本模块只注入
问答两条路（ask 合成 / continuous episode）。**同一套判读此前只覆盖了发问路径，
问答路径是裸的**——本模块补的是这个缺口，代价是七条全局规则里有五条与那份文件
语义重合（措辞不同，个别地方那边写得更全，如六步复盘路径 vs 本模块 CR-01 的三步）。

没有合并成一份，是因为两者形态不同且都有存在理由：那份是散文体、含大量 foresight
专用内容（发问落点、认同度阶梯），整份塞进问答 prompt 会稀释并浪费预算；本模块是
结构化、带 id、可 A/B、有测试守着。**但重叠必须登记**——见 ``_METHODOLOGY_OVERLAP``
与 ``test_reading_baseline.py`` 的漂移门禁：那边改了措辞或删了条目，这边测试会红，
强制回来对账。这条纪律的出处是本仓 CLAUDE.md「同一份清单存两处必漂，且漂的时候
没人知道」。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

#: env 开关。设为 0/false/no/off 时整块不注入（模型输入逐字节回到未内置状态），
#: 用于度量「加了判读基线，答案有没有变好」。缺省视为开启。
ENV_FLAG = "FINANCE_READING_BASELINE"

_FALSEY = {"0", "false", "no", "off"}


@dataclass(frozen=True)
class ReadingRule:
    """一条判读规则。``source`` 保留血缘——出问题时能查到它是哪一档证据进来的。"""

    id: str
    title: str
    rule: str
    source: str


#: 批一：无数据依赖的全局元规则，进两个引擎的系统提示词。
_BATCH1_RULES: tuple[ReadingRule, ...] = (
    ReadingRule(
        id="FY-A10",
        title="框架自身可被证伪",
        rule=(
            "不把单次观察写成定律。使用下列任何一条判读规则时，若本轮证据与规则冲突，"
            "以证据为准并明说冲突，不得机械套用；规则被证伪时说明是哪一条、因何失效。"
        ),
        source="风远画像 anti_patterns；与 CLAUDE.md「跑马策略处于假设验证阶段」同构",
    ),
    ReadingRule(
        id="FY-A09",
        title="反顺从检查",
        rule=(
            "不因为已经给出过某个方向的判断，就在后续论证里调低它的风险权重；"
            "对自己上文的结论做一次反向检查再收尾。"
        ),
        source="风远画像 falsification_style",
    ),
    ReadingRule(
        id="CR-01",
        title="先阶段，再板块，最后个股",
        rule=(
            "任何板块或个股判断，先确认市场处于哪一阶段（成交额中枢、指数箱体位置），"
            "再判该板块在主线周期的哪一段，最后才落到个股。不脱离阶段断言新主线。"
        ),
        source="SPT「先量能后板块再个股」× 风远「先定周期位置再谈标的」（两人共识）",
    ),
    ReadingRule(
        id="CR-02",
        title="证据分层顺序",
        rule=(
            "证据硬度自高至低：盘面量价资金结构 > 涨价/订单/产能等产业硬事实 > "
            "第三方数据与金融验证链 > 卖方观点 > 小作文传闻。"
            "低层级证据不得推翻高层级；只有低层级证据时必须说明结论强度受限。"
        ),
        source="SPT × 风远 evidence_hierarchy（两人顺序几乎一致）",
    ),
    ReadingRule(
        id="CR-03",
        title="结论条件化并自带证伪",
        rule=(
            "给方向判断时同时给出：需满足哪些量价确认条件才升级、当前满足几条、"
            "出现哪些信号即降级或放弃。不给无条件结论。"
        ),
        source="SPT「推演剧本化」× 风远「条件化买点（列出当前满足几条）」（两人共识）",
    ),
    ReadingRule(
        id="CR-04",
        title="组合信号优先于单点",
        rule=(
            "不用单一指标定性。按层级或多条件组合判断，并说明各条件当前状态；"
            "缺条件时说明缺哪一条，不得用其他条件补位凑成结论。"
        ),
        source="SPT「板块回流三件套」× 风远「三级信号体系按层级而非单点」（两人共识）",
    ),
    ReadingRule(
        id="SPT-A10",
        title="基本面定地图，交易面定买卖",
        rule=(
            "基本面结论（赛道容量、渗透率位置、验证链）只用于确定方向地图；"
            "买卖时点与强弱判断必须由量价资金结构确认。逻辑再好也不替代盘面确认。"
        ),
        source="SPT 画像 reasoning_patterns",
    ),
)


#: 与 ``intelligence/foresight_methodology.md`` 的重叠登记：``规则 id -> 那份文件里
#: 的锚点原文``。锚点必须是文件里逐字存在的短语——测试据此反查，那边改措辞或删条目
#: 就会红，强制两边回来对账。值为 ``None`` 表示本模块独有、那份文件没有。
#:
#: 新增全局规则时**必须**在这里登记（登记 None 也算登记），否则守门测试不通过。
_METHODOLOGY_OVERLAP: dict[str, str | None] = {
    "FY-A10": "禁止把单次观察写成定律或硬规则",
    "FY-A09": None,  # 反顺从检查：那份文件没有等价条目
    "CR-01": "标准复盘路径不可跳步",
    "CR-02": "证据硬度分层",
    "CR-03": "可证伪：点明领先指标",
    "CR-04": "累积成台账，单点是噪音",
    "SPT-A10": None,  # 基本面定地图/交易面定买卖：那份文件未拆出这一层
}

#: 那份方法论文件的仓内路径（漂移门禁与文档交叉引用共用）。
METHODOLOGY_DOC = "intelligence/foresight_methodology.md"


_ANALOG_RULE = ReadingRule(
    id="SPT-A11",
    title="历史同构类比",
    rule=(
        "类比的是结构与节点（所处阶段、量价形态、演化位置），不是标的本身；"
        "不得因历史窗口相似就推断本次会有相同结果"
    ),
    source="SPT 画像 reasoning_patterns",
)


#: 批二：挂具体数据块的规则。贴着数据走，检索到什么才带什么规则——不占常驻预算，
#: 也不会张冠李戴（问财务时不会带盘面判读）。按**块**索引而不是按规则索引：
#: 一个块可以挂多条，同一条也可以挂多个块（如三个类比块共用 SPT-A11），
#: 但规则文本只有这一份，不各抄一句，否则改一处漏两处。
#:
#: 键用逻辑块名而非裸 D 编号：``[D4]`` 由两个物理块共用（ask_blocks 的主线题材
#: 结构、market_timeseries 的双红快照，见 ask.py:1668-1673 是有意合并引用号），
#: 裸编号会让两个块拿到同一批规则。
_BLOCK_RULES: dict[str, tuple[ReadingRule, ...]] = {
    "D0": (
        ReadingRule(
            id="SPT-A01",
            title="量能状态机定阶段",
            rule=(
                "先用成交额中枢与指数箱体位置确定市场阶段；新主线只有在市场出现极小量"
                "（老主线筹码躺平）之后才可能发育，在此之前的板块启动不得断言为新主线"
            ),
            source="SPT 画像 market_lenses「量能状态机」+ anti_patterns 第 1 条",
        ),
        ReadingRule(
            id="FY-A02",
            title="出清形态两分",
            rule=(
                "区分 A 型出清（恐慌放量后 V 型回抽）与 B 型出清（买盘枯竭、缩量阴跌）；"
                "两种形态的买点条件完全不同，不得混用同一套判据"
            ),
            source="风远画像 market_lenses「出清形态判别」",
        ),
    ),
    "D1": (
        ReadingRule(
            id="FY-A08",
            title="纯叙事无业绩锚则出局",
            rule=(
                "纯叙事标的若无业绩锚、且估值锚定在极远期，在排序中直接出局，"
                "不进入横向比较，而不是排在末位"
            ),
            source="风远画像 risk_triggers",
        ),
        ReadingRule(
            id="FY-A03'",
            title="排序权重随场景变化",
            rule=(
                "排序维度的权重不是固定的，需随市场场景（恐慌反弹／主升／高位拥挤）"
                "调整并说明本轮按哪种场景取权；命中一票否决项的候选直接出局。"
                "本条只修饰既有排序口径，不替代它——已有 skill 口径（如 serenity-alpha "
                "的 12 项优先级与 4 条禁止）仍然优先适用"
            ),
            source=(
                "风远画像「五维排序」降解版。2026-08-19 与 serenity-alpha "
                "ranking-rubric 对表：整条内置会用 5 维稀释掉那 4 条硬禁止，"
                "故只取 serenity 没有的「场景调权重＋一票否决出局」"
            ),
        ),
    ),
    "D4_mainline": (
        ReadingRule(
            id="FY-A01",
            title="双锚模型",
            rule=(
                "方向锚（板块方向股）与高度锚（连板高标）同时恶化，且最后一龙冲高回落，"
                "才构成全板块逆转信号；单锚恶化不成立"
            ),
            source="风远画像 market_lenses「双锚模型」",
        ),
        ReadingRule(
            id="FY-A07",
            title="利多不涨＋连板高标＝踩踏前兆",
            rule="利多不涨与连板高标同时出现，读作板块抱团踩踏的前兆信号",
            source="风远画像 risk_triggers（识别部分；仓位动作归 persona 层）",
        ),
        ReadingRule(
            id="SPT-A07",
            title="题材容量决定持续性",
            rule=(
                "题材本质是故事，容量越大、可整合的要素越多则走得越远；"
                "宏大叙事必须能自上而下落到千亿／万亿级赛道且逻辑闭环，否则降权"
            ),
            source="SPT 画像 market_lenses「故事容量与定价权」+ anti_patterns 第 4 条",
        ),
        ReadingRule(
            id="SPT-A08",
            title="无全球定价权则降权",
            rule="缺乏全球定价权的事件驱动题材直接降权，筹码结构差时进一步降权",
            source="SPT 画像 market_lenses + anti_patterns 第 3 条",
        ),
        ReadingRule(
            id="SPT-A09",
            title="拥挤度反向使用",
            rule=(
                "卖方年度策略取交集当地图使用；一致性拥挤度作为反向指标——"
                "周末被一致吹爆的题材，周一大概率被兑现"
            ),
            source="SPT 画像 market_lenses + anti_patterns 第 2 条",
        ),
    ),
    "D6": (
        ReadingRule(
            id="SPT-A03",
            title="承接板块的识别形态",
            rule=(
                "老主线做完日线大型顶部后，承接板块的形态特征是：底部 N 字"
                "（否定日线下跌趋势）＋明显放量＋距上方压力位有较大距离"
            ),
            source="SPT 画像 opportunity_preferences 第 1 条（判读部分）",
        ),
    ),
    "D9": (
        ReadingRule(
            id="SPT-A04",
            title="异向性异常放量＝冷门轮动早期信号",
            rule=(
                "日线底部结构下的异向性异常放量，读作冷门方向轮动的**早期发现**信号，"
                "不是确认信号，不得据此直接给方向结论"
            ),
            source="SPT 画像 opportunity_preferences 第 8 条",
        ),
        ReadingRule(
            id="SPT-A05",
            title="顶部信号的两种形态",
            rule=(
                "见顶信号有二：量价不匹配的大阴量；单一行业短期净流入极端放量后的结构"
                "超级顶值——后者次日一旦量价不匹配即为分歧确认"
            ),
            source="SPT 画像 market_lenses + risk_triggers 第 4 条（识别部分）",
        ),
        ReadingRule(
            id="FY-A06",
            title="资金结构归因",
            rule=(
                "暴跌先归因再应对：区分基本面恶化与多类资金共振卖出"
                "（主动减仓／止损／割肉／ETF 赎回），不可一律读作基本面恶化"
            ),
            source="风远画像 reasoning_patterns",
        ),
    ),
    "D8": (_ANALOG_RULE,),
    "D10": (_ANALOG_RULE,),
    "D11": (_ANALOG_RULE,),
}


#: 批三：用户已裁定采纳、但**本地缺数据源**，因此不注入。
#:
#: 为什么写在代码里而不是只留在文档：规则和它卡住的数据缺口放在同一处可见，
#: 补完数据的人不需要回头重新推导「当初要补这个是为了支持哪条判读」。
#: ``requires`` 对应 docs/learning/reading-rules-inventory-2026-08-19.md §5 的缺口 id。
_PENDING_RULES: tuple[tuple[ReadingRule, str, str], ...] = (
    (
        ReadingRule(
            id="SPT-A02",
            title="板块回流的前置形态",
            rule=(
                "主线做完复杂顶后必有回流，但回流需先满足：大幅缩量＋回到支撑位＋"
                "30 分钟级别底背离；三者不全不算回流"
            ),
            source="SPT 画像 market_lenses + falsification_style 第 4 条",
        ),
        "G5",
        "主库无分钟级 K 线；fph2026 旁路库有 MACD 背离/缠论，需先确认可否跨库引用",
    ),
    (
        ReadingRule(
            id="SPT-A06",
            title="秒板未换手则后排无价值",
            rule=(
                "事件催化后核心标的若以秒板完成而未经充分换手，"
                "则后排标的不具备参与价值"
            ),
            source="SPT 画像 risk_triggers 第 3 条",
        ),
        "G1",
        "G1a：fact_theme_limit_stock_daily 有封板时间但无块输出；G1b：同表 open_times 恒 NULL（静默降级）",
    ),
    (
        ReadingRule(
            id="FY-A04",
            title="三级信号体系定周期位置",
            rule=(
                "按层级判断产业周期位置：领先指标（CapEx／交期／产能利用率）→"
                "确认指标（现货价／涨幅收敛）→滞后指标（合约价转负／库存）；"
                "不得用滞后指标做领先判断"
            ),
            source="风远画像 market_lenses + anti_patterns 第 3 条",
        ),
        "G3",
        "缺产业链价格（现货/合约）、交期、产能利用率的结构化来源",
    ),
    (
        ReadingRule(
            id="FY-A05",
            title="供给侧通胀四条件",
            rule=(
                "涨价确定性排序看四条件是否齐备：全球寡头格局＋零新增产能＋"
                "扩产周期长＋需求爆发 → 供给弹性趋近零的环节确定性最高"
            ),
            source="风远画像 market_lenses「供给侧通胀框架」",
        ),
        "G3",
        "同上：缺产能与扩产周期的结构化来源",
    ),
)


def enabled(env: dict[str, str] | None = None) -> bool:
    """总开关。缺省开启；显式设成 0/false/no/off 才关。"""

    raw = (env or os.environ).get(ENV_FLAG)
    if raw is None:
        return True
    return str(raw).strip().lower() not in _FALSEY


def baseline_rules(env: dict[str, str] | None = None) -> tuple[ReadingRule, ...]:
    """当前生效的全局判读规则；关掉开关时返回空元组。"""

    return _BATCH1_RULES if enabled(env) else ()


def baseline_guidance(env: dict[str, str] | None = None) -> str:
    """渲染成注入用文本；关掉开关时返回空串（调用方据此整段不注入）。"""

    rules = baseline_rules(env)
    if not rules:
        return ""
    return "\n".join(f"- [{r.id}] {r.title}：{r.rule}" for r in rules)


def methodology_overlap() -> dict[str, str | None]:
    """每条全局规则在 foresight 方法论文件里的锚点原文（``None``＝本模块独有）。"""

    return dict(_METHODOLOGY_OVERLAP)


def pending_rules() -> tuple[tuple[ReadingRule, str, str], ...]:
    """已裁定采纳但因数据缺口未激活的规则：``(规则, 缺口 id, 缺口说明)``。

    **永远不进 prompt**——注入它们等于让模型按它拿不到的数据去判读，
    会诱发编造。补齐对应缺口后，移进 ``_BLOCK_RULES`` 才算激活。
    """

    return _PENDING_RULES


def registered_blocks() -> tuple[str, ...]:
    """所有登记了判读规则的块 id。守门测试据此反查「登记了但没接线」。"""

    return tuple(_BLOCK_RULES)


def block_rules(block_id: str, env: dict[str, str] | None = None) -> tuple[ReadingRule, ...]:
    """某个数据块上挂的判读规则；开关关闭或块未登记时返回空元组。"""

    if not enabled(env):
        return ()
    return _BLOCK_RULES.get(block_id, ())


def block_rule_lines(block_id: str, env: dict[str, str] | None = None) -> list[str]:
    """渲染成数据块内的若干行；开关关闭或块未登记返回空列表。

    调用方模式固定为 ``lines.extend(block_rule_lines(...))``——空列表时块内容
    逐字节回到未内置状态，不需要调用方再写 if。
    """

    return [f"- 判读[{r.id}]：{r.rule}。" for r in block_rules(block_id, env)]
