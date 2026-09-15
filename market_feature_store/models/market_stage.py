"""周期阶段（market_stage）分类器 v1：numpy 多分类逻辑回归，监督 = fupanhui 历史标签。

为什么是自己训：fupanhui 账号风控后周期阶段没有来源；价格趋势手写规则 7 类一致率 37%、粗粒度 58%。
本模型（2026-09-07，343 个可用标签日，按时间分块 5 折）：**精确 ≈42%，粗粒度（上行/下行/横盘）≈51%**——
只比规则略好，最近一块（2026-05-28~09-02）只有 ~20%。所以：
- 写库时带 ``market_stage_source='local:stage-lr-v1'`` 与 ``market_stage_confidence``，日报读得到这是自家低置信标签；
- 每天 ``qa_local_vs_fupanhui.py`` 在有 fupanhui 标签的日子上出一致率；标签多了 ``train`` 重训，权重 JSON 进仓可复现。

特征全部来自本地表：上证收盘链（fact_market_daily.sh_index_close）、量能/涨家数/涨跌停/强度/前三行业占比、
全A等权涨跌与广度（fact_stock_daily）。推断时用「滞回」平滑：新阶段概率要比当前阶段高出 HYSTERESIS 才切换，
stage_day 按切换后累计。
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import numpy as np

from ..db import connect, init_db

CLASSES = ["主升阶段", "反弹阶段", "横盘阶段", "顶部横盘阶段", "底部横盘阶段", "探底阶段", "下跌阶段"]
NORMALIZE = {"主升": "主升阶段", "下跌": "下跌阶段", "探底": "探底阶段", "反弹": "反弹阶段", "顶部横盘": "顶部横盘阶段", "横盘": "横盘阶段"}
COARSE = {"主升阶段": "上行", "反弹阶段": "上行", "横盘阶段": "横盘", "顶部横盘阶段": "横盘", "底部横盘阶段": "横盘",
          "探底阶段": "下行", "下跌阶段": "下行"}
FEATURES = ["ret1", "ret5", "ret20", "ret60", "c_ma5", "c_ma20", "c_ma60", "ma20_slope5", "ma60_slope10", "pos60", "dd60", "up60",
            "vol20", "volume_ratio", "amt_vs_y", "breadth", "breadth5", "breadth20", "log_lu", "log_ld", "lu5", "strength", "top3",
            "eqw_ret1", "eqw_ret5", "eqw_ret20", "above20", "above20_5", "nh20", "nh20_5"]
ARTIFACT = Path(__file__).with_name("market_stage_lr_v1.json")
SOURCE = "local:stage-lr-v1"
HYSTERESIS = 0.15
STAGE_COLUMNS = {"market_stage_source": "TEXT", "market_stage_confidence": "DOUBLE"}


def ensure_stage_columns(con) -> None:
    for name, typ in STAGE_COLUMNS.items():
        con.execute(f"ALTER TABLE fact_market_daily ADD COLUMN IF NOT EXISTS {name} {typ}")


def normalize_label(label) -> str | None:
    if not label:
        return None
    return NORMALIZE.get(str(label), str(label))


# ---------------------------------------------------------------------------
# 特征
# ---------------------------------------------------------------------------
def _roll(a: np.ndarray, w: int, fn) -> np.ndarray:
    out = np.full_like(a, np.nan, dtype=float)
    for i in range(w - 1, len(a)):
        out[i] = fn(a[i - w + 1:i + 1])
    return out


def build_feature_frame(con, end_date=None) -> tuple[list[str], np.ndarray, np.ndarray]:
    """返回 (日期列表, 特征矩阵, 标签索引数组；无标签为 -1)。按 fact_market_daily 有上证收盘的日子排。"""
    params = []
    where = "sh_index_close IS NOT NULL"
    if end_date is not None:
        where += " AND trade_date <= ?"
        params.append(end_date)
    cols = {r[0] for r in con.execute("DESCRIBE fact_market_daily").fetchall()}
    src_col = "market_stage_source" if "market_stage_source" in cols else "CAST(NULL AS VARCHAR)"  # 老库/只读连接尚未加列
    rows = con.execute(
        f"""
        SELECT CAST(trade_date AS VARCHAR), sh_index_close, market_stage, volume_ratio, amount_vs_yesterday_pct, advancers, limit_up, limit_down,
               strength_avg_pct, top3_industry_ratio,
               (SELECT COUNT(*) FROM fact_stock_daily s WHERE s.trade_date = m.trade_date) AS n_stocks,
               {src_col} AS market_stage_source
        FROM fact_market_daily m WHERE {where} ORDER BY trade_date
        """,
        params,
    ).fetchall()
    dates = [r[0] for r in rows]
    n = len(rows)
    close = np.array([r[1] for r in rows], dtype=float)
    br = con.execute(
        """
        WITH s AS (
          SELECT trade_date, stock_ts_code, close, pct_chg,
                 AVG(close) OVER (PARTITION BY stock_ts_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) ma20,
                 MAX(close) OVER (PARTITION BY stock_ts_code ORDER BY trade_date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) hi20
          FROM fact_stock_daily WHERE trade_date >= CAST(? AS DATE) - INTERVAL 40 DAY AND stock_ts_code NOT LIKE '%.BJ')
        SELECT CAST(trade_date AS VARCHAR), AVG(pct_chg), AVG(CASE WHEN close > ma20 THEN 1 ELSE 0 END), AVG(CASE WHEN close > hi20 THEN 1 ELSE 0 END)
        FROM s GROUP BY 1
        """,
        [dates[0] if dates else date.today()],
    ).fetchall()
    brm = {d: (a, b, c) for d, a, b, c in br}
    eqw = np.array([(brm[d][0] or 0) / 100 if d in brm and brm[d][0] is not None else np.nan for d in dates], dtype=float)
    above20 = np.array([brm[d][1] if d in brm else np.nan for d in dates], dtype=float)
    nh20 = np.array([brm[d][2] if d in brm else np.nan for d in dates], dtype=float)
    eqw_idx = np.cumprod(1 + np.nan_to_num(eqw))
    ret1 = np.concatenate([[np.nan], close[1:] / close[:-1] - 1])
    ma5, ma20, ma60 = _roll(close, 5, np.mean), _roll(close, 20, np.mean), _roll(close, 60, np.mean)
    hi60, lo60 = _roll(close, 60, np.max), _roll(close, 60, np.min)
    vol20 = _roll(ret1, 20, np.nanstd)
    breadth = np.array([(r[5] / r[10]) if (r[5] is not None and r[10]) else np.nan for r in rows], dtype=float)
    lu = np.array([r[6] if r[6] is not None else np.nan for r in rows], dtype=float)
    X = np.full((n, len(FEATURES)), np.nan)
    for i, r in enumerate(rows):
        f = {
            "ret1": ret1[i],
            "ret5": close[i] / close[i - 5] - 1 if i >= 5 else np.nan,
            "ret20": close[i] / close[i - 20] - 1 if i >= 20 else np.nan,
            "ret60": close[i] / close[i - 60] - 1 if i >= 60 else np.nan,
            "c_ma5": close[i] / ma5[i] - 1, "c_ma20": close[i] / ma20[i] - 1, "c_ma60": close[i] / ma60[i] - 1,
            "ma20_slope5": ma20[i] / ma20[i - 5] - 1 if i >= 5 else np.nan,
            "ma60_slope10": ma60[i] / ma60[i - 10] - 1 if i >= 10 else np.nan,
            "pos60": (close[i] - lo60[i]) / (hi60[i] - lo60[i]) if hi60[i] > lo60[i] else np.nan,
            "dd60": close[i] / hi60[i] - 1, "up60": close[i] / lo60[i] - 1, "vol20": vol20[i],
            "volume_ratio": r[3] / 100 if r[3] is not None else np.nan,
            "amt_vs_y": r[4] / 100 if r[4] is not None else np.nan,
            "breadth": breadth[i], "breadth5": np.nanmean(breadth[max(0, i - 4):i + 1]), "breadth20": np.nanmean(breadth[max(0, i - 19):i + 1]),
            "log_lu": np.log1p(r[6]) if r[6] is not None else np.nan, "log_ld": np.log1p(r[7]) if r[7] is not None else np.nan,
            "lu5": np.log1p(np.nanmean(lu[max(0, i - 4):i + 1])) if not np.isnan(lu[max(0, i - 4):i + 1]).all() else np.nan,
            "strength": r[8] / 10 if r[8] is not None else np.nan, "top3": r[9] / 100 if r[9] is not None else np.nan,
            "eqw_ret1": eqw[i], "eqw_ret5": eqw_idx[i] / eqw_idx[i - 5] - 1 if i >= 5 else np.nan,
            "eqw_ret20": eqw_idx[i] / eqw_idx[i - 20] - 1 if i >= 20 else np.nan,
            "above20": above20[i], "above20_5": np.nanmean(above20[max(0, i - 4):i + 1]),
            "nh20": nh20[i], "nh20_5": np.nanmean(nh20[max(0, i - 4):i + 1]),
        }
        X[i] = [f[k] for k in FEATURES]
    # 只把 fupanhui（非 local）标签当监督
    y = np.array([
        CLASSES.index(normalize_label(r[2])) if (r[2] and normalize_label(r[2]) in CLASSES and not str(r[11] or "").startswith("local:")) else -1
        for r in rows
    ])
    return dates, X, y


# ---------------------------------------------------------------------------
# 模型
# ---------------------------------------------------------------------------
def _fit(X: np.ndarray, y: np.ndarray, l2: float = 1.0, epochs: int = 4000, lr: float = 0.01):
    k = len(CLASSES)
    mu, sd = X.mean(0), X.std(0) + 1e-9
    Z = np.hstack([(X - mu) / sd, np.ones((len(X), 1))])
    W = np.zeros((Z.shape[1], k))
    counts = np.bincount(y, minlength=k).astype(float)
    cw = (len(y) / (k * np.maximum(counts, 1)))[y]
    Y = np.eye(k)[y]
    for _ in range(epochs):
        S = Z @ W
        P = np.exp(S - S.max(1, keepdims=True))
        P /= P.sum(1, keepdims=True)
        G = Z.T @ ((P - Y) * cw[:, None]) / len(Z) + l2 * np.vstack([W[:-1], np.zeros((1, k))]) / len(Z)
        W -= lr * np.clip(G, -5, 5)
    return {"mu": mu.tolist(), "sd": sd.tolist(), "W": W.tolist()}


def _proba(model: dict, X: np.ndarray) -> np.ndarray:
    mu, sd, W = np.array(model["mu"]), np.array(model["sd"]), np.array(model["W"])
    Z = np.hstack([(X - mu) / sd, np.ones((len(X), 1))])
    S = Z @ W
    P = np.exp(S - S.max(1, keepdims=True))
    return P / P.sum(1, keepdims=True)


def train(con=None, out_path: Path = ARTIFACT, folds: int = 5) -> dict:
    """在全部 fupanhui 标签日上训练并导出 JSON；同时给出分块时间 CV 读数写进产物。"""
    own = con is None
    if own:
        init_db()
        con = connect(read_only=True)
    try:
        dates, X, y = build_feature_frame(con)
    finally:
        if own:
            con.close()
    valid = (y >= 0) & ~np.isnan(X).any(axis=1)
    idx = np.where(valid)[0]
    if len(idx) < 100:
        raise RuntimeError(f"可用标签日只有 {len(idx)}，不训")
    blocks = np.array_split(idx, folds)
    acc, cacc = [], []
    for te in blocks:
        te_set = set(te.tolist())
        tr = np.array([i for i in idx if i not in te_set])
        m = _fit(X[tr], y[tr])
        pred = _proba(m, X[te]).argmax(1)
        acc.append(float(np.mean(pred == y[te])))
        cacc.append(float(np.mean([COARSE[CLASSES[a]] == COARSE[CLASSES[b]] for a, b in zip(pred, y[te])])))
    model = _fit(X[idx], y[idx])
    artifact = {
        "version": "stage-lr-v1", "trained_at": datetime.now().isoformat(timespec="seconds"),
        "classes": CLASSES, "features": FEATURES, "model": model,
        "train_days": int(len(idx)), "train_range": [dates[idx[0]], dates[idx[-1]]],
        "cv": {"folds": folds, "exact_acc_mean": float(np.mean(acc)), "coarse_acc_mean": float(np.mean(cacc)),
               "exact_acc_by_block": acc, "coarse_acc_by_block": cacc},
        "baselines": {"hand_rule_exact": 0.37, "hand_rule_coarse": 0.58},
    }
    Path(out_path).write_text(json.dumps(artifact, ensure_ascii=False, indent=1), encoding="utf-8")
    return artifact


def load_artifact(path: Path = ARTIFACT) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def predict_stage(trade_date, *, con=None, artifact: dict | None = None, write: bool = True) -> dict:
    """预测某日阶段并（默认）写回 fact_market_daily：market_stage / stage_day / market_stage_source / market_stage_confidence。

    滞回：若前一日已有阶段（fupanhui 的或本地的），新阶段概率需高出前一日阶段概率 HYSTERESIS 才切换。
    有 fupanhui 标签的日子不覆盖（那是监督源）。
    """
    td = trade_date if isinstance(trade_date, date) else date.fromisoformat(str(trade_date)[:10])
    own = con is None
    if own:
        init_db()
        con = connect()
    try:
        ensure_stage_columns(con)
        art = artifact or load_artifact()
        dates, X, _y = build_feature_frame(con, end_date=td)
        if not dates or dates[-1] != td.isoformat():
            raise RuntimeError(f"{td} fact_market_daily 无上证收盘行，先跑 index-daily")
        x = X[-1:]
        if np.isnan(x).any():
            missing = [f for f, v in zip(FEATURES, x[0]) if np.isnan(v)]
            raise RuntimeError(f"{td} 特征缺失: {missing}")
        p = _proba(art["model"], x)[0]
        cur = con.execute(
            "SELECT market_stage, market_stage_source, stage_day FROM fact_market_daily WHERE trade_date = ?", [td]
        ).fetchone()
        if cur and cur[0] and not str(cur[1] or "").startswith("local:"):
            return {"trade_date": td.isoformat(), "action": "kept-fupanhui-label", "market_stage": cur[0]}
        prev = con.execute(
            "SELECT market_stage, stage_day FROM fact_market_daily WHERE trade_date < ? AND market_stage IS NOT NULL ORDER BY trade_date DESC LIMIT 1",
            [td],
        ).fetchone()
        best = int(p.argmax())
        label = CLASSES[best]
        prev_label = normalize_label(prev[0]) if prev else None
        if prev_label in CLASSES:
            pi = CLASSES.index(prev_label)
            if p[best] < p[pi] + HYSTERESIS:
                label = prev_label
        stage_day = (int(prev[1] or 0) + 1) if (prev and prev_label == label) else 1
        conf = round(float(p[CLASSES.index(label)]), 3)
        if write:
            con.execute(
                "UPDATE fact_market_daily SET market_stage = ?, stage_day = ?, market_stage_source = ?, market_stage_confidence = ? WHERE trade_date = ?",
                [label, stage_day, SOURCE, conf, td],
            )
        return {"trade_date": td.isoformat(), "action": "written" if write else "predicted", "market_stage": label, "stage_day": stage_day,
                "confidence": conf, "argmax": CLASSES[best], "proba": {c: round(float(v), 3) for c, v in zip(CLASSES, p)},
                "prev_stage": prev_label}
    finally:
        if own:
            con.close()
