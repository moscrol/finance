"""多维对照镜头:证明它让 agent 看见标量距离藏起来的东西。

这里的核心不是「新模块能跑」,是**构造一个标量距离会骗人的局**,
然后验证:旧读数(一个距离 + top-K)会选错,新读数把选错的理由摆在明面上。
"""

from __future__ import annotations

import json

import pytest

from intelligence.services.market_regime_analogs import (
    signature_distance,
    standardize_vectors,
    window_signature,
)
from intelligence.services.river_lens import (
    build_lens,
    decompose,
    dimension_groups,
    landscape,
    lens_block,
)

FEATS = ("breadth_a", "breadth_b", "breadth_c", "flow", "opinion", "stock")


def _rng(seed: int):
    """确定性 LCG —— 测试不许依赖全局随机状态。"""

    state = seed

    def nxt() -> float:
        nonlocal state
        state = (1103515245 * state + 12345) % (2 ** 31)
        return state / (2 ** 31) - 0.5

    return nxt


def _history() -> list[dict]:
    """300 天历史。

    **刻意造的结构:**
    - ``breadth_a/b/c`` 共享同一条基序列(只差一点噪声)⇒ 它们在历史上几乎是同一件事
    - ``flow`` / ``opinion`` / ``stock`` 各自独立

    然后放两个候选窗口:
    - **窗口 A**:三个 breadth 维与当下完全吻合,另外三维都差一截 → **标量距离更小**
    - **窗口 B**:flow/opinion/stock 三维吻合,三个 breadth 都差 → **标量距离更大**

    A 的「3 个维度吻合」其实是**一件事**吻合;B 的「3 个维度吻合」是**三件独立的事**
    都吻合。标量距离把这个区别抹掉了,而且抹掉之后**排名是反的**。
    """

    nxt = _rng(7)
    rows: list[dict] = []
    for i in range(300):
        base = nxt() * 4  # 三个 breadth 维共享
        rows.append(
            {
                "trade_date": f"2024-{1 + i // 31:02d}-{1 + i % 31:02d}",
                "breadth_a": base + nxt() * 0.05,
                "breadth_b": base + nxt() * 0.05,
                "breadth_c": base + nxt() * 0.05,
                "flow": nxt() * 4,
                "opinion": nxt() * 4,
                "stock": nxt() * 4,
            }
        )

    def paint(lo: int, hi: int, breadth: float, other: float) -> None:
        for i in range(lo, hi):
            rows[i].update(
                breadth_a=breadth, breadth_b=breadth, breadth_c=breadth,
                flow=other, opinion=other, stock=other,
            )

    paint(100, 110, breadth=3.0, other=0.3)   # 窗口 A
    paint(200, 210, breadth=0.0, other=3.0)   # 窗口 B
    paint(290, 300, breadth=3.0, other=3.0)   # 当下
    return rows


CURRENT = ("2024-10-15", "2024-10-24")
WINDOW_A = ("2024-04-11", "2024-04-20")
WINDOW_B = ("2024-07-20", "2024-07-29")


def _spans(rows: list[dict]) -> tuple[tuple[str, str], tuple[str, str], tuple[str, str]]:
    return (
        (rows[290]["trade_date"], rows[299]["trade_date"]),
        (rows[100]["trade_date"], rows[109]["trade_date"]),
        (rows[200]["trade_date"], rows[209]["trade_date"]),
    )


# --------------------------------------------------------------------------- #
def test_three_breadth_dims_are_one_thing_not_three() -> None:
    """名义 6 维,实际 4 组 —— 不知道这件事就会把一件事数成三件。"""

    rows = _history()
    z, _ = standardize_vectors(rows, FEATS)
    st = dimension_groups(z, FEATS)

    assert st.nominal_dims == 6
    assert st.effective_dims == 4, f"应塌成 4 组，实得 {[g.members for g in st.groups]}"
    big = next(g for g in st.groups if g.size > 1)
    assert set(big.members) == {"breadth_a", "breadth_b", "breadth_c"}
    assert big.max_abs_r is not None and big.max_abs_r > 0.95
    # 三个独立维各自成组
    singles = {g.members[0] for g in st.groups if g.size == 1}
    assert singles == {"flow", "opinion", "stock"}


