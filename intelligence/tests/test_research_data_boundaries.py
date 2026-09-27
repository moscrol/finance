"""实测发现的研究数据边界：估值可比组不可凭概念共现，公告空手不可下否定结论。"""
from pathlib import Path

import duckdb
import pytest
import subprocess
from unittest.mock import Mock

from intelligence.services import ask_blocks, l3_evidence, valuation_estimate


def make_db(path: Path, *, target_industry="食品饮料-白酒Ⅱ"):
    con = duckdb.connect(str(path))
    con.execute("create table fact_stock_daily (stock_ts_code varchar, stock_name varchar)")
    con.execute("insert into fact_stock_daily values ('600519.SH', '贵州茅台')")
    con.execute("""create table fact_sector_stock_daily (
        trade_date date, stock_ts_code varchar, stock_name varchar, sector_name varchar,
        sw_industry varchar, amount double, total_mcap_yi double)""")
    con.executemany("insert into fact_sector_stock_daily values ('2026-09-17',?,?,?,?,?,?)", [
        ("600519.SH", "贵州茅台", "乡村振兴", target_industry, 30, 15800),
        ("000988.SZ", "华工科技", "乡村振兴", "机械设备-自动化设备", 90, 800),
        ("000858.SZ", "五粮液", "白酒", "食品饮料-白酒Ⅱ", 40, 3500),
        ("000858.SZ", "五粮液", "国企改革", "食品饮料-白酒Ⅱ", 40, 3500),
        ("000568.SZ", "泸州老窖", "白酒", "食品饮料-白酒Ⅱ", 20, 1500),
        ("000799.SZ", "酒鬼酒", "白酒", "食品饮料-白酒Ⅱ", 10, 100),
        # 冲突身份不能因为有一行白酒，就忽略另外一行。
        ("000799.SZ", "酒鬼酒", "其他", "身份冲突", 10, 100),
    ])
    con.close()


def fetcher(calls, *, old_peer=False):
    def fetch(code, name=""):
        calls.append(code)
        day = "2026-09-16" if old_peer and code != "600519.SH" else "2026-09-17"
        return valuation_estimate.ValuationSnapshot(code, name, 100, 20, 3, day)
    return fetch


def test_theme_co_membership_is_not_a_valuation_peer(tmp_path):
    db = tmp_path / "t.duckdb"
    make_db(db)
    calls = []
    block = ask_blocks._valuation_block_for_llm("贵州茅台贵不贵", "乡村振兴", db,
                                               fetcher=fetcher(calls), as_of="2026-09-17")
    assert calls == ["600519.SH", "000858.SZ", "000568.SZ"]
    assert "华工科技" not in block
    assert "酒鬼酒" not in block
    assert "五粮液" in block and "泸州老窖" in block
    assert "同细分行业" in block
    assert "业务和成长差异仍需核验" in block


@pytest.mark.parametrize("industry", [None, "", " "])
def test_missing_industry_does_not_fall_back_to_themes(tmp_path, industry):
    db = tmp_path / "t.duckdb"
    make_db(db, target_industry=industry)
    calls = []
    block = ask_blocks._valuation_block_for_llm("贵州茅台贵不贵", None, db,
                                               fetcher=fetcher(calls), as_of="2026-09-17")
    assert calls == ["600519.SH"]
    assert "缺可比集" in block
    assert "可比 PE(TTM) 估值带" not in block


def test_cross_date_peers_are_not_mixed_into_current_band(tmp_path):
    db = tmp_path / "t.duckdb"
    make_db(db)
    block = ask_blocks._valuation_block_for_llm("贵州茅台贵不贵", None, db,
        fetcher=fetcher([], old_peer=True), as_of="2026-09-17")
    assert "缺可比集" in block
    assert "可比 PE(TTM) 估值带" not in block


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_l3_rc0_with_upstream_403_is_failure_not_empty(monkeypatch, tmp_path, stream):
    diagnostic = "[fetch] query failed page=1: HTTP Error 403: Forbidden\n"
    outputs = {"stdout": "[]", "stderr": ""}
    outputs[stream] = diagnostic + outputs[stream]
    run = Mock(return_value=subprocess.CompletedProcess([], 0, **outputs))
    monkeypatch.setattr(l3_evidence.subprocess, "run", run)
    cfg = l3_evidence.L3LookupConfig(enabled=True, cache_dir=str(tmp_path), cache_ttl_seconds=900)
    for _ in range(2):
        bundle = l3_evidence.lookup_l3_company("600519", config=cfg)
        assert bundle.status == "request_error"
        assert not bundle.items
        assert "403" in " ".join(bundle.warnings)
    assert run.call_count == 2  # 失败不能缓存成成功空集
    assert not list(tmp_path.glob("*.json"))


def test_l3_one_source_failed_retains_other_rows_but_reports_partial(monkeypatch):
    output = ('[warn] 源 sse_einteract 失败：timeout\n'
              '[{"source":"cninfo","title":"合同公告","summary":"签订合同"}]')
    monkeypatch.setattr(l3_evidence.subprocess, "run", Mock(
        return_value=subprocess.CompletedProcess([], 0, output, "")))
    bundle = l3_evidence.lookup_l3_company("600519", config=l3_evidence.L3LookupConfig(enabled=True))
    assert bundle.status == "partial"
    assert len(bundle.items) == 1
    assert "sse_einteract" in " ".join(bundle.warnings)


def test_l3_clean_empty_is_not_request_failure(monkeypatch):
    monkeypatch.setattr(l3_evidence.subprocess, "run", Mock(
        return_value=subprocess.CompletedProcess([], 0, "[]", "")))
    bundle = l3_evidence.lookup_l3_company("600519", config=l3_evidence.L3LookupConfig(enabled=True))
    assert bundle.status == "empty"
    assert not bundle.items


@pytest.mark.parametrize("payload", [
    '[{"title": "公告",',
    '{"data": "bad"}',
    '{"unrecognized": true}',
    'null',
    '[42]',
])
def test_malformed_l3_json_is_parse_error_not_evidence(monkeypatch, payload):
    monkeypatch.setattr(l3_evidence.subprocess, "run", Mock(
        return_value=subprocess.CompletedProcess([], 0, payload, "")))
    bundle = l3_evidence.lookup_l3_company("600519", config=l3_evidence.L3LookupConfig(enabled=True))
    assert bundle.status == "parse_error"
    assert not bundle.items


def test_multiline_l3_diagnostic_is_not_plaintext_evidence(monkeypatch):
    output = '[warn] 源 irm_szse 失败："None of [Index(\n dtype=object)] are in columns"'
    monkeypatch.setattr(l3_evidence.subprocess, "run", Mock(
        return_value=subprocess.CompletedProcess([], 0, output, "")))
    bundle = l3_evidence.lookup_l3_company("600519", config=l3_evidence.L3LookupConfig(enabled=True))
    assert bundle.status == "request_error"
    assert not bundle.items


def test_l3_json_preserves_official_published_at():
    items = l3_evidence._try_parse_json_items("company", '[{"source":"cninfo",'
        '"title":"公告","summary":"签订合同","published_at":"2026-09-17T17:00:00+08:00"}]')
    assert "2026-09-17" in items[0].summary


def test_empty_l3_does_not_claim_company_has_not_delivered():
    block = l3_evidence.L3EvidenceBundle(query="贵州茅台").to_prompt_block()
    assert "读作「公司端尚未兑现」" not in block
    assert "证据缺口" in block
    assert "不能据此断言" in block
