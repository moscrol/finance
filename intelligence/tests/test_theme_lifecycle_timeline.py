from __future__ import annotations

import unittest
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from intelligence.services.theme_lifecycle_timeline import (
    STAGE_DIVERGENCE,
    STAGE_EBB,
    STAGE_FERMENT,
    STAGE_FIRST_MOVE,
    STAGE_INCUBATION,
    STAGE_MAIN_UP,
    STAGE_REFLOW,
    derive_stages,
    is_double_red,
    lifecycle_markdown,
    load_message_dates,
    load_theme_daily_rows,
    load_theme_timeline_artifact,
)

try:
    import duckdb
except Exception:  # pragma: no cover
    duckdb = None


def _day(i: int) -> str:
    return (date(2026, 3, 2) + timedelta(days=i)).isoformat()


def _row(
    i: int,
    pct: float = -0.5,
    diff: float = 2.0,
    amount: float = 300.0,
    limit_up: float | None = None,
    first_board: float | None = None,
    boards: float | None = None,
) -> dict:
    return {
        "trade_date": _day(i),
        "pct_chg": pct,
        "diff_ratio": diff,
        "amount": amount,
        "limit_up_count": limit_up,
        "market_share": None,
        "max_boards": boards,
        "first_board_count": first_board,
    }


def _dr(i: int, amount: float = 900.0, boards: float | None = None, **kw) -> dict:
    """双红日。"""
    return _row(i, pct=2.5, diff=15.0, amount=amount, boards=boards, **kw)


class DoubleRedTests(unittest.TestCase):
    def test_strict_definition(self) -> None:
        self.assertTrue(is_double_red(_dr(0)))
        self.assertFalse(is_double_red(_row(0, pct=2.5, diff=15.0, amount=400.0)))
        self.assertFalse(is_double_red(_row(0, pct=-0.1, diff=15.0, amount=900.0)))
        self.assertFalse(is_double_red(_row(0, pct=2.5, diff=8.0, amount=900.0)))
        self.assertFalse(is_double_red({"trade_date": _day(0)}))


