"""观察剧本对象 + 硬门 + 登记的契约测试（roadmap G-03；终局 spec §3.2、§10 最小验收集 4）。

钉的是**判据**不是文案：错误码、状态、是否进校准、有没有落 checkpoint。
文案会改，判据不该改。
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from intelligence.services import checkpoints
from intelligence.services import compliance_gate as cg
from intelligence.services import observation_script as osc

# 周三：次日开盘就是次日，不牵扯周末规则。周末那条单独测。
AS_OF = "2026-09-02"
DUE = "2026-09-03"
# 次日开盘前 / 后各一个时刻（+08:00）。
IN_TIME = "2026-09-03T08:00:00+08:00"
TOO_LATE = "2026-09-03T10:00:00+08:00"


def _script(**over) -> osc.ObservationScript:
    base = dict(
        as_of=AS_OF,
        scope="theme",
        entity_ids=["算力租赁"],
        variables=["题材轨：题材所处阶段是否推进"],
        downgrade_or_abandon_conditions=["题材轨阶段标签回退或转为缺口"],
        recorded_at=IN_TIME,
        # 夹具剧本视为从切片派生：带投影哈希（工单 #34 门禁；用户手写的另测 user_authored）。
        projection_hash="cp:fixture000000001",
        model_id="deterministic",
    )
    base.update(over)
    return osc.make(**base)


class HardGateTests(unittest.TestCase):
    """spec §10 验收 4：含推荐 / 时点 / 目标价 / 概率的剧本被拒且给出错误码。"""

    def _codes(self, script: osc.ObservationScript) -> set[str]:
        return {r.code for r in osc.validate(script)}

    def test_clean_script_passes(self) -> None:
        self.assertEqual(osc.validate(_script()), [])

    def test_stock_scope_rejected(self) -> None:
        self.assertIn(osc.E_SCOPE, self._codes(_script(scope="stock")))

    def test_stock_entity_rejected(self) -> None:
        self.assertIn(cg.E_STOCK_SCOPE, self._codes(_script(entity_ids=["600519.SH"])))

    def test_direction_word_in_variable_rejected(self) -> None:
        self.assertIn(cg.E_DIRECTION, self._codes(_script(variables=["明天低吸这个题材"])))

    def test_timing_word_rejected(self) -> None:
        self.assertIn(cg.E_TIMING, self._codes(_script(upgrade_conditions=["给出买点"])))

    def test_target_price_rejected(self) -> None:
        self.assertIn(cg.E_TARGET_PRICE, self._codes(_script(variables=["能否涨到 25 元"])))

    def test_probability_rejected(self) -> None:
        self.assertIn(cg.E_PROBABILITY, self._codes(_script(variables=["延续的胜率 70%"])))

    def test_scope_theme_but_stock_in_text_still_rejected(self) -> None:
        """只查 scope 会漏：scope 填 theme、变量里写个股代码，照样得拦。"""
        codes = self._codes(_script(variables=["600519 的量能"]))
        self.assertIn(cg.E_STOCK_SCOPE, codes)

    def test_missing_variables_rejected(self) -> None:
        self.assertIn(osc.E_NO_VARIABLES, self._codes(_script(variables=[])))

    def test_missing_abandon_condition_rejected(self) -> None:
        """没有放弃条件 = 不可证伪，回检时判不了——这是产品判据不是洁癖。"""
        self.assertIn(
            osc.E_NO_ABANDON_CONDITION, self._codes(_script(downgrade_or_abandon_conditions=[]))
        )

    def test_bad_machine_condition_rejected(self) -> None:
        self.assertIn("E_MACHINE_CONDITION", self._codes(_script(machine_conditions=["涨得多"])))

    def test_rejection_carries_field_and_hint(self) -> None:
        rejections = osc.validate(_script(variables=["明天低吸"]))
        r = next(r for r in rejections if r.code == cg.E_DIRECTION)
        self.assertEqual(r.field, "variables")
        self.assertTrue(r.hint)

    def test_ensure_valid_raises_with_machine_readable_payload(self) -> None:
        with self.assertRaises(osc.ObservationScriptRejected) as ctx:
            osc.ensure_valid(_script(scope="stock"))
        payload = ctx.exception.to_dict()
        self.assertTrue(payload["rejected"])
        self.assertIn(osc.E_SCOPE, [r["code"] for r in payload["rejections"]])


class LateTests(unittest.TestCase):
    def test_before_next_open_is_not_late(self) -> None:
        self.assertFalse(osc.is_late(_script(recorded_at=IN_TIME)))

    def test_after_next_open_is_late(self) -> None:
        self.assertTrue(osc.is_late(_script(recorded_at=TOO_LATE)))

    def test_unparseable_recorded_at_is_late(self) -> None:
        """判不出登记时刻就算 late：不能证明及时，就不能算及时。"""
        self.assertTrue(osc.is_late(_script(recorded_at="上周某天")))
        self.assertTrue(osc.is_late(_script(recorded_at=None)))

    def test_explicit_next_open_overrides_calendar_default(self) -> None:
        """回填 / 回放时由调用方传真交易日历（``next_trading_open``），本层不猜。"""
        earlier = datetime.fromisoformat("2026-09-03T07:00:00+08:00")
        self.assertTrue(osc.is_late(_script(recorded_at=IN_TIME), next_open=earlier))

    def test_weekend_is_not_late(self) -> None:
        """周五的功课周六补做不算迟到：两者之间没有交易，用户看不到任何后续行情。"""
        friday = _script(as_of="2026-09-04", recorded_at="2026-09-05T10:00:00+08:00")
        self.assertFalse(osc.is_late(friday))
        self.assertEqual(osc.default_next_open("2026-09-04").date().isoformat(), "2026-09-07")

    def test_after_weekend_open_is_late(self) -> None:
        monday_late = _script(as_of="2026-09-04", recorded_at="2026-09-07T10:00:00+08:00")
        self.assertTrue(osc.is_late(monday_late))

    def test_due_follows_the_same_weekend_rule(self) -> None:
        """回检日落在周六 = 问错了日子，resolver 查无当日行会伪装成「判不了」。"""
        self.assertEqual(osc.default_due("2026-09-04"), "2026-09-07")

    def test_enters_calibration_only_for_confirmed(self) -> None:
        self.assertTrue(osc.enters_calibration({"status": "confirmed"}))
        for status in ("drafted", "skipped", "late", "expired"):
            self.assertFalse(osc.enters_calibration({"status": status}), status)


class RegisterTests(unittest.TestCase):
    def test_confirmed_registers_checkpoint_with_object_type(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spath, cpath = Path(tmp) / "os.jsonl", Path(tmp) / "checkpoints.jsonl"
            _, rec = osc.register(spath, _script(status="confirmed"), checkpoints_path=cpath)
            self.assertEqual(rec["status"], "confirmed")
            self.assertFalse(rec["late"])
            self.assertEqual(rec["due"], DUE)
            cks, _ = checkpoints.load_checkpoints(cpath)
            self.assertEqual(len(cks), 1)
            self.assertEqual(cks[0]["id"], rec["checkpoint_id"])
            self.assertEqual(checkpoints.object_type_of(cks[0]), "observation_script")
            # claim 必须把条件写进去，否则半年后回看只剩「关注 XX」，判不了对错。
            self.assertIn("降级或放弃", cks[0]["claim"])

    def test_late_confirmation_downgrades_and_skips_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spath, cpath = Path(tmp) / "os.jsonl", Path(tmp) / "checkpoints.jsonl"
            _, rec = osc.register(
                spath, _script(status="confirmed", recorded_at=TOO_LATE), checkpoints_path=cpath
            )
            self.assertEqual(rec["status"], "late")
            self.assertTrue(rec["late"])
            self.assertIsNone(rec["checkpoint_id"])
            self.assertFalse(osc.enters_calibration(rec))
            self.assertEqual(checkpoints.load_checkpoints(cpath)[0], [])

    def test_drafted_and_skipped_do_not_enter_recheck_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spath, cpath = Path(tmp) / "os.jsonl", Path(tmp) / "checkpoints.jsonl"
            osc.register(spath, _script(status="drafted"), checkpoints_path=cpath)
            osc.register(spath, _script(status="skipped"), checkpoints_path=cpath)
            self.assertEqual(checkpoints.load_checkpoints(cpath)[0], [])
            self.assertEqual(len(osc.load(spath)), 2)

    def test_confirmed_without_checkpoints_path_raises(self) -> None:
        """确认即入回检队列。少给路径就静默不登记，等于产品说「记下了」其实没记。"""
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                osc.register(Path(tmp) / "os.jsonl", _script(status="confirmed"))

    def test_rejected_script_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spath = Path(tmp) / "os.jsonl"
            with self.assertRaises(osc.ObservationScriptRejected):
                osc.register(spath, _script(scope="stock", status="drafted"))
            self.assertFalse(spath.exists())

    def test_machine_conditions_become_market_daily_metric(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spath, cpath = Path(tmp) / "os.jsonl", Path(tmp) / "checkpoints.jsonl"
            osc.register(
                spath,
                _script(status="confirmed", machine_conditions=["advancers>=3000"]),
                checkpoints_path=cpath,
            )
            (ck,), _ = checkpoints.load_checkpoints(cpath)
            self.assertEqual(ck["metric"]["type"], "market_daily")
            self.assertEqual(ck["metric"]["conditions"][0]["field"], "advancers")
            # 回检判「变量是否按条件触发」，不判涨跌——所以不能是 stock_return。
            self.assertNotEqual(ck["metric"]["type"], "stock_return")

    def test_no_machine_condition_means_manual_not_guess(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spath, cpath = Path(tmp) / "os.jsonl", Path(tmp) / "checkpoints.jsonl"
            osc.register(spath, _script(status="confirmed"), checkpoints_path=cpath)
            (ck,), _ = checkpoints.load_checkpoints(cpath)
            self.assertIsNone(ck.get("metric"), "无机检条件时不许编一个 metric 出来")

    def test_record_is_append_only_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spath, cpath = Path(tmp) / "os.jsonl", Path(tmp) / "checkpoints.jsonl"
            osc.register(spath, _script(status="confirmed"), checkpoints_path=cpath)
            osc.register(spath, _script(status="skipped"), checkpoints_path=cpath)
            lines = spath.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0])["status"], "confirmed")


class LedgerTests(unittest.TestCase):
    def test_expire_stale_only_touches_drafted(self) -> None:
        records = [
            {"id": "a", "status": "drafted", "due": "2026-09-05"},
            {"id": "b", "status": "skipped", "due": "2026-09-05"},
            {"id": "c", "status": "confirmed", "due": "2026-09-05"},
            {"id": "d", "status": "drafted", "due": "2099-01-01"},
        ]
        out = {r["id"]: r["status"] for r in osc.expire_stale(records, today="2026-09-10")}
        self.assertEqual(out["a"], "expired")
        # 跳过是用户做了决定，过期是产品没接住他；合成一个状态，负担指标就测不出来。
        self.assertEqual(out["b"], "skipped")
        self.assertEqual(out["c"], "confirmed")
        self.assertEqual(out["d"], "drafted")

    def test_status_counts(self) -> None:
        counts = osc.status_counts([{"status": "confirmed"}, {"status": "skipped"}, {"status": "x"}])
        self.assertEqual(counts["confirmed"], 1)
        self.assertEqual(counts["skipped"], 1)
        self.assertEqual(sum(counts.values()), 2)

    def test_load_skips_broken_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "os.jsonl"
            p.write_text('{"id":"a","status":"drafted"}\n不是 JSON\n\n', encoding="utf-8")
            self.assertEqual([r["id"] for r in osc.load(p)], ["a"])

    def test_default_due_is_next_day(self) -> None:
        self.assertEqual(osc.default_due(AS_OF), DUE)
        self.assertEqual(
            osc.default_next_open(AS_OF),
            datetime.fromisoformat("2026-09-03T09:30:00+08:00"),
        )

    def test_next_trading_open_returns_none_without_db(self) -> None:
        """无库时回落到默认（更早的截止线），不抛错、不阻断登记。"""
        self.assertIsNone(osc.next_trading_open(AS_OF, db_path="/tmp/no-such.duckdb"))


class CheckpointObjectTypeTests(unittest.TestCase):
    """存量记录不许被一个默认值折叠成「用户判断」。"""

    def test_declared_wins(self) -> None:
        self.assertEqual(
            checkpoints.object_type_of({"object_type": "observation_script"}), "observation_script"
        )

    def test_agent_source_inferred(self) -> None:
        self.assertEqual(
            checkpoints.object_type_of({"source": "framework_interpretation"}), "agent_judgment"
        )

    def test_user_source_inferred(self) -> None:
        self.assertEqual(checkpoints.object_type_of({"source": "foresight_judgment"}), "judgment")

    def test_unknown_legacy_not_folded_into_judgment(self) -> None:
        self.assertEqual(checkpoints.object_type_of({"claim": "老记录"}), "unknown_legacy")

    def test_illegal_object_type_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                checkpoints.register_checkpoint(
                    Path(tmp) / "c.jsonl", claim="x", due="2026-09-05", object_type="乱写"
                )

    def test_legacy_default_still_judgment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, rec = checkpoints.register_checkpoint(
                Path(tmp) / "c.jsonl", claim="x", due="2026-09-05"
            )
            self.assertEqual(rec["object_type"], "judgment")


class TimeContractTests(unittest.TestCase):
    def test_recorded_at_defaults_to_now_and_is_stamped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spath = Path(tmp) / "os.jsonl"
            script = osc.make(
                as_of=AS_OF,
                scope="theme",
                entity_ids=["算力租赁"],
                variables=["题材轨阶段"],
                downgrade_or_abandon_conditions=["转为缺口"],
            )
            self.assertIsNone(script.recorded_at)
            _, rec = osc.register(spath, script)
            self.assertTrue(rec["recorded_at"], "登记时刻必须落盘：没有它就判不了 late")
            stamped = datetime.fromisoformat(rec["recorded_at"])
            self.assertLess(abs(datetime.now(osc.CN_TZ) - stamped), timedelta(minutes=5))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
