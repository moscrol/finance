"""Offline regressions for PR #773: real parsing, writers, quality gate and retry."""
from __future__ import annotations

import importlib.util
import hashlib
import json
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

from market_feature_store.db import init_db
from scripts import check_daily_review_data as checker

ROOT = Path(__file__).resolve().parents[1]
MONEYFLOW = ROOT / "scripts" / "moneyflow"
DATE = "2026-09-16"
DAY = "20260916"
HEADER = "时间,成交价格,成交数量,叫买序号,叫卖序号\n"
TICKS = HEADER + "093000000,100000,200000,2,1\n"


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    db = tmp_path / "l2.duckdb"
    with duckdb.connect(str(db)) as con:
        init_db(con)
    monkeypatch.setenv("MARKET_FEATURE_STORE_DB", str(db))
    monkeypatch.setenv("FINANCE_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("L2_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("L2_SOURCE", "baidu-share:xianyu-l2-7z")
    monkeypatch.setenv("L2_TOP_N", "100")
    for name in ("L2_FORCE_RESCAN", "L2_PAUSED", "L2_ALLOW_ALL_EMPTY", "L2_SUSPENSION_EVIDENCE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.syspath_prepend(str(MONEYFLOW))
    modules = {}
    # Bare script imports share sys.modules with unrelated skills in the full suite.
    for name in (
        "config", "l2_paths", "moneyflow", "write_to_duckdb",
        "process_l2_archive", "baidu_share", "cdn_chunks", "run_l2_from_share",
    ):
        spec = importlib.util.spec_from_file_location(name, MONEYFLOW / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        modules[name] = module
    processor = modules["process_l2_archive"]
    runner = modules["run_l2_from_share"]
    writer = modules["write_to_duckdb"]
    monkeypatch.setattr(writer, "connect", lambda: duckdb.connect(str(db)))
    monkeypatch.setattr(
        checker, "_connect_read_only", lambda: duckdb.connect(str(db), read_only=True)
    )
    codes = [f"{600000 + i:06d}" for i in range(100)]
    monkeypatch.setattr(processor, "prev_trade_date", lambda date: "2026-09-15")
    monkeypatch.setattr(processor, "duck_limitup_codes", lambda date: codes[:1])
    monkeypatch.setattr(processor, "duck_top_turnover_codes", lambda date, n: codes)
    monkeypatch.setattr(processor, "duck_pct_chg_map", lambda date: dict.fromkeys(codes, 1.0))
    monkeypatch.setattr(
        processor, "stock_info", lambda codes: {c: {"name": c, "cap": 100.0} for c in codes}
    )
    monkeypatch.setattr(processor, "_seven_zip", lambda: "stub-7z")
    state = SimpleNamespace(
        db=db, processor=processor, runner=runner, codes=codes,
        mode="ok", calls=[], meta=[], cache=tmp_path / "cache",
        real_run=subprocess.run,
    )

    def extract(cmd, **kwargs):
        out = Path(next(arg[2:] for arg in cmd if arg.startswith("-o")))
        selected = codes[:1] if state.mode in {"partial", "crc"} else codes
        for code in selected:
            path = out / DAY / processor.folder(code) / "逐笔成交.csv"
            path.parent.mkdir(parents=True, exist_ok=True)
            text = TICKS
            if code == codes[1]:
                if state.mode == "empty":
                    text = HEADER
                elif state.mode == "malformed":
                    text = "wrong,columns\n1,2\n"
            path.write_bytes(text.encode("gb18030"))
        rc = 2 if state.mode in {"crc", "crc_full"} else 0
        return subprocess.CompletedProcess(cmd, rc, "CRC Failed" if rc else "OK", "")

    def download(name, size, *, dest, pan_file):
        state.calls.append(name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"offline archive fixture")

    monkeypatch.setattr(processor.subprocess, "run", extract)
    monkeypatch.setattr(runner, "wait_share_file", lambda date: None)
    monkeypatch.setattr(runner, "ensure_transferred", lambda *args: {
        "file": {"size": 23}, "inbox": "/offline", "meta": {},
    })
    monkeypatch.setattr(runner, "download", download)
    monkeypatch.setattr(runner, "write_meta", state.meta.append)
    return state


def _ledger(pipeline):
    with duckdb.connect(str(pipeline.db), read_only=True) as con:
        return con.execute(
            "SELECT step, status, row_count, input_count, processed_count, failed_count "
            "FROM ops_pipeline_run_daily WHERE pipeline='l2-moneyflow' ORDER BY step"
        ).fetchall()


def test_historical_archive_never_fetches_live_valuation(pipeline, monkeypatch):
    monkeypatch.setattr(pipeline.processor, "_today", lambda: "2026-09-27", raising=False)
    monkeypatch.setattr(
        pipeline.processor, "stock_info",
        lambda codes: pytest.fail("historical scan fetched current valuation"),
    )
    monkeypatch.setattr(pipeline.processor, "quant_from_ticks", lambda ticks: {
        "量化单总额(万)": 2200.0, "占大单买入%": 11.0,
        "簇数": 1, "笔数": 11, "最大簇": "fixture quant cluster",
    })
    pipeline.runner.run_date(DATE)
    with duckdb.connect(str(pipeline.db), read_only=True) as con:
        rows = con.execute(
            "SELECT main_buy_net_wan, total_buy_net_wan, float_mktcap_yi, score "
            "FROM feature_l2_capital_flow_daily"
        ).fetchall()
        assert len(rows) == 101
        assert all(row[0] is not None and row[1] is not None for row in rows)
        assert all(row[2:] == (None, None) for row in rows)
        messages = con.execute(
            "SELECT message FROM ops_pipeline_run_daily WHERE step IN ('limitup','top100')"
        ).fetchall()
        assert all("historical_valuation_unavailable" in row[0] for row in messages)
        assert con.execute("SELECT count(*) FROM feature_l2_quant_orders_daily").fetchone()[0] == 100
    assert checker.check_l2(DATE) == []


def test_same_day_archive_keeps_same_day_valuation(pipeline, monkeypatch):
    monkeypatch.setattr(pipeline.processor, "_today", lambda: DATE, raising=False)
    pipeline.runner.run_date(DATE)
    with duckdb.connect(str(pipeline.db), read_only=True) as con:
        rows = con.execute("SELECT float_mktcap_yi, score FROM feature_l2_capital_flow_daily").fetchall()
        assert len(rows) == 101
        assert all(cap == 100.0 and score == pytest.approx(0.014) for cap, score in rows)


def _suspension_input(tmp_path, *, date=DATE):
    source = tmp_path / "official-notice.pdf"
    source.write_bytes(b"offline authoritative-notice fixture")
    manifest = tmp_path / "suspension-input.json"
    manifest.write_text(json.dumps({
        "trade_date": date,
        "entries": [{
            "stock_code": "002860", "reason": "开市起全天停牌",
            "source_url": "https://static.cninfo.com.cn/finalpage/2026-09-16/fixture.PDF",
            "evidence_path": str(source),
            "evidence_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        }],
    }), encoding="utf-8")
    return manifest, source


def test_verified_full_day_suspension_is_disclosed_not_fabricated_as_zero(
    pipeline, monkeypatch, tmp_path,
):
    manifest, source = _suspension_input(tmp_path)
    monkeypatch.setenv("L2_SUSPENSION_EVIDENCE", str(manifest))
    monkeypatch.setattr(pipeline.processor, "duck_limitup_codes", lambda date: [*pipeline.codes[:1], "002860"])
    pipeline.runner.run_date(DATE)
    assert _ledger(pipeline)[0] == ("limitup", "complete", 1, 1, 1, 0)
    with duckdb.connect(str(pipeline.db), read_only=True) as con:
        assert con.execute(
            "SELECT count(*) FROM feature_l2_capital_flow_daily WHERE stock_code='002860'"
        ).fetchone()[0] == 0
        message = con.execute(
            "SELECT message FROM ops_pipeline_run_daily WHERE step='limitup'"
        ).fetchone()[0]
        assert "excluded_suspensions=002860" in message
        assert "original_candidates=2" in message
        assert '"evidence_sha256"' in message
        assert hashlib.sha256(source.read_bytes()).hexdigest() in message
    assert checker.check_l2(DATE) == []


@pytest.mark.parametrize("damage", ["wrong_date", "changed_source", "has_market_row", "has_amount", "has_volume", "not_candidate"])
def test_suspension_override_requires_matching_evidence_and_candidate(
    pipeline, monkeypatch, tmp_path, damage,
):
    manifest, source = _suspension_input(tmp_path, date="2026-09-15" if damage == "wrong_date" else DATE)
    monkeypatch.setenv("L2_SUSPENSION_EVIDENCE", str(manifest))
    if damage != "not_candidate":
        monkeypatch.setattr(pipeline.processor, "duck_limitup_codes", lambda date: [*pipeline.codes[:1], "002860"])
    if damage == "changed_source":
        source.write_bytes(b"changed notice")
    if damage == "has_market_row":
        monkeypatch.setattr(pipeline.processor, "duck_pct_chg_map", lambda date: {**dict.fromkeys(pipeline.codes, 1.0), "002860": 2.0})
    if damage in {"has_amount", "has_volume"}:
        with duckdb.connect(str(pipeline.db)) as con:
            con.execute(
                "INSERT INTO fact_stock_daily (trade_date,stock_ts_code,close,pre_close,pct_chg,amount,volume) "
                "VALUES (?, '002860.XSHE', 11, 10, NULL, ?, ?)",
                [DATE, 100 if damage == "has_amount" else None,
                 10 if damage == "has_volume" else None],
            )
    with pytest.raises(ValueError, match="suspension"):
        pipeline.runner.run_date(DATE)
    with duckdb.connect(str(pipeline.db), read_only=True) as con:
        assert con.execute("SELECT count(*) FROM feature_l2_capital_flow_daily").fetchone()[0] == 0


def test_suspension_price_only_shell_is_not_trading_evidence(pipeline, monkeypatch, tmp_path):
    manifest, _ = _suspension_input(tmp_path)
    monkeypatch.setenv("L2_SUSPENSION_EVIDENCE", str(manifest))
    monkeypatch.setattr(pipeline.processor, "duck_limitup_codes", lambda date: [*pipeline.codes[:1], "002860"])
    with duckdb.connect(str(pipeline.db)) as con:
        con.execute(
            "INSERT INTO fact_stock_daily (trade_date,stock_ts_code,close,pre_close,pct_chg,amount,volume) "
            "VALUES (?, '002860.XSHE', 10, 10, NULL, 0, 0)", [DATE],
        )
    pipeline.runner.run_date(DATE)
    assert checker.check_l2(DATE) == []


@pytest.mark.parametrize("mode", ["crc", "crc_full", "partial", "empty", "malformed"])
def test_bad_archive_cannot_publish_or_skip_retry(pipeline, mode):
    pipeline.mode = mode
    with pytest.raises((RuntimeError, KeyError)):
        pipeline.runner.run_date(DATE)
    assert {row[1] for row in _ledger(pipeline)} == {"failed"}
    with duckdb.connect(str(pipeline.db), read_only=True) as con:
        for table in checker.L2_TABLES:
            assert con.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
    assert checker.check_l2(DATE)
    assert not pipeline.runner.already_complete(DATE)
    assert not (pipeline.cache / f"{DAY}.7z").exists()
    assert not (pipeline.cache / f"extract-{DAY}").exists()
    assert pipeline.meta == []


def test_failed_day_is_retried_without_force_and_zero_quant_is_valid(pipeline):
    pipeline.mode = "partial"
    with pytest.raises(RuntimeError, match="missing tick file"):
        pipeline.runner.run_date(DATE)
    pipeline.mode = "ok"
    pipeline.runner.run_date(DATE)
    assert _ledger(pipeline) == [
        ("limitup", "complete", 1, 1, 1, 0),
        ("quant", "complete", 0, 100, 100, 0),
        ("top100", "complete", 100, 100, 100, 0),
    ]
    assert checker.check_l2(DATE) == []
    assert pipeline.runner.already_complete(DATE)
    assert not (pipeline.cache / f"{DAY}.7z").exists()
    assert pipeline.meta[0]["last_processed"] == DATE
    pipeline.runner.run_date(DATE)
    assert len(pipeline.calls) == 2
    assert len(pipeline.meta) == 1


@pytest.mark.parametrize("damage", ["partial", "missing_stats", "result_deleted", "failed"])
def test_skip_revalidates_ledger_and_result_tables(pipeline, damage):
    pipeline.runner.run_date(DATE)
    with duckdb.connect(str(pipeline.db)) as con:
        if damage in {"partial", "result_deleted"}:
            con.execute(
                "DELETE FROM feature_l2_capital_flow_daily "
                "WHERE scan_type='top100' AND stock_code != '600000'"
            )
        if damage == "partial":
            # Old false-complete shape: 1 real row but self-reported 100/100, no failures.
            con.execute("UPDATE ops_pipeline_run_daily SET row_count=1 WHERE step='top100'")
        elif damage == "missing_stats":
            con.execute("UPDATE ops_pipeline_run_daily SET processed_count=NULL WHERE step='quant'")
        elif damage == "failed":
            con.execute("UPDATE ops_pipeline_run_daily SET failed_count=1 WHERE step='quant'")
    assert checker.check_l2(DATE)
    assert not pipeline.runner.already_complete(DATE)
    pipeline.runner.run_date(DATE)
    assert len(pipeline.calls) == 2
    assert checker.check_l2(DATE) == []


def test_share_failure_is_visible_in_ledger(pipeline, monkeypatch):
    def missing(date):
        raise FileNotFoundError("share not ready")

    monkeypatch.setattr(pipeline.runner, "wait_share_file", missing)
    with pytest.raises(FileNotFoundError, match="share not ready"):
        pipeline.runner.run_date(DATE)
    assert {row[1] for row in _ledger(pipeline)} == {"failed"}
    assert not pipeline.runner.already_complete(DATE)
    assert not pipeline.calls


def test_failed_forced_rescan_preserves_valid_previous_results(pipeline, monkeypatch):
    pipeline.runner.run_date(DATE)
    before = _ledger(pipeline)
    monkeypatch.setenv("L2_FORCE_RESCAN", "1")
    pipeline.mode = "crc"
    with pytest.raises(RuntimeError, match="extraction failed"):
        pipeline.runner.run_date(DATE)
    assert _ledger(pipeline) == before
    assert checker.check_l2(DATE) == []
    assert not (pipeline.cache / f"{DAY}.7z").exists()
    monkeypatch.delenv("L2_FORCE_RESCAN")
    assert pipeline.runner.already_complete(DATE)


@pytest.mark.parametrize("missing", [False, True])
def test_real_7z_archive_coverage(pipeline, monkeypatch, tmp_path, missing):
    executable = shutil.which("7zz") or shutil.which("7z")
    if not executable:
        pytest.skip("7z not installed; deterministic extraction regressions still run")
    monkeypatch.setattr(pipeline.processor.subprocess, "run", pipeline.real_run)
    monkeypatch.setattr(pipeline.processor, "_seven_zip", lambda: executable)
    source = tmp_path / "source"
    for code in pipeline.codes[:1] if missing else pipeline.codes:
        tick = source / DAY / pipeline.processor.folder(code) / "逐笔成交.csv"
        tick.parent.mkdir(parents=True)
        tick.write_bytes(TICKS.encode("gb18030"))
    archive = tmp_path / "real.7z"
    pipeline.real_run(
        [executable, "a", str(archive), DAY], cwd=source,
        capture_output=True, check=True,
    )
    if missing:
        with pytest.raises(RuntimeError, match="missing tick file"):
            pipeline.processor.process_date(DATE, archive)
        assert checker.check_l2(DATE)
        assert not pipeline.runner.already_complete(DATE)
    else:
        assert pipeline.processor.process_date(DATE, archive) == {
            "limitup": 1, "top100": 100, "quant": 0,
        }
        assert checker.check_l2(DATE) == []
        assert pipeline.runner.already_complete(DATE)


def test_empty_candidate_list_does_not_extract_whole_archive(pipeline, monkeypatch):
    monkeypatch.setattr(pipeline.processor, "duck_limitup_codes", lambda date: [])
    with pytest.raises(RuntimeError, match="incomplete candidates"):
        pipeline.runner.run_date(DATE)
    assert {row[1] for row in _ledger(pipeline)} == {"failed"}
    assert not (pipeline.cache / f"extract-{DAY}").exists()


@pytest.fixture
def cached_downloads(pipeline):
    pipeline.cache.mkdir(parents=True, exist_ok=True)
    targets = [pipeline.cache / f"{DAY}{suffix}" for suffix in (".7z", ".7z.part", ".7z.part.ok")]
    for path in targets:
        path.write_bytes(b"temporary download")
    extracted = pipeline.cache / f"extract-{DAY}"
    extracted.mkdir()
    (extracted / "ticks.csv").write_bytes(b"temporary ticks")
    targets.append(extracted)
    unrelated = pipeline.cache / "20260915.7z"
    unrelated.write_bytes(b"another trade date")
    return targets, unrelated


def test_cleanup_rejects_paths_outside_cache(pipeline, tmp_path):
    victim = tmp_path / "outside.7z"
    victim.write_bytes(b"not a download cache")
    with pytest.raises(ValueError, match="YYYYMMDD"):
        pipeline.runner.cleanup_local(str(victim.with_suffix("")))
    assert victim.read_bytes() == b"not a download cache"


@pytest.mark.parametrize("dangling", [False, True])
def test_cleanup_unlinks_extraction_symlink_without_following_it(pipeline, tmp_path, dangling):
    outside = tmp_path / "outside"
    if not dangling:
        outside.mkdir()
        (outside / "keep.txt").write_text("keep", encoding="utf-8")
    pipeline.cache.mkdir(parents=True)
    link = pipeline.cache / f"extract-{DAY}"
    link.symlink_to(outside, target_is_directory=True)
    pipeline.runner.cleanup_local(DAY)
    assert not link.is_symlink()
    if not dangling:
        assert (outside / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_cleanup_failure_is_not_reported_as_success(pipeline, cached_downloads, monkeypatch):
    def denied(*args, **kwargs):
        raise PermissionError("cleanup denied")

    monkeypatch.setattr(pipeline.runner.shutil, "rmtree", denied)
    with pytest.raises(PermissionError, match="cleanup denied"):
        pipeline.runner.cleanup_local(DAY)


@pytest.mark.parametrize("complete", [False, True], ids=["success", "skip-complete"])
def test_run_always_cleans_only_its_date(pipeline, cached_downloads, monkeypatch, complete):
    monkeypatch.setattr(pipeline.runner, "already_complete", lambda date: complete)
    pipeline.runner.run_date(DATE)
    targets, unrelated = cached_downloads
    assert all(not path.exists() for path in targets)
    assert unrelated.read_bytes() == b"another trade date"
    assert len(pipeline.calls) == (0 if complete else 1)


@pytest.mark.parametrize("stage,error", [
    ("already_complete", RuntimeError),
    ("wait_share_file", FileNotFoundError),
    ("ensure_transferred", RuntimeError),
    ("download", OSError),
    ("process_date", RuntimeError),
    ("process_date", KeyboardInterrupt),
    ("process_date", SystemExit),
    ("write_meta", OSError),
])
def test_failed_run_cleans_downloads_at_every_stage(
    pipeline, cached_downloads, monkeypatch, stage, error,
):
    failure = error("cleanup regression")

    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr(pipeline.runner, stage, fail)
    with pytest.raises(error, match="cleanup regression") as raised:
        pipeline.runner.run_date(DATE)
    assert raised.value is failure
    targets, unrelated = cached_downloads
    assert all(not path.exists() for path in targets)
    assert unrelated.read_bytes() == b"another trade date"


def test_failed_ledger_write_still_cleans_downloads(pipeline, cached_downloads, monkeypatch):
    def fail_processing(*args):
        raise RuntimeError("processing failed")

    def fail_ledger(*args):
        raise OSError("ledger unavailable")

    monkeypatch.setattr(pipeline.runner, "process_date", fail_processing)
    monkeypatch.setattr(pipeline.runner, "mark_failed", fail_ledger)
    with pytest.raises(OSError, match="ledger unavailable"):
        pipeline.runner.run_date(DATE)
    targets, unrelated = cached_downloads
    assert all(not path.exists() for path in targets)
    assert unrelated.exists()


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
def test_cli_signal_cleans_downloads(pipeline, cached_downloads, signum):
    code = f"""
import os
import sys
sys.path.insert(0, {str(MONEYFLOW)!r})
import run_l2_from_share as runner
runner.already_complete = lambda date: False
runner.wait_share_file = lambda date: None
runner.ensure_transferred = lambda *args: {{'file': {{'size': 0}}, 'inbox': '/offline', 'meta': {{}}}}
runner.download = lambda *args, **kwargs: None
runner.process_date = lambda *args: os.kill(os.getpid(), {int(signum)})
sys.argv = ['run_l2_from_share.py', {DATE!r}]
runner.main()
"""
    result = pipeline.real_run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=20,
    )
    assert result.returncode in (-int(signum), 128 + int(signum)), result.stderr
    targets, unrelated = cached_downloads
    assert all(not path.exists() for path in targets)
    assert unrelated.read_bytes() == b"another trade date"
