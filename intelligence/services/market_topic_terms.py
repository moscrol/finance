"""路由词的共享词汇表：每个词只写一次，各处**自己组合**成自己的外延。

## 为什么不是「一张单子生成六处」

设计稿附录 E 写的是「单一真本源 `MARKET_TOPIC_TERMS` 生成六处」。照字面做会**改掉
路由**——那六处的外延是**故意不同**的，至少一处的差异在源码注释里写明是有意为之：

    query_understanding._DATED_MARKET_TOPIC_RE   刻意**不收**「板块」
        （注释：收了会把 theme-research 的问题抢走；over-routing 比 under-routing
          更难发现——答案看起来是有的，只是答错了层）
    evidence_capabilities._MARKET_SUBJECT_MARKERS 刻意**收**「板块」
        （主体词，命中后 mainline_context 才有意义）

把它们并成一张单子，就是谓词稿 §9-C 拒绝的「削齐」，只是方向相反：那条讲的是不该
各写各的，这条讲的是不该强行合并**本来就该不同**的判据。

## 真正的漂移风险在词汇层，不在列表层

「主线」出现在四处、「涨停」出现在三处，各处各写一遍字面。改一个词的写法（比如
把「涨家数」改成「涨跌家数」）时，没人知道另外三处也要跟着改。

所以本模块只做一件事：**每个词只写一次**。各消费者从原子组合出自己的那一份，
外延该不同就不同，但用的是同一个字面。哪一处该收哪些词，仍由那一处自己决定并
自己写注释——本模块不替它们做判断。

新增路由词先加进本模块，再被某一处引用；不要直接在消费者里写字面。
"""

from __future__ import annotations

# --- 原子 ---------------------------------------------------------------
# 分组只为可读，不代表「必须整组一起用」。消费者按需挑。

#: 涨跌停与梯队结构
LIMIT_MOVE = ("涨停", "跌停", "连板", "梯队", "断层")
#: 家数类
BREADTH = ("涨家数", "跌家数", "涨跌家数", "涨停家数")
#: 量能类
VOLUME = ("量能", "缩量", "放量", "成交额")
#: 新高新低
EXTREMES = ("新高", "新低")
#: 市场状态
MARKET_STATE = ("市场阶段", "市场情绪", "赚钱效应")
#: 主体词
SUBJECTS = ("市场", "大盘", "行情", "板块", "盘面", "a股", "指数")
#: 结构词
MAINLINE = "主线"
DOUBLE_RED = "双红"


# --- 各消费者的外延（顺序即正则里的顺序，改序会改字面）------------------

#: `query_understanding._DATED_MARKET_TOPIC_RE`
#: 只收**盘面复盘专有**的词。刻意不收「题材」「板块」「资金流」——它们同时是题材
#: 研究的常用词，收进来会把 theme-research 的问题抢走。
DATED_MARKET_TOPIC = (
    DOUBLE_RED,
    *LIMIT_MOVE,
    MAINLINE,
    *EXTREMES,
    "涨家数",
    "跌家数",
    *VOLUME[:3],
    "成交额",
    *MARKET_STATE,
)

#: `answer_orchestrator._MARKET_LEVEL_STATE_WORDS`
#: 判断某个**分句**是不是在问全市场。只 5 个词是刻意的：宽了会把「创新药板块当前
#: 主线是哪几个」抢进 market_review。
MARKET_LEVEL_STATE = (MAINLINE, "赚钱效应", "涨跌家数", "涨停家数", "市场情绪")

#: `evidence_capabilities._MARKET_SUBJECT_MARKERS`
#: 主体词：问的是整个市场/板块层面的状态，命中后 mainline_context 才有意义。
#: **收「板块」**——与 `DATED_MARKET_TOPIC` 的取舍相反，那是两个不同的判断。
MARKET_SUBJECT = (*SUBJECTS[:4], MAINLINE, *SUBJECTS[4:])

#: `task_frame` 里「一个财务词都不带地问最典型盘面指标」那一条
#: （2026-08-13 R15-C2：「2026-02-17 涨停家数多少」）
FINANCIAL_TASK_MARKET = ("涨停", "跌停", "连板", "涨家数", "成交额")


def as_alternation(terms: tuple[str, ...]) -> str:
    """组合成正则交替串。顺序保持不变——改序会改字面，字面变了 parity 就红。"""

    return "|".join(terms)
