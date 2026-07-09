"""子任务并行执行器（planner-worker 轻量版）：把互相独立的取数块并行跑。

拆解是**确定性**的：块本来就是规则门控（意图词面/问题类型命中才生成），
这里只把「命中的块」当作互相独立的子任务扔进线程池，取回后仍按原有
固定顺序汇总——所以最终 evidence_text / 引用编号与串行版逐字节一致，
并行纯粹是快（取数块大多在等 IO：DuckDB 查询/东财 HTTP/文件读取）。

选型取舍（教学点）：
- 没上 LLM planner（Knevo 那种「思考后拆任务」）——更聪明但多一次 LLM
  调用、产出不可测（单测难写）；等真有开放式子任务再上。
- 用 ThreadPoolExecutor 不用 asyncio：块内部全是同步代码（duckdb/requests），
  改 async 要把整条链翻掉；线程池零侵入，GIL 对 IO 等待不构成瓶颈。
- 线程安全：每个块内部各开自己的 DuckDB 只读连接（既有约定），
  不共享连接对象，无跨线程状态。

任一子任务抛异常只降级为该块缺失 + warning，不拖垮整问。
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable

DEFAULT_MAX_WORKERS = 6


@dataclass
class BlockTask:
    """一个可并行的取数子任务：tag/label 用于可观测，build 返回 (块文本, 引用)。"""

    tag: str
    label: str
    build: Callable[[], tuple[str, Any]]


@dataclass
class BlockOutcome:
    tag: str
    label: str
    block: str = ""
    citation: Any = None
    error: str = ""
    elapsed_ms: int = 0


def _run_one(task: BlockTask) -> BlockOutcome:
    started = time.monotonic()
    try:
        block, citation = task.build()
        return BlockOutcome(
            tag=task.tag,
            label=task.label,
            block=block or "",
            citation=citation,
            elapsed_ms=int((time.monotonic() - started) * 1000),
        )
    except Exception as exc:  # 单块失败只降级，不拖垮整问
        return BlockOutcome(
            tag=task.tag,
            label=task.label,
            error=f"{type(exc).__name__}: {exc}",
            elapsed_ms=int((time.monotonic() - started) * 1000),
        )


def run_block_tasks(
    tasks: list[BlockTask],
    max_workers: int = DEFAULT_MAX_WORKERS,
    parallel: bool = True,
) -> list[BlockOutcome]:
    """并行执行子任务，**按输入顺序**返回结果（保证汇总顺序确定）。"""
    if not tasks:
        return []
    if not parallel or len(tasks) == 1:
        return [_run_one(task) for task in tasks]
    with ThreadPoolExecutor(max_workers=min(max_workers, len(tasks))) as pool:
        return list(pool.map(_run_one, tasks))
