"""KC-05：反方检索规划。

Knevo 为每个核心逻辑构造反事实；我方 R/W 原先只有 anchor+theme+query
正面口径，counterpoint 只能从正面证据里硬挤。这里把风险词按类型分桶，
实体/主题 × 桶 生成反方 target，装配时在 ``max_evidence`` 窗内保底 1-2
个反方槽（不抬上限、无命中不空占）。
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TypeVar

COUNTER_MARK = "[反]"
MISSING_COUNTER_EVIDENCE = "未检索到反方证据"
COUNTER_SLOT_RESERVE = 2
T = TypeVar("T")

# 桶名按 spec KC-05；检索式用 terms[0]，匹配用整组。
# 「政策」不用光秃词——产业政策支持是正面口径，会误伤。
COUNTER_RISK_BUCKETS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("产能过剩", ("产能过剩", "供给过剩", "扩产过快", "库存高企")),
    ("价格战", ("价格战", "恶性降价", "杀价竞争")),
    ("技术替代", ("技术替代", "技术路线切换", "被替代")),
    ("需求不及", ("需求不及预期", "需求不及", "订单下滑", "需求疲软")),
    ("竞格恶化", ("竞争格局恶化", "竞争加剧", "新进入者涌入", "份额被抢")),
    ("政策", ("政策收紧", "监管趋严", "补贴退坡", "出口限制")),
)


@dataclass(frozen=True)
class CounterTarget:
    subject: str
    bucket: str
    query: str
    terms: tuple[str, ...]


def plan_counter_targets(*subjects: str) -> tuple[CounterTarget, ...]:
    """实体/主题 × 六桶。空串与重复 subject 丢掉，顺序稳定。"""
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in subjects:
        subject = str(raw or "").strip()
        if not subject or subject in seen:
            continue
        seen.add(subject)
        ordered.append(subject)
    targets: list[CounterTarget] = []
    for subject in ordered:
        for bucket, terms in COUNTER_RISK_BUCKETS:
            targets.append(
                CounterTarget(
                    subject=subject,
                    bucket=bucket,
                    query=f"{subject} {terms[0]}",
                    terms=terms,
                )
            )
    return tuple(targets)


def match_counter_bucket(text: str) -> str | None:
    """正文命中哪个风险桶。先长词后短词，避免「需求不及」抢「需求不及预期」。"""
    blob = str(text or "")
    ranked: list[tuple[int, str, str]] = []
    for bucket, terms in COUNTER_RISK_BUCKETS:
        for term in terms:
            ranked.append((len(term), term, bucket))
    ranked.sort(key=lambda item: item[0], reverse=True)
    for _length, term, bucket in ranked:
        if term in blob:
            return bucket
    return None


def reserve_counter_slots(
    support: Sequence[T],
    counter: Sequence[T],
    *,
    max_n: int,
    reserve: int = COUNTER_SLOT_RESERVE,
) -> list[tuple[T, bool]]:
    """窗内保底 ``min(reserve, 命中数)`` 条反方；有空位时反方可超过保底。

    无反方命中不空占。总行数不超过 ``max_n``。
    """
    if max_n <= 0:
        return []
    guaranteed = min(len(counter), max(0, reserve), max_n)
    support_room = max_n - guaranteed
    taken_support = list(support[:support_room])
    remaining = max_n - len(taken_support)
    taken_counter = list(counter[:remaining])
    return [(item, False) for item in taken_support] + [
        (item, True) for item in taken_counter
    ]


def counter_disclosure(counter_count: int) -> str | None:
    if counter_count > 0:
        return None
    return MISSING_COUNTER_EVIDENCE
