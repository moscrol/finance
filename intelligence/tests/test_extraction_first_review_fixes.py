"""工单 #53 质检返修的回归（2026-09-14 质检 N2/N3、S1–S10）。

每一条都对应一个**质检实测触发序列**，不是对实现的复述。先证明修前红、修后绿；
原缺陷断言不保留成「兼容」。

分组与质检给的返修顺序一致：
1. 草稿 → 确认 → 再读 的版本 / 字段链（S1 / S4 / S5）
2. 尝试终态与动作去重（S2 / S3 / S6 / S7 / S9 / N3）
3. 持久化恢复与列表（N2 / S8 / S10）
"""

from __future__ import annotations

import json
import unittest
from unittest import mock

from intelligence import cli
from intelligence.services import guided_reading as gr
from intelligence.services import observation_extraction as ox
from intelligence.services import observation_script as osc
from intelligence.tests.test_observation_extraction_first import (
    AS_OF,
    Base,
    CANON,
    ENTITY,
    MY_ABANDON,
    MY_VARS,
    OTHER_CANON,
    OTHER_ENTITY,
    SLICE,
    _run,
)

# 身份能解析、六轨全是 no_data：有阅读目标、但**没有系统骨架**。
NO_SKELETON_SLICE = {
    **SLICE,
    "tracks": {
        t: {"track": t, "gap": True, "reason": "no_data", "detail": ""}
        for t in ("market", "theme", "opinion", "capital", "stock", "judgment")
    },
}


# =========================================================================== #
# 1 草稿 → 确认 → 再读：版本与字段链
# =========================================================================== #
class S1ConfirmFromDraftKeepsUserConditions(Base):
    def test_upgrade_and_machine_conditions_survive_confirm(self) -> None:
        """质检 S1：草稿里写的升级条件与机检规则，确认后**不许静默清空**。

        机检条件没了，及时确认的剧本到期就从「盘面自动判定」掉成「人工判定」，
        而台账上看不出发生过这件事。
        """
        code, out = self.draft(extra=["--upgrade", "题材轨阶段推进", "--condition", "advancers>=3000"])
        self.assertEqual(code, 0, out)
        code, out = _run(
            ["observation", "confirm", "--user", "u1", "--as-of", AS_OF, "--from-draft", ENTITY,
             "--db-path", "/tmp/no-such.duckdb", "--json"]
        )
        self.assertEqual(code, 0, out)
        record = json.loads(out)
        self.assertEqual(list(record["upgrade_conditions"]), ["题材轨阶段推进"])
        self.assertEqual(list(record["machine_conditions"]), ["advancers>=3000"])

    def test_cli_values_still_override_the_draft(self) -> None:
        self.draft(extra=["--upgrade", "草稿写的", "--condition", "advancers>=3000"])
        _, out = _run(
            ["observation", "confirm", "--user", "u1", "--as-of", AS_OF, "--from-draft", ENTITY,
             "--upgrade", "命令行写的", "--db-path", "/tmp/no-such.duckdb", "--json"]
        )
        record = json.loads(out)
        self.assertEqual(list(record["upgrade_conditions"]), ["命令行写的"])
        self.assertEqual(list(record["machine_conditions"]), ["advancers>=3000"], "只覆盖给了的那个")


class S4FromDraftHonoursAttemptId(Base):
    def test_attempt_of_another_target_is_refused(self) -> None:
        """质检 S4：传另一个阅读目标的 attempt ID，不许 exit=0 后悄悄改用 latest。"""
        self.draft(entity=ENTITY)
        self.draft(entity=OTHER_ENTITY)
        other = [
            a for a in self.pending()
            if a["canonical_entity_id"] == OTHER_CANON
        ][0]["attempt_id"]
        code, out = _run(
            ["observation", "confirm", "--user", "u1", "--as-of", AS_OF, "--from-draft", ENTITY,
             "--attempt-id", other, "--db-path", "/tmp/no-such.duckdb"]
        )
        self.assertEqual(code, 2, out)
        self.assertIn("不属于", out)

    def test_explicit_attempt_selects_that_attempts_draft_version(self) -> None:
        """§2.4.4：后续确认可关联**已完成尝试的具体草稿版本**，不是一律取 latest。"""
        self.draft(variables=["题材轨：题材所处阶段是否推进"])
        first = self.pending()[0]["attempt_id"]
        _run(["observation", "close", "--user", "u1", "--attempt-id", first])
        self.draft(variables=["资金轨：板块 / 题材资金流是否延续"])

        _, out = _run(
            ["observation", "confirm", "--user", "u1", "--as-of", AS_OF, "--from-draft", ENTITY,
             "--attempt-id", first, "--db-path", "/tmp/no-such.duckdb", "--json"]
        )
        record = json.loads(out)
        self.assertEqual(list(record["variables"]), ["题材轨：题材所处阶段是否推进"],
                         "指定了尝试就该取那次的版本")
        self.assertTrue(record["source_draft_id"])


