"""KB 消费侧 top-k 槽位重排（V9b / 方案 B5①③）。

把 ``via_neighbor`` 且代表段为「相关实体/相关概念」的页排到队尾，
再交给既有 ``sanitize_hits`` 截 k——过采样够时它们被挤出槽位。

不改窗内容（那是 V9a）。不调 cross-encoder / 任何模型。
不读 remaining、不另建降档函数：本函数是纯启发式，BM25 档也付得起。

人话：检索把「链接里提到长电」的邻页也递过来了；换窗之后那些页变成
邻页自己的一句话，但仍占着 top-k。这里按「怎么进来的」降权，不按窗里
写了什么重写。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")

# B5① 指定的两节。不要复用 V9a 的 STRUCTURAL_SECTIONS——「原始资料链接」
# 是同页错段（换窗），不是邻页占槽。
NEIGHBOR_REP_SECTIONS = frozenset({"相关实体", "相关概念"})


@dataclass(frozen=True)
class SlotRerankStats:
    demoted: int = 0


def _crumb_parts(section: str) -> list[str]:
    return [part.strip() for part in str(section or "").split(">") if part.strip()]


def is_structural_neighbor_rep(hit: object) -> bool:
    """B5①：via_neighbor 且代表段 ∈ {相关实体, 相关概念}。

    无 via_neighbor 的相关实体页不挤——那些是 BM25 直接命中，也是 V9a
    retrieve 钉（section=相关实体、未打邻居标）能保持绿的共存条件。
    """

    if not bool(getattr(hit, "via_neighbor", False)):
        return False
    return any(
        part in NEIGHBOR_REP_SECTIONS
        for part in _crumb_parts(str(getattr(hit, "section", "") or ""))
    )


def allocate_topk_slots(hits: Sequence[T]) -> tuple[list[T], SlotRerankStats]:
    """结构邻页代表块排后；相对次序各自保持。不截 k（交给 sanitize_hits）。"""

    primary: list[T] = []
    demoted: list[T] = []
    for hit in hits:
        if is_structural_neighbor_rep(hit):
            demoted.append(hit)
        else:
            primary.append(hit)
    return primary + demoted, SlotRerankStats(demoted=len(demoted))
