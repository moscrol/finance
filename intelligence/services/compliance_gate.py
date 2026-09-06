"""合规硬门的词表与扫描器（roadmap G-12a；终局 spec §3.2「硬门」、§1.2 非目标）。

**一份词表，多个消费者**——不许各存一份：

- ``observation_script``：观察剧本登记前的硬门，命中即拒，返回可修正的错误码；
- ``scripts/validate_marketing_contracts.py``：对外物料禁词 lint；
- （待接）G-07 / G-08 的判官「不得出现概率数字」，接进来时直接用 ``scan(codes=...)``。

同一份词表存两处必漂，且漂的时候没人知道——本仓在 CLAUDE.md 的能力清单上真出过这个事故。

## 判据方向：宁可误拦，不可放行

硬门的错误是**可修正的提示**（spec §3.2 原文「必须返回可修正的错误提示」），
用户改一句话就能过；放行一条方向词进台账，则是产品定位红线破口。所以规则一律
fail closed：认不出来的形态（比如日期串像个股代码）按命中处理。

唯一的例外写在 ``_DIRECTION_TERMS`` 的注释里：会**在正常观察变量里高频出现**的词
（如「基金重仓股占比」的「重仓」）不进词表——那种误拦不是「改一句话」，是逼用户
放弃一个合法的观察变量。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# --------------------------------------------------------------------------- #
# 错误码：机器可判，写进产品错误提示与测试断言
# --------------------------------------------------------------------------- #
E_STOCK_SCOPE = "E_STOCK_SCOPE"  # 个股代码 / 个股名单
E_DIRECTION = "E_DIRECTION"  # 方向词
E_TIMING = "E_TIMING"  # 买卖时点
E_NEXT_DAY_DIRECTION = "E_NEXT_DAY_DIRECTION"  # 「第二天的方向」——产品语言禁用
E_TARGET_PRICE = "E_TARGET_PRICE"  # 目标价
E_PROBABILITY = "E_PROBABILITY"  # 概率承诺（带数字）
E_STRATEGY_WORD = "E_STRATEGY_WORD"  # 「策略」单独出现

# 观察剧本硬门用全套；对外物料 lint 只用后两条（前五条在营销文案里本来就不该出现，
# 但 products.yaml 已有自己的 PROHIBITED_PATTERNS，两边不重复造）。
OBSERVATION_SCRIPT_CODES = (
    E_STOCK_SCOPE,
    E_DIRECTION,
    E_TIMING,
    E_NEXT_DAY_DIRECTION,
    E_TARGET_PRICE,
    E_PROBABILITY,
)
MARKETING_CODES = (E_NEXT_DAY_DIRECTION, E_STRATEGY_WORD)

CODE_HINTS: dict[str, str] = {
    E_STOCK_SCOPE: "观察剧本只到指数 / 板块 / 题材，不到个股名单——把个股换成它所在的题材或板块",
    E_DIRECTION: "去掉方向词，改写成「要观察什么变量」——剧本回答「看什么」，不回答「做什么」",
    E_TIMING: "去掉买卖时点，改写成「什么条件出现算升级 / 降级」",
    E_NEXT_DAY_DIRECTION: "「第二天的方向」不是产品语言，改成「明天要看的变量」",
    E_TARGET_PRICE: "去掉目标价——剧本不承诺价位",
    E_PROBABILITY: "去掉概率数字——样本不足时产品显示「样本不足」，不出比率",
    E_STRATEGY_WORD: "「策略」不单独出现；内部模块名（策略一 / 策略进化）不受此限",
}


@dataclass(frozen=True)
class Hit:
    """一次命中。``context`` 给用户看「哪句话要改」，不只给一个词。"""

    code: str
    term: str
    start: int
    context: str

    def to_dict(self) -> dict[str, str | int]:
        return {"code": self.code, "term": self.term, "start": self.start, "context": self.context}

    @property
    def hint(self) -> str:
        return CODE_HINTS.get(self.code, "")


# --------------------------------------------------------------------------- #
# 词表
# --------------------------------------------------------------------------- #
# ⚠ 不收「重仓」：「基金重仓股占比」是合法观察变量，拦它等于逼用户放弃一个能看的量。
#   同理不收「持仓」「仓位」——它们描述的是市场状态，不是给用户的动作。
_DIRECTION_TERMS = (
    "看多", "看空", "做多", "做空", "买入", "卖出", "加仓", "减仓", "建仓", "清仓",
    "满仓", "空仓", "抄底", "逃顶", "上车", "止盈", "止损", "补仓", "接盘",
    "埋伏", "低吸", "追高", "打板", "梭哈", "割肉", "推荐买", "值得买",
)

_TIMING_TERMS = (
    "买点", "卖点", "买卖时点", "入场时机", "出场时机", "进场时机", "介入时点",
    "明天买", "明日买", "次日买", "第二天买", "开盘买", "收盘买", "尾盘买",
    "明天卖", "次日卖", "什么时候买", "什么时候卖",
)

_NEXT_DAY_DIRECTION_TERMS = ("第二天的方向", "明天的方向", "次日的方向")

# 「策略」的内部模块名白名单：这些是仓内既有的代码 / 技能名（strategy1-matrix、
# strategy-evolve），不是对外产品语言，不该被 lint 拦。
_STRATEGY_ALLOW = ("策略一", "策略1", "策略进化", "策略参数", "策略回测", "策略矩阵")

# 目标价：「目标价 / 目标位」直给，或「涨到 12 元」「看到 20 块」这类价位承诺。
_TARGET_PRICE_RE = re.compile(r"目标价|目标位|(?:涨|跌|看)到\s*\d+(?:\.\d+)?\s*[元块]")

# 概率：**带数字**才算承诺。裸「概率」允许出现（「本产品不给概率」要说得出口），
# 但「大概率 / 十有八九」这类无数字的口头承诺同样禁——它们在读者那里就是概率。
_PROBABILITY_RE = re.compile(
    r"大概率|小概率|十有八九|八九不离十"
    r"|(?:概率|胜率|把握|确定性)\s*[:：]?\s*(?:约|大约)?\s*\d+(?:\.\d+)?\s*[%％]?"
    r"|\d+(?:\.\d+)?\s*[%％]\s*(?:的)?(?:概率|胜率|把握)"
    r"|[一二三四五六七八九十\d]\s*成\s*(?:的)?(?:把握|概率)"
)

# 个股代码：``600519.SH`` 这类带后缀的，或裸六位且前缀落在 A 股实际号段。
#
# 两处防误伤，都是实测踩出来的：
# 1. 裸六位要求后面不接 ``.字母``——``883418.FP`` 是同花顺板块代码，落在北交所 88 号段里，
#    不加这条会把最常见的合法实体（板块）当个股拦掉；带 ``.SH/.SZ/.BJ`` 的走第一条分支。
# 2. 号段里**不收 88**：``881xxx`` / ``883xxx`` 是同花顺板块 / 概念代码，在本仓文本里比
#    88 段个股常见得多。88 段个股只在带交易所后缀时才认——宁可这一段严格些，
#    也不能让「板块名写成代码」的用户被硬门挡在门外。
# 3. 裸六位前后不接数字，避开 ``20260906`` 这类日期串。
_STOCK_CODE_RE = re.compile(
    r"\d{6}\.(?:SH|SZ|BJ|sh|sz|bj)"
    r"|(?<!\d)(?:00|30|60|68|43|83|87)\d{4}(?!\d)(?!\.[A-Za-z])"
)

_CONTEXT_PAD = 12


def _context(text: str, start: int, end: int) -> str:
    lo = max(0, start - _CONTEXT_PAD)
    hi = min(len(text), end + _CONTEXT_PAD)
    prefix = "…" if lo > 0 else ""
    suffix = "…" if hi < len(text) else ""
    return f"{prefix}{text[lo:hi]}{suffix}"


def _term_hits(text: str, terms: tuple[str, ...], code: str) -> list[Hit]:
    out: list[Hit] = []
    for term in terms:
        start = text.find(term)
        while start != -1:
            out.append(Hit(code, term, start, _context(text, start, start + len(term))))
            start = text.find(term, start + 1)
    return out


def _re_hits(text: str, pattern: re.Pattern[str], code: str) -> list[Hit]:
    return [
        Hit(code, m.group(0), m.start(), _context(text, m.start(), m.end()))
        for m in pattern.finditer(text)
    ]


def _strategy_hits(text: str) -> list[Hit]:
    """「策略」单独出现才算命中；命中点落在白名单词内部则放行。"""
    out: list[Hit] = []
    for m in re.finditer("策略", text):
        window = text[m.start() : m.start() + max(len(a) for a in _STRATEGY_ALLOW)]
        if any(window.startswith(allow) for allow in _STRATEGY_ALLOW):
            continue
        out.append(Hit(E_STRATEGY_WORD, "策略", m.start(), _context(text, m.start(), m.end())))
    return out


def scan(text: str, *, codes: tuple[str, ...] = OBSERVATION_SCRIPT_CODES) -> list[Hit]:
    """扫一段文本，返回命中列表（按位置升序、同位置去重）。

    ``codes`` 选规则子集：观察剧本硬门用 ``OBSERVATION_SCRIPT_CODES``，
    对外物料 lint 用 ``MARKETING_CODES``，判官接入时自己挑。

    同一位置可能被两条规则同时命中（「大概率」同时含「概率」形态），只保留先注册的
    那条——错误提示要能指导修改，堆同义错误码只会让人不知道改哪个。
    """
    if not text:
        return []
    hits: list[Hit] = []
    if E_STOCK_SCOPE in codes:
        hits += _re_hits(text, _STOCK_CODE_RE, E_STOCK_SCOPE)
    if E_NEXT_DAY_DIRECTION in codes:
        hits += _term_hits(text, _NEXT_DAY_DIRECTION_TERMS, E_NEXT_DAY_DIRECTION)
    if E_TIMING in codes:
        hits += _term_hits(text, _TIMING_TERMS, E_TIMING)
    if E_DIRECTION in codes:
        hits += _term_hits(text, _DIRECTION_TERMS, E_DIRECTION)
    if E_TARGET_PRICE in codes:
        hits += _re_hits(text, _TARGET_PRICE_RE, E_TARGET_PRICE)
    if E_PROBABILITY in codes:
        hits += _re_hits(text, _PROBABILITY_RE, E_PROBABILITY)
    if E_STRATEGY_WORD in codes:
        hits += _strategy_hits(text)

    seen: set[int] = set()
    out: list[Hit] = []
    for hit in hits:
        if hit.start in seen:
            continue
        seen.add(hit.start)
        out.append(hit)
    return sorted(out, key=lambda h: h.start)


def is_stock_entity(entity_id: str) -> bool:
    """实体 id 看起来是不是个股。板块 ``.TI`` / ``.FP`` 与指数名不会命中。"""
    return bool(_STOCK_CODE_RE.search(str(entity_id or "")))
