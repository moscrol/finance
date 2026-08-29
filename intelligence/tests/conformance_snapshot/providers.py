"""参数表（逐 provider）+ 能力声明表 + 场景驱动器（零网络）。

缝：``market_snapshot_sync.sync_market_snapshot`` 编排下的快照供数链——
``existing_complete`` 旁路 / ``duckdb_exact`` / ``akshare_exact``（生产为
子进程，本套件按工单用假 runner）/ ``duckdb_latest`` 回退，共享
``ProviderAttempt`` / ``MarketSnapshotSyncResult`` 契约。

与工具缝/数据块缝的判据差别：这条缝的四个 provider **分模块、分进程、
分失败形状**（更接近运行时后端缝），但 attempt/发布契约由编排器单点收口
——所以声明表仍全 SUPPORTED，逐 provider 的差异（旁路零发布、回退恒
historical 等）走 notes。

既有 ``test_market_snapshot_sync.py`` 盖场景终态；本套件盖**逐 provider 的
统一契约**（任一路发布必须过 root contract、降级必显式留痕、链序如实），
断言不重复（分工见 README）。

零网络：AkShare 路 = 进程内假 runner；DuckDB 路 = 临时小库（复用
``test_duckdb_market_snapshot._build_db``，与既有测试同一夹具源，不抄
第二份 schema）。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import duckdb

from intelligence.services.market_snapshot_sync import (
    MarketSnapshotSyncResult,
    sync_market_snapshot,
)
from intelligence.tests.test_duckdb_market_snapshot import _build_db

# 供数链的机读顺序（编排器代码里的尝试顺序；existing_complete 是链前旁路）。
CHAIN_ORDER: tuple[str, ...] = ("duckdb_exact", "akshare_exact", "duckdb_latest")
PROVIDER_NAMES: tuple[str, ...] = ("existing_complete", *CHAIN_ORDER)

MS_INVARIANT_IDS: tuple[str, ...] = ("MS-1", "MS-2", "MS-3", "MS-4", "MS-5")

PROVIDER_DECLARATIONS: dict[str, dict[str, str]] = {
    name: {inv: "supported" for inv in MS_INVARIANT_IDS}
    for name in PROVIDER_NAMES
}
PROVIDER_NOTES: dict[str, str] = {
    "existing_complete": (
        "保护旁路：目标日已有更高优先级（非 OWNED_SOURCES）complete 快照时"
        "整链不跑、零发布（written_files 空、attempt.published=False）、"
        "原文件字节不动——它的「发布契约」= 不发布，MS-1 对它断保护语义。"
    ),
    "akshare_exact": (
        "生产为子进程 runner（scripts.sync_akshare_market_snapshot，剥代理"
        "env）；本套件按工单用进程内假 runner，子进程装配面归"
        " test_akshare_runtime_assets 等既有测试。"
    ),
    "duckdb_latest": (
        "回退档：served_trade_date < requested，freshness 恒 historical，"
        "目标日文件不落盘（只更新 latest/meta）——「旧日冒充当日」由 MS-1 的"
        " served/requested 分离断言看住。"
    ),
}

REQUESTED = "2026-07-16"
PRIOR = "2026-07-15"


def _complete_akshare_document(trade_date: str) -> dict[str, object]:
    return {
        "schema_version": "1.1-akshare",
        "trade_date": trade_date,
        "generated_at": "2026-07-16T16:20:00+08:00",
        "source": "AkShare",
        "source_data_date": trade_date,
        "captured_at": "2026-07-16T16:20:00+08:00",
        "freshness": "fresh",
        "quality": "complete",
        "source_errors": [],
        "market": {
            "stage": "震荡阶段",
            "total_amount": 22000.0,
            "amount_ratio": None,
            "advancers": 2800,
            "decliners": 2400,
            "limit_up": 60,
            "limit_down": 12,
            "capacity_top3": [],
        },
        "themes": [
            {
                "concept": "光模块",
                "priority_score": 80.0,
                "trigger_types": ["akshare_limit_up_pool"],
            }
        ],
        "strong_stocks": [
            {
                "stock_name": "探针股份",
                "stock_ts_code": "600001.SH",
                "concepts": ["光模块"],
                "pct_chg": 10.0,
                "amount": 10.0,
            }
        ],
    }


def complete_akshare_runner(
    output_dir: Path,
    trade_date: str,
) -> subprocess.CompletedProcess[str]:
    """写出可过 contract 的 complete 产物的假 runner。"""

    output_dir.mkdir(parents=True, exist_ok=True)
    document = _complete_akshare_document(trade_date)
    meta = {
        "schema_version": "1.1-akshare",
        "latest_trade_date": trade_date,
        "updated_at": "2026-07-16T16:20:00+08:00",
        "source": "AkShare",
        "source_data_date": trade_date,
        "freshness": "fresh",
        "quality": "complete",
    }
    for name, payload in (
        (f"{trade_date}.json", document),
        ("latest.json", document),
        ("meta.json", meta),
    ):
        (output_dir / name).write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
    return subprocess.CompletedProcess(
        args=["fake-akshare"], returncode=0, stdout="", stderr=""
    )


def failed_akshare_runner(
    _output_dir: Path,
    _trade_date: str,
) -> subprocess.CompletedProcess[str]:
    """什么都不写、退出码非零的假 runner（远端故障形状）。"""

    return subprocess.CompletedProcess(
        args=["fake-akshare"], returncode=1, stdout="", stderr="remote disconnected"
    )


def forbidden_akshare_runner(
    _output_dir: Path,
    _trade_date: str,
) -> subprocess.CompletedProcess[str]:
    raise AssertionError("本场景 AkShare 不得被调用")


def empty_db(path: Path) -> Path:
    """有 schema、零数据的临时库（duckdb_exact/duckdb_latest 双双落空）。"""

    _build_db(path)
    connection = duckdb.connect(str(path))
    for table in (
        "fact_market_daily",
        "fact_stock_daily",
        "fact_sector_daily",
        "fact_mainline_sector_daily",
    ):
        connection.execute(f"DELETE FROM {table}")
    connection.close()
    return path


def write_protected_snapshot(root: Path, trade_date: str) -> Path:
    """目标日写入更高优先级来源（非 OWNED_SOURCES）的 complete 快照。"""

    root.mkdir(parents=True, exist_ok=True)
    document = _complete_akshare_document(trade_date)
    document["source"] = "daily-full"
    path = root / f"{trade_date}.json"
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return path


def run_publishing_scenario(
    publisher: str,
    tmp_path: Path,
) -> MarketSnapshotSyncResult:
    """构造让指定 provider 成为发布者的最小输入并跑编排器。"""

    root = tmp_path / "snapshot"
    if publisher == "existing_complete":
        write_protected_snapshot(root, REQUESTED)
        db_path = _build_db(tmp_path / "market.duckdb", trade_date=REQUESTED)
        runner = forbidden_akshare_runner
    elif publisher == "duckdb_exact":
        db_path = _build_db(tmp_path / "market.duckdb", trade_date=REQUESTED)
        runner = forbidden_akshare_runner
    elif publisher == "akshare_exact":
        db_path = empty_db(tmp_path / "market.duckdb")
        runner = complete_akshare_runner
    elif publisher == "duckdb_latest":
        db_path = _build_db(tmp_path / "market.duckdb", trade_date=PRIOR)
        runner = failed_akshare_runner
    else:  # pragma: no cover - 参数表守卫
        raise AssertionError(f"未知 provider：{publisher}")
    return sync_market_snapshot(
        root,
        db_path=db_path,
        target_date=REQUESTED,
        akshare_runner=runner,
    )


def run_total_failure(tmp_path: Path) -> MarketSnapshotSyncResult:
    """三源全败的终态（existing_complete 旁路也不满足）。"""

    return sync_market_snapshot(
        tmp_path / "snapshot",
        db_path=empty_db(tmp_path / "market.duckdb"),
        target_date=REQUESTED,
        akshare_runner=failed_akshare_runner,
    )
