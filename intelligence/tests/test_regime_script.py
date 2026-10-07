"""环境剧本:重点不是「能造出对象」,是**闸拦不拦得住噪声**。

一个会给噪声起名字的命名器,比没有命名器更坏 —— 它把随机波动包装成「历史规律」,
而且带着 ID 和后续事实统计,看起来很可信。所以这里一半的测试在证明它**不**产出东西。
"""

from __future__ import annotations

import random

from intelligence.services.market_regime_analogs import RegimeSignature
from intelligence.services.regime_script import (
    evaluate_gate,
    explanatory_power,
    match_script,
    mint_scripts,
    permutation_null,
    scripts_block,
)

FEATS = ("amount", "limit_up", "flow")


def _sig(amount: float, limit_up: float, flow: float, trend: float = 0.0) -> RegimeSignature:
    return RegimeSignature(
        {"amount": (amount, trend), "limit_up": (limit_up, trend), "flow": (flow, trend)}
    )


# --------------------------------------------------------------------------- #
# 闸：拦噪声
# --------------------------------------------------------------------------- #
def test_gate_refuses_to_name_clusters_built_on_noise() -> None:
    """**最重要的一条。**后续事实与簇无关时,必须不过闸、不铸造、并说明原因。"""

    rng = random.Random(42)
    assign = {f"w{i}": i % 3 for i in range(30)}
    outcomes = {f"w{i}": rng.gauss(0, 1) for i in range(30)}

    gate = evaluate_gate(assign, outcomes)
    assert not gate.passed, f"噪声竟然过闸了：{gate.to_dict()}"
    assert gate.beats_random is False
    assert any("随机分簇" in r for r in gate.reasons)

    scripts, g2 = mint_scripts(
        train={f"w{i}": _sig(0, 0, 0) for i in range(30)},
        train_assignments=assign,
        holdout_assignments={f"h{k}": v for k, v in assign.items()},
        holdout_outcomes={f"h{k}": v for k, v in outcomes.items()},
        features=FEATS,
    )
    assert scripts == [], "闸没过却铸造了剧本"
    assert not g2.passed


def test_block_says_plainly_that_nothing_was_named() -> None:
    """空结果必须**明说是空结果**,而且要劝阻调参凑过闸。"""

    rng = random.Random(7)
    assign = {f"w{i}": i % 3 for i in range(30)}
    outcomes = {f"w{i}": rng.gauss(0, 1) for i in range(30)}
    gate = evaluate_gate(assign, outcomes)
    text = scripts_block([], gate)

    assert "未过闸" in text and "不命名" in text
    assert "诚实的空结果" in text
    assert "不要调参数凑过闸" in text
    # 没过闸时不该出现剧本表
    assert "已命名的剧本" not in text


def test_gate_refuses_when_holdout_is_too_small() -> None:
    """留出段太小就不评 —— 四五个窗口上算出的解释力不是读数。"""

    gate = evaluate_gate({"a": 0, "b": 1, "c": 0}, {"a": 1.0, "b": -1.0, "c": 0.9})
    assert not gate.passed
    assert any("不足以评判" in r for r in gate.reasons)


def test_gate_refuses_when_holdout_lands_in_one_cluster() -> None:
    """留出段全落一个簇 ⇒ 无从比较,不能默认通过。"""

    gate = evaluate_gate(
        {f"w{i}": 0 for i in range(12)},
        {f"w{i}": float(i) for i in range(12)},
    )
    assert not gate.passed
    assert any("只落进了一个簇" in r for r in gate.reasons)


# --------------------------------------------------------------------------- #
# 闸：放过真结构
# --------------------------------------------------------------------------- #
def _real_structure():
    """簇 0 的后续事实明显为正、簇 1 明显为负 —— 真有结构。"""

    assign, outcomes = {}, {}
    for i in range(20):
        w = f"w{i}"
        assign[w] = i % 2
        outcomes[w] = (5.0 if i % 2 == 0 else -5.0) + (i % 3) * 0.1
    return assign, outcomes