class S5ConfirmedRowIsNotADraftVersion(Base):
    def test_confirmed_row_does_not_become_the_latest_draft(self) -> None:
        """质检 S5：`--from-draft` 写出的 confirmed 行也是 author=user，不许冒充草稿版。"""
        self.draft()
        key = ox.make_key("u1", AS_OF, CANON)
        before = osc.latest_user_draft(osc.load_raw(self.ledger()), key=key)
        _run(["observation", "confirm", "--user", "u1", "--as-of", AS_OF, "--from-draft", ENTITY,
              "--db-path", "/tmp/no-such.duckdb"])
        after = osc.latest_user_draft(osc.load_raw(self.ledger()), key=key)
        self.assertEqual(after["draft_id"], before["draft_id"])
        self.assertEqual(after["id"], before["id"])

    def test_confirmation_does_not_bump_the_next_draft_version(self) -> None:
        self.draft()
        _run(["observation", "confirm", "--user", "u1", "--as-of", AS_OF, "--from-draft", ENTITY,
              "--db-path", "/tmp/no-such.duckdb"])
        aid = self.pending()[0]["attempt_id"] if self.pending() else None
        if aid:
            _run(["observation", "close", "--user", "u1", "--attempt-id", aid])
        self.draft(variables=["资金轨：板块 / 题材资金流是否延续"])
        key = ox.make_key("u1", AS_OF, CANON)
        self.assertEqual(osc.latest_user_draft(osc.load_raw(self.ledger()), key=key)["draft_version"], 2)


# =========================================================================== #
# 2 尝试终态与动作去重
# =========================================================================== #
class S2NoSkeletonIsNotACompletedRead(Base):
    def _no_skeleton(self):
        # 直接换掉 CLI 那一跳：``Base.setUp`` 已经把 ``_fake_slice`` 绑进 mock 的
        # ``side_effect``，事后改类属性对那个已建好的 mock 没有影响。
        return mock.patch.object(cli, "_observation_slice", return_value=NO_SKELETON_SLICE)

    def test_gap_delivery_is_not_read_completed(self) -> None:
        """质检 S2：六轨全缺 → 交付的是缺口说明，不是完整带读。不记 read_completed。"""
        self.draft()
        with self._no_skeleton():
            code, out = self.read(extra=["--json"])
        self.assertEqual(code, 0, out)
        self.assertIsNone(json.loads(out)["draft"], "这一天确实没有骨架")
        self.assertEqual(self.kinds(osc.EVENT_READ_COMPLETED), [])

    def test_attempt_stays_pending_when_nothing_was_delivered(self) -> None:
        self.draft()
        with self._no_skeleton():
            self.read()
        self.assertEqual(len(self.pending()), 1, "没交付完整带读就不算结束这次尝试")


class S3CompletedAttemptReplaysTheReceipt(Base):
    def test_retry_returns_the_original_receipt_without_rebuilding(self) -> None:
        """质检 S3：正常完成后同 ID 重试要**拿回原收据**，而不是撞上「已结束」退 2。"""
        self.draft()
        self.read()
        (receipt,) = self.kinds(osc.EVENT_READ_COMPLETED)
        aid = receipt["attempt_id"]

        with mock.patch.object(gr, "build", wraps=gr.build) as built:
            code, out = self.read(extra=["--attempt-id", aid, "--json"])
        self.assertEqual(code, 0, out)
        self.assertEqual(built.call_count, 0, "重试不重新构建骨架")
        self.assertEqual(json.loads(out)["event_id"], receipt["event_id"])
        self.assertEqual(len(self.kinds(osc.EVENT_READ_COMPLETED)), 1, "不重复记完成事件")

    def test_explicitly_closed_unfinished_attempt_still_refuses(self) -> None:
        """显式 close 掉的**未完成**尝试不能复活——这一条不因上面的修复而松动。"""
        self.read()
        aid = self.pending()[0]["attempt_id"]
        _run(["observation", "close", "--user", "u1", "--attempt-id", aid])
        code, out = self.read(extra=["--attempt-id", aid])
        self.assertEqual(code, 2)
        self.assertIn("已结束", out)

    def test_another_users_receipt_is_not_readable(self) -> None:
        self.draft(user="u1")
        self.read(user="u1")
        aid = self.kinds(osc.EVENT_READ_COMPLETED, user="u1")[0]["attempt_id"]
        code, out = self.read(user="u2", extra=["--attempt-id", aid])
        self.assertEqual(code, 2, out)