class DeriveStagesTests(unittest.TestCase):
    def test_empty_rows_gap(self) -> None:
        segments, gaps = derive_stages([])
        self.assertEqual(segments, [])
        self.assertTrue(any("无盘面逐日行" in g for g in gaps))

    def test_no_signal_declares_gap(self) -> None:
        segments, gaps = derive_stages([_row(i) for i in range(30)])
        self.assertEqual(segments, [])
        self.assertTrue(any("未进入盘面生命周期" in g for g in gaps))

    def test_full_cycle_with_reflow(self) -> None:
        rows = []
        # 0-2 弱势；3 首板日（涨停出现但未双红）；4-8 连续双红且高度抬升（主升）；
        # 9 放量新高但边际转负（分歧）；10-15 断红 ≥5 日（退潮）；
        # 16-17 连续两日双红（滞回确认 → 回流，起点回溯 16）
        rows += [_row(i) for i in range(3)]
        rows.append(_row(3, limit_up=2.0, first_board=2.0, boards=1.0))
        rows.append(_dr(4, amount=900.0, boards=2.0))
        rows.append(_dr(5, amount=1000.0, boards=3.0))
        rows.append(_dr(6, amount=1100.0, boards=4.0))
        rows.append(_dr(7, amount=1200.0, boards=5.0))
        rows.append(_dr(8, amount=1300.0, boards=5.0))
        rows.append(_row(9, pct=-1.0, diff=-5.0, amount=1500.0, boards=5.0))
        rows += [_row(10 + k, boards=1.0) for k in range(6)]
        rows.append(_dr(16, amount=800.0, boards=2.0))
        rows.append(_dr(17, amount=850.0, boards=2.0))
        rows.append(_row(18))

        message_dates = (_day(0), _day(1))
        segments, gaps = derive_stages(rows, message_dates=message_dates)
        stages = [s.stage for s in segments]
        self.assertEqual(
            stages,
            [
                STAGE_INCUBATION,
                STAGE_FIRST_MOVE,
                STAGE_FERMENT,
                STAGE_MAIN_UP,
                STAGE_DIVERGENCE,
                STAGE_EBB,
                STAGE_REFLOW,
            ],
        )
        by_stage = {s.stage: s for s in segments}
        self.assertEqual(by_stage[STAGE_INCUBATION].start_date, _day(0))
        self.assertEqual(by_stage[STAGE_FIRST_MOVE].start_date, _day(3))
        self.assertEqual(by_stage[STAGE_FERMENT].start_date, _day(4))
        self.assertEqual(by_stage[STAGE_MAIN_UP].start_date, _day(6))
        self.assertIn("高度抬升", by_stage[STAGE_MAIN_UP].trigger)
        self.assertEqual(by_stage[STAGE_DIVERGENCE].start_date, _day(9))
        # 退潮起点回溯到断红首日（分歧日 9 是首个断红日）
        self.assertEqual(by_stage[STAGE_EBB].start_date, _day(9))
        # 回流经两日确认，起点回溯到确认串首日 16
        self.assertEqual(by_stage[STAGE_REFLOW].start_date, _day(16))
        self.assertIn("确认回流", by_stage[STAGE_REFLOW].trigger)
        # 消息面已提供 → 不应报酝酿缺口
        self.assertFalse(any("酝酿段无法判定" in g for g in gaps))

    def test_isolated_double_red_in_ebb_does_not_flip(self) -> None:
        # 滞回核心：退潮中孤立单日双红不切回流（这正是 live 上 53 段锯齿的根源）
        rows = [_dr(i) for i in range(4)]                      # 发酵/主升
        rows += [_row(4 + k) for k in range(6)]                # 退潮
        rows.append(_dr(10))                                   # 孤立单日双红
        rows += [_row(11 + k) for k in range(6)]               # 继续断红
        rows.append(_dr(18))                                   # 又一次孤立
        rows.append(_row(19))
        segments, _ = derive_stages(rows)
        stages = [s.stage for s in segments]
        self.assertNotIn(STAGE_REFLOW, stages)
        self.assertEqual(segments[-1].stage, STAGE_EBB)

    def test_reflow_confirm_one_restores_sensitive_behavior(self) -> None:
        rows = [_dr(i) for i in range(4)]
        rows += [_row(4 + k) for k in range(6)]
        rows.append(_dr(10))
        rows.append(_row(11))
        segments, _ = derive_stages(rows, reflow_confirm_days=1)
        self.assertIn(STAGE_REFLOW, [s.stage for s in segments])

    def test_mainup_requires_board_lift_when_data_present(self) -> None:
        # 连续双红 ≥3 但连板高度不抬升 → 停在发酵
        rows = [_dr(i, boards=3.0) for i in range(6)] + [_row(6, boards=3.0)]
        segments, _ = derive_stages(rows)
        self.assertEqual([s.stage for s in segments], [STAGE_FERMENT])

    def test_mainup_waived_without_board_data(self) -> None:
        rows = [_dr(i) for i in range(6)] + [_row(6)]
        segments, gaps = derive_stages(rows)
        self.assertIn(STAGE_MAIN_UP, [s.stage for s in segments])
        self.assertTrue(any("连板高度数据缺失" in g for g in gaps))

    def test_no_message_dates_declares_incubation_gap(self) -> None:
        rows = [_dr(i) for i in range(4)]
        segments, gaps = derive_stages(rows)
        self.assertNotIn(STAGE_INCUBATION, [s.stage for s in segments])
        self.assertTrue(any("酝酿段无法判定" in g for g in gaps))

    def test_divergence_requires_volume_high_and_negative_diff(self) -> None:
        # 断红但缩量 → 不判分歧，走退潮路径
        rows = [_dr(i, amount=1000.0) for i in range(4)]
        rows += [_row(4 + k, amount=400.0, diff=-3.0) for k in range(6)]
        segments, _ = derive_stages(rows)
        stages = [s.stage for s in segments]
        self.assertNotIn(STAGE_DIVERGENCE, stages)
        self.assertIn(STAGE_EBB, stages)