def test_gate_passes_when_clusters_really_explain_the_outcome() -> None:
    assign, outcomes = _real_structure()
    gate = evaluate_gate(assign, outcomes)
    assert gate.passed, gate.to_dict()
    assert gate.beats_random is True
    assert gate.observed > 0.9


def test_permutation_null_is_deterministic_and_centred_near_zero() -> None:
    """置换零分布必须可重算,且在随机标签下不应系统性地高。"""

    assign, outcomes = _real_structure()
    a = permutation_null(assign, outcomes)
    b = permutation_null(assign, outcomes)
    assert a == b, "固定种子下置换结果必须一致"
    assert len(a) > 100
    median = a[len(a) // 2]
    assert -0.3 < median < 0.3, f"随机标签的解释力中位竟是 {median}"


# --------------------------------------------------------------------------- #
# 留出法真的是留出
# --------------------------------------------------------------------------- #
def test_training_fit_is_not_mistaken_for_explanatory_power() -> None:
    """同一组簇:训练段上看着有解释力,留出段上原形毕露。

    这条钉死「留出法不是摆设」—— 如果有人把 holdout 换成 train,这条会失败。
    """

    rng = random.Random(11)
    n = 24
    # 训练段：按后续事实的正负切簇 —— 必然完美拟合
    train_out = {f"t{i}": rng.gauss(0, 1) for i in range(n)}
    train_assign = {k: (0 if v > 0 else 1) for k, v in train_out.items()}
    assert explanatory_power(train_assign, train_out) > 0.5, "训练段应当看起来很好"

    # 留出段：同样的簇定义套到新窗口上，后续事实与簇无关
    hold_assign = {f"h{i}": i % 2 for i in range(n)}
    hold_out = {f"h{i}": rng.gauss(0, 1) for i in range(n)}
    gate = evaluate_gate(hold_assign, hold_out)
    assert not gate.passed, "留出段应当拆穿它"


# --------------------------------------------------------------------------- #
# 铸造出来的对象
# --------------------------------------------------------------------------- #
def _minted():
    train = {}
    train_assign = {}
    for i in range(16):
        w = f"t{i}"
        hot = i % 2 == 0
        train[w] = _sig(1.8 if hot else -1.6, 1.6 if hot else -1.4, 0.2, trend=0.1)
        train_assign[w] = 0 if hot else 1
    hold_assign = {f"h{i}": i % 2 for i in range(20)}
    hold_out = {f"h{i}": (4.0 if i % 2 == 0 else -4.0) + (i % 5) * 0.1 for i in range(20)}
    return mint_scripts(
        train=train,
        train_assignments=train_assign,
        holdout_assignments=hold_assign,
        holdout_outcomes=hold_out,
        train_outcomes={f"t{i}": (3.0 if i % 2 == 0 else -3.0) for i in range(16)},
        features=FEATS,
        labels={"amount": "成交额", "limit_up": "涨停", "flow": "资金"},
    )


def test_scripts_carry_identity_members_and_forward_facts_not_probabilities() -> None:
    scripts, gate = _minted()
    assert gate.passed
    assert len(scripts) == 2

    for s in scripts:
        assert s.script_id.startswith("rs-")
        assert len(s.members) >= 4
        d = s.to_dict()
        assert d["forward_facts"]["n_samples"] > 0
        # 不编概率
        txt = d["forward_facts"]["statement"]
        assert "不是概率" in txt
        assert "%" not in txt
        # 可回溯
        assert d["centroid_z"] and d["features"] == list(FEATS)
        assert d["gate"]["passed"] is True

    # 自动描述用的是可读名,且是描述不是起名
    assert any("成交额" in s.auto_label for s in scripts)


def test_script_id_is_content_addressed_and_stable() -> None:
    a, _ = _minted()
    b, _ = _minted()
    assert [s.script_id for s in a] == [s.script_id for s in b], "同输入必须同 ID"


def test_match_refuses_to_claim_membership_when_two_scripts_are_equally_close() -> None:
    """归属不明确时必须说不明确 —— 这正是最容易编出来的地方。"""

    scripts, _ = _minted()
    assert len(scripts) == 2
    a, b = scripts[0].centroid, scripts[1].centroid
    mid = RegimeSignature(
        {f: ((a.stats[f][0] + b.stats[f][0]) / 2, (a.stats[f][1] + b.stats[f][1]) / 2)
         for f in a.stats if f in b.stats}
    )
    m = match_script(mid, scripts, total_dims=len(FEATS))
    assert m.confident is False
    assert "归属不明确" in m.note
    assert m.runner_up is not None

    # 明确落在某一侧时则 confident
    clear = match_script(scripts[0].centroid, scripts, total_dims=len(FEATS))
    assert clear.confident is True
    assert clear.script.script_id == scripts[0].script_id


def test_block_surfaces_internal_divergence_against_carving_the_boat() -> None:
    """相同剧本 ≠ 相同行情。簇内分歧维必须出现在给 agent 的文本里。"""

    scripts, gate = _minted()
    text = scripts_block(
        scripts, gate,
        match=match_script(scripts[0].centroid, scripts, total_dims=len(FEATS)),
        labels={"amount": "成交额", "limit_up": "涨停", "flow": "资金"},
    )
    assert "过闸" in text
    assert "簇内最大分歧维" in text
    assert "相同剧本不等于相同行情" in text
    assert "不是概率预测" in text
    assert "当前落在哪个剧本" in text


# --------------------------------------------------------------------------- #
# 整条链路
# --------------------------------------------------------------------------- #
def _series(n: int, *, structured: bool):
    """n 个按时间排序的窗口。``structured`` 决定后续事实跟不跟签名走。"""

    rng = random.Random(5)
    sigs, outs, order = {}, {}, []
    for i in range(n):
        w = f"d{i:03d}"
        order.append(w)
        hot = (i // 3) % 2 == 0          # 成段出现，像真实行情那样
        sigs[w] = _sig(
            1.5 + rng.gauss(0, 0.2) if hot else -1.5 + rng.gauss(0, 0.2),
            1.4 + rng.gauss(0, 0.2) if hot else -1.3 + rng.gauss(0, 0.2),
            rng.gauss(0, 0.3),
        )
        outs[w] = (4.0 if hot else -4.0) + rng.gauss(0, 0.5) if structured else rng.gauss(0, 4)
    return sigs, outs, order


def test_pipeline_names_scripts_when_signature_really_tracks_the_outcome() -> None:
    from intelligence.services.regime_script import build_scripts

    sigs, outs, order = _series(60, structured=True)
    scripts, gate, split = build_scripts(
        signatures=sigs, outcomes=outs, order=order, features=FEATS, cluster_threshold=1.5
    )
    assert gate.passed, gate.to_dict()
    assert scripts
    assert split["split"].startswith("按时间")
    assert split["n_windows"] == 60


def test_pipeline_stays_silent_when_the_outcome_is_noise() -> None:
    """**同样的签名结构、同样的聚类,后续事实换成噪声 ⇒ 必须一个剧本都不铸。**"""

    from intelligence.services.regime_script import build_scripts

    sigs, outs, order = _series(60, structured=False)
    scripts, gate, _ = build_scripts(
        signatures=sigs, outcomes=outs, order=order, features=FEATS, cluster_threshold=1.5
    )
    assert scripts == [], "噪声上铸出了剧本"
    assert not gate.passed


def test_holdout_is_the_tail_in_time_not_a_random_sample() -> None:
    """时间序列上随机切会漏 —— 留出段必须是时间上的尾巴。"""

    from intelligence.services.regime_script import build_scripts

    sigs, outs, order = _series(60, structured=True)
    _, _, split = build_scripts(
        signatures=sigs, outcomes=outs, order=order, features=FEATS, cluster_threshold=1.5
    )
    assert split["train"][0] == order[0]
    assert split["holdout"][-1] == order[-1]
    assert split["train"][-1] < split["holdout"][0], "训练段必须整体早于留出段"
