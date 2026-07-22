"""Turn 级检索查询台账（P1-B）：同 provider+query 每 turn 最多真实执行一次。

背景（双审查合并方案 ②）：一个 research turn 里 Web 检索可被 E 兜底、agent
web_search、W7 事件块各自发起，资讯检索同理——各层只有局部去重（agent 只对
自己去重、kb_rag 只对自己缓存），跨层重复没人管。本模块提供 turn-scoped 账本：

- key = ``(provider, normalized_query, as_of, corpus_revision, variant)``；
- 工具层经 :func:`executed` 原子登记：首次真实执行并 memoize 结果，同 key
  再来直接复用（fetch 不再发起）；
- 无活动账本时零行为变化（直接执行，CLI 单测不受影响）；
- ``summary()`` 供 trace 落盘：执行/去重次数、逐条记录。

与 retrieval_cache（TTL 进程级缓存）的分工：那是"跨 turn 的数据新鲜度缓存"，
本模块是"turn 内的执行去重 + 审计账本"，key 里带 turn 语义（scope 生命周期）
而不是 TTL。
"""

from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable, Iterator
from concurrent.futures import Future
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_query(query: str) -> str:
    return _WHITESPACE_RE.sub(" ", str(query or "").strip()).casefold()


QueryKey = tuple[str, str, str, str, str]


