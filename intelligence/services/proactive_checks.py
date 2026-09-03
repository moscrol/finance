"""本轮主动检查：漏检闸，不是 KOL 观点层。

用户要的「主动服务」= 本轮已经在下冰点 / 新主线 / 主升这类结论时，
把该核对的结构条件列为强制检查，并写明须核验 / INSUFFICIENT。
HIT / MISS 由本轮证据对照后填写；本模块先做触发与证据齐备性，
不在这里用未回测数字阈值做自动买卖判断。

与 ``reading_baseline`` 的分工：

- 判读基线：全局读法，默认几乎每轮都在；
- 本模块：被触发才出现的本轮检查清单，更具体，带三种结果口径。

不把 ``sptfei.json`` 整份打进中立，不改 ``perspective_mode`` 默认值。
把 SPT 升格为默认主视角是另一步——会移动全部中立基线读数，本模块只是过渡：
复盘数据先按他的读法做漏检，口吻与倾向仍要显式选视角。

开关 ``FINANCE_PROACTIVE_CHECKS``（0/false/no/off 整块关闭），与
``FINANCE_READING_BASELINE`` 正交，便于单独 A/B。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

ENV_FLAG = "FINANCE_PROACTIVE_CHECKS"
_FALSEY = {"0", "false", "no", "off"}

#: 复盘 / 阶段题：即使用户没说出「冰点」「主升」，也常在下这类结论。
_STAGE_QUESTION_TYPES = frozenset(
    {
        "market_forecast",
        "dated_market_review",
        "market_watch",
        "market_review",
    }
)

_CLAIM_TERMS = (
    "冰点",
    "新主线",
    "主升",
    "断代",
    "伴身",
    "旗型",
    "一体两面",
    "主线",
    "承接",
    "回流",
    "怎么看",
    "复盘",
)


def enabled(env: dict[str, str] | None = None) -> bool:
    source = env if env is not None else os.environ
    raw = str(source.get(ENV_FLAG, "") or "").strip().casefold()
    return raw not in _FALSEY


@dataclass(frozen=True)
class ProactiveCheck:
    """一条本轮漏检。``source`` 留血缘，出问题能追到哪次蒸馏 / 哪条画像。"""

    id: str
    title: str
    rule: str
    required_kinds: tuple[str, ...]
    source: str
    trigger_terms: tuple[str, ...] = ()


@dataclass(frozen=True)
class CheckResult:
    check: ProactiveCheck
    status: str
    missing_kinds: tuple[str, ...]


@dataclass(frozen=True)
class CheckReport:
    triggered: bool
    items: tuple[CheckResult, ...]


CHECKS: tuple[ProactiveCheck, ...] = (
    ProactiveCheck(
        id="SPT-P12",
        title="冰点共振",
        rule=(
            "把某日定为市场冰点起始日，必须多指数（尤其本轮杀跌元凶）同日见底。"
            "单指数冰点不得升格为全市场冰点。"
        ),
        required_kinds=("index_breadth",),
        source="sptfei 2026.34 量能状态机扩写；升格前仅作本轮检查，不进 reading_baseline",
        trigger_terms=("冰点", "极小量", "见底"),
    ),
    ProactiveCheck(
        id="SPT-P13",
        title="断代日抢资金",
        rule=(
            "临突破或部分放量不足以确认新主线；须在新老主线同日放量的断代日"
            "仍能主动抢到资金，而不是只当老主线对立面。"
        ),
        required_kinds=("volume_structure", "sector_flow"),
        source="sptfei 2026.34 推理模板「冰点共振再断代再抢资金」",
        trigger_terms=("新主线", "主线", "断代", "临突破"),
    ),
    ProactiveCheck(
        id="SPT-P14",
        title="旗型一体两面",
        rule=(
            "共建主线或旗型蓄能阶段，单次高潮不得升格为连续主升；"
            "须板块与指数一体两面放量才能承认加速。"
        ),
        required_kinds=("volume_structure", "index_level"),
        source="sptfei 2026.34 推理模板「旗型蓄能一体两面」",
        trigger_terms=("主升", "旗型", "一体两面", "高潮", "主线"),
    ),
    ProactiveCheck(
        id="SPT-P15",
        title="伴身分轨",
        rule=(
            "底部 N 型有强度但未临突破的板块，只读作伴身轮动或高潮后承接，"
            "不得断言为新主线。"
        ),
        required_kinds=("sector_structure",),
        source="sptfei 2026.34 推理模板「伴身分轨与宽度夺价」",
        trigger_terms=("伴身", "承接", "新主线", "主线", "N字", "N 字"),
    ),
)


def triggered(query: str, question_type: str = "") -> bool:
    if str(question_type or "").strip() in _STAGE_QUESTION_TYPES:
        return True
    folded = str(query or "")
    return any(term in folded for term in _CLAIM_TERMS)


def _select_checks(query: str, question_type: str) -> tuple[ProactiveCheck, ...]:
    """阶段题跑全集；其它题只跑被触发词点名的检查。"""

    if str(question_type or "").strip() in _STAGE_QUESTION_TYPES:
        return CHECKS
    folded = str(query or "")
    picked = tuple(
        check
        for check in CHECKS
        if any(term in folded for term in check.trigger_terms)
    )
    return picked or CHECKS if triggered(query, question_type) else ()


def evaluate(
    query: str,
    *,
    question_type: str = "",
    present_kinds: tuple[str, ...] | None = None,
    env: dict[str, str] | None = None,
) -> CheckReport:
    if not enabled(env) or not triggered(query, question_type):
        return CheckReport(triggered=False, items=())

    present = None if present_kinds is None else frozenset(present_kinds)
    items: list[CheckResult] = []
    for check in _select_checks(query, question_type):
        if present is None:
            items.append(CheckResult(check=check, status="open", missing_kinds=()))
            continue
        missing = tuple(kind for kind in check.required_kinds if kind not in present)
        items.append(
            CheckResult(
                check=check,
                status="insufficient" if missing else "open",
                missing_kinds=missing,
            )
        )
    return CheckReport(triggered=True, items=tuple(items))


def render(report: CheckReport) -> str:
    if not report.triggered or not report.items:
        return ""
    lines = [
        "以下是本轮漏检闸，不是 KOL 观点或口吻。"
        "每条必须给出 HIT / MISS / INSUFFICIENT："
        "HIT=本轮证据满足该条全部结构条件；"
        "MISS=证据在场但条件不成立，不得升格结论；"
        "INSUFFICIENT=缺该条所需证据种类，必须在回答开头声明，"
        "不得用次级证据冒充。"
    ]
    for item in report.items:
        if item.status == "insufficient":
            flag = "INSUFFICIENT：缺 " + "、".join(item.missing_kinds)
        else:
            flag = "须核验"
        lines.append(f"- [{item.check.id}] {item.check.title}（{flag}）：{item.check.rule}")
    return "\n".join(lines)


def guidance(
    query: str,
    *,
    question_type: str = "",
    present_kinds: tuple[str, ...] | None = None,
    env: dict[str, str] | None = None,
) -> str:
    return render(
        evaluate(
            query,
            question_type=question_type,
            present_kinds=present_kinds,
            env=env,
        )
    )


PROMPT_HEADING = "本轮主动检查（漏检闸，强制；不是 KOL 观点）"


def as_prompt_section(body: str) -> str:
    """给已渲染的清单加上统一标题。空串保持空，避免旧调用方无故变长。"""

    text = str(body or "").strip()
    if not text:
        return ""
    if text.startswith("##"):
        return text
    return (
        f"## {PROMPT_HEADING}\n"
        "用户没有点名这些检查，但本轮结论若涉及冰点 / 新主线 / 主升，"
        "必须逐条给出 HIT / MISS / INSUFFICIENT，不得跳过或改写成买卖建议。\n"
        f"{text}"
    )


def prompt_section(
    query: str,
    *,
    question_type: str = "",
    present_kinds: tuple[str, ...] | None = None,
    env: dict[str, str] | None = None,
) -> str:
    """带标题的整段，给复盘专线 / 工作台契约复用，避免各处各写一套标签。"""

    return as_prompt_section(
        guidance(
            query,
            question_type=question_type,
            present_kinds=present_kinds,
            env=env,
        )
    )
