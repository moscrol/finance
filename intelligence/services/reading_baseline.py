"""判读基线：专家 knowhow 里「怎么读数据」那一半，默认生效。

与 perspective_lab 的分工（2026-08-19 用户对齐）：

- **本模块 = 判读方法**：这份数据该怎么读。关掉它，agent 退化成查数机器人，
  所以它是领域基线——默认生效、不需要用户显式选视角。
- **perspective_lab = 判断倾向**：怎么下注（不接飞刀、不追第一波…）。关掉只是
  少一个观点，所以留在可开关、可并列、可归因的 persona 层。

规则来源与裁定见 ``docs/learning/reading-rules-inventory-2026-08-19.md``：从
SPT-Molmansk 与风远两份画像里切出，用户 2026-08-19 逐组勾选确认。本模块只装
**批一**（无数据依赖的全局元规则）；批二/批三按该文件 §7 落到具体数据块。

三条设计约束（同一文件 §7「三批共同要求」）：

1. 每条规则带 id，答案里引用得到，出问题能定位到是哪条判读在起作用；
2. 只装**结构性判读**，不装未回测的数字阈值——数字走 ``evolution/`` 回测队列，
   标定后才允许升格（用户自评：外部框架「结构可信，单点阈值没有回测支撑」）；
3. 留一个 env 总开关做 A/B——没有它就永远无法回答「内置判读到底有没有让答案变好」。

⚠ 顺序不是随意的：``FY-A10``（框架自身可被证伪）排第一是刻意的。它是唯一一条
**约束其他内置规则**的规则；先装自限阀再装规则，反过来会有一段时间里所有判读
不带失效条件地生效。
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


#: 批一：无数据依赖的全局元规则。新增前先读 inventory §7 的分批依据。
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


#: 挂具体数据块的规则：贴着数据走，检索到什么才带什么规则——不占常驻预算，
#: 也不会张冠李戴（问财务时不会带盘面判读）。单一真本源：三个类比块共用这一份，
#: 不各抄一句，否则改一处漏两处。
_BLOCK_RULES: dict[str, ReadingRule] = {
    "SPT-A11": ReadingRule(
        id="SPT-A11",
        title="历史同构类比",
        rule=(
            "类比的是结构与节点（所处阶段、量价形态、演化位置），不是标的本身；"
            "不得因历史窗口相似就推断本次会有相同结果"
        ),
        source="SPT 画像 reasoning_patterns",
    ),
}


def enabled(env: dict[str, str] | None = None) -> bool:
    """总开关。缺省开启；显式设成 0/false/no/off 才关。"""

    raw = (env or os.environ).get(ENV_FLAG)
    if raw is None:
        return True
    return str(raw).strip().lower() not in _FALSEY


def baseline_rules(env: dict[str, str] | None = None) -> tuple[ReadingRule, ...]:
    """当前生效的判读规则；关掉开关时返回空元组。"""

    return _BATCH1_RULES if enabled(env) else ()


def baseline_guidance(env: dict[str, str] | None = None) -> str:
    """渲染成注入用文本；关掉开关时返回空串（调用方据此整段不注入）。"""

    rules = baseline_rules(env)
    if not rules:
        return ""
    return "\n".join(f"- [{r.id}] {r.title}：{r.rule}" for r in rules)


def block_rule_line(rule_id: str, env: dict[str, str] | None = None) -> str:
    """渲染成数据块内的一行（含前导 ``- 判读：``）；开关关闭或 id 未登记返回空串。

    调用方模式固定为「非空才 append」，这样关掉开关时块内容逐字节回到未内置状态。
    """

    if not enabled(env):
        return ""
    rule = _BLOCK_RULES.get(rule_id)
    if rule is None:
        return ""
    return f"- 判读[{rule.id}]：{rule.rule}。"