class S6ConfirmRetryIsDeduped(Base):
    def test_same_confirm_action_twice_records_one_event(self) -> None:
        """质检 S6：同一 pending 尝试里重跑同一条 confirm，只算一次确认。"""
        self.draft()
        argv = ["observation", "confirm", "--user", "u1", "--as-of", AS_OF,
                "--from-slice", ENTITY, "--db-path", "/tmp/no-such.duckdb"]
        self.assertEqual(_run(argv)[0], 0)
        self.assertEqual(_run(argv)[0], 0)
        self.assertEqual(len(self.kinds(osc.EVENT_SCRIPT_CONFIRMED)), 1)

    def test_retry_across_a_second_boundary_is_still_one_action(self) -> None:
        """动作身份不能由录入时刻派生：跨秒重试换了键就等于没去重。"""
        self.draft()
        argv = ["observation", "confirm", "--user", "u1", "--as-of", AS_OF,
                "--from-slice", ENTITY, "--db-path", "/tmp/no-such.duckdb"]
        _run(argv)
        stamps = iter(["2026-09-14T10:00:00+08:00", "2026-09-14T10:00:59+08:00"])
        with mock.patch.object(osc, "_now_iso", lambda: next(stamps, "2026-09-14T10:01:00+08:00")):
            _run(argv)
        self.assertEqual(len(self.kinds(osc.EVENT_SCRIPT_CONFIRMED)), 1)

    def test_dedup_adds_neither_a_script_row_nor_a_checkpoint(self) -> None:
        """去重必须发生在**产生 checkpoint 之前**：先登记再发现重复，
        回检队列里已经多了一条，而台账 append-only 删不掉也不该删。

        夹具的 as_of 早于今天，所以这条确认必然是 late（late 不登记 checkpoint）。
        断言因此写成「第二次相对第一次零增量」，不写死条数——写死会把
        「本来就没登记」误读成「去重生效了」。
        """
        from intelligence.services import checkpoints

        self.draft()
        argv = ["observation", "confirm", "--user", "u1", "--as-of", AS_OF,
                "--from-slice", ENTITY, "--db-path", "/tmp/no-such.duckdb"]
        _run(argv)
        cks_once, _ = checkpoints.load_checkpoints(self.space().checkpoints_path)
        rows_once = [r for r in osc.load(self.ledger()) if r["status"] in {"confirmed", "late"}]
        self.assertEqual(len(rows_once), 1)

        _run(argv)
        cks_twice, _ = checkpoints.load_checkpoints(self.space().checkpoints_path)
        rows_twice = [r for r in osc.load(self.ledger()) if r["status"] in {"confirmed", "late"}]
        self.assertEqual(len(cks_twice), len(cks_once), "重复确认不许再登记一个可证伪点")
        self.assertEqual([r["id"] for r in rows_twice], [r["id"] for r in rows_once],
                         "重复确认不许再追加一条剧本行")


