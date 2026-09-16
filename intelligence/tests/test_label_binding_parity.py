"""标签层（旁路库 SQL）与 River 绑定层（内存 payload）必须给出同一个真值。

为什么要专门钉：同名同版本的标签走两条路径——``methodology_backtest.labels`` 的 SQL 产出
``history_labels`` 供规则编译器用，``river_derive.bind`` 从切片 payload 现算供情景树分枝与
区间派生用——而派生对象照样标 ``label_version``。两边口径不一致时，「同一个标签」在两条
路径上得到不同真值，且**没有任何地方会报错**（09-12 复核抓到：`pct=1 / diff=NULL /
amount=100` 时标签层判 0、绑定层判「未知」，恰好是三值逻辑修好一半的形状）。

做法：同一组输入分别喂两条路径，逐格比对。SQL 那条走真 DuckDB（真库形状太贵，用最小
合成库），绑定那条走内存切片。
"""

from __future__ import annotations


import duckdb
import pytest

from intelligence.services.methodology_backtest.labels import build_labels
from intelligence.services.river import Gap, RiverObject, RiverSlice
from intelligence.services.river_derive import bind
from market_feature_store.db import init_db

DAY = "2026-09-01"
PREV = "2026-08-31"

# (pct_chg, amount, diff_ratio)；None = 该字段缺失。覆盖三值逻辑的每一格。
CASES: dict[str, tuple[float | None, float | None, float | None]] = {
    "full_yes": (1.0, 900.0, 20.0),          # 全已知、全为真 → True
    "full_no_diff": (1.0, 900.0, 5.0),       # 全已知、diff 不够 → False
    "amount_low_diff_null": (1.0, 100.0, None),   # amount 已知为假 → False（不必知道 diff）
    "pct_down_diff_null": (-1.0, 900.0, None),    # pct 已知为假 → False
    "diff_low_pct_null": (None, 900.0, 3.0),      # diff 已知为假 → False
    "all_pass_but_diff_null": (1.0, 900.0, None),  # 已知的都为真、仍有缺失 → None
    "amount_null_others_pass": (1.0, None, 20.0),  # 同上，缺的是 amount → None
}


@pytest.fixture(scope="module")
def sql_labels(tmp_path_factory: pytest.TempPathFactory) -> dict[str, float | None]:
    """把 CASES 灌进最小合成库，跑真 ``build_labels``，读回 ``dual_red_strict``。"""
    root = tmp_path_factory.mktemp("parity")
    src, lab = root / "src.duckdb", root / "labels.duckdb"
    con = duckdb.connect(str(src))
    try:
        init_db(con)
        for d in (PREV, DAY):
            con.execute(
                "INSERT INTO fact_market_daily (trade_date, market_stage, total_amount, advancers) VALUES (?,?,?,?)",
                [d, "主升阶段", 10000.0, 2000],
            )
        rows = []
        for code, (pct, amt, diff) in CASES.items():
            for d in (PREV, DAY):
                rows.append((d, "legacy", f"{code}.TI", code, pct, amt, diff, None))
        con.executemany(
            "INSERT INTO fact_sector_daily_generation (trade_date, sector_universe_snapshot_id,"
            " sector_ts_code, sector_name, pct_chg, amount, diff_ratio, multi_period_resonance)"
            " VALUES (?,?,?,?,?,?,?,?)",
            rows,
        )
    finally:
        con.close()
    build_labels(src, lab)
    con = duckdb.connect(str(lab), read_only=True)
    try:
        got = {}
        for code in CASES:
            row = con.execute(
                "SELECT value_num FROM history_labels WHERE entity_id=? AND label='dual_red_strict' AND trade_date=?",
                [f"{code}.TI", DAY],
            ).fetchone()
            got[code] = None if row is None else row[0]
        return got
    finally:
        con.close()


def _slice_for(pct: float | None, amt: float | None, diff: float | None) -> RiverSlice:
    payload = {"pct_chg": pct, "amount": amt, "diff_ratio": diff}
    market = [
        RiverObject(
            track="market", entity_id="E", object_type="label",
            ref=f"fact_sector_daily:{DAY}:E", source_hash="h1",
            valid_from=DAY, recorded_at=f"{DAY}T18:00:00", payload=payload,
        )
    ]
    tracks: dict = {t: Gap(t, "no_data", "fixture") for t in ("theme", "opinion", "capital", "stock", "judgment")}  # type: ignore[arg-type]
    tracks["market"] = market
    return RiverSlice(as_of=DAY, entity_id="E", entity_name="E", knowledge_cutoff=DAY, tracks=tracks)


def test_river_derive_matches_labels_layer(sql_labels: dict[str, float | None]) -> None:
    """逐格比对：SQL 的 1/0/NULL 与绑定层的 True/False/None 必须一一对应。"""
    mismatches = []
    for code, (pct, amt, diff) in CASES.items():
        sql_value = sql_labels[code]
        expected = None if sql_value is None else bool(sql_value)
        bound, refs = bind("dual_red_strict", _slice_for(pct, amt, diff))
        if bound != expected:
            mismatches.append(f"{code}: SQL={sql_value!r}→{expected!r} vs 绑定={bound!r}")
        assert refs, f"{code}: 绑定必须带 member ref"
    assert not mismatches, "标签层与 River 绑定层判断不一致：\n" + "\n".join(mismatches)


def test_parity_covers_every_three_valued_branch(sql_labels: dict[str, float | None]) -> None:
    """夹具本身要真的覆盖三种结局，否则这条一致性测试可能在只有一种值时假绿。"""
    values = {sql_labels[c] for c in CASES}
    assert values == {0.0, 1.0, None}, values