class QueryPublishGuard:
    """Atomically suppress this scope's late publication without killing threads.

    The guard does not own or cancel an unrelated scope that already owns the
    same ledger key; it only governs work that entered ``query_publish_guard_scope``.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._open = True
        self._deactivators: list[Callable[[], None]] = []

    def close(self) -> None:
        with self._lock:
            if not self._open:
                return
            self._open = False
            deactivators = tuple(self._deactivators)
            self._deactivators.clear()
            for deactivate in deactivators:
                deactivate()

    @contextmanager
    def publication_scope(self) -> Iterator[bool]:
        """Hold the guard registration boundary while the ledger mutates."""

        with self._lock:
            yield self._open

    def _add_deactivator_locked(self, deactivate: Callable[[], None]) -> None:
        """Register while ``publication_scope`` holds the guard lock."""

        self._deactivators.append(deactivate)


_PUBLISH_GUARD: ContextVar[QueryPublishGuard | None] = ContextVar(
    "query_publish_guard",
    default=None,
)


@contextmanager
def _publication_scope(
    guard: QueryPublishGuard | None,
) -> Iterator[bool]:
    if guard is None:
        yield True
        return
    with guard.publication_scope() as is_open:
        yield is_open


@dataclass
class QueryRecord:
    provider: str
    normalized_query: str
    as_of: str
    corpus_revision: str
    variant: str
    result: Any
    elapsed_ms: int
    reuse_count: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "query": self.normalized_query,
            "as_of": self.as_of,
            "corpus_revision": self.corpus_revision,
            "variant": self.variant,
            "elapsed_ms": self.elapsed_ms,
            "reuse_count": self.reuse_count,
        }


@dataclass
class _QuerySubscription:
    active: bool


@dataclass
class _InflightQuery:
    future: Future[Any]
    subscriptions: list[_QuerySubscription] = field(default_factory=list)


@dataclass
class QueryLedger:
    entries: dict[QueryKey, QueryRecord] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _inflight: dict[QueryKey, _InflightQuery] = field(default_factory=dict)

    def executed(
        self,
        provider: str,
        query: str,
        fetch: Callable[[], Any],
        *,
        as_of: str = "",
        corpus_revision: str = "",
        variant: str = "",
    ) -> Any:
        """Per-key single-flight：同 key 合并执行，不同 key 可并行。

        全局锁只保护 map 状态，绝不包住慢 IO。第一个调用者在锁外 fetch，
        同 key 后来者等待同一 Future；失败广播给本批等待者但不写成功缓存，
        后续新调用仍可重试。
        """
        key: QueryKey = (
            provider,
            normalize_query(query),
            as_of,
            corpus_revision,
            variant,
        )
        guard = _PUBLISH_GUARD.get()
        with _publication_scope(guard) as is_open:
            with self._lock:
                record = self.entries.get(key)
                if record is not None:
                    if is_open:
                        record.reuse_count += 1
                    return record.result
                inflight = self._inflight.get(key)
                is_owner = inflight is None
                if inflight is None:
                    inflight = _InflightQuery(Future())
                    self._inflight[key] = inflight
                subscription = _QuerySubscription(active=is_open)
                inflight.subscriptions.append(subscription)
                if guard is not None and is_open:
                    guard._add_deactivator_locked(
                        lambda subscription=subscription: self._deactivate_subscription(
                            subscription
                        )
                    )

        if not is_owner:
            result = inflight.future.result()
            with self._lock:
                if subscription.active:
                    record = self.entries.get(key)
                    if record is not None:
                        record.reuse_count += 1
            return result

        started = time.monotonic()
        try:
            result = fetch()
        except BaseException as exc:
            with self._lock:
                try:
                    if self._inflight.get(key) is inflight:
                        self._inflight.pop(key)
                finally:
                    if not inflight.future.done():
                        inflight.future.set_exception(exc)
            raise

        record = QueryRecord(
            provider=provider,
            normalized_query=key[1],
            as_of=as_of,
            corpus_revision=corpus_revision,
            variant=variant,
            result=result,
            elapsed_ms=max(0, round((time.monotonic() - started) * 1000)),
        )
        with self._lock:
            try:
                owns_inflight = self._inflight.get(key) is inflight
                if owns_inflight:
                    self._inflight.pop(key)
                    if any(item.active for item in inflight.subscriptions):
                        self.entries[key] = record
            finally:
                if not inflight.future.done():
                    inflight.future.set_result(result)
        return result

    def _deactivate_subscription(self, subscription: _QuerySubscription) -> None:
        with self._lock:
            subscription.active = False

    def summary(self) -> dict[str, object]:
        with self._lock:
            records = list(self.entries.values())
        return {
            "executed_count": len(records),
            "deduped_count": sum(record.reuse_count for record in records),
            "by_provider": _count_by(records, "provider"),
            "records": [record.to_dict() for record in records],
        }


def _count_by(records: list[QueryRecord], attr: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        key = getattr(record, attr)
        counts[key] = counts.get(key, 0) + 1
    return counts


_LEDGER: ContextVar[QueryLedger | None] = ContextVar(
    "turn_query_ledger",
    default=None,
)


@contextmanager
def query_publish_guard_scope(guard: QueryPublishGuard) -> Iterator[None]:
    """Prevent guarded work that finishes after close from publishing cache."""

    token = _PUBLISH_GUARD.set(guard)
    try:
        yield
    finally:
        _PUBLISH_GUARD.reset(token)


@contextmanager
def query_ledger_scope() -> Iterator[QueryLedger]:
    """开启 turn 级查询台账；已有活动账本时复用（嵌套不重置）。"""
    existing = _LEDGER.get()
    if existing is not None:
        yield existing
        return
    ledger = QueryLedger()
    token = _LEDGER.set(ledger)
    try:
        yield ledger
    finally:
        _LEDGER.reset(token)


def current_query_ledger() -> QueryLedger | None:
    return _LEDGER.get()


def executed(
    provider: str,
    query: str,
    fetch: Callable[[], Any],
    *,
    as_of: str = "",
    corpus_revision: str = "",
    variant: str = "",
) -> Any:
    """工具层入口：有活动账本走去重，没有则直接执行（零行为变化）。"""
    ledger = _LEDGER.get()
    if ledger is None:
        return fetch()
    return ledger.executed(
        provider,
        query,
        fetch,
        as_of=as_of,
        corpus_revision=corpus_revision,
        variant=variant,
    )
