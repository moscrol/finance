"""教学标签 → 判定路径的桥：命名空间保持分离、缺旁路库落 unknown、身份进收据。

合成样本分三类，互不重叠：

- **正常样本**：2026-01-12。桥接逻辑就是对着这一天的 payload 形状写出来的。
- **反例**：旁路库缺席 / 命名空间混用 / 留置标签 / ``0`` 被当成缺失 —— 四条都必须失败得明明白白。
- **未参与调试的验证样本**：夹具里除 01-12 以外的所有交易日。断言不写死任何期望值，
  而是拿旁路库原始行与绑定结果做往返一致性比对，外加「不同日子必须给出不同读数」的常量探测。
  这样这组断言既没有用到开发时的观察，也不会被「永远返回同一个值」的实现蒙混过关。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from intelligence.services.teaching_framework.pit_identity import first_known_at as pit_first_known_at

from intelligence.services import river_teaching_bridge as bridge
from intelligence.services import scenario_trees as st
from intelligence.services.river import Gap, RiverSlice
from intelligence.services.teaching_framework.river_objects import STAGE_LABELS, teaching_objects
from intelligence.tests.teaching_sidecar_fixture import build_sidecar

DEV_DAY = "2026-01-12"  # 开发用的那一天


@pytest.fixture
def sidecar(tmp_path: Path) -> Path:
    return build_sidecar(tmp_path / "labels.duckdb")



def _restamp(row: list, cols: list[str]) -> None:
    """复制样板行之后，按真实判据重算 ``first_known_at``。

    夹具是 ``SELECT *`` 出一行再改几个字段。样板那行是市场级标签、盖的是构建时刻；
    若照抄，结构事件也会拿到构建时刻 —— 那就测不出 PIT 身份到底有没有生效。
    """

    ix = {c: cols.index(c) for c in ("label", "entity_type", "entity_id", "trade_date", "value_num", "value_text", "computed_at")}
    row[cols.index("first_known_at")] = pit_first_known_at(
        label=str(row[ix["label"]]), entity_type=str(row[ix["entity_type"]]),
        entity_id=str(row[ix["entity_id"]]), trade_date=row[ix["trade_date"]],
        value_num=row[ix["value_num"]], value_text=row[ix["value_text"]],
        previous={}, build_time=row[ix["computed_at"]],
    )


def _slice(sidecar: Path, day: str) -> RiverSlice:
    return RiverSlice(
        as_of=day, entity_id="__market__", entity_name="全市场", knowledge_cutoff=day,
        tracks={"market": list(teaching_objects(sidecar, day, top=2))},
    )


def _bare_slice(day: str = DEV_DAY) -> RiverSlice:
    """没接旁路库的切片：盘面轨上一个 teaching_* 对象都没有。"""
    return RiverSlice(
        as_of=day, entity_id="__market__", entity_name="全市场", knowledge_cutoff=day, tracks={"market": []},
    )


# --------------------------------------------------------------------------- #
# 正常样本：2026-01-12
# --------------------------------------------------------------------------- #
def test_open_teaching_labels_bind_on_a_slice_that_has_the_sidecar(sidecar: Path) -> None:
    sl = _slice(sidecar, DEV_DAY)
    value, refs = bridge.bind_teaching("tf.above_week_ma", sl)
    assert value is False and refs == [f"history_teaching_labels:{DEV_DAY}:market"]
    assert bridge.bind_teaching("tf.money_losing_day", sl)[0] is True
    assert bridge.bind_teaching("tf.money_losing_streak", sl)[0] == 2.0
    assert bridge.bind_teaching("tf.stage_coarse", sl)[0] == "左底向下"
    assert bridge.bind_teaching("tf.deviation_band", sl)[0] == "below"
    assert bridge.bind_teaching("tf.below_ma_cycle_day", sl)[0] == 1.0


def test_teaching_predicate_compiles_into_a_scenario_tree_condition() -> None:
    """判定路径的闸口放行 tf.*，且按声明的值域校验 op 与 value。"""
    preds, errs = st.compile_condition(
        {"all": [
            {"label": "tf.above_week_ma", "op": "==", "value": False},
            {"label": "tf.stage_coarse", "op": "in", "value": ["左底向下", "左底向上"]},
            {"label": "tf.money_losing_streak", "op": ">=", "value": 2},
        ]},
        where="t",
    )
    assert errs == []
    assert preds is not None and [p.label for p in preds] == [
        "tf.above_week_ma", "tf.stage_coarse", "tf.money_losing_streak",
    ]


def test_identity_of_the_reading_is_recoverable(sidecar: Path) -> None:
    """收据里必须看得出「哪一版教学框架、哪天、什么指纹」——教学标签是事后重算的。"""
    prov = bridge.teaching_provenance(_slice(sidecar, DEV_DAY))
    assert prov is not None
    assert prov["namespace"] == "teaching"
    assert prov["ref"] == f"history_teaching_labels:{DEV_DAY}:market"
    assert prov["framework_version"]            # 非空
    assert prov["source_hash"]                  # 非空
    assert prov["recorded_at"]                  # 成员最晚 first_known_at，供 PIT 门过滤


# --------------------------------------------------------------------------- #
# 反例
# --------------------------------------------------------------------------- #
def test_without_the_sidecar_it_is_unknown_not_false() -> None:
    """反例 1：旁路库没接 → (None, [])。

    这是整座桥最要紧的一条。若此处返回 False，一棵情景树会在旁路库缺席时悄悄走到
    另一个分枝，而收据上看不出任何差别。
    """
    sl = _bare_slice()
    for label in bridge.TEACHING_LABEL_KINDS:
        value, refs = bridge.bind_teaching(label, sl)
        assert value is None and refs == [], f"{label} 在没有旁路库时必须是 unknown"
    assert bridge.teaching_provenance(sl) is None


def test_bare_name_without_namespace_prefix_is_rejected() -> None:
    """反例 2：缺少前缀的名字不能用作教学标签。"""
    with pytest.raises(bridge.TeachingLabelNotBridged, match="命名空间"):
        bridge.teaching_kind("above_week_ma")
    _preds, errs = st.compile_condition(
        {"all": [{"label": "above_week_ma", "op": "==", "value": False}]}, where="t"
    )
    assert [r.detail for r in errs] == ["label 'above_week_ma' 不是注册标签（ALL_LABELS）"]


def test_withheld_label_is_rejected_with_the_reason_quoted() -> None:
    """反例 3：留置标签必须带理由被拒，不能静默放行、也不能无理由地拒。"""
    with pytest.raises(bridge.TeachingLabelNotBridged, match="只写出、不进计分"):
        bridge.teaching_kind("tf.volume_band")
    _preds, errs = st.compile_condition(
        {"all": [{"label": "tf.volume_band", "op": "==", "value": "shrink"}]}, where="t"
    )
    assert len(errs) == 1
    assert "00-concept-label-skeleton.md" in errs[0].detail and "不进计分" in errs[0].detail


def test_zero_is_a_definite_false_not_a_missing_reading(sidecar: Path) -> None:
    """反例 4：``above_week_ma = 0`` 是「在周均线下方」这个确定的假，不是「没读数」。

    旁路库把 bool 存成 ``value_num`` 的 0/1；若实现用真值判断过滤，0 会被误当缺失，
    于是「确定在周均线下方」会退化成 unknown——方向性错误，且无声。
    """
    value, refs = bridge.bind_teaching("tf.above_week_ma", _slice(sidecar, DEV_DAY))
    assert value is False, "0 被当成缺失了"
    assert refs, "确定的假也必须带 ref"


def test_catalog_parity_guards_against_silent_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    """反例 5：旁路库新增标签而目录没表态 → 必须抛，不能默认开放或默认留置。"""
    bridge.assert_teaching_catalog_parity()  # 当前应通过
    monkeypatch.setattr(bridge, "STAGE_LABELS", (*STAGE_LABELS, "tf.brand_new_label"))
    with pytest.raises(bridge.TeachingLabelNotBridged, match="未表态"):
        bridge.assert_teaching_catalog_parity()


# --------------------------------------------------------------------------- #
# 未参与调试的验证样本：夹具里除 2026-01-12 以外的交易日
# --------------------------------------------------------------------------- #
def _sidecar_rows(sidecar: Path, day: str) -> dict[str, Any]:
    import duckdb

    con = duckdb.connect(str(sidecar), read_only=True)
    try:
        rows = con.execute(
            """SELECT label, value_num, value_text FROM history_teaching_labels
               WHERE entity_type = 'market' AND entity_id = 'market' AND status = 'ok' AND trade_date = ?""",
            [day],
        ).fetchall()
    finally:
        con.close()
    return {r[0]: (r[2] if r[2] is not None else r[1]) for r in rows}


def _holdout_days(sidecar: Path) -> list[str]:
    import duckdb

    con = duckdb.connect(str(sidecar), read_only=True)
    try:
        days = [str(r[0]) for r in con.execute(
            """SELECT DISTINCT trade_date FROM history_teaching_labels
               WHERE entity_type = 'market' AND entity_id = 'market' AND status = 'ok' ORDER BY trade_date"""
        ).fetchall()]
    finally:
        con.close()
    return [d for d in days if d != DEV_DAY]


def test_holdout_days_round_trip_without_any_hardcoded_expectation(sidecar: Path) -> None:
    """对每个未用于开发的交易日：绑定值必须等于旁路库原始值按声明值域的还原。

    断言不写死任何读数，所以这组检查没有用到开发时对夹具的观察。
    """
    days = _holdout_days(sidecar)
    assert len(days) >= 5, f"验证样本太少：{days}"
    checked = 0
    for day in days:
        raw = _sidecar_rows(sidecar, day)
        sl = _slice(sidecar, day)
        for label, kind in bridge.TEACHING_LABEL_KINDS.items():
            bound, refs = bridge.bind_teaching(label, sl)
            if label not in raw:
                assert bound is None and refs == [], f"{day} {label}：旁路库没有这条，却绑出了 {bound!r}"
                continue
            expected = bridge._coerce(raw[label], kind)
            assert bound == expected, f"{day} {label}：绑定 {bound!r} ≠ 原始 {raw[label]!r} 还原 {expected!r}"
            if expected is not None:
                assert refs == [f"history_teaching_labels:{day}:market"]
                checked += 1
    assert checked >= 5, f"验证样本上真正比对到的读数只有 {checked} 条，太少"


def test_holdout_days_are_not_all_the_same_reading(sidecar: Path) -> None:
    """常量探测：若实现永远返回 01-12 的值或永远返回同一个常量，上一条也会通过，这条不会。"""
    seen: set[Any] = set()
    for day in _holdout_days(sidecar):
        value, _refs = bridge.bind_teaching("tf.above_week_ma", _slice(sidecar, day))
        seen.add(value)
    assert len(seen) >= 2, f"所有验证日的 tf.above_week_ma 读数都一样（{seen}），疑似常量实现"


# --------------------------------------------------------------------------- #
# teaching_cycle：旁路库早就算了、此前从未搬上河的那 9 个
# --------------------------------------------------------------------------- #
CYCLE_ROWS = {
    "tf.gap_down_open": 1, "tf.cross_above_week_ma": 0, "tf.deviation_narrowing": 1,
    "tf.shrink_day": 1, "tf.volume_shrink_streak": 3, "tf.double_volume_day": 0,
    "tf.mainline_volume_top3": 1, "tf.mainline_share_trend_up": 0, "tf.max_boards": 5,
}


@pytest.fixture
def sidecar_with_cycle(sidecar: Path) -> Path:
    """把周期位置标签写进旁路库。单独写在测试里而不是改公共夹具——
    公共夹具被多个逐字断言的测试共用，改它会把无关测试一起拖下水。"""
    import duckdb

    con = duckdb.connect(str(sidecar))
    try:
        cols = [r[1] for r in con.execute("PRAGMA table_info('history_teaching_labels')").fetchall()]
        template = con.execute(
            "SELECT * FROM history_teaching_labels WHERE label = 'tf.money_losing_streak' AND trade_date = ?",
            [DEV_DAY],
        ).fetchone()
        assert template is not None, "夹具形状变了，样板行取不到"
        i_label, i_num, i_text = cols.index("label"), cols.index("value_num"), cols.index("value_text")
        for label, num in CYCLE_ROWS.items():
            row = list(template)
            row[i_label], row[i_num], row[i_text] = label, float(num), None
            _restamp(row, cols)
            con.execute(
                f"INSERT INTO history_teaching_labels VALUES ({', '.join('?' for _ in cols)})", row
            )
    finally:
        con.close()
    return sidecar


def test_cycle_labels_reach_the_judgment_path(sidecar_with_cycle: Path) -> None:
    """周期标签接上后必须可判定，并保留对象来源。"""
    sl = _slice(sidecar_with_cycle, DEV_DAY)
    assert any(o.object_type == "teaching_cycle" for o in sl.tracks["market"]), "teaching_cycle 对象没出现"
    assert bridge.bind_teaching("tf.gap_down_open", sl)[0] is True            # 转点「缺口」
    assert bridge.bind_teaching("tf.cross_above_week_ma", sl)[0] is False     # 尚未站上周均
    assert bridge.bind_teaching("tf.shrink_day", sl)[0] is True               # 「缩量」
    assert bridge.bind_teaching("tf.volume_shrink_streak", sl)[0] == 3.0
    assert bridge.bind_teaching("tf.mainline_volume_top3", sl)[0] is True     # 「量板块」
    assert bridge.bind_teaching("tf.max_boards", sl)[0] == 5.0
    # ref 必须指向 cycle 对象而不是 stage 对象——两个对象的 ref 不同，收据要能分辨
    assert bridge.bind_teaching("tf.gap_down_open", sl)[1] == [
        f"history_teaching_labels:{DEV_DAY}:market:cycle"
    ]


def test_cycle_conjunction_compiles_end_to_end() -> None:
    """合成条件混合布尔和分类谓词，检查编译结果而非金融有效性。"""
    preds, errs = st.compile_condition(
        {"all": [
            {"label": "tf.gap_down_open", "op": "==", "value": True},
            {"label": "tf.above_week_ma", "op": "==", "value": False},
            {"label": "tf.cross_below_kind", "op": "in", "value": ["first"]},
        ]},
        where="转点",
    )
    assert errs == [] and preds is not None and len(preds) == 3


def test_cycle_labels_are_unknown_when_the_cycle_object_is_absent(sidecar: Path) -> None:
    """反例：旁路库里没有周期标签的日子（未写入 cycle 行）→ unknown，不是 false。

    注意这与 stage 对象是否存在无关——stage 在的时候 cycle 仍可能缺，
    若实现退化成「找不到就去 stage 里碰运气」，这条会炸。
    """
    sl = _slice(sidecar, DEV_DAY)   # 只有 stage，没有 cycle
    assert any(o.object_type == "teaching_stage" for o in sl.tracks["market"])
    assert not any(o.object_type == "teaching_cycle" for o in sl.tracks["market"])
    for label in ("tf.gap_down_open", "tf.shrink_day", "tf.max_boards"):
        assert bridge.bind_teaching(label, sl) == (None, []), f"{label} 应为 unknown"
    # 同一片切片上 stage 的标签仍然照常可判，缺一个对象不该拖垮另一个
    assert bridge.bind_teaching("tf.above_week_ma", sl)[0] is False


def test_sibling_overlap_check_works_on_teaching_predicates() -> None:
    """``_domain`` 取不到 tf.* 的 kind 会 KeyError，兄弟互斥检查就形同虚设。

    后果不是报错而是**放行**：两个重叠的分枝条件都登记成功，树同时走两条路。
    """
    assert st._domain("tf.above_week_ma", []) == [True, False]
    assert st._domain("tf.max_boards", []) == list(range(0, st.NUM_DOMAIN_MAX + 1))
    text_domain = st._domain(
        "tf.stage_coarse",
        [(st.Predicate("tf.stage_coarse", "==", "左底向下"),)],
    )
    assert "左底向下" in text_domain and "__other__" in text_domain


# ── 结构事件（板块级）：第一批非市场级的教学标签 ──────────────────────────────

SECTOR_A, SECTOR_B = "801080.TI", "801770.TI"
STRUCTURE_ROWS = (("tf.macd_bottom_div_confirm", "2026-01-05"), ("tf.macd_top_div", "2026-01-09"))


@pytest.fixture()
def sidecar_with_structure(sidecar: Path) -> Path:
    """给板块 SECTOR_A 写两条背离事件行（底背离确认 + 顶背离）。

    同样不改公共夹具——理由见 ``sidecar_with_cycle``。
    """
    import duckdb

    con = duckdb.connect(str(sidecar))
    try:
        cols = [r[1] for r in con.execute("PRAGMA table_info('history_teaching_labels')").fetchall()]
        template = con.execute(
            "SELECT * FROM history_teaching_labels WHERE label = 'tf.money_losing_streak' AND trade_date = ?",
            [DEV_DAY],
        ).fetchone()
        assert template is not None, "夹具形状变了，样板行取不到"
        idx = {c: cols.index(c) for c in ("label", "value_num", "value_text", "entity_type", "entity_id")}
        for label, anchor in STRUCTURE_ROWS:
            row = list(template)
            row[idx["label"]], row[idx["value_num"]], row[idx["value_text"]] = label, 1.0, anchor
            row[idx["entity_type"]], row[idx["entity_id"]] = "sector", SECTOR_A
            _restamp(row, cols)
            con.execute(f"INSERT INTO history_teaching_labels VALUES ({', '.join('?' for _ in cols)})", row)
    finally:
        con.close()
    return sidecar


def _entity_slice(sidecar: Path, entity_id: str) -> RiverSlice:
    objs = teaching_objects(sidecar, DEV_DAY, top=2, entity_type="sector", entity_id=entity_id)
    tracks: dict[str, Any] = {"market": [], "theme": []}
    for o in objs:
        tracks["market" if o.entity_id == "__market__" else o.track].append(o)
    return RiverSlice(
        as_of=DEV_DAY, entity_id=entity_id, entity_name="测试板块",
        knowledge_cutoff=DEV_DAY, tracks=tracks,
    )


def test_sector_level_divergence_reaches_the_judgment_path(sidecar_with_structure: Path) -> None:
    """第一个**非市场级**教学标签走通判定路径。

    此前河上 65 个教学标签全是 ``entity_type='market'``，规则 DSL 的板块层只有
    ``dual_red_streak`` 一个、个股层 0 个。这条钉的是「板块自己的背离」能被绑上。
    """
    sl = _entity_slice(sidecar_with_structure, SECTOR_A)
    value, refs = bridge.bind_teaching("tf.macd_bottom_div_confirm", sl)
    assert value is True
    assert refs and refs[0].endswith(f":sector:{SECTOR_A}:structure")
    assert bridge.bind_teaching("tf.macd_top_div", sl)[0] is True


def test_structure_object_rides_the_entity_track_not_the_market_track(sidecar_with_structure: Path) -> None:
    """结构对象必须挂实体自己的轨。

    桥原先把轨写死成 ``"market"``。那样实体级标签永远绑不到值，且失败是**静默的**
    unknown——收据上看不出是「没接旁路库」还是「找错了轨」。
    """
    sl = _entity_slice(sidecar_with_structure, SECTOR_A)
    assert [o.object_type for o in sl.tracks["theme"]] == ["teaching_structure"]
    assert all(o.object_type != "teaching_structure" for o in sl.tracks["market"])
    assert bridge._TRACK_OF_OBJECT["teaching_structure"] == "theme"
    assert bridge._TRACK_OF_OBJECT["teaching_stage"] == "market"  # 市场级那批没被挪走


def test_divergence_is_unknown_not_false_when_the_entity_has_no_event(
    sidecar_with_structure: Path,
) -> None:
    """换一个没有事件行的板块 → unknown，不是「没背离」。

    这组是**事件标签**（只落事件日）：「今天没事件」与「旁路库没接」在读数上长得一样。
    绑成 False 会让「没有顶背离」这种分枝在旁路库缺席时悄悄成立——正是 rules 里
    「『从未成立』与『今天没成立』在读数上长得一样」防的同一个坑。
    """
    sl = _entity_slice(sidecar_with_structure, SECTOR_B)
    assert sl.tracks["theme"] == []
    assert bridge.bind_teaching("tf.macd_top_div", sl) == (None, [])
    # 一个对象缺席不能拖垮另一个：同片切片上的市场级标签照常绑得到
    assert bridge.bind_teaching("tf.above_week_ma", sl)[0] is not None


def test_market_level_objects_are_unchanged_when_no_entity_is_given(sidecar_with_structure: Path) -> None:
    """不传实体 = 与改动前逐字节一致。结构对象是**附加**，不是改写。"""
    before = [o.to_dict() for o in teaching_objects(sidecar_with_structure, DEV_DAY, top=2)]
    after = [
        o.to_dict()
        for o in teaching_objects(sidecar_with_structure, DEV_DAY, top=2, entity_type="sector", entity_id=SECTOR_A)
        if o.entity_id == "__market__"
    ]
    assert before == after


def test_sector_divergence_compiles_into_a_scenario_tree_condition() -> None:
    """板块事件与市场级条件可在同一条合取中编译。"""
    preds, errs = st.compile_condition(
        {"all": [
            {"label": "tf.macd_bottom_div_confirm", "op": "==", "value": True},
            {"label": "tf.mainline_volume_top3", "op": "==", "value": True},
        ]},
        where="n1",
    )
    assert errs == [] and preds is not None and len(preds) == 2


# ── 板块角色（C 类）：量板块 / 价板块 / 锐度 / RPS / 双红 / 赚钱效应 ──────────

ROLE_ROWS = {
    "tf.role_volume_top3": 1.0, "tf.role_price_top10": 0.0,
    "tf.rps_5d_rank": 4.0, "tf.limit_up_count": 7.0,
    "tf.money_effect.kmeans_hot": 1.0, "tf.dual_red_strict": 1.0,
}


@pytest.fixture()
def sidecar_with_roles(sidecar: Path) -> Path:
    """给 SECTOR_A 写板块角色行。同样不改公共夹具。"""
    import duckdb

    con = duckdb.connect(str(sidecar))
    try:
        cols = [r[1] for r in con.execute("PRAGMA table_info('history_teaching_labels')").fetchall()]
        template = con.execute(
            "SELECT * FROM history_teaching_labels WHERE label = 'tf.money_losing_streak' AND trade_date = ?",
            [DEV_DAY],
        ).fetchone()
        assert template is not None, "夹具形状变了，样板行取不到"
        idx = {c: cols.index(c) for c in ("label", "value_num", "value_text", "entity_type", "entity_id")}
        for label, num in ROLE_ROWS.items():
            row = list(template)
            row[idx["label"]], row[idx["value_num"]], row[idx["value_text"]] = label, num, None
            row[idx["entity_type"]], row[idx["entity_id"]] = "sector", SECTOR_A
            _restamp(row, cols)
            con.execute(f"INSERT INTO history_teaching_labels VALUES ({', '.join('?' for _ in cols)})", row)
    finally:
        con.close()
    return sidecar


def test_sector_roles_reach_the_judgment_path(sidecar_with_roles: Path) -> None:
    """板块角色读数与 ref 均来自板块对象，而非市场对象。"""
    sl = _entity_slice(sidecar_with_roles, SECTOR_A)
    assert bridge.bind_teaching("tf.role_volume_top3", sl)[0] is True      # 量板块
    assert bridge.bind_teaching("tf.role_price_top10", sl)[0] is False     # 价板块：确定的假
    assert bridge.bind_teaching("tf.rps_5d_rank", sl)[0] == 4.0
    _, refs = bridge.bind_teaching("tf.money_effect.kmeans_hot", sl)
    assert refs and refs[0].endswith(f":sector:{SECTOR_A}:sector_role")


def test_role_and_structure_are_separate_objects_on_the_same_track(
    sidecar_with_roles: Path, sidecar_with_structure: Path
) -> None:
    """角色与结构同在 theme 轨但是两个对象，各自的 ref 要能分辨出来源。"""
    sl = _entity_slice(sidecar_with_roles, SECTOR_A)
    kinds = sorted(o.object_type for o in sl.tracks["theme"])
    assert kinds == ["teaching_sector_role", "teaching_structure"]
    role_ref = bridge.bind_teaching("tf.role_volume_top3", sl)[1][0]
    div_ref = bridge.bind_teaching("tf.macd_bottom_div_confirm", sl)[1][0]
    assert role_ref != div_ref and role_ref.endswith(":sector_role") and div_ref.endswith(":structure")


def test_no_teaching_label_belongs_to_two_objects() -> None:
    """同名不同物守门。

    ``tf.mainline_volume_top3`` 在市场级（CYCLE_LABELS）和板块级（SECTOR_LABELS）都存在、
    含义不同。碰撞时谓词绑到哪一层取决于字典插入顺序——**不报错，只给错答案**。
    所以搬运侧剔除了板块级那个别名（它本就等于 role_volume_top3），这里钉住不变量本身。
    """
    seen: dict[str, str] = {}
    for name, group in bridge._LABEL_GROUPS:
        for label in group:
            assert label not in seen, f"{label} 同时在 {seen[label]} 与 {name}"
            seen[label] = name
    assert "tf.mainline_volume_top3" in dict(bridge._LABEL_GROUPS)["CYCLE_LABELS"]
    assert "tf.role_volume_top3" in dict(bridge._LABEL_GROUPS)["SECTOR_ROLE_LABELS"]


def test_three_level_rule_compiles_end_to_end() -> None:
    """大盘阶段 × 板块角色 × 板块背离，一条合成条件里混用三层。"""
    preds, errs = st.compile_condition(
        {"all": [
            {"label": "tf.stage_coarse", "op": "==", "value": "共建主线"},   # 大盘
            {"label": "tf.role_volume_top3", "op": "==", "value": True},      # 板块：量板块
            {"label": "tf.macd_bottom_div_confirm", "op": "==", "value": True},  # 板块结构
        ]},
        where="n1",
    )
    assert errs == [] and preds is not None and len(preds) == 3


# --- 跨子系统同名守卫（2026-10-07 补证包 FINDINGS §3） ---------------------


def test_known_cross_subsystem_reuse_is_declared() -> None:
    """桥上这 4 个名字在 index_stage 另有一份量上证日线的同名标签，必须已登记。"""

    from intelligence.services.teaching_framework.index_stage import STRUCTURE_EVENTS

    market_level = {f"tf.{name}" for name in STRUCTURE_EVENTS}
    reused = bridge._BRIDGED_LABELS & market_level
    assert reused == set(bridge._CROSS_SUBSYSTEM_REUSE), (
        "桥上开放的标签与 index_stage 市场级结构事件的重名集合，必须与登记表完全一致"
    )
    assert reused == {
        "tf.macd_bottom_div_observe", "tf.macd_bottom_div_confirm",
        "tf.macd_bottom_div_failed", "tf.macd_top_div",
    }


def test_undeclared_cross_subsystem_reuse_raises(monkeypatch) -> None:
    """新增一个未登记的重名 —— 导入期就得炸，不能等某棵树悄悄绑到另一层。"""

    monkeypatch.setattr(
        bridge, "_CROSS_SUBSYSTEM_REUSE",
        {k: v for k, v in bridge._CROSS_SUBSYSTEM_REUSE.items() if k != "tf.macd_top_div"},
    )
    with pytest.raises(AssertionError) as err:
        bridge._assert_no_undeclared_cross_subsystem_reuse()
    assert "tf.macd_top_div" in str(err.value)
    assert "上证日线" in str(err.value)


def test_stale_reuse_registration_raises(monkeypatch) -> None:
    """登记表留着桥上已没有的标签，会让下一个人以为重名还在。"""

    monkeypatch.setattr(
        bridge, "_CROSS_SUBSYSTEM_REUSE",
        {**bridge._CROSS_SUBSYSTEM_REUSE, "tf.not_on_the_bridge": "过期"},
    )
    with pytest.raises(AssertionError) as err:
        bridge._assert_no_undeclared_cross_subsystem_reuse()
    assert "tf.not_on_the_bridge" in str(err.value)


def test_market_level_structure_events_are_not_bridged() -> None:
    """市场级那批（含会改写历史的 _hist / _dif）没有被搬上桥 —— 搬了第一道断言会先炸。"""

    rewriting = {
        "tf.macd_top_div_hist", "tf.macd_top_div_dif",
        "tf.macd_bottom_div_hist", "tf.macd_bottom_div_dif",
        "tf.chan_stroke_bottom_divergence", "tf.chan_stroke_top_divergence",
        "tf.chan_third_buy", "tf.chan_third_sell",
    }
    assert not (bridge._BRIDGED_LABELS & rewriting), (
        "这批字段在 2026-10-07 补证包的前缀一致性检查里会改写历史（完整序列 vs 截至当天不一致），"
        "不能当历史实时信号搬上判定路径"
    )


# --- PIT 身份：历史切片上还看不看得见 -------------------------------------
#
# 这组测试是整件事的理由。在加 first_known_at 之前，实测过：trade_date 2026-01-12
# 的教学对象 recorded_at 是 2026-09-07（重建时刻），knowledge_cutoff=2026-01-12 时
# 整条教学轨退化成 Gap(pit_filtered)。也就是说「在长河里回放历史找规律」这件事，
# 当时在任何历史日上都拿不到一条教学读数。


def test_structure_event_survives_the_real_pit_gate(sidecar_with_structure: Path) -> None:
    """端到端：把对象真的喂给 ``river._enforce_cutoff``，站在当天回看。

    这是整件事的验收点。修之前，同样的调用会让整条轨变成 ``Gap(pit_filtered)``。
    """

    from intelligence.services.river import _enforce_cutoff
    from intelligence.services.teaching_framework.pit_identity import close_of

    objs = list(teaching_objects(sidecar_with_structure, DEV_DAY, top=2,
                                 entity_type="sector", entity_id=SECTOR_A))
    structure = [o for o in objs if o.object_type == "teaching_structure"]
    assert structure, "板块结构对象没出现"
    assert structure[0].recorded_at == close_of(DEV_DAY).isoformat(), (
        f"结构对象应盖在交易日收盘（{close_of(DEV_DAY).isoformat()}），实际 {structure[0].recorded_at}"
    )

    kept = _enforce_cutoff({"theme": structure}, DEV_DAY)
    assert not isinstance(kept["theme"], Gap), (
        f"站在 {DEV_DAY} 回看 {DEV_DAY} 的结构事件，整条轨却被滤成 {kept['theme']}"
    )
    assert [o.object_type for o in kept["theme"]] == ["teaching_structure"]


def test_structure_event_is_invisible_before_its_trade_date(sidecar_with_structure: Path) -> None:
    """反向：事件日之前回看，必须看不见。修 PIT 不能变成放行一切。"""

    from intelligence.services.river import _enforce_cutoff

    objs = list(teaching_objects(sidecar_with_structure, DEV_DAY, top=2,
                                 entity_type="sector", entity_id=SECTOR_A))
    structure = [o for o in objs if o.object_type == "teaching_structure"]
    day_before = "2026-01-11"
    assert day_before < DEV_DAY
    kept = _enforce_cutoff({"theme": structure}, day_before)
    assert isinstance(kept["theme"], Gap), "事件日之前就能看见 = 前视，比原来的毛病更严重"


def test_market_labels_are_still_filtered_and_that_is_honest(sidecar: Path) -> None:
    """市场级标签**仍然**在历史切片上不可见——没提交前缀一致性证据，fail-closed 是对的。

    这条测试是故意把范围讲清楚：加了 first_known_at 不等于 44 个标签一夜之间都有了
    PIT 身份。只有拿得出证据的那几个有。其余的要靠 carry-forward 从第一次构建起往后
    慢慢积累，或者补上前缀检查证据再进 KNOWABLE_AT_CLOSE。
    """

    from intelligence.services.teaching_framework.pit_identity import KNOWABLE_AT_CLOSE, close_of

    objs = list(teaching_objects(sidecar, DEV_DAY, top=2))
    stage = [o for o in objs if o.object_type == "teaching_stage"]
    assert stage, "阶段对象没出现"
    assert "tf.stage_coarse" not in KNOWABLE_AT_CLOSE
    assert stage[0].recorded_at != close_of(DEV_DAY).isoformat(), (
        "市场级阶段标签没有前缀一致性证据，不该声称交易日收盘就可知"
    )


def test_object_takes_the_latest_of_its_members_not_the_earliest() -> None:
    """对象是多条标签打包的整体：要到**最晚**那条也可知之后，整个对象才算可知。"""

    from datetime import datetime

    from intelligence.services.teaching_framework.river_objects import _earliest_known_values

    early, late = datetime(2026, 1, 5, 7, 0), datetime(2026, 3, 9, 7, 0)
    assert _earliest_known_values([early, late]) == late, "取 min 会让对象声称比其成分更早可知"


def test_any_missing_stamp_makes_the_whole_object_unknown() -> None:
    """任何一条成分没有戳记 ⇒ 整个对象 recorded_at=None ⇒ 河的闸 fail-closed 滤掉。"""

    from datetime import datetime

    from intelligence.services.teaching_framework.river_objects import _earliest_known_values

    assert _earliest_known_values([datetime(2026, 1, 5, 7, 0), None]) is None
    assert _earliest_known_values([]) is None


def test_rebuild_does_not_bump_the_stamp_when_content_is_unchanged() -> None:
    """重建的老毛病：DELETE 全表再插，把每一行历史的戳记都刷成今天。"""

    from datetime import date, datetime

    from intelligence.services.teaching_framework.pit_identity import first_known_at

    key = ("market", "market", date(2026, 1, 12), "tf.stage_coarse")
    previous = {key: (None, "左底向下", datetime(2026, 1, 15, 7, 0))}
    later = datetime(2026, 9, 30, 12, 0)
    kwargs = dict(label="tf.stage_coarse", entity_type="market", entity_id="market",
                  trade_date=date(2026, 1, 12), previous=previous, build_time=later)

    unchanged = first_known_at(value_num=None, value_text="左底向下", **kwargs)
    assert unchanged == datetime(2026, 1, 15, 7, 0), "内容没变却刷新了戳记 —— 正是要修的那个 bug"

    changed = first_known_at(value_num=None, value_text="高位震荡", **kwargs)
    assert changed == later, "值真的变了，那就是一条新读数，应该盖新戳"


def test_history_rewriting_fields_can_never_claim_close_of_day() -> None:
    """补证包证明会被后来行情改写的字段，永远不得声称「那天就知道」。"""

    from intelligence.services.teaching_framework import pit_identity

    assert not (pit_identity.KNOWABLE_AT_CLOSE & set(pit_identity.KNOWN_HISTORY_REWRITING))
    assert pit_identity.KNOWN_HISTORY_REWRITING["tf.chan_stroke_dir"] == 186
    note = pit_identity.horizon_note("tf.chan_fractal")
    assert "29 天不一致" in note and "build_time" in note


def test_registry_entries_must_carry_evidence() -> None:
    """声称「当天可知」要有证据；证据表留过期条目也要炸。"""

    from intelligence.services.teaching_framework import pit_identity

    assert set(pit_identity.KNOWABLE_AT_CLOSE) == set(pit_identity.KNOWABLE_AT_CLOSE_EVIDENCE)
    for label, why in pit_identity.KNOWABLE_AT_CLOSE_EVIDENCE.items():
        assert "structure_prefix_check" in why or "同 tf." in why, (
            f"{label} 的证据既没引用前缀一致性检查的收据，也没说明沿用哪一条"
        )
