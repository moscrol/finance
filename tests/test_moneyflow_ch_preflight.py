"""ClickHouse Fake-IP / DNS 回退 / 空结果扫描语义单元测试（不连真实库）。"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MONEYFLOW_DIR = ROOT / "scripts" / "moneyflow"


def _load_moneyflow(monkeypatch):
    monkeypatch.syspath_prepend(str(MONEYFLOW_DIR))
    for name in ("config", "moneyflow"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    return importlib.import_module("moneyflow")


def test_is_fake_ip_detects_shadowrocket_range(monkeypatch):
    mf = _load_moneyflow(monkeypatch)
    assert mf._is_fake_ip("198.18.0.24") is True
    assert mf._is_fake_ip("198.19.255.1") is True
    assert mf._is_fake_ip("36.139.233.80") is False
    assert mf._is_fake_ip("not-an-ip") is False


def test_resolve_rejects_literal_fake_ip(monkeypatch):
    mf = _load_moneyflow(monkeypatch)
    with pytest.raises(RuntimeError, match="Fake-IP"):
        mf.resolve_clickhouse_host("198.18.0.1")


def test_resolve_uses_public_dns_when_system_is_fake(monkeypatch):
    mf = _load_moneyflow(monkeypatch)
    monkeypatch.setattr(mf, "_system_resolve", lambda host: ["198.18.0.24"])
    monkeypatch.setattr(
        mf,
        "_dig_resolve",
        lambda host, dns: ["36.139.233.80"] if dns == "223.5.5.5" else [],
    )
    monkeypatch.delenv("CH_HOST_FALLBACK", raising=False)
    host, note, candidates = mf.resolve_clickhouse_host("db.base32.cn")
    assert host == "36.139.233.80"
    assert "36.139.233.80" in candidates
    assert "dig@" in note or "system=" in note


def test_resolve_honors_host_fallback(monkeypatch):
    mf = _load_moneyflow(monkeypatch)
    monkeypatch.setattr(mf, "_system_resolve", lambda host: ["198.18.0.24"])
    monkeypatch.setattr(mf, "_dig_resolve", lambda host, dns: [])
    monkeypatch.setenv("CH_HOST_FALLBACK", "36.140.180.104,198.18.0.9")
    host, _note, candidates = mf.resolve_clickhouse_host("db.base32.cn")
    assert host == "36.140.180.104"
    assert "198.18.0.9" not in candidates


def test_run_scan_skips_null_cache_entries(monkeypatch, tmp_path):
    mf = _load_moneyflow(monkeypatch)
    cache = tmp_path / "scan_cache_top100_2026-07-15.json"
    cache.write_text(
        '{"000001": null, "000002": null, "000003": {"code": "000003", "x": 1}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(mf, "out_path", lambda name: str(tmp_path / name))
    monkeypatch.setenv("L2_ALLOW_ALL_EMPTY", "1")

    calls = []

    def compute(client, code):
        calls.append(code)
        return client, {"code": code}

    client, rows, stats = mf.run_scan(
        client=object(),
        codes=["000001", "000002", "000003"],
        date="2026-07-15",
        tag="top100",
        compute=compute,
        passes=1,
        batch_size=100,
        batch_rest=0,
    )
    # null 缓存条目应被忽略并重扫；有效 000003 跳过
    assert "000003" not in calls
    assert "000001" in calls and "000002" in calls
    assert stats["nonempty_count"] == 3
    assert len(rows) == 3


def test_run_scan_rejects_all_empty(monkeypatch, tmp_path):
    mf = _load_moneyflow(monkeypatch)
    monkeypatch.setattr(mf, "out_path", lambda name: str(tmp_path / name))
    monkeypatch.delenv("L2_ALLOW_ALL_EMPTY", raising=False)

    def compute(client, code):
        return client, None

    with pytest.raises(RuntimeError, match="全部空结果"):
        mf.run_scan(
            client=object(),
            codes=[f"{i:06d}" for i in range(1, 25)],
            date="2026-07-15",
            tag="top100",
            compute=compute,
            passes=1,
            batch_size=100,
            batch_rest=0,
        )
