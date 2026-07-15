#!/usr/bin/env python3
"""ClickHouse server-side aggregation and shared cache for L2 scans."""
from __future__ import annotations

import json
import random
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date as date_type
from datetime import datetime
from pathlib import Path
from typing import Protocol

CACHE_VERSION = 1
OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"


class QueryClient(Protocol):
    def execute(
        self, query: str, params: dict[str, object]
    ) -> list[tuple[object, ...]]: ...

    def disconnect(self) -> None: ...


@dataclass(frozen=True)
class TradeSource:
    table: str
    time_column: str
    price_column: str
    volume_column: str
    type_column: str
    type_value: str


@dataclass(frozen=True)
class CapitalFlowSummary:
    active_net_wan: float
    total_net_wan: float
    change_pct: float


def trade_source(code: str) -> TradeSource:
    if code.startswith("6"):
        return TradeSource(
            table="share.ngts_tick",
            time_column="TickTime",
            price_column="Price",
            volume_column="Volume",
            type_column="TickType",
            type_value="T",
        )
    return TradeSource(
        table="share.trans",
        time_column="TradeTime",
        price_column="TradePrice",
        volume_column="TradeVolume",
        type_column="ExecType",
        type_value="1",
    )


def build_capital_flow_query(code: str) -> str:
    source = trade_source(code)
    return f"""
    SELECT
        count() AS trade_count,
        argMin(price, t) AS first_price,
        argMax(price, t) AS last_price,
        sumIf(amount, buy_no > sell_no AND buy_order_amount >= %(threshold)s)
          - sumIf(amount, buy_no < sell_no AND sell_order_amount >= %(threshold)s)
          AS active_net,
        sumIf(amount, buy_order_amount >= %(threshold)s)
          - sumIf(amount, sell_order_amount >= %(threshold)s)
          AS total_net
    FROM (
        SELECT
            t,
            price,
            buy_no,
            sell_no,
            amount,
            sum(amount) OVER (PARTITION BY buy_no) AS buy_order_amount,
            sum(amount) OVER (PARTITION BY sell_no) AS sell_order_amount
        FROM (
            SELECT
                {source.time_column} AS t,
                toFloat64({source.price_column}) AS price,
                BuyNo AS buy_no,
                SellNo AS sell_no,
                toFloat64({source.price_column}) * {source.volume_column} AS amount
            FROM {source.table}
            PREWHERE TradeDate = %(date)s AND SecurityID = %(code)s
            WHERE {source.type_column} = %(type_value)s
        )
    )
    """


def build_buyer_order_query(code: str) -> str:
    source = trade_source(code)
    return f"""
    SELECT max(t) AS t, sum(amount) AS order_amount
    FROM (
        SELECT
            {source.time_column} AS t,
            BuyNo AS buy_no,
            toFloat64({source.price_column}) * {source.volume_column} AS amount
        FROM {source.table}
        PREWHERE TradeDate = %(date)s AND SecurityID = %(code)s
        WHERE {source.type_column} = %(type_value)s
    )
    GROUP BY buy_no
    HAVING order_amount >= %(threshold)s
    """


