"""时间长河 as-of 切片的契约测试（垂直切片 v0）。

只钉**契约**，不钉某一天的具体读数——读数会随每日同步变，钉死会变成日更噪声门禁。
真库不在时整份跳过：这些用例要证明的是「读真库能不能联立」，用桩证不了
（桩的形状复刻不了 `updated_at` 被重发布推走这类真实失败分支）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence.services.river import (
    TRACKS,
    Gap,
    RiverObject,
    RiverSlice,
    slice_river,
)

DB = Path("db/market_feature_store.duckdb")
# 实测存在且六轨齐全的一天（2026-09-05 复量）。换日子要连同理由一起改。
AS_OF = "2026-08-31"
ENTITY = "算力租赁"

pytestmark = pytest.mark.skipif(not DB.exists(), reason="需要真库 db/market_feature_store.duckdb")


# 判断轨必须显式喂夹具，不能走 `user_space()`：`conftest.py` 会 delenv
# `FORESIGHT_USERS_DIR`（防止测试读写真人目录，见那里 2026-08-11 的事故记录），
# 于是测试进程里判断轨**恒为缺口**——依赖真实文件的断言会永远 skip，是假门禁。
# 记录形状逐字段照抄真实 checkpoints.jsonl（id/ts/claim/category/themes/metric/due），
# 不简化：桩比现实简单时，守门断言够不到它要守的分支。
_CHECKPOINT_FIXTURE = {
    "id": f"ck-{AS_OF}-fixture",
    "ts": f"{AS_OF}T16:31:49+00:00",
    "claim": f"[{AS_OF}][旧逻辑唤醒] {ENTITY}：旧逻辑唤醒将获得新证据支撑",
    "category": "theme_evidence",
    "themes": [ENTITY],
    "stocks": [],
    "metric": {"type": "kb_evidence", "op": ">=", "target": 1.0, "target_name": ENTITY},
    "due": "2026-09-07",
    "source": "test-fixture",
}


@pytest.fixture(scope="module")
def checkpoints_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("river") / "checkpoints.jsonl"
    path.write_text(json.dumps(_CHECKPOINT_FIXTURE, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def sl(checkpoints_file: Path) -> RiverSlice:
    return slice_river(AS_OF, ENTITY, checkpoints_path=checkpoints_file)


def test_六条轨都有结果_要么对象要么缺口(sl: RiverSlice) -> None:
    assert set(sl.tracks) == set(TRACKS)
    for track, result in sl.tracks.items():
        assert isinstance(result, (list, Gap)), track
        if isinstance(result, list):
            assert result, f"{track} 返回空列表——空列表冒充「这条轨为零」，应返回 Gap"


def test_任何一条轨都不得用空列表冒充零(checkpoints_file: Path) -> None:
    """空列表和 ``Gap`` 的区别是「这条轨为零」和「这条轨读不出来」——不能混。

    单取一天证不了这件事：数据齐全的那天根本走不到空分支（变异测试实测：把某个
    provider 的 ``return Gap(...)`` 改成 ``return []``，只跑 2026-08-31 不会红）。
    所以横跨若干天取样，并**断言确实取到了缺口**——没取到就是前提失效，
    不是通过。
    """
    sampled = [
        slice_river(d, ENTITY, checkpoints_path=checkpoints_file)
        for d in ("2026-08-31", "2026-07-01", "2026-03-02", "2025-01-02")
    ]
    for sl_ in sampled:
        for track, result in sl_.tracks.items():
            if isinstance(result, list):
                assert result, f"{sl_.as_of} 的 {track} 返回空列表，应返回 Gap"
    observed = {g.reason for sl_ in sampled for g in sl_.gaps}
    assert "no_data" in observed, (
        f"取样里一个 no_data 缺口都没有（只见到 {observed}）——"
        "这条用例没触达它要守的分支，等于没跑"
    )


def test_幂等_同一入参两次调用逐字段相同() -> None:
    a = slice_river(AS_OF, ENTITY).to_dict()
    b = slice_river(AS_OF, ENTITY).to_dict()
    assert json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)


def test_每个对象都能回溯到主数据(sl: RiverSlice) -> None:
    for obj in sl.objects:
        assert isinstance(obj, RiverObject)
        assert obj.ref and ":" in obj.ref, obj
        assert obj.source_hash and len(obj.source_hash) == 16, obj
        # valid_from 不必等于 as_of：研报这类事件对象从它自己的日期起为真，
        # 切片只是在 as_of 这天把它取出来。真正的不变量是**不得来自未来**。
        assert obj.valid_from <= AS_OF, obj


def test_索引层不持有主数据副本(sl: RiverSlice) -> None:
    """payload 只放读切片所需的字段，不整表搬运（终局 §9 / F4 的可测化）。"""
    for obj in sl.objects:
        assert len(obj.payload) <= 20, f"{obj.ref} payload 字段过多，像在复制主数据"


def test_实体解析不做模糊匹配() -> None:
    """「算力」不是板块名，必须解析失败并六轨全缺，不能猜成「算力租赁」。"""
    sl = slice_river(AS_OF, "算力")
    assert len(sl.gaps) == len(TRACKS)
    assert all(g.reason == "entity_unresolved" for g in sl.gaps)


def test_缺轨返回_Gap_且写明原因(sl: RiverSlice) -> None:
    for gap in sl.gaps:
        assert gap.reason in {"no_data", "no_source", "entity_unresolved", "pit_filtered"}
        assert gap.detail, "缺口必须说清为什么缺，否则下游无法判断能不能补"


def test_require_strict_滤掉晚于_cutoff_的对象() -> None:
    """无前视红线：不能只降档、把决定推给下游。"""
    early = "2026-08-01"
    loose = slice_river(AS_OF, ENTITY, knowledge_cutoff=early)
    strict = slice_river(AS_OF, ENTITY, knowledge_cutoff=early, require_strict=True)
    assert any(o.recorded_at and o.recorded_at[:10] > early for o in loose.objects), (
        "前提失效：这一天已经没有晚于 cutoff 的对象了，本用例证不了滤除行为"
    )
    assert not strict.objects, "require_strict 下不应留下任何晚于 cutoff 的对象"
    assert any(g.reason == "pit_filtered" for g in strict.gaps)


def test_空切片不得报_strict() -> None:
    """``all([])`` 恒真——空切片报 strict 会让「六轨全缺」伪装成「全部通过 PIT」。"""
    empty = slice_river(AS_OF, ENTITY, knowledge_cutoff="2020-01-01", require_strict=True)
    assert not empty.objects
    assert empty.pit_grade == "trade_date_only"


def test_判断轨的_ref_用记录自带的稳定_id(sl: RiverSlice) -> None:
    judgment = sl.tracks["judgment"]
    assert not isinstance(judgment, Gap), "判断轨夹具没被读到——这条断言又变回假门禁了"
    for obj in judgment:
        assert obj.ref == f"checkpoints.jsonl:{_CHECKPOINT_FIXTURE['id']}", obj.ref
        assert obj.recorded_at, "判断轨是唯一原生带记录时刻的轨，不该为 None"
        # valid_from 是判断所指的交易日，不是写下的日子（roadmap G-02 判断轨专属规则）。
        assert obj.valid_from == AS_OF


def test_判断轨按实体精确匹配_不串轨(checkpoints_file: Path) -> None:
    """夹具挂在「算力租赁」上，取另一个板块的切片时判断轨必须是缺口。"""
    other = slice_river(AS_OF, "国防军工", checkpoints_path=checkpoints_file)
    assert isinstance(other.tracks["judgment"], Gap)


def test_六个维度就是终局钦定的那六条(sl: RiverSlice) -> None:
    """初版把「板块」单列、漏了「舆论」，与终局 §3 + F9 对不上。钉死，防再漂。"""
    assert TRACKS == ("market", "theme", "opinion", "capital", "stock", "judgment")
    assert set(sl.tracks) == set(TRACKS)


def test_舆论轨用_created_at_不用_updated_at(sl: RiverSlice) -> None:
    """该表的 ``updated_at`` 已被 09-02 那次批量重写抹平成一天，``created_at`` 才是真值。

    所以舆论轨的 ``recorded_at`` 必须早于（或等于）切片日——用错列会让它变成
    「未来才记下来的」，整片被降档甚至被无前视滤除。
    """
    opinion = sl.tracks["opinion"]
    if isinstance(opinion, Gap):
        pytest.skip(f"{AS_OF} 的「{ENTITY}」无卖方覆盖")
    for obj in opinion:
        assert obj.recorded_at, obj.ref
        assert obj.recorded_at[:10] <= AS_OF, f"{obj.ref} 的 recorded_at 晚于切片日"


def test_舆论轨不发明阶段词(sl: RiverSlice) -> None:
    """阶段词表是 G-06 待拍板项，且当前样本撑不住密度斜率——只能标 unverifiable。"""
    opinion = sl.tracks["opinion"]
    if isinstance(opinion, Gap):
        pytest.skip(f"{AS_OF} 的「{ENTITY}」无卖方覆盖")
    coverage = [o for o in opinion if o.object_type == "label"]
    assert coverage, "舆论轨应有一个覆盖度量对象"
    for obj in coverage:
        assert obj.payload["stage"] == "unverifiable"
        assert obj.payload["stage_reason"]
