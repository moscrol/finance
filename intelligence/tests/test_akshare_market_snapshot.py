from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from types import ModuleType
from zoneinfo import ZoneInfo

from intelligence.services.akshare_market_snapshot import (
    sync_akshare_market_snapshot,
)


class FakeFrame:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    @property
    def empty(self) -> bool:
        return not self.rows

    def to_dict(self, orient: str) -> list[dict[str, object]]:
        assert orient == "records"
        return list(self.rows)


def _module(
    *,
    spot: list[dict[str, object]] | Exception,
    limit_up: list[dict[str, object]] | Exception,
    limit_down: list[dict[str, object]] | Exception,
) -> ModuleType:
    module = ModuleType("fake_akshare")

    def frame_or_raise(value: list[dict[str, object]] | Exception) -> FakeFrame:
        if isinstance(value, Exception):
            raise value
        return FakeFrame(value)

    module.stock_zh_a_spot_em = lambda: frame_or_raise(spot)
    module.stock_zt_pool_em = lambda **_kwargs: frame_or_raise(limit_up)
    module.stock_zt_pool_dtgc_em = lambda **_kwargs: frame_or_raise(limit_down)
    return module


def test_success_writes_canonical_daily_latest_meta_and_status(
    tmp_path: Path,
) -> None:
    module = _module(
        spot=[
            {"涨跌幅": 2.0, "成交额": 200_000_000},
            {"涨跌幅": -1.0, "成交额": 100_000_000},
        ],
        limit_up=[
            {
                "名称": "测试股份",
                "代码": "600001",
                "所属行业": "液冷",
                "涨跌幅": 10.0,
                "成交额": 150_000_000,
            }
        ],
        limit_down=[],
    )

    result = sync_akshare_market_snapshot(
        tmp_path,
        trade_date="2026-07-16",
        akshare_module=module,
        now=datetime(2026, 7, 16, 15, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert result.ok is True
    assert result.quality == "complete"
    for name in (
        "2026-07-16.json",
        "latest.json",
        "meta.json",
        "akshare_status.json",
    ):
        assert (tmp_path / name).is_file()
    daily = json.loads((tmp_path / "latest.json").read_text(encoding="utf-8"))
    assert daily["source"] == "AkShare"
    assert daily["source_data_date"] == "2026-07-16"
    assert daily["market"]["total_amount"] == 3.0
    assert daily["strong_stocks"][0]["stock_ts_code"] == "600001.SH"


def test_total_failure_preserves_existing_latest_and_records_error(
    tmp_path: Path,
) -> None:
    previous = {"trade_date": "2026-07-15", "quality": "complete"}
    latest = tmp_path / "latest.json"
    latest.write_text(json.dumps(previous), encoding="utf-8")
    before = latest.read_bytes()
    module = _module(
        spot=ConnectionError("spot disconnected"),
        limit_up=ConnectionError("pool disconnected"),
        limit_down=ConnectionError("down disconnected"),
    )

    result = sync_akshare_market_snapshot(
        tmp_path,
        trade_date="2026-07-16",
        akshare_module=module,
        now=datetime(2026, 7, 16, 15, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert result.ok is False
    assert result.preserved_existing_snapshot is True
    assert latest.read_bytes() == before
    status = json.loads(
        (tmp_path / "akshare_status.json").read_text(encoding="utf-8")
    )
    assert status["quality"] == "failed"
    assert "ConnectionError" in "；".join(status["errors"])


def test_partial_fetch_does_not_downgrade_existing_complete_daily(
    tmp_path: Path,
) -> None:
    daily = tmp_path / "2026-07-16.json"
    daily.write_text(
        json.dumps({"trade_date": "2026-07-16", "quality": "complete"}),
        encoding="utf-8",
    )
    before = daily.read_bytes()
    module = _module(
        spot=ConnectionError("spot disconnected"),
        limit_up=[
            {
                "名称": "测试股份",
                "代码": "000001",
                "所属行业": "液冷",
                "涨跌幅": 10.0,
                "成交额": 50_000_000,
            }
        ],
        limit_down=[],
    )

    result = sync_akshare_market_snapshot(
        tmp_path,
        trade_date="2026-07-16",
        akshare_module=module,
        now=datetime(2026, 7, 16, 15, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert result.ok is True
    assert result.quality == "partial"
    assert result.preserved_existing_snapshot is True
    assert daily.read_bytes() == before
