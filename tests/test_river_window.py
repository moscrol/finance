"""区间特征与聚类的契约测试。

聚类最容易出的两种假绿：全部并成一簇，或全部散成单点。两者都「没报错」。
所以这里有阳性对照——用真数据造出两组量纲差很远的窗口，聚类必须把它们分开。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from intelligence.services.market_regime_analogs import standardize_vectors
from intelligence.services.river_window import (
    BY_NAME,
    FEATURE_NAMES,
    build_daily_vectors,
    cluster_windows,
    distance_matrix,
    window_features,
    windows_around,
)

DB = Path("db/market_feature_store.duckdb")
pytestmark = pytest.mark.skipif(not DB.exists(), reason="需要真库 db/market_feature_store.duckdb")


@pytest.fixture(scope="module")
def daily() -> list[dict]:
    return build_daily_vectors()


@pytest.fixture(scope="module")
def z_rows(daily: list[dict]) -> list[dict]:
    rows, _ = standardize_vectors(daily, FEATURE_NAMES)
    return rows


def test_缺数留_None_不补零(daily: list[dict]) -> None:
    """补零会把「这天没数据」变成真实极值：资金轨只有 12% 的日子有数，
    补零等于造出 360 多天的假极值，标准化后必然主导聚类。"""
    missing = [r for r in daily if r["theme_net_flow"] is None]
    assert missing, "资金轨已经全覆盖了？请复核 fact_theme_flow_daily"
    assert all(r["theme_net_flow"] is None for r in missing)
    assert not any(r["theme_net_flow"] == 0 for r in missing)


def test_区间特征可回溯到表和列(daily: list[dict], z_rows: list[dict]) -> None:
    wf = window_features(daily, "2026-08-17", "2026-09-02", z_rows=z_rows)
    assert wf is not None
    assert wf.provenance, "签名里一维都没有，回溯链是空的"
    for item in wf.provenance:
        spec = BY_NAME[item["feature"]]
        # 聚合特征（如带谓词的 COUNT）没有单一列，所以只钉「指向一张真表或用户态文件」，
        # 具体怎么算由 rule 说清——两者缺一，聚类结果就拆不回主数据。
        assert item["source"].startswith("fact_") or item["source"].endswith(".jsonl"), item
        assert item["rule"], f"{spec.name} 没写清怎么算的，聚类结果就拆不回去"
        assert item["track"] in {"market", "theme", "opinion", "capital", "stock", "judgment"}


def test_退出签名的维度必须如实报而不是当成零(daily: list[dict], z_rows: list[dict]) -> None:
    wf = window_features(daily, "2025-01-02", "2025-03-31", z_rows=z_rows)
    assert wf is not None
    assert wf.dropped_dims, "这个区间应当有覆盖不足的维度（舆论/资金当时还没数据）"
    for name in wf.dropped_dims:
        assert name not in wf.signature.stats
        # 退出的原因必须是覆盖率，而不是被静默丢掉
        assert wf.coverage[name] < 1.0


def test_窗口按交易日取而不是自然日(daily: list[dict], z_rows: list[dict]) -> None:
    """跨节假日时自然日窗口长度会不同，距离就变成在比窗口长度。"""
    wins = windows_around(daily, ["2026-01-06", "2026-06-15"], after=9, z_rows=z_rows)
    assert len(wins) == 2
    assert {w.n_days for w in wins} == {10}


def test_聚类幂等(daily: list[dict], z_rows: list[dict]) -> None:
    anchors = ["2025-05-06", "2025-09-05", "2026-01-06", "2026-04-30", "2026-08-20"]
    wins = windows_around(daily, anchors, z_rows=z_rows)
    a, _ = cluster_windows(wins)
    b, _ = cluster_windows(wins)
    assert [[m.label for m in c.members] for c in a] == [[m.label for m in c.members] for c in b]


def test_阳性对照_量纲差很远的窗口必须被分开(daily: list[dict], z_rows: list[dict]) -> None:
    """取成交额最高与最低的各 3 天做锚点：它们若被并进同一簇，说明距离没在起作用。"""
    have = [r for r in daily if r["total_amount"] is not None]
    ordered = sorted(have, key=lambda r: r["total_amount"])
    lows = [r["trade_date"] for r in ordered[:3]]
    highs = [r["trade_date"] for r in ordered[-3:]]
    wins = windows_around(daily, lows + highs, after=4, z_rows=z_rows)
    clusters, _ = cluster_windows(wins, threshold=0.5)
    label_to_cluster = {m.label: i for i, c in enumerate(clusters) for m in c.members}
    low_ids = {label_to_cluster[d] for d in lows if d in label_to_cluster}
    high_ids = {label_to_cluster[d] for d in highs if d in label_to_cluster}
    assert low_ids and high_ids
    assert not (low_ids & high_ids), "极高与极低成交额的窗口被聚到了同一簇，距离没起作用"


def test_阴性对照_阈值放大后会并成一簇(daily: list[dict], z_rows: list[dict]) -> None:
    """反方向：阈值足够大时必须能并起来，否则说明聚类根本没在合并。"""
    anchors = ["2025-05-06", "2025-09-05", "2026-01-06", "2026-04-30", "2026-08-20"]
    wins = windows_around(daily, anchors, z_rows=z_rows)
    clusters, _ = cluster_windows(wins, threshold=1e6)
    assert len(clusters) == 1
    assert clusters[0].size == len(wins)


def test_无共有维的窗口单列而不是塞进簇(daily: list[dict], z_rows: list[dict]) -> None:
    """不可比 ≠ 距离很远。距离矩阵里的 None 必须传导成 orphan，不能当大数处理。"""
    wins = windows_around(daily, ["2025-01-06", "2026-08-20"], z_rows=z_rows)
    dm = distance_matrix(wins)
    assert all(dm[i][i] == 0.0 for i in range(len(wins)))
    clusters, orphan = cluster_windows(wins)
    assert len(clusters) + len(orphan) >= 1
    for w in orphan:
        assert all(
            dm[i][j] is None
            for i, x in enumerate(wins)
            if x.label == w.label
            for j in range(len(wins))
            if j != i
        )
