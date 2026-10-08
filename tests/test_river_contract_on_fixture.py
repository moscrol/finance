"""时间长河的**可移植**契约测试——不需要真库，CI 上必跑。

与 `test_river_slice.py` 的分工（不要合并这两个文件）：

- `test_river_slice.py` 断言**真实数据语义**：供应商 .TI → .FP 的换源日、2026-01
  那次回填批次让累计覆盖失真、`fact_theme_fundamental_doc` 只有 5/37 份挂了
  linked_sectors。这些只有真库能证，所以它整份 ``skipif(not DB.exists())`` 是**对的**，
  本文件不去替它变绿——那会变成本仓反复警告的假门禁。
- 本文件断言**换一套数据也必须成立的不变量**：六轨齐全、缺轨报 Gap 不用空列表冒充、
  幂等、可回溯、无前视四道门、实体归一。这些此前**在 CI 上一次都没跑过**，
  因为 ``.gitignore`` 把 ``db/`` 与 ``*.duckdb`` 全排除，runner 上没有真库。

夹具库由 `tests/fixtures/river_mini_db.py` 按 `market_feature_store/schema.sql` 现建，
所以 schema 改了列名，夹具会在 `_require_tables` 或 INSERT 处直接报错，
不会悄悄测一个已经不存在的形状。
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from intelligence.services.river import (
    TRACKS,
    Gap,
    RiverObject,
    RiverSlice,
    slice_river,
)
from tests.fixtures.river_mini_db import (
    ALIAS_ENTITY,
    ALIAS_OLD_CODE,
    BARE_ENTITY,
    ENTITY,
    build_mini_db,
    checkpoint_fixture,
    trading_days,
)

DAYS = trading_days()
AS_OF = DAYS[10]
BEFORE_SWITCH = DAYS[2]
AFTER_SWITCH = DAYS[12]


@pytest.fixture(scope="module")
def db(tmp_path_factory: pytest.TempPathFactory) -> str:
    return build_mini_db(tmp_path_factory.mktemp("river-fixture") / "mini.duckdb")


@pytest.fixture(scope="module")
def ck(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("river-fixture-ck") / "checkpoints.jsonl"
    path.write_text(json.dumps(checkpoint_fixture(AS_OF), ensure_ascii=False) + "\n", encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def sl(db: str, ck: Path) -> RiverSlice:
    return slice_river(AS_OF, ENTITY, db_path=db, checkpoints_path=ck)


# --------------------------------------------------------------------------- #
# 结构：六轨齐全，缺轨报 Gap
# --------------------------------------------------------------------------- #
def test_六个维度就是终局钦定的那六条(sl: RiverSlice) -> None:
    """初版把「板块」单列、漏了「舆论」，与终局 §3 + F9 对不上。钉死，防再漂。"""
    assert TRACKS == ("market", "theme", "opinion", "capital", "stock", "judgment")
    assert set(sl.tracks) == set(TRACKS)


def test_每条轨要么有对象要么是缺口_不得用空列表冒充零(sl: RiverSlice) -> None:
    for track, result in sl.tracks.items():
        assert isinstance(result, (list, Gap)), track
        if isinstance(result, list):
            assert result, f"{track} 返回空列表——空列表冒充「这条轨为零」，应返回 Gap"


def test_无覆盖的实体舆论轨报_no_data_阳性对照(db: str, ck: Path) -> None:
    """夹具故意不给 BARE_ENTITY 发任何研报。取不到这个缺口 = 这条用例没触达分支。"""
    bare = slice_river(AS_OF, BARE_ENTITY, db_path=db, checkpoints_path=ck)
    opinion = bare.tracks["opinion"]
    assert isinstance(opinion, Gap), "无卖方覆盖的板块，舆论轨必须是缺口"
    assert opinion.reason == "no_data"
    assert opinion.detail, "缺口必须说清为什么缺，否则下游无法判断能不能补"


def test_缺轨返回_Gap_且原因在白名单内(sl: RiverSlice) -> None:
    for gap in sl.gaps:
        assert gap.reason in {"no_data", "no_source", "entity_unresolved", "pit_filtered"}
        assert gap.detail


def test_实体解析不做模糊匹配(db: str, ck: Path) -> None:
    """「算力」不是板块名，必须解析失败并六轨全缺，不能猜成「算力租赁」。"""
    sl_ = slice_river(AS_OF, "算力", db_path=db, checkpoints_path=ck)
    assert len(sl_.gaps) == len(TRACKS)
    assert all(g.reason == "entity_unresolved" for g in sl_.gaps)


# --------------------------------------------------------------------------- #
# 幂等与可回溯
# --------------------------------------------------------------------------- #
def test_幂等_同一入参两次调用逐字段相同(db: str, ck: Path) -> None:
    a = slice_river(AS_OF, ENTITY, db_path=db, checkpoints_path=ck).to_dict()
    b = slice_river(AS_OF, ENTITY, db_path=db, checkpoints_path=ck).to_dict()
    assert json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)


def test_每个对象都能回溯到主数据(sl: RiverSlice) -> None:
    assert sl.objects, "前提失效：夹具切片一个对象都没有，下面的断言等于没跑"
    for obj in sl.objects:
        assert isinstance(obj, RiverObject)
        assert obj.ref and ":" in obj.ref, obj
        assert obj.source_hash and len(obj.source_hash) == 16, obj
        assert obj.valid_from <= AS_OF, obj


def test_索引层不持有主数据副本(sl: RiverSlice) -> None:
    """payload 只放读切片所需的字段，不整表搬运（终局 §9 / F4 的可测化）。"""
    for obj in sl.objects:
        assert len(obj.payload) <= 20, f"{obj.ref} payload 字段过多，像在复制主数据"


def test_判断轨的_ref_用记录自带的稳定_id(sl: RiverSlice) -> None:
    judgment = sl.tracks["judgment"]
    assert not isinstance(judgment, Gap), "判断轨夹具没被读到——这条断言又变回假门禁了"
    for obj in judgment:
        assert obj.ref == f"checkpoints.jsonl:{checkpoint_fixture(AS_OF)['id']}"
        assert obj.recorded_at, "判断轨是唯一原生带记录时刻的轨，不该为 None"
        assert obj.valid_from == AS_OF


def test_判断轨按实体精确匹配_不串轨(db: str, ck: Path) -> None:
    other = slice_river(AS_OF, ALIAS_ENTITY, db_path=db, checkpoints_path=ck)
    assert isinstance(other.tracks["judgment"], Gap)


# --------------------------------------------------------------------------- #
# 无前视：四道门
# --------------------------------------------------------------------------- #
def test_cutoff_晚于_as_of_直接拒绝(db: str, ck: Path) -> None:
    """默认拒绝而不是默认放行：传 2099 会让所有对象通过 PIT 检查，
    回放结果因此偏乐观且自称可信。"""
    with pytest.raises(ValueError, match="事后视角"):
        slice_river(AS_OF, ENTITY, knowledge_cutoff="2099-01-01", db_path=db, checkpoints_path=ck)


def test_hindsight_显式签字后不得报_strict(db: str, ck: Path) -> None:
    sl_ = slice_river(AS_OF, ENTITY, knowledge_cutoff=DAYS[-1], allow_hindsight=True,
                      db_path=db, checkpoints_path=ck)
    assert sl_.hindsight is True
    assert sl_.pit_grade != "strict"


def test_allow_hindsight_与_require_strict_互斥(db: str, ck: Path) -> None:
    with pytest.raises(ValueError, match="互斥"):
        slice_river(AS_OF, ENTITY, knowledge_cutoff=DAYS[-1], allow_hindsight=True,
                    require_strict=True, db_path=db, checkpoints_path=ck)


def test_require_strict_滤掉晚于_cutoff_的对象(db: str, ck: Path) -> None:
    """无前视红线：不能只降档、把决定推给下游。"""
    early = DAYS[0]
    loose = slice_river(AS_OF, ENTITY, knowledge_cutoff=early, db_path=db, checkpoints_path=ck)
    strict = slice_river(AS_OF, ENTITY, knowledge_cutoff=early, require_strict=True,
                         db_path=db, checkpoints_path=ck)
    assert any(o.recorded_at and o.recorded_at[:10] > early for o in loose.objects), (
        "前提失效：这一天已经没有晚于 cutoff 的对象了，本用例证不了滤除行为"
    )
    assert not strict.objects, "require_strict 下不应留下任何晚于 cutoff 的对象"
    assert any(g.reason == "pit_filtered" for g in strict.gaps)


def test_空切片不得报_strict(db: str, ck: Path) -> None:
    """``all([])`` 恒真——空切片报 strict 会让「六轨全缺」伪装成「全部通过 PIT」。"""
    empty = slice_river(AS_OF, ENTITY, knowledge_cutoff="2020-01-02", require_strict=True,
                        db_path=db, checkpoints_path=ck)
    assert not empty.objects
    assert empty.pit_grade == "trade_date_only"


# --------------------------------------------------------------------------- #
# 实体归一：身份稳定，可比性另说
# --------------------------------------------------------------------------- #
def test_实体身份跨供应商换源必须稳定(db: str, ck: Path) -> None:
    """夹具在第 8 个交易日把 ALIAS_ENTITY 的代码从 .TI 换成 .FP。
    不归一的话，同一个板块在换源前后是两个 entity_id，区间与队列查询会把它悄悄劈成两个实体。"""
    before = slice_river(BEFORE_SWITCH, ALIAS_ENTITY, db_path=db, checkpoints_path=ck)
    after = slice_river(AFTER_SWITCH, ALIAS_ENTITY, db_path=db, checkpoints_path=ck)
    assert before.entity_id == after.entity_id, "跨换源日 entity_id 不一致，河上实体断代了"
    assert before.alias_applied is True and after.alias_applied is False, (
        "alias_applied 没如实标记——前提失效则本用例证不了归一行为"
    )


def test_ref_保留当天真实代码不被归一改写(db: str, ck: Path) -> None:
    """entity_id 归一，但 ref 指向的是那一行真实数据——改了就回溯不过去。"""
    sl_ = slice_river(BEFORE_SWITCH, ALIAS_ENTITY, db_path=db, checkpoints_path=ck)
    refs = [o.ref for o in sl_.objects if o.entity_id != "__market__" and "fact_sector_daily" in o.ref]
    assert refs, "这一天的盘面轨没有板块量价对象，本用例证不了 ref 行为"
    assert all(ALIAS_OLD_CODE in r for r in refs), f"ref 被归一改写了：{refs[:2]}"


# --------------------------------------------------------------------------- #
# 轨内口径
# --------------------------------------------------------------------------- #
def test_题材轨用已解析的整数而不是字符串(sl: RiverSlice) -> None:
    """sync 已经把「1/1」解析成 up_stat_days / up_stat_boards 两个整数存好了，
    2026-09-05 审计发现整数列全仓无人读、下游还在解析字符串。"""
    theme = sl.tracks["theme"]
    assert not isinstance(theme, Gap), "夹具每天都有涨停成分，前提失效"
    # 题材轨同时发 stage（阶段，派生自时间线）与 event（当日涨停成分）两类对象，
    # up_stat_* 只在后者上。不筛类型会把阶段对象也要求带涨停字段，是断言写错不是实现错。
    events = [o for o in theme if o.object_type == "event"]
    assert events, "夹具每天都有涨停成分，题材轨应有 event 对象"
    for obj in events:
        assert "up_stat_days" in obj.payload
        days = obj.payload["up_stat_days"]
        assert days is None or isinstance(days, int), f"应是整数而不是字符串：{days!r}"


def test_舆论轨用_created_at_不用_updated_at(sl: RiverSlice) -> None:
    """夹具把研报的 ``updated_at`` 全部设成区间最后一天（复刻真表被批量重写抹平的形状）。
    读错列会让舆论轨对象变成「未来才记下来的」，这条断言就会红。"""
    opinion = sl.tracks["opinion"]
    assert not isinstance(opinion, Gap), "夹具给了卖方覆盖，前提失效"
    for obj in opinion:
        assert obj.recorded_at, obj.ref
        assert obj.recorded_at[:10] <= AS_OF, f"{obj.ref} 的 recorded_at 晚于切片日"


def test_产业文档不参与任何度量(sl: RiverSlice) -> None:
    """core_theme / verification_points 是散文：可读、可进 prompt，但不可重算。
    它们只能待在 payload 里，不得混进覆盖度量那个对象。"""
    opinion = sl.tracks["opinion"]
    assert not isinstance(opinion, Gap)
    coverage = [o for o in opinion if o.object_type == "label"]
    assert coverage, "舆论轨应有一个覆盖度量对象"
    for obj in coverage:
        assert "core_theme" not in obj.payload
        assert "verification_points" not in obj.payload


def test_散文对象的_derivation_是_frozen_llm(sl: RiverSlice) -> None:
    """09-06 spec §4.2 两类派生：只有 deterministic 的能进条件与统计。
    产业文档是模型写一次的散文，必须标 frozen_llm，否则会被当成可重算的事实。"""
    opinion = sl.tracks["opinion"]
    assert not isinstance(opinion, Gap)
    docs = [o for o in opinion if o.object_type == "narrative_version"]
    assert docs, "产业文档没接上——审计发现的那张无人读的表又断了"
    for d in docs:
        assert d.derivation == "frozen_llm", f"{d.ref} 的 derivation 应为 frozen_llm"


# --------------------------------------------------------------------------- #
# 区间派生：线状特征
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def win(db: str, ck: Path):
    from intelligence.services.river_window_contract import window

    return window(DAYS[0], DAYS[-1], ENTITY, knowledge_cutoff=DAYS[-1],
                  db_path=db, checkpoints_path=ck)


def test_区间每一片与单点切片逐字节相同(win, db: str, ck: Path) -> None:
    """``window()`` 今天是逐日调 ``slice_river``；日后若加按区间批量取数的快路径，
    正确性靠这条断言守，不靠信任。"""
    for sl_ in win.slices:
        # 区间里每一天都用同一个 C 读：对 day < end 的天，C > day 在**单点**语义里叫
        # hindsight，所以 window() 取片时传 allow_hindsight=True，再把 hindsight 标记改成
        # **区间级**的（C > end 才算）。复现时必须照做，否则比的是两种不同口径。
        same = slice_river(sl_.as_of, ENTITY, knowledge_cutoff=DAYS[-1], allow_hindsight=True,
                           db_path=db, checkpoints_path=ck)
        # `replace(sl, hindsight=...)` 会重跑 __post_init__，pit_grade 随之由区间级标记
        # 重算——所以复现时也要走同一个 replace，比的才是同一个口径。
        same = replace(same, hindsight=False)
        assert sl_.hindsight is False, "区间级 hindsight：C 不晚于 end 时整段都不是事后视角"
        assert json.dumps(sl_.to_dict(), sort_keys=True, default=str) == json.dumps(
            same.to_dict(), sort_keys=True, default=str
        ), sl_.as_of


def test_transition_抓出跃迁且每次都能回溯到相邻两天(win) -> None:
    """这是「线」而不是「点的罗列」的最小证据：带日期、带方向、带源行。"""
    from intelligence.services import river_derive as rd

    obj = rd.derive_transitions(win, "market_stage")
    assert obj.payload["status"] == "ok"
    transitions = obj.payload["transitions"]
    assert transitions, "夹具的 market_stage 逐日变化，必须抓到跃迁；抓不到说明派生断了"
    for t in transitions:
        assert t["from"] != t["to"]
        assert len(t["refs"]) == 2, "跃迁要能回溯到相邻两天各自的源行"
    assert obj.validity_kind == "range"
    assert obj.payload["pit_grade"] in {"strict", "trade_date_only"}


def test_streak_拒绝非布尔标签_不返回假零(win) -> None:
    """回归：``market_stage`` 是分类标签，此前会静默返回 longest=0 且 status=ok。

    那个 0 看着像一个正常读数，调用方无从知道自己问错了问题。
    """
    from intelligence.services.river_derive import LabelNotSliceEvaluable, derive_streak

    with pytest.raises(LabelNotSliceEvaluable, match="只接布尔谓词"):
        derive_streak(win, "market_stage")


def test_streak_对布尔谓词仍然正常工作(win) -> None:
    """阳性对照：加了类型门之后，布尔标签这条路不能被一起堵死。"""
    from intelligence.services.river_derive import derive_streak

    obj = derive_streak(win, "dual_red_strict")
    assert obj.payload["status"] in {"ok", "unverifiable"}
    if obj.payload["status"] == "ok":
        assert isinstance(obj.payload["longest"], int)
        assert obj.payload["days"] == len(win.slices)


def test_派生对象可拆回到天(win) -> None:
    from intelligence.services import river_derive as rd

    obj = rd.derive_transitions(win, "market_stage")
    assert obj.payload["member_refs"], "member_refs 为空 = 区间派生回溯不到天"
    assert all(":" in r for r in obj.payload["member_refs"])


# --------------------------------------------------------------------------- #
# 标签词汇：白名单是整条河的表达力上限
#
# 这一组测的不是「某个标签算得对不对」（那是 parity 测试的事），而是**白名单本身**：
# 它有几个词、每个词是不是真能在切片上出值、下游拿到的名单是不是同一份。
# 之所以要专门钉：白名单少一个词，河就少一种说法，而少说一种话**不会让任何测试变红**。
# --------------------------------------------------------------------------- #
def test_夹具必须让每个可判标签都出现过非空值() -> None:
    """阳性对照的阳性对照。

    若某个标签在整个夹具区间恒为 None，所有关于它的断言都会「通过」而什么都没验到——
    本仓反复点名的那种绿。这条在 15 天里逐个标签数非空格子，恒空直接红，
    并把人指回夹具的 *_BY_DAY 序列。
    """
    pytest.importorskip("duckdb")
    from intelligence.services.river_derive import SLICE_EVALUABLE_LABELS, bind

    import tests.fixtures.river_mini_db as fx

    path = build_mini_db(Path(str(fx.__file__)).parent / "_vocab_tmp.duckdb")
    try:
        empty: list[str] = []
        for label in SLICE_EVALUABLE_LABELS:
            seen = set()
            for day in DAYS:
                s = slice_river(day, ENTITY, db_path=path, allow_hindsight=True)
                v, _ = bind(label, s)
                if v is not None:
                    seen.add(v)
            if not seen:
                empty.append(label)
        assert not empty, (
            f"这些标签在夹具的 {len(DAYS)} 天里恒为 None，关于它们的断言都是假绿："
            f"{empty}；去 tests/fixtures/river_mini_db.py 的 *_BY_DAY 序列里给它们喂值"
        )
    finally:
        Path(path).unlink(missing_ok=True)


@pytest.mark.parametrize("label", ["multi_period_resonance", "opinion_stage", "lifecycle_stage"])
def test_新接线的标签在切片上真的出值并带_ref(sl: RiverSlice, label: str) -> None:
    """接线有没有接上，看的是「出值 + 带 ref」两件事一起成立。

    只断言出值不够：绑定函数返回 ``(值, [])`` 也能让值看起来对，但派生对象的
    ``member_refs`` 会是空的，于是「可拆回到天」这条契约在它身上静默失效
    （``cumulative.member_refs`` 为空就是现成的例子，见质检 P2）。
    """
    from intelligence.services.river_derive import bind

    value, refs = bind(label, sl)
    assert value is not None, f"{label} 在 {AS_OF} 应能判出值（夹具这天有原料）"
    assert refs, f"{label} 判出了 {value!r} 却没带 ref，下游拆不回源行"
    assert all(r in {o.ref for o in sl.objects} for r in refs), f"{label} 的 ref 不在本切片对象里"


def test_白名单里的名字必须都是已注册标签() -> None:
    """G-16 红线：河不新造标签名。

    绑定层是最容易破这条线的地方——写个新函数塞进 dict 就能让情景树用上一个
    ``ALL_LABELS`` 里没有的词，而且跑得通。那样一来「标签」就有两个互不知道的注册表，
    ``label_version`` 也不再能描述派生对象实际用了什么口径。
    """
    from intelligence.services.methodology_backtest.labels import ALL_LABELS
    from intelligence.services.river_derive import SLICE_EVALUABLE_LABELS

    unknown = sorted(set(SLICE_EVALUABLE_LABELS) - set(ALL_LABELS))
    assert not unknown, f"绑定层出现了未注册标签 {unknown}；要新标签请先进 labels.py 并升 LABEL_VERSION"


def test_下游看到的可判名单与河完全一致() -> None:
    """``research_evolution.adapters`` 与 ``scenario_trees`` 必须读同一份白名单。

    adapters 原本手抄了一份四元组。手抄件只会往一个方向出错：河扩了词、抄件没跟上，
    于是新标签在 01 的目录里不出现——**功能悄悄不生效，没有任何测试会红**。
    """
    from intelligence.services import scenario_trees
    from intelligence.services.research_evolution import adapters
    from intelligence.services.river_derive import SLICE_EVALUABLE_LABELS

    expected = tuple(SLICE_EVALUABLE_LABELS)
    assert tuple(adapters.SLICE_EVALUABLE_LABELS) == expected
    assert tuple(scenario_trees.SLICE_EVALUABLE_LABELS) == expected


def test_resonance_是布尔列的直接投影_不做任何解释(sl: RiverSlice) -> None:
    """标签层是 ``CASE WHEN … IS NULL THEN NULL WHEN … THEN 1 ELSE 0 END``，没有阈值。
    绑定层若自作主张（比如把 0 当缺失、把字符串 'N' 当真），两条路径会对同一天给出
    不同真值且无人报错。这里直接拿源行的原值比。"""
    from intelligence.services.river_derive import bind

    quote = next(
        o for o in sl.objects
        if o.track == "market" and o.object_type == "label" and "sector_ts_code" in o.payload
    )
    raw = quote.payload.get("multi_period_resonance")
    value, _ = bind("multi_period_resonance", sl)
    assert value == (None if raw is None else bool(raw)), f"源行 {raw!r} 投影成了 {value!r}"


def test_lifecycle_取当天读数而不是段落表的事后视角(sl: RiverSlice) -> None:
    """题材轨的 stage 对象同时带 ``stage``（站在当天）与 ``segment_hindsight``
    （段落表的事后视角：起点回溯、短段合并）。两者可以不同，而 PIT 下只有前者可用。
    绑定取错会让「当时就知道」这件事凭空成立——最难发现的那类前视。"""
    from intelligence.services.river_derive import bind

    stage_obj = next(
        o for o in sl.objects
        if o.track == "theme" and o.object_type == "stage" and o.payload.get("mapping_version")
    )
    value, refs = bind("lifecycle_stage", sl)
    assert value == stage_obj.payload["stage"]
    assert refs == [stage_obj.ref]


def test_opinion_stage_取舆论轨已算好的那个对象_不重算(sl: RiverSlice) -> None:
    """切片的舆论轨已经调过 ``opinion_stage.derive_stage``，标签层调的是同一个函数。
    绑定层若重算一遍，就有了第三份实现，而三份实现迟早不一致。"""
    from intelligence.services.river_derive import bind

    stage_obj = next(o for o in sl.objects if o.track == "opinion" and o.object_type == "stage")
    value, refs = bind("opinion_stage", sl)
    assert value == stage_obj.payload["stage"]
    assert refs == [stage_obj.ref]


def test_新标签立刻可以作为情景树的分枝条件() -> None:
    """这条是整次扩张的**验收**：词汇扩了，判读层要真的能用上。

    情景树的编译器只认 ``SLICE_EVALUABLE_LABELS``（它直接 import 那个 dict），
    所以「白名单多了三个词」与「情景树多了三种分枝」之间不该有第二道闸。
    这里正反各验一次：新标签编得过，仍不可判的标签照旧被拒。
    """
    from intelligence.services import scenario_trees as st

    ok, errs = st.compile_condition(
        {"all": [{"label": "lifecycle_stage", "op": "in", "value": ["主升", "分歧"]},
                 {"label": "multi_period_resonance", "op": "==", "value": True}]},
        where="node.test",
    )
    assert not errs, f"新标签应能编译成条件，却被拒：{errs}"
    assert ok is not None

    _, errs2 = st.compile_condition(
        {"all": [{"label": "ma5_peak_confirmed", "op": "==", "value": True}]}, where="node.neg"
    )
    assert any(e.code == st.E_LABEL_NOT_SLICE_EVALUABLE for e in errs2), (
        "仍然判不了的标签必须继续被拒——否则这次扩张顺手放进来了一个河其实算不出的词"
    )


def test_lifecycle_跃迁可被_derive_transitions_抓出(win) -> None:
    """扩词汇的直接产物：多了一类**线状**对象。

    扩张之前 ``derive_transitions`` 只能跑在 ``market_stage`` 上——整条河唯一一个
    有段位语义的词。接上 ``lifecycle_stage`` 之后，「这个题材什么时候从发酵走到主升」
    第一次成为可机读的派生对象，而不是要人去翻 15 天的原始行。

    顺带钉住一处容易被当成 bug 的**正确行为**：题材在首个盘面信号之前没有段
    （夹具第 1 天就是这种日子），默认 ``gap_policy="unverifiable"`` 下整个对象判
    unverifiable 并写明缺哪天——缺一天不是「没跃迁」。要数跃迁就得显式选 ``break``，
    把「那天不知道」这件事签字画押地当成中断。两条路径都验，否则只验了舒服的那条。
    """
    from intelligence.services import river_derive as rd

    default = rd.derive_transitions(win, "lifecycle_stage")
    assert default.object_type == "transition"
    assert default.payload["status"] == "unverifiable", "段外的那天必须让整个对象降级，不能默默跳过"
    assert any(g.startswith("missing:") for g in default.payload["gaps_applied"]), "要写明缺的是哪天"
    assert "count" not in default.payload, "unverifiable 的对象不得同时给出一个像是结论的计数"

    counted = rd.derive_transitions(win, "lifecycle_stage", gap_policy="break")
    assert counted.payload["status"] == "ok"
    assert counted.payload["count"] >= 1, "夹具里 lifecycle_stage 确实换过段，应至少抓到一次跃迁"
    for t in counted.payload["transitions"]:
        assert t["from"] != t["to"], "跃迁两端必须不同，否则是把「没变」记成了变化"
        assert t["day"] in DAYS
    assert counted.payload["member_refs"], "跃迁对象必须能拆回到源行"


# --------------------------------------------------------------------------- #
# 文本标签的取值域
#
# 由一次「agent 真实消费」实验挖出来的：扩张后把三个 text 标签接进白名单，
# agent 写分枝条件时必须填一个取值——而编译器此前只查字符（不许有 SQL 味），
# **不查这个词在不在词表里**。写错一个字，条件编译通过、运行零报错、永远命中 0 天。
# 「从未成立」与「今天没成立」在读数上长得一模一样，和 derive_streak 的假零同形。
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("label", "value", "should_pass"),
    [
        ("lifecycle_stage", "主升", True),      # 词表内
        ("lifecycle_stage", "主升段", False),   # 本仓自己的七段里没有这个词
        ("opinion_stage", "拥挤", True),
        ("opinion_stage", "过热", False),       # 像行话，但不是 derive_stage 的输出
        ("market_stage", "主升", True),
        ("market_stage", "主升阶段", False),    # 未归一：绑定层给的是「主升」
        # 「反弹」在夹具 15 天里一次没出现，但它是上游合法段位。必须放行——
        # market_stage 的取值由供应商决定，硬编有限词表会在上游新增段位时误杀。
        ("market_stage", "反弹", True),
    ],
)
def test_文本条件的取值必须真能命中(label: str, value: str, should_pass: bool) -> None:
    from intelligence.services import scenario_trees as st

    _, errs = st.compile_condition(
        {"all": [{"label": label, "op": "in", "value": [value]}]}, where="node.x"
    )
    if should_pass:
        assert not errs, f"{label}={value!r} 是合法取值，不该被拒：{[e.detail for e in errs]}"
    else:
        assert errs, f"{label}={value!r} 永远命中不了，必须在编译期就拒绝"


def test_取值被拒时要把合法词表摊给调用方() -> None:
    """报错只说「非法」等于把人/agent 推回去读源码。

    封闭词表的标签要列出全部合法值；market_stage 这种上游拥有取值的，
    要给出归一后的正确写法。两种都要让对方**看完报错就能改对**。
    """
    from intelligence.services import scenario_trees as st

    _, errs = st.compile_condition(
        {"all": [{"label": "lifecycle_stage", "op": "==", "value": "主升段"}]}, where="n"
    )
    assert errs and "酝酿" in errs[0].detail and "回流" in errs[0].detail, "要把七段全列出来"

    _, errs2 = st.compile_condition(
        {"all": [{"label": "market_stage", "op": "==", "value": "主升阶段"}]}, where="n"
    )
    assert errs2 and "'主升'" in errs2[0].detail, "要直接给出归一后的正确写法"


def test_market_stage_不得声明有限词表() -> None:
    """守住一条**不要做的事**。

    ``normalize_market_stage`` 的 docstring 明写规则是 data-driven 而非有限别名表，
    为的是上游新增段位时自动获得同样的归一处理。若哪天有人给 market_stage 加了封闭词表，
    一个合法的新段位会被判成非法——比漏判更糟，且会在上游变更的当天才爆。
    """
    from intelligence.services.methodology_backtest import rules

    assert "market_stage" in rules.OPEN_TEXT_LABELS
    assert "market_stage" not in rules._closed_text_domains()  # noqa: SLF001


def test_词表从各自的_SSOT_现取而不是抄一份() -> None:
    """抄一份就等着漂移：词表改了、校验还按旧表拒，错误信息里列的也是旧词。"""
    from intelligence.services.methodology_backtest import rules
    from intelligence.services.opinion_stage import STAGES
    from intelligence.services.theme_stage_vocab import CANONICAL_STAGES

    domains = rules._closed_text_domains()  # noqa: SLF001
    assert domains["lifecycle_stage"] == tuple(CANONICAL_STAGES)
    assert domains["opinion_stage"] == (*STAGES, "unverifiable")
