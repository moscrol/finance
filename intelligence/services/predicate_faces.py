"""谓词的多面：算数 / 说明书 / 路由特例，由同一个开关 id 统辖。

一句话：**关正典 ≠ agent 忘了双红。**

关掉 `signals` 里的算数，模型仍然会背公式（思考宪法里手抄着同一条 SQL），路由仍然
会因为问句里出现「双红」两个字把这题特道进盘面复盘。只灭一面，得到的是一个
**说得出、道得通、就是算不出来**的 agent——那不是消融。

## 「三面」是上限，不是每个谓词都有三面

设计稿的口号是「算数 + 说明书 + 路由共一 id」。实测下来只有 `double-red` 三面俱全：

    double-red        算数 + 说明书 + 路由（唯一算数面真正读 faces() 的）
    capacity-top3     说明书（宪法「容量行业」；算数还没接到缝）
    sqrt-weighted     说明书（宪法「个股加权强度」）
    limit-heat-min2   说明书（宪法「涨停热度映射」）
    dated-market-topic 只有路由
    single-red 等     正典已建，但无生产缝，不进 OWNERSHIP / 不进实验臂

**所以正控是「它声明的每一面都要变」，不是「三面都要变」。** 硬要三面，会把只有
两面的谓词判成失败——那是判据错，不是开关坏。这跟路由词表那件事同形：外延本来
不同的东西，不许为了整齐划一而削齐。

路由词只登记**该谓词专有**的。「涨停」同时属于涨停一族和盘面复盘通用词，摘掉它会
连带改掉别的判断，那是一拧动两件。

本模块只回答「某个 id 关掉之后，它名下这几面各自应该变成什么」。**它不执行拧动**
——拧动发生在 runner 的 composition root。生产路径传空集合，行为与本模块不存在时
完全一致。
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator

from intelligence.services import market_topic_terms

# runner 在 composition root 写入；生产不写 → 空集合 → 与本模块不存在时一致。
_DISABLED: ContextVar[frozenset[str]] = ContextVar(
    "predicate_faces_disabled", default=frozenset()
)

FACE_ARITHMETIC = "arithmetic"
FACE_PROSE = "prose"
FACE_ROUTE = "route"
FACE_PACK = "pack"


@dataclass(frozen=True)
class PredicateOwnership:
    """一个谓词名下有哪几面，各面拥有什么。"""

    route_terms: tuple[str, ...] = ()
    prose_markers: tuple[str, ...] = ()
    has_arithmetic: bool = True
    has_pack: bool = False

    @property
    def declared_faces(self) -> frozenset[str]:
        faces = {FACE_ARITHMETIC} if self.has_arithmetic else set()
        if self.route_terms:
            faces.add(FACE_ROUTE)
        if self.prose_markers:
            faces.add(FACE_PROSE)
        if self.has_pack:
            faces.add(FACE_PACK)
        return frozenset(faces)


#: 登记表。没登记的 id = 还没接三面，runner 会报 not_implemented 而不是空过。
OWNERSHIP: dict[str, PredicateOwnership] = {
    "predicate.double-red": PredicateOwnership(
        route_terms=("双红",),
        prose_markers=("双红定义", "双红题材边际量", "双红题材首日"),
    ),
    # 说明书/路由面已接到生产缝。算数面只有 double-red 真读 faces()；
    # 下面三个 has_arithmetic=False，避免 runner 用「集合里有 id」当正控。
    "predicate.capacity-top3": PredicateOwnership(
        prose_markers=("容量行业",), has_arithmetic=False
    ),
    "predicate.sqrt-weighted": PredicateOwnership(
        prose_markers=("个股加权强度",), has_arithmetic=False
    ),
    "predicate.limit-heat-min2": PredicateOwnership(
        prose_markers=("涨停热度映射",), has_arithmetic=False
    ),
    # 它**就是**路由那一面本身：关掉 = 整张盘面复盘词表不再特道路由。
    "predicate.dated-market-topic": PredicateOwnership(
        route_terms=market_topic_terms.DATED_MARKET_TOPIC,
        has_arithmetic=False,
    ),
    # 整包注入（系统提示词 + 各数据块）。不是宪法里的说明书行。
    "predicate.reading-baseline": PredicateOwnership(
        has_arithmetic=False,
        has_pack=True,
    ),
}


@dataclass(frozen=True)
class PredicateFaces:
    """一次拨法下，各面的样子。"""

    disabled: frozenset[str]

    def declared_faces(self, switch_id: str) -> frozenset[str]:
        owner = OWNERSHIP.get(switch_id)
        return owner.declared_faces if owner else frozenset()

    def arithmetic_enabled(self, switch_id: str) -> bool:
        """算数面：这个谓词还允不允许被计算。"""

        return switch_id not in self.disabled

    def route_alternation(self) -> str:
        """路由面：摘掉被关谓词名下的专有词之后的交替串。"""

        dropped = {
            term
            for switch_id in self.disabled
            for term in OWNERSHIP.get(switch_id, PredicateOwnership()).route_terms
        }
        return market_topic_terms.as_alternation(
            tuple(
                term
                for term in market_topic_terms.DATED_MARKET_TOPIC
                if term not in dropped
            )
        )

    def prose_lines(self, lines: tuple[str, ...]) -> tuple[str, ...]:
        """说明书面：滤掉被关谓词名下的行。

        关掉算数却照样把公式注进系统提示词，模型会照着它自己心算一个数报出来——
        比不给更糟，因为它看起来像有依据。
        """

        markers = {
            marker
            for switch_id in self.disabled
            for marker in OWNERSHIP.get(switch_id, PredicateOwnership()).prose_markers
        }
        if not markers:
            return lines
        return tuple(
            line for line in lines if not any(marker in line for marker in markers)
        )

    def counts_double_red(self) -> bool:
        """算数面的具体一问：预取还报不报双红个数。"""

        return self.arithmetic_enabled("predicate.double-red")


def faces(disabled: frozenset[str] | set[str] | tuple[str, ...] | None = None) -> PredicateFaces:
    """不传则读 contextvar。生产不写 → 空集合 → 与本模块不存在时一致。"""

    if disabled is None:
        disabled = _DISABLED.get()
    return PredicateFaces(frozenset(disabled))


@contextmanager
def using(disabled: frozenset[str] | set[str] | tuple[str, ...] = ()) -> Iterator[None]:
    """runner 在 composition root 套这一层；loop 里不加产品 if。"""

    token = _DISABLED.set(frozenset(disabled))
    try:
        yield
    finally:
        _DISABLED.reset(token)


def is_disabled(switch_id: str) -> bool:
    """当前上下文里这颗谓词是否被 `using()` 关掉。

    给谓词的**宿主模块**用（如 `reading_baseline.enabled`）：让关断真的传导到
    注入产物本身，而不是只翻 faces 视图。生产从不写 contextvar → 恒 False。
    """

    return switch_id in _DISABLED.get()


def wired_predicate_ids() -> frozenset[str]:
    """已经接了**至少一面生产缝**的谓词。空声明不进——那是还没接线。"""

    return frozenset(
        switch_id
        for switch_id, owner in OWNERSHIP.items()
        if owner.declared_faces
    )