def test_scalar_distance_ranks_the_weaker_match_first() -> None:
    """**先把「标量距离会骗人」钉死** —— 否则后面的演示没有意义。"""

    rows = _history()
    cur_s, a_s, b_s = _spans(rows)
    z, _ = standardize_vectors(rows, FEATS)

    def sig(span):
        idx = [i for i, r in enumerate(rows) if span[0] <= r["trade_date"] <= span[1]]
        return window_signature([z[i] for i in idx], FEATS)

    cur, a, b = sig(cur_s), sig(a_s), sig(b_s)
    da = signature_distance(cur, a, len(FEATS))
    db = signature_distance(cur, b, len(FEATS))
    assert da is not None and db is not None
    assert da < db, "构造失败：A 必须在标量距离上排前面，演示才成立"


def test_lens_shows_different_correlation_group_counts_not_independence() -> None:
    """同一份数据给出相关分组，不把组数当独立证据认证。"""

    rows = _history()
    cur_s, a_s, b_s = _spans(rows)
    res = build_lens(
        rows, FEATS,
        current=cur_s,
        candidates=[("窗口A", *a_s), ("窗口B", *b_s)],
        knowledge_cutoff="2024-10-24",
    )
    by = {c.label: c.decomposition for c in res.candidates}
    assert set(by) == {"窗口A", "窗口B"}

    # 旧视角：A 的距离更小，排第一
    assert by["窗口A"].total < by["窗口B"].total
    assert res.candidates[0].label == "窗口A"

    assert len(by["窗口A"].low_contribution) == 3
    assert len(by["窗口B"].low_contribution) == 3
    assert len(by["窗口A"].low_contribution_groups) == 1
    assert len(by["窗口B"].low_contribution_groups) == 3

    assert {d.feature for d in by["窗口A"].high_contribution} == {"flow", "opinion", "stock"}
    assert {d.feature for d in by["窗口B"].high_contribution} == {
        "breadth_a", "breadth_b", "breadth_c"
    }


def test_block_delivers_same_group_and_contribution_objects() -> None:
    """递给agent的读数可逐项反查同一对象，不靠旧排版字符串验收。"""

    rows = _history()
    cur_s, a_s, b_s = _spans(rows)
    res = build_lens(
        rows, FEATS, current=cur_s,
        candidates=[("窗口A", *a_s), ("窗口B", *b_s)],
        knowledge_cutoff="2024-10-24",
        labels={"breadth_a": "涨停", "breadth_b": "连板", "breadth_c": "新高",
                "flow": "资金", "opinion": "舆论", "stock": "个股"},
    )
    text = lens_block(res)

    payload = json.loads(text.split("```json\n")[1].split("\n```")[0])
    assert payload == res.model_payload()
    assert len(payload["dimension_structure"]["groups"]) == 4
    assert ["涨停", "连板", "新高"] in payload["dimension_structure"]["groups"]
    table = payload["candidates"]
    candidates = {ref: dict(zip(table["columns"], row, strict=True)) for ref, row in table["windows"].items()}
    by = {c["label"]: c for c in candidates.values()}
    assert by["窗口A"]["low_contribution_groups"] == 1
    assert by["窗口B"]["low_contribution_groups"] == 3
    a_id = next(k for k, c in candidates.items() if c["label"] == "窗口A")
    cols = payload["signatures"]["columns"]
    rows = [dict(zip(cols, row, strict=True)) for row in payload["signatures"]["windows"][a_id]]
    high = [r["feature"] for r in rows if r["contribution_band"] == "high"]
    assert set(high) == {"资金", "舆论", "个股"}
    assert "不是概率预测" in text


