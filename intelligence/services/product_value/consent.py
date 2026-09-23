"""同意范围折叠：写侧门与读侧测量共用的一段。

两侧问的是同一个问题——某身份在某时刻生效的同意范围是什么。写侧
(``ObservingRunStore`` 决定要不要落测量事件) 与读侧 (05 ``measure`` 决定这条事件
算不算数) 若各留一份折叠，改了排序键或集合运算只会有一侧变红，净效果是「写了
读不到」或「已撤回却仍进读数」。折叠只此一份，排序键也只在这里出现一次。

**不属于这里的**，是两侧有意的差异，它们留在各自调用点：

- 取哪些记录：读侧只认带 ``participant_id`` 的试点记录，写侧认 owner 自己的记录
  （``participant_id`` 为空或等于 owner）；
- 没有任何记录怎么办：读侧返回 None（未知，记 limitation），写侧按自用默认放行；
- 时间戳不可解析怎么办：读侧让 ``event_time`` 抛（台账已过校验，坏值是真异常），
  写侧跳过该条并留 stderr。**别在这里统一它**：静默跳过一条 ``withdraw``
  等于把已撤回当成仍授权。
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable

from intelligence.services.product_value.contracts import REQUIRED_MEASUREMENT_SCOPES

__all__ = ["ConsentEntry", "scopes_at", "covers_measurement"]

# (生效时刻, action, 该条涉及的范围)
ConsentEntry = tuple[datetime, str, frozenset[str]]


def scopes_at(entries: Iterable[ConsentEntry], at: datetime) -> frozenset[str]:
    """折叠出 ``at`` 时刻生效的同意范围。

    排序键 ``(effective_at, action)``：同一时刻 ``grant`` 在 ``withdraw`` 之前，
    所以同毫秒的授权+撤回净效果是撤回（保守方向）。``effective_at > at`` 之后的
    记录尚未生效，直接截断。认识的 action 只有 grant / withdraw，其余不动集合。

    空输入返回空集。**空集不等于「没有记录」**：后者的含义由调用方决定（读侧未知、
    写侧自用默认），不要在这里替它们回答。
    """

    active: set[str] = set()
    for effective, action, scopes in sorted(entries, key=lambda item: (item[0], item[1])):
        if effective > at:
            break
        if action == "grant":
            active |= scopes
        elif action == "withdraw":
            active -= scopes
    return frozenset(active)


def covers_measurement(scopes: Iterable[str]) -> bool:
    """这组范围是否够做测量：``research`` + ``logging`` 必须同时在。"""

    return REQUIRED_MEASUREMENT_SCOPES <= frozenset(scopes)
