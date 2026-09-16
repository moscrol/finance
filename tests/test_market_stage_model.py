"""周期阶段自训分类器 v1：标签归一、可分数据能学到、滞回与 stage_day、不覆盖 fupanhui 标签。"""
from __future__ import annotations

import duckdb
import numpy as np

from market_feature_store.db import init_db
from market_feature_store.models import market_stage as ms


def test_normalize_label_maps_short_forms():
    assert ms.normalize_label("主升") == "主升阶段" and ms.normalize_label("顶部横盘") == "顶部横盘阶段"
    assert ms.normalize_label("底部横盘阶段") == "底部横盘阶段" and ms.normalize_label(None) is None


def test_fit_learns_separable_toy_problem():
    rng = np.random.default_rng(0)
    k = len(ms.CLASSES)
    centers = rng.normal(size=(k, len(ms.FEATURES))) * 3
    y = np.repeat(np.arange(k), 30)
    X = centers[y] + rng.normal(scale=0.3, size=(len(y), len(ms.FEATURES)))
    model = ms._fit(X, y, epochs=1500, lr=0.05)
    pred = ms._proba(model, X).argmax(1)
    assert np.mean(pred == y) > 0.95
    assert len(model["W"]) == len(ms.FEATURES) + 1 and len(model["W"][0]) == k


def _con_with_rows():
    con = duckdb.connect()
    init_db(con)
    con.execute("INSERT INTO fact_market_daily (trade_date, sh_index_close, market_stage, stage_day, market_stage_source) VALUES ('2026-09-02', 3941.0, '底部横盘阶段', 4, NULL)")
    con.execute("INSERT INTO fact_market_daily (trade_date, sh_index_close) VALUES ('2026-09-03', 3942.0)")
    return con


def test_predict_applies_hysteresis_and_stage_day(monkeypatch):
    con = _con_with_rows()
    k = len(ms.CLASSES)
    x = np.zeros((1, len(ms.FEATURES)))
    monkeypatch.setattr(ms, "build_feature_frame", lambda con_, end_date=None: (["2026-09-02", "2026-09-03"], np.vstack([x, x]), np.array([-1, -1])))
    # 概率：下跌 0.40、底部横盘 0.35 → 差 0.05 < 0.15 → 滞回保留底部横盘，stage_day 4→5
    p = np.full(k, 0.05)
    p[ms.CLASSES.index("下跌阶段")] = 0.40
    p[ms.CLASSES.index("底部横盘阶段")] = 0.35
    monkeypatch.setattr(ms, "_proba", lambda model, X: np.vstack([p / p.sum()] * len(X)))
    r = ms.predict_stage("2026-09-03", con=con, artifact={"model": {}})
    assert r["market_stage"] == "底部横盘阶段" and r["stage_day"] == 5 and r["argmax"] == "下跌阶段"
    row = con.execute("SELECT market_stage, stage_day, market_stage_source FROM fact_market_daily WHERE trade_date='2026-09-03'").fetchone()
    assert row == ("底部横盘阶段", 5, ms.SOURCE)
    # 概率拉开 → 切换，stage_day 归 1
    p2 = np.full(k, 0.02)
    p2[ms.CLASSES.index("下跌阶段")] = 0.70
    monkeypatch.setattr(ms, "_proba", lambda model, X: np.vstack([p2 / p2.sum()] * len(X)))
    r2 = ms.predict_stage("2026-09-03", con=con, artifact={"model": {}})
    assert r2["market_stage"] == "下跌阶段" and r2["stage_day"] == 1 and r2["confidence"] > 0.6


def test_predict_never_overwrites_fupanhui_label(monkeypatch):
    con = _con_with_rows()
    con.execute("UPDATE fact_market_daily SET market_stage='主升阶段', market_stage_source='fupanhui:reviews' WHERE trade_date='2026-09-03'")
    monkeypatch.setattr(ms, "build_feature_frame", lambda con_, end_date=None: (["2026-09-03"], np.zeros((1, len(ms.FEATURES))), np.array([-1])))
    monkeypatch.setattr(ms, "_proba", lambda model, X: np.full((len(X), len(ms.CLASSES)), 1 / len(ms.CLASSES)))
    r = ms.predict_stage("2026-09-03", con=con, artifact={"model": {}})
    assert r["action"] == "kept-fupanhui-label"
    assert con.execute("SELECT market_stage FROM fact_market_daily WHERE trade_date='2026-09-03'").fetchone()[0] == "主升阶段"
