"""`knowledge_cutoff` 不得晚于 `as_of`——时间穿越门禁（2026-09-06 评审 #598 硬伤）。

原缺陷：``cutoff = knowledge_cutoff or as_of`` 之后**零校验**。传 `2099-01-01`，
`_enforce_cutoff` 与 `pit_grade` 都拿它做比较 → **所有对象都通过 PIT 检查**，
回放读数因此偏乐观，而且自称 `pit_grade=strict`（即「无前视」）。
文档里早写着「必须 <= as_of」，只是没人执行——写了不拦等于没写。

spec §4.1 确实留了第三档「事后人工复核」允许 `C=now`，但要求标 `hindsight=true`
且**不得进入任何校准或方法有效性统计**。所以正确形状是**默认拒绝 + 显式签字**，
不是一律禁止。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from intelligence.services.river import TRACKS, Gap, RiverSlice, slice_river

DB = Path("db/market_feature_store.duckdb")
AS_OF = "2026-08-31"
ENTITY = "算力租赁"


def _slice(**over) -> RiverSlice:
    base = dict(
        as_of=AS_OF,
        entity_id="x",
        entity_name="x",
        knowledge_cutoff=AS_OF,
        tracks={t: Gap(t, "no_data") for t in TRACKS},
    )
    base.update(over)
    return RiverSlice(**base)


class TestHindsightGrade:
    """纯对象层，不需要真库。"""

    def test_hindsight_slice_is_never_strict(self) -> None:
        sl = _slice(knowledge_cutoff="2099-01-01", hindsight=True)
        assert sl.pit_grade == "trade_date_only"

    def test_hindsight_survives_serialization(self) -> None:
        """回放器可能只拿到 JSON——标记丢了，下游就无从知道这片带着后见之明。"""
        assert _slice(hindsight=True).to_dict()["hindsight"] is True
        assert _slice().to_dict()["hindsight"] is False

    def test_default_is_not_hindsight(self) -> None:
        assert _slice().hindsight is False


@pytest.mark.skipif(not DB.exists(), reason="需要真库 db/market_feature_store.duckdb")
class TestCutoffRejected:
    def test_future_cutoff_raises(self) -> None:
        with pytest.raises(ValueError, match="晚于 as_of"):
            slice_river(AS_OF, ENTITY, knowledge_cutoff="2099-01-01")

    def test_one_day_after_also_raises(self) -> None:
        """不是只拦离谱的年份：晚一天同样是前视。"""
        with pytest.raises(ValueError, match="晚于 as_of"):
            slice_river(AS_OF, ENTITY, knowledge_cutoff="2026-09-01")

    def test_equal_cutoff_is_allowed(self) -> None:
        sl = slice_river(AS_OF, ENTITY, knowledge_cutoff=AS_OF)
        assert sl.hindsight is False

    def test_earlier_cutoff_is_allowed(self) -> None:
        sl = slice_river(AS_OF, ENTITY, knowledge_cutoff="2026-08-20")
        assert sl.hindsight is False

    def test_explicit_opt_in_marks_the_slice(self) -> None:
        sl = slice_river(AS_OF, ENTITY, knowledge_cutoff="2099-01-01", allow_hindsight=True)
        assert sl.hindsight is True
        assert sl.pit_grade == "trade_date_only", "事后视角片不许自称 strict"

    def test_hindsight_and_require_strict_are_mutually_exclusive(self) -> None:
        """一个放进未来对象、一个要求无前视，同时传是自相矛盾，早点炸掉。"""
        with pytest.raises(ValueError, match="互斥"):
            slice_river(
                AS_OF, ENTITY, knowledge_cutoff="2099-01-01",
                allow_hindsight=True, require_strict=True,
            )