class SharedQueryCache:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._entries = self._load()

    def _load(self) -> dict[str, object]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(payload, dict) or payload.get("version") != CACHE_VERSION:
            return {}
        entries = payload.get("entries")
        return entries if isinstance(entries, dict) else {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps(
                {"version": CACHE_VERSION, "entries": self._entries},
                ensure_ascii=False,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    @staticmethod
    def _key(kind: str, date: str, code: str, threshold_wan: float) -> str:
        threshold = int(round(threshold_wan * 1e4))
        return f"{kind}:{date}:{code}:{threshold}"

    def get_capital_flow(
        self, date: str, code: str, threshold_wan: float
    ) -> tuple[bool, CapitalFlowSummary | None]:
        key = self._key("capital", date, code, threshold_wan)
        if key not in self._entries:
            return False, None
        value = self._entries[key]
        if value is None:
            return True, None
        if not isinstance(value, dict):
            return False, None
        try:
            return True, CapitalFlowSummary(
                active_net_wan=float(value["active_net_wan"]),
                total_net_wan=float(value["total_net_wan"]),
                change_pct=float(value["change_pct"]),
            )
        except (KeyError, TypeError, ValueError):
            return False, None

    def put_capital_flow(
        self,
        date: str,
        code: str,
        threshold_wan: float,
        summary: CapitalFlowSummary | None,
    ) -> None:
        key = self._key("capital", date, code, threshold_wan)
        self._entries[key] = None if summary is None else asdict(summary)
        self._save()

    def get_buyer_orders(
        self, date: str, code: str, threshold_wan: float
    ) -> tuple[bool, list[tuple[str, float]]]:
        key = self._key("buyer-orders", date, code, threshold_wan)
        if key not in self._entries:
            return False, []
        value = self._entries[key]
        if not isinstance(value, list):
            return False, []
        rows: list[tuple[str, float]] = []
        try:
            for row in value:
                if not isinstance(row, dict):
                    return False, []
                rows.append((str(row["t"]), float(row["amount"])))
        except (KeyError, TypeError, ValueError):
            return False, []
        return True, rows

    def put_buyer_orders(
        self,
        date: str,
        code: str,
        threshold_wan: float,
        rows: list[tuple[str, float]],
    ) -> None:
        key = self._key("buyer-orders", date, code, threshold_wan)
        self._entries[key] = [{"t": timestamp, "amount": amount} for timestamp, amount in rows]
        self._save()


class L2QueryService:
    def __init__(
        self,
        date: str,
        threshold_wan: float,
        client_factory: Callable[[], QueryClient],
        cache: SharedQueryCache | None = None,
        retries: int = 3,
    ):
        self.date = date
        self.threshold_wan = threshold_wan
        self.threshold = threshold_wan * 1e4
        self.client_factory = client_factory
        self.cache = cache or SharedQueryCache(
            OUTPUT_DIR / f"l2_query_cache_{date}.json"
        )
        self.retries = retries

    def _execute(
        self,
        client: QueryClient,
        query: str,
        params: dict[str, object],
    ) -> tuple[QueryClient, list[tuple[object, ...]]]:
        for attempt in range(self.retries):
            try:
                return client, client.execute(query, params)
            except Exception:
                if attempt == self.retries - 1:
                    raise
                try:
                    client.disconnect()
                except Exception:
                    pass
                time.sleep(min(60.0, 5.0 * (2**attempt)) + random.uniform(0, 3))
                client = self.client_factory()
        raise RuntimeError("unreachable query retry state")

    def capital_flow(
        self, client: QueryClient, code: str
    ) -> tuple[QueryClient, CapitalFlowSummary | None]:
        hit, cached = self.cache.get_capital_flow(
            self.date, code, self.threshold_wan
        )
        if hit:
            return client, cached
        source = trade_source(code)
        client, rows = self._execute(
            client,
            build_capital_flow_query(code),
            {
                "date": self.date,
                "code": code,
                "threshold": self.threshold,
                "type_value": source.type_value,
            },
        )
        if not rows:
            summary = None
        else:
            trade_count, first_price, last_price, active_net, total_net = rows[0]
            if int(trade_count) <= 0 or first_price in (None, 0) or last_price is None:
                summary = None
            else:
                summary = CapitalFlowSummary(
                    active_net_wan=float(active_net) / 1e4,
                    total_net_wan=float(total_net) / 1e4,
                    change_pct=(float(last_price) / float(first_price) - 1) * 100,
                )
        self.cache.put_capital_flow(
            self.date, code, self.threshold_wan, summary
        )
        return client, summary

    def buyer_orders(
        self, client: QueryClient, code: str
    ) -> tuple[QueryClient, list[tuple[str, float]]]:
        hit, cached = self.cache.get_buyer_orders(
            self.date, code, self.threshold_wan
        )
        if hit:
            return client, cached
        source = trade_source(code)
        client, rows = self._execute(
            client,
            build_buyer_order_query(code),
            {
                "date": self.date,
                "code": code,
                "threshold": self.threshold,
                "type_value": source.type_value,
            },
        )
        orders = [
            (_timestamp_text(timestamp), float(amount)) for timestamp, amount in rows
        ]
        self.cache.put_buyer_orders(
            self.date, code, self.threshold_wan, orders
        )
        return client, orders


def _timestamp_text(value: object) -> str:
    if isinstance(value, (datetime, date_type)):
        return value.isoformat()
    return str(value)