class S7RepointDoesNotForgeASecondConfirmation(Base):
    def test_repoint_keeps_exactly_one_confirmation_event(self) -> None:
        """质检 S7：改回检日期是修点，不是第二次确认。"""
        us = self.space()
        us.root.mkdir(parents=True, exist_ok=True)
        _, record = osc.register(
            us.observation_scripts_path,
            osc.make(as_of=AS_OF, scope="theme", entity_ids=[ENTITY], variables=MY_VARS,
                     downgrade_or_abandon_conditions=MY_ABANDON, user_id="u1",
                     status="confirmed", recorded_at="2026-09-03T08:00:00+08:00"),
            checkpoints_path=us.checkpoints_path,
            entrypoint="confirm", canonical_entity_id=CANON, user_authored=True,
        )
        self.assertEqual(len(self.kinds(osc.EVENT_SCRIPT_CONFIRMED)), 1)
        new = osc.repoint_due(
            us.observation_scripts_path,
            record,
            checkpoints_path=us.checkpoints_path,
            verdicts_path=us.verdicts_path,
            trading_days={"2026-09-04", "2026-09-07"},
        )
        self.assertIsNotNone(new)
        # 两道分别钉住：写入侧不复制动作元数据、读取侧按 action_key 去重。
        # 只断言「事件数=1」会被读取侧那道兜住，写入侧回退了也看不出来。
        self.assertNotIn("action_event", new, "改点行不该带着原确认的动作元数据")
        self.assertEqual(len(self.kinds(osc.EVENT_SCRIPT_CONFIRMED)), 1,
                         "用户只确认过一次，台账上就只能有一次")

    def test_projection_dedups_even_if_a_duplicate_row_slips_in(self) -> None:
        """第二道：台账里真混进了复制行，读取面也只投影一次。"""
        us = self.space()
        us.root.mkdir(parents=True, exist_ok=True)
        _, record = osc.register(
            us.observation_scripts_path,
            osc.make(as_of=AS_OF, scope="theme", entity_ids=[ENTITY], variables=MY_VARS,
                     downgrade_or_abandon_conditions=MY_ABANDON, user_id="u1",
                     status="confirmed", recorded_at="2026-09-03T08:00:00+08:00"),
            checkpoints_path=us.checkpoints_path,
            entrypoint="confirm", canonical_entity_id=CANON, user_authored=True,
        )
        with self.ledger().open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({**record, "id": record["id"] + "-dup"}, ensure_ascii=False) + "\n")
        self.assertEqual(len(self.kinds(osc.EVENT_SCRIPT_CONFIRMED)), 1)


class S9ClosedAttemptRefusesASubmission(Base):
    def test_draft_interleaved_with_close_is_refused_at_write_time(self) -> None:
        """质检 S9：open → close → submit 的真实交错。CLI 先查过，不等于落盘时仍有效。"""
        key = ox.make_key("u1", AS_OF, CANON)
        attempt, _ = osc.open_attempt(self.ledger(), key=key, entrypoint="draft")
        aid = str(attempt["attempt_id"])
        osc.close_attempt(self.ledger(), attempt_id=aid, user_id="u1",
                          reason="user_closed", entrypoint="close")
        script = osc.make(as_of=AS_OF, scope="theme", entity_ids=[ENTITY], variables=MY_VARS,
                          downgrade_or_abandon_conditions=MY_ABANDON, user_id="u1")
        with self.assertRaises(ValueError):
            osc.submit_draft(self.ledger(), script, key=key, attempt_id=aid, entrypoint="draft")
        self.assertEqual(self.kinds(osc.EVENT_DRAFT_SUBMITTED), [])

    def test_record_event_on_a_closed_attempt_is_refused(self) -> None:
        key = ox.make_key("u1", AS_OF, CANON)
        attempt, _ = osc.open_attempt(self.ledger(), key=key, entrypoint="read")
        aid = str(attempt["attempt_id"])
        osc.close_attempt(self.ledger(), attempt_id=aid, user_id="u1",
                          reason="user_closed", entrypoint="close")
        with self.assertRaises(ValueError):
            osc.record_event(self.ledger(), event=osc.EVENT_DRAFT_SKIPPED, key=key,
                             entrypoint="read", attempt_id=aid)


