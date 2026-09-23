"""mootdx 日线源健康探针：把「源挂了」和「这只票真的没数据」分开。

为什么需要这个模块（2026-09-22 复盘）
------------------------------------
``sync_mootdx_stock_daily`` 原来的失败分类是：

    if df is None or len(df) == 0:
        failures.append((code, "empty"))

而 ``Quotes.factory(market="std")`` 默认 ``raise_exception=False``——tdxpy 的
``last_ack_time`` 装饰器会把底层异常吞掉、返回 ``None``，``to_data(None)`` 再把它
变成空 DataFrame。于是**协议级故障和单票无数据塌缩成同一个 "empty"**。

实测后果：通达信免费主站在 2026-09-07 之后对所有行情命令只回 2 字节 body
（``0x2003``，即 ret_count=800 但没有任何 K 线体），tdxpy 在
``get_security_bars.py`` 解析时抛 ``struct.error``，被吞掉 → 上层看到 5553 只票
全部 "empty" → ``rows_written=0`` → **CLI 仍然 return 0**。
``fact_stock_daily`` 的 source 分布显示 mootdx 最后一天正是 2026-09-07，
之后两周靠人工每天换替补源（sina / eastmoney:snapshot / hithink）救火。
根因不是某天抓取失败，而是**源死亡没有触发红灯**。

39 台主站扫描结论（tmp/mootdx-unblock-20260922/server-sweep.json）：
15 台可连、``get_security_count`` 全部正常返回 24296，但 K 线 body 恒为
``0x2003``、实时报价恒为 0 行。即：**元数据服务活着、行情服务停供**。
所以"连得上"和"名单查得到"都不能作为源可用的证据——必须真的要一根 K 线。

设计要点
--------
1. 探针走 ``client.bars()``（与同步主循环同一条代码路径），不走私有 API：
   否则探针通过而主路径失败，护栏就是摆设。
2. 客户端必须用 ``raise_exception=True`` 构造，让协议错误以异常形式暴露。
3. 基准票选 ``000001``（平安银行）：深市主板、日均成交额数十亿、无长期停牌史。
   它都取不到 K 线，就不是"这只票的问题"。
4. 三态判定，不是二值：``no_route`` / ``metadata_only`` / ``empty_payload``
   对应完全不同的处置（换网络 / 换源 / 查日期），合并成 "失败" 会丢诊断信息。
5. fail closed：不健康就抛异常，调用方在**批量写入之前**中止，一行都不写。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

#: 基准探测票：深市主板、长期高流动性，缺 K 线只可能是源的问题。
PROBE_CODE = "000001"
#: 探针拉几根。要 >1，只拉 1 根时某些实现会走不同分支。
PROBE_BARS = 8
#: 日线频次（tdxpy category=9 = 日K）。与 sync 主路径保持一致。
PROBE_FREQUENCY = 9

VERDICT_OK = "ok"
#: 连不上/握手失败：网络、防火墙、服务器下线。换网络或换服务器可能有救。
VERDICT_NO_ROUTE = "no_route"
#: 能连、元数据命令正常，但行情命令回不可解析的响应。供应商侧停供，本地无解。
VERDICT_METADATA_ONLY = "metadata_only"
#: 协议链路完好，但基准票拿到 0 根。可能是日期/参数问题，也可能是软性限流。
VERDICT_EMPTY_PAYLOAD = "empty_payload"

#: 判定 → 人话处置建议。写进异常消息，让值班的人不用翻代码。
_ADVICE = {
    VERDICT_NO_ROUTE: "连不上行情服务器：检查网络/代理，或换 server 再试。",
    VERDICT_METADATA_ONLY: (
        "服务器只回元数据、行情命令返回不可解析的响应——这是供应商侧停供，"
        "本地改配置无效。请切换到其他日线源（如 hithink）。"
    ),
    VERDICT_EMPTY_PAYLOAD: (
        "协议正常但基准票 0 根 K 线：确认请求参数/交易日，或视为源降级。"
    ),
}


class MootdxSourceUnavailable(RuntimeError):
    """mootdx 源不可用。携带结构化诊断，供调用方写收据/告警。"""

    def __init__(self, health: "SourceHealth") -> None:
        self.health = health
        super().__init__(health.message())


@dataclass(frozen=True)
class SourceHealth:
    """一次源健康探测的结构化结果。

    ok=False 时 verdict 说明**故障层次**，detail 保留原始异常文本以便追溯。
    """

    ok: bool
    verdict: str
    detail: str = ""
    server: Any = None
    security_count: int | None = None
    probe_code: str = PROBE_CODE
    probe_rows: int = 0
    elapsed_s: float = 0.0
    extra: dict = field(default_factory=dict)

    def message(self) -> str:
        advice = _ADVICE.get(self.verdict, "")
        parts = [
            f"mootdx 日线源不可用 verdict={self.verdict}",
            f"server={self.server}",
            f"security_count={self.security_count}",
            f"probe={self.probe_code}/{self.probe_rows}根",
        ]
        if self.detail:
            parts.append(f"detail={self.detail}")
        if advice:
            parts.append(advice)
        return " | ".join(parts)

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "verdict": self.verdict,
            "detail": self.detail,
            "server": list(self.server) if isinstance(self.server, (list, tuple)) else self.server,
            "security_count": self.security_count,
            "probe_code": self.probe_code,
            "probe_rows": self.probe_rows,
            "elapsed_s": round(self.elapsed_s, 3),
            **({"extra": self.extra} if self.extra else {}),
        }

    def raise_if_unhealthy(self) -> "SourceHealth":
        """fail closed 用：不健康直接抛，调用方不必写 if。"""
        if not self.ok:
            raise MootdxSourceUnavailable(self)
        return self


def _rows_of(df: Any) -> int:
    """兼容 DataFrame / list / None 的行数统计。探针不该假设返回类型。"""
    if df is None:
        return 0
    try:
        return int(len(df))
    except TypeError:
        return 0


def probe_source_health(client: Any, *, probe_code: str = PROBE_CODE,
                        probe_bars: int = PROBE_BARS) -> SourceHealth:
    """对已建好的 mootdx 客户端做一次三态健康探测。不写库、不改状态。

    client 只需鸭子类型地提供 ``stock_count(market)`` 与
    ``bars(symbol=, frequency=, offset=)``，方便测试注入假客户端。

    注意：client 必须以 ``raise_exception=True`` 构造，否则协议错误会被 tdxpy
    吞成 None，探针会误判成 ``empty_payload`` 而不是 ``metadata_only``。
    """
    started = time.monotonic()
    server = getattr(client, "server", None)
    count: int | None = None

    # 第一层：元数据命令。它能过说明 TCP 通、握手成功、协议版本被接受。
    try:
        count = client.stock_count(0)
    except Exception as exc:  # noqa: BLE001 - 任何异常都意味着链路不可用
        return SourceHealth(
            ok=False, verdict=VERDICT_NO_ROUTE,
            detail=f"stock_count 失败: {type(exc).__name__}: {exc}",
            server=server, elapsed_s=time.monotonic() - started,
        )

    # 第二层：真正要一根 K 线。这是 metadata_only 与 ok 的唯一分界线。
    try:
        df = client.bars(symbol=probe_code, frequency=PROBE_FREQUENCY, offset=probe_bars)
    except Exception as exc:  # noqa: BLE001
        return SourceHealth(
            ok=False, verdict=VERDICT_METADATA_ONLY,
            detail=f"bars 失败: {type(exc).__name__}: {exc}",
            server=server, security_count=count, probe_code=probe_code,
            elapsed_s=time.monotonic() - started,
        )

    rows = _rows_of(df)
    if rows == 0:
        return SourceHealth(
            ok=False, verdict=VERDICT_EMPTY_PAYLOAD,
            detail=f"基准票 {probe_code} 返回 0 根 K 线（请求 {probe_bars} 根）",
            server=server, security_count=count, probe_code=probe_code,
            elapsed_s=time.monotonic() - started,
        )

    return SourceHealth(
        ok=True, verdict=VERDICT_OK, server=server, security_count=count,
        probe_code=probe_code, probe_rows=rows,
        elapsed_s=time.monotonic() - started,
    )


def open_checked_client(factory: Callable[..., Any] | None = None, **kwargs: Any):
    """建 mootdx 客户端并立刻体检；不健康就抛 MootdxSourceUnavailable。

    强制 ``raise_exception=True``：调用方传 False 会让护栏失效，直接覆盖掉。
    返回 ``(client, health)``，health 写进同步收据留痕。
    """
    if factory is None:
        from mootdx.quotes import Quotes

        def factory(**kw: Any):  # type: ignore[misc]
            return Quotes.factory(market="std", **kw)

    kwargs["raise_exception"] = True
    try:
        client = factory(**kwargs)
    except Exception as exc:  # noqa: BLE001
        raise MootdxSourceUnavailable(SourceHealth(
            ok=False, verdict=VERDICT_NO_ROUTE,
            detail=f"建立连接失败: {type(exc).__name__}: {exc}",
        )) from exc

    health = probe_source_health(client)
    health.raise_if_unhealthy()
    return client, health