class RenderTests(unittest.TestCase):
    def test_markdown_contains_discipline_and_gaps(self) -> None:
        rows = [_dr(i) for i in range(6)] + [_row(6)]
        segments, gaps = derive_stages(rows)
        from intelligence.services.theme_lifecycle_timeline import ThemeTimelineArtifact

        artifact = ThemeTimelineArtifact(
            "固态电池", tuple(segments), tuple(gaps),
            {"mainup_consecutive": 3, "ebb_break_days": 5, "double_red": "pct>0 & diff>10 & amount>500"},
        )
        text = lifecycle_markdown(artifact)
        self.assertIn("题材生命周期：固态电池", text)
        self.assertIn("当前阶段", text)
        self.assertIn("数据缺口", text)
        self.assertIn("不是预测", text)

    def test_unavailable_renders_empty(self) -> None:
        from intelligence.services.theme_lifecycle_timeline import ThemeTimelineArtifact

        artifact = ThemeTimelineArtifact("X", (), (), {}, degrade_reason="库不存在")
        self.assertEqual(lifecycle_markdown(artifact), "")


@unittest.skipIf(duckdb is None, "duckdb 不可用")
class LoaderTests(unittest.TestCase):
    def _make_db(self, path: Path) -> None:
        con = duckdb.connect(str(path))
        con.execute(
            "create table fact_sector_daily (trade_date date, sector_name varchar, "
            "pct_chg double, diff_ratio double, amount double)"
        )
        con.execute(
            "create table fact_theme_limit_heat_daily (trade_date date, "
            "sector_name varchar, limit_up_count integer, market_share double)"
        )
        con.execute(
            "create table fact_limit_advance_daily (trade_date date, "
            "stock_ts_code varchar, boards integer, theme varchar)"
        )
        for i in range(20):
            hot = 5 <= i < 12
            con.execute(
                "insert into fact_sector_daily values (?, '固态电池', ?, ?, ?)",
                [_day(i), 2.5 if hot else -0.5, 15.0 if hot else 2.0, 900.0 if hot else 300.0],
            )
            if hot:
                con.execute(
                    "insert into fact_theme_limit_heat_daily values (?, '固态电池', 5, 0.2)",
                    [_day(i)],
                )
                con.execute(
                    "insert into fact_limit_advance_daily values (?, 's1', ?, '固态电池')",
                    [_day(i), 2 + (i - 5)],
                )
        con.close()

    def test_loader_and_artifact(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)
            con = duckdb.connect(str(db), read_only=True)
            rows = load_theme_daily_rows(con, "固态电池")
            con.close()
            self.assertEqual(len(rows), 20)
            self.assertEqual(rows[5]["limit_up_count"], 5)
            self.assertEqual(rows[5]["max_boards"], 2)
            artifact = load_theme_timeline_artifact("固态电池", market_db_path=db)
        self.assertTrue(artifact.available)
        stages = [s.stage for s in artifact.segments]
        self.assertIn(STAGE_FERMENT, stages)
        self.assertIn(STAGE_MAIN_UP, stages)
        # 12 日后断红 8 日 → 应进入退潮并停在退潮
        self.assertEqual(artifact.current_stage, STAGE_EBB)

    def test_missing_theme_degrades(self) -> None:
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.duckdb"
            self._make_db(db)
            artifact = load_theme_timeline_artifact("不存在的题材", market_db_path=db)
        self.assertFalse(artifact.available)
        self.assertIn("无「不存在的题材」", artifact.degrade_reason or "")

    def test_missing_db_degrades(self) -> None:
        artifact = load_theme_timeline_artifact("固态电池", market_db_path="/nonexistent/x.duckdb")
        self.assertFalse(artifact.available)
        self.assertIsNotNone(artifact.degrade_reason)


class MessageDatesTests(unittest.TestCase):
    def test_load_from_vault(self) -> None:
        with TemporaryDirectory() as tmp:
            relations = Path(tmp) / "wiki" / "relations"
            relations.mkdir(parents=True)
            (relations / "theme_signals.json").write_text(
                '{"themes": {"固态电池": {"recognition_timeline": '
                '[{"date": "2026-03-01", "note": "x"}, {"date": "2026-02-20"}]}}}',
                encoding="utf-8",
            )
            dates = load_message_dates(tmp, "固态电池")
            self.assertEqual(dates, ("2026-02-20", "2026-03-01"))
            self.assertEqual(load_message_dates(tmp, "别的题材"), ())
        self.assertEqual(load_message_dates(None, "固态电池"), ())
        self.assertEqual(load_message_dates("/nonexistent", "固态电池"), ())


if __name__ == "__main__":
    unittest.main()