def test_decomposition_sums_to_the_same_distance_no_second_metric() -> None:
    """**不建第二套距离**:分解只是把 signature_distance 的和式拆开。"""

    rows = _history()
    cur_s, a_s, _ = _spans(rows)
    z, _ = standardize_vectors(rows, FEATS)

    def sig(span):
        idx = [i for i, r in enumerate(rows) if span[0] <= r["trade_date"] <= span[1]]
        return window_signature([z[i] for i in idx], FEATS)

    cur, a = sig(cur_s), sig(a_s)
    dec = decompose(cur, a, len(FEATS))
    assert dec.total == pytest.approx(signature_distance(cur, a, len(FEATS)))
    assert dec.to_dict()["total_dims"] == len(FEATS)  # 保留覆盖率惩罚的分母，消费方才能复算。

    used = len(dec.shared)
    hand = (sum(d.contribution for d in dec.dims) / used) * (len(FEATS) / used)
    assert hand == pytest.approx(dec.total), "逐维贡献之和必须还原成同一个距离"


def test_landscape_retains_legacy_number_but_withdraws_qualification() -> None:
    tight = landscape([0.10] + [2.0 + i * 0.01 for i in range(200)])
    flat = landscape([1.0 + i * 0.001 for i in range(200)])
    assert tight.standout >= 1.0 and flat.standout < 0.2
    assert tight.to_dict()["interpretation"] == flat.to_dict()["interpretation"] == "descriptive_only"
    assert "standout" not in tight.to_dict()
    assert "绝对相似" in tight.reading


def test_undetermined_pairs_are_not_silently_called_independent() -> None:
    """共同观测不足时,宁可少并组,但必须如实报「证据不足」。"""

    rows = [
        {"trade_date": f"2024-01-{i + 1:02d}", "x": float(i % 7), "y": float((i * 3) % 5),
         "sparse": (float(i) if i < 5 else None)}
        for i in range(60)
    ]
    z, _ = standardize_vectors(rows, ("x", "y", "sparse"))
    st = dimension_groups(z, ("x", "y", "sparse"))
    names = {p[:2] for p in st.undetermined}
    assert any("sparse" in n for n in names), "稀疏维必须进 undetermined"
    assert "未并组不等于已证明独立" in st.to_dict()["note"]


# --------------------------------------------------------------------------- #
# 真库入口：不自己取数、不绕开 PIT
# --------------------------------------------------------------------------- #
def test_lens_from_db_goes_through_river_window_and_passes_cutoff(monkeypatch) -> None:
    """镜头**不自己连库**。取数必须走 build_daily_vectors —— 那里强制 cutoff。

    另开一条取数路径就等于另开一个漏 PIT 的口子。这条测试钉死「只有一条路」。
    """

    from intelligence.services import river_lens, river_window as rw

    seen: dict = {}

    def fake_build(*, knowledge_cutoff, db_path=None, checkpoints_path=None):
        seen["cutoff"] = knowledge_cutoff
        nxt = _rng(3)
        return [
            {
                "trade_date": f"2026-03-{i + 1:02d}",
                **{f: nxt() * 3 for f in rw.COMPARABLE_FEATURE_NAMES},
            }
            for i in range(28)
        ]

    monkeypatch.setattr(rw, "build_daily_vectors", fake_build)
    res = river_lens.lens_from_db(knowledge_cutoff="2026-03-20", window=5, step=5)

    assert seen["cutoff"] == "2026-03-20", "cutoff 必须原样透传给取数层"
    assert res.knowledge_cutoff == "2026-03-20"
    assert "knowledge_cutoff=2026-03-20" in lens_block(res)


def test_candidate_windows_never_overlap_the_current_window(monkeypatch) -> None:
    """自己跟自己像不是信息 —— 与当前窗重叠的候选必须被剔除。"""

    from intelligence.services import river_lens, river_window as rw

    def fake_build(*, knowledge_cutoff, db_path=None, checkpoints_path=None):
        nxt = _rng(11)
        return [
            {
                "trade_date": f"2026-04-{i + 1:02d}",
                **{f: nxt() * 3 for f in rw.COMPARABLE_FEATURE_NAMES},
            }
            for i in range(30)
        ]

    monkeypatch.setattr(rw, "build_daily_vectors", fake_build)
    res = river_lens.lens_from_db(
        knowledge_cutoff="2026-04-30", as_of="2026-04-30", window=5, step=1, top=50
    )
    cur_start = "2026-04-26"  # 最后 5 个交易日
    for candidate in res.candidates:
        assert candidate.end_date < cur_start