class N3CloseRetryHealsTheAbandonedEvent(Base):
    def test_failed_abandoned_append_is_completed_on_retry(self) -> None:
        """质检 N3：closed 行已落、abandoned 追加失败 → 重试必须补齐，不能永久断裂。"""
        key = ox.make_key("u1", AS_OF, CANON)
        attempt, _ = osc.open_attempt(self.ledger(), key=key, entrypoint="read")
        aid = str(attempt["attempt_id"])

        real = osc._record_event_locked
        with mock.patch.object(osc, "_record_event_locked", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                osc.close_attempt(self.ledger(), attempt_id=aid, user_id="u1",
                                  reason="user_closed", entrypoint="close")
        self.assertEqual(self.kinds(osc.EVENT_ABANDONED), [], "这一刻事件确实还没落")

        with mock.patch.object(osc, "_record_event_locked", real):
            osc.close_attempt(self.ledger(), attempt_id=aid, user_id="u1",
                              reason="user_closed", entrypoint="close")
        self.assertEqual(len(self.kinds(osc.EVENT_ABANDONED)), 1)


# =========================================================================== #
# 3 持久化恢复与列表
# =========================================================================== #
class N2TornLineDoesNotSwallowTheNextWrite(Base):
    def test_next_append_survives_a_partial_tail(self) -> None:
        """质检 N2：断电留下的半行，不许把下一次成功写入一起吃掉。

        flock 只防同时写、fsync 只保证已写字节落盘——两者都不修残片。
        """
        self.ledger().parent.mkdir(parents=True, exist_ok=True)
        self.ledger().write_text('{"id":"partial",', encoding="utf-8")
        key = ox.make_key("u1", AS_OF, CANON)
        attempt, created = osc.open_attempt(self.ledger(), key=key, entrypoint="read")
        self.assertTrue(created)
        reread = osc.attempt_states(osc.load_raw(self.ledger()))
        self.assertIn(str(attempt["attempt_id"]), reread, "重开读取必须还能看到这条记录")

    def test_the_fragment_is_kept_not_silently_truncated(self) -> None:
        """残片是证据：隔离它，不抹掉它。"""
        self.ledger().parent.mkdir(parents=True, exist_ok=True)
        self.ledger().write_text('{"id":"partial",', encoding="utf-8")
        osc.open_attempt(self.ledger(), key=ox.make_key("u1", AS_OF, CANON), entrypoint="read")
        self.assertIn('{"id":"partial",', self.ledger().read_text(encoding="utf-8"))


class S8ExpiryDoesNotUnlockTheRedaction(Base):
    def _write_system_draft(self, *, due: str) -> None:
        self.ledger().parent.mkdir(parents=True, exist_ok=True)
        self.ledger().write_text(
            json.dumps(
                {"id": "os-sys", "record_kind": osc.RECORD_SCRIPT,
                 "author_origin": osc.AUTHOR_SYSTEM, "status": "drafted", "due": due,
                 "as_of": AS_OF, "user_id": "u1", "canonical_entity_id": CANON,
                 "variables": ["盘面轨：指数阶段、成交与边际量是否延续"],
                 "downgrade_or_abandon_conditions": ["盘面轨该实体的量价对象消失或转为缺口"]},
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

    def test_past_due_system_draft_is_still_redacted(self) -> None:
        """质检 S8：展示用的 drafted→expired 转换，不该解除遮蔽资格。"""
        self._write_system_draft(due="2026-09-03")  # 早于今天 → expire_stale 会改成 expired
        code, out = _run(["observation", "list", "--user", "u1", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        (row,) = payload["records"]
        self.assertEqual(row["status"], "expired", "这条确实过期了")
        self.assertTrue(row["redacted"], "过期不等于可以回显")
        self.assertNotIn("盘面轨：指数阶段", out)

    def test_future_due_system_draft_is_redacted_too(self) -> None:
        self._write_system_draft(due="2099-01-01")
        _, out = _run(["observation", "list", "--user", "u1", "--json"])
        self.assertNotIn("盘面轨：指数阶段", out)


class S10AttemptFilterCoversPendingToo(Base):
    def test_pending_is_filtered_by_the_same_attempt_predicate(self) -> None:
        """质检 S10：按 attempt 查询时，pending 不能把别的尝试也带出来。"""
        self.read(entity=ENTITY)
        self.read(entity=OTHER_ENTITY)
        self.assertEqual(len(self.pending()), 2)
        target = self.pending()[0]["attempt_id"]
        _, out = _run(["observation", "list", "--user", "u1", "--events", "--json",
                       "--attempt-id", target])
        payload = json.loads(out)
        self.assertEqual([a["attempt_id"] for a in payload["pending_attempts"]], [target])

    def test_unknown_attempt_id_returns_empty_not_everything(self) -> None:
        self.read(entity=ENTITY)
        _, out = _run(["observation", "list", "--user", "u1", "--events", "--json",
                       "--attempt-id", "oa-does-not-exist"])
        payload = json.loads(out)
        self.assertEqual(payload["pending_attempts"], [])
        self.assertEqual(payload["events"], [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
