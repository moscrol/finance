"""提取前置 P0 的验收测试（工单 #53 §6 A1–A14）。

钉的是**判据**不是文案：门放不放行、骨架有没有被生成、事件记没记、差异是哪几项。

三条贯穿全文的判据，每条都对应一个真实会出的错：

1. **门没过时系统构建函数不许被调用**——只要骨架对象存在，任何一个 ``--json`` 分支、
   日志或异常回显都可能把它漏出去。所以断言的是 ``guided_reading.build`` 的调用次数，
   不是输出里有没有那几个字。
2. **等待不是离开**——``read`` 提示后没有后续动作，尝试必须停在 ``pending``；
   命令返回就记 ``abandoned`` 是在凭空造事实。
3. **差异不评分**——本单新增的输出与台账里不许出现相似度 / 一致率 / 收敛分数。
"""

from __future__ import annotations

import ast
import contextlib
import io
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from intelligence import cli, userspace
from intelligence.services import guided_reading as gr
from intelligence.services import observation_extraction as ox
from intelligence.services import observation_script as osc

AS_OF = "2026-09-02"          # 周三：次日开盘就是次日，不牵扯周末规则
NEXT_DAY = "2026-09-03"
ENTITY = "算力租赁"
CANON = "990306.FP"
OTHER_ENTITY = "固态电池"
OTHER_CANON = "990401.FP"

SLICE = {
    "as_of": AS_OF,
    "entity_id": CANON,
    "entity_name": ENTITY,
    "knowledge_cutoff": AS_OF,
    "pit_grade": "strict",
    "tracks": {
        "market": [
            {
                "object_type": "label",
                "ref": f"fact_sector_daily:{CANON}@{AS_OF}",
                "source_hash": "abc",
                "payload": {"pct_chg": 3.2},
            }
        ]
    },
}
# 六轨全缺、且原因是「实体解析不出来」——此时 entity_id 是**用户输入的别名不是身份**。
UNRESOLVED_SLICE = {
    "as_of": AS_OF,
    "entity_id": "不存在的题材",
    "entity_name": "不存在的题材",
    "knowledge_cutoff": AS_OF,
    "pit_grade": "trade_date_only",
    "tracks": {
        t: {"track": t, "gap": True, "reason": "entity_unresolved", "detail": ""}
        for t in ("market", "theme", "opinion", "capital", "stock", "judgment")
    },
}

SYSTEM_VARS = ["盘面轨：指数阶段、成交与边际量是否延续"]
SYSTEM_ABANDON = ["盘面轨该实体的量价对象消失或转为缺口"]
MY_VARS = ["题材轨：题材所处阶段是否推进"]
MY_ABANDON = ["题材轨阶段标签回退或转为缺口"]

REPORT = {
    "date": AS_OF,
    "logic_batch": {"results": [{"market_theme": ENTITY, "priority_score": 90}]},
}


def _run(argv: list[str]) -> tuple[int, str]:
    """跑一条 CLI，收走 stdout。返回 ``(退出码, 输出)``。"""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = cli.main(argv)
    return code, buf.getvalue()


class Base(unittest.TestCase):
    """隔离的 users 目录 + 固定切片 + 显式开关。绝不碰真实用户台账与真库。"""

    guided_reading_env = "on"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        env = {"FORESIGHT_USERS_DIR": self.root, "FORESIGHT_GUIDED_READING": self.guided_reading_env}
        self._env = mock.patch.dict(os.environ, env, clear=False)
        self._env.start()
        self.addCleanup(self._env.stop)
        self.addCleanup(self._tmp.cleanup)
        # 切片与身份都打桩：本文件测的是提取门，不是 DuckDB。
        self._slice = mock.patch.object(cli, "_observation_slice", side_effect=self._fake_slice)
        self._slice.start()
        self.addCleanup(self._slice.stop)
        self._ident = mock.patch.object(ox, "resolve_identity", side_effect=self._fake_identity)
        self._ident.start()
        self.addCleanup(self._ident.stop)

    @staticmethod
    def _fake_slice(args, us, entity):  # noqa: ARG004 - 签名要与真函数一致
        if entity == OTHER_ENTITY:
            return {**SLICE, "entity_id": OTHER_CANON, "entity_name": OTHER_ENTITY}
        if entity == ENTITY:
            return {**SLICE, "as_of": getattr(args, "as_of", AS_OF)}
        return UNRESOLVED_SLICE

    @staticmethod
    def _fake_identity(as_of, entity, *, db_path=None):  # noqa: ARG004
        if entity == ENTITY:
            return CANON
        if entity == OTHER_ENTITY:
            return OTHER_CANON
        raise ox.IdentityUnresolved(f"{as_of} 的板块宇宙里没有「{entity}」")

    # -- 便捷入口 ---------------------------------------------------------- #
    def space(self, user: str = "u1"):
        return userspace.user_space(user)

    def ledger(self, user: str = "u1") -> Path:
        return self.space(user).observation_scripts_path

    def draft(self, *, user: str = "u1", as_of: str = AS_OF, entity: str = ENTITY,
              variables: list[str] | None = None, abandons: list[str] | None = None,
              extra: list[str] | None = None) -> tuple[int, str]:
        argv = ["observation", "draft", "--user", user, "--as-of", as_of, "--entity", entity]
        for v in variables or MY_VARS:
            argv += ["--variable", v]
        for a in abandons or MY_ABANDON:
            argv += ["--abandon", a]
        return _run(argv + (extra or []))

    def read(self, *, user: str = "u1", as_of: str = AS_OF, entity: str = ENTITY,
             extra: list[str] | None = None) -> tuple[int, str]:
        return _run(
            ["observation", "read", "--user", user, "--as-of", as_of, "--entity", entity]
            + (extra or [])
        )

    def events(self, *, user: str = "u1") -> list[dict]:
        return osc.load_events(self.ledger(user))

    def kinds(self, event: str, *, user: str = "u1") -> list[dict]:
        return [e for e in self.events(user=user) if e["event"] == event]

    def pending(self, *, user: str = "u1") -> list[dict]:
        return [
            s
            for s in osc.attempt_states(osc.load_raw(self.ledger(user))).values()
            if s["status"] == osc.ATTEMPT_PENDING
        ]


# =========================================================================== #
# A1 草稿 / 身份
# =========================================================================== #
class A1DraftAndIdentity(Base):
    def test_draft_then_list_finds_it(self) -> None:
        code, out = self.draft()
        self.assertEqual(code, 0, out)
        code, out = _run(["observation", "list", "--user", "u1", "--json"])
        self.assertEqual(code, 0)
        records = json.loads(out)["records"]
        mine = [r for r in records if r.get("author_origin") == osc.AUTHOR_USER]
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine[0]["canonical_entity_id"], CANON)
        self.assertEqual(list(mine[0]["variables"]), MY_VARS)

    def test_latest_version_wins_and_old_versions_are_kept(self) -> None:
        self.draft(variables=["题材轨：题材所处阶段是否推进"])
        # 换一个尝试再提交第二版：内容改了 = 新版本，旧版留在台账里。
        aid = self.pending()[0]["attempt_id"]
        _run(["observation", "close", "--user", "u1", "--attempt-id", aid])
        self.draft(variables=["资金轨：板块 / 题材资金流是否延续"])
        raw = osc.load_raw(self.ledger())
        key = ox.make_key("u1", AS_OF, CANON)
        drafts = osc.user_drafts(raw, key=key)
        self.assertEqual(len(drafts), 2, "旧版必须保留")
        self.assertEqual(drafts[0]["draft_version"], 1)
        self.assertEqual(
            list(osc.latest_user_draft(raw, key=key)["variables"]),
            ["资金轨：板块 / 题材资金流是否延续"],
        )

    def test_changing_only_the_abandon_condition_is_a_new_version(self) -> None:
        self.draft()
        aid = self.pending()[0]["attempt_id"]
        _run(["observation", "close", "--user", "u1", "--attempt-id", aid])
        self.draft(abandons=["题材轨连续无新增覆盖事件"])
        key = ox.make_key("u1", AS_OF, CANON)
        self.assertEqual(len(osc.user_drafts(osc.load_raw(self.ledger()), key=key)), 2)

    def test_key_is_per_user_per_day_per_scope_per_entity(self) -> None:
        self.draft(user="u1")
        raw = osc.load_raw(self.ledger("u1"))
        for key in (
            ox.make_key("u2", AS_OF, CANON),        # 另一个用户
            ox.make_key("u1", NEXT_DAY, CANON),     # 相邻交易日
            ox.make_key("u1", AS_OF, OTHER_CANON),  # 另一个实体
            ox.make_key("u1", AS_OF, "SH000001"),   # 另一个作用域（index）
        ):
            self.assertIsNone(osc.latest_user_draft(raw, key=key), key)

    def test_key_scope_comes_from_identity_not_from_user_input(self) -> None:
        """``--scope`` 填错不该让草稿在带读面前消失：键里的 scope 由身份推导。"""
        code, out = self.draft(extra=["--scope", "index"])
        self.assertEqual(code, 0, out)
        key = ox.make_key("u1", AS_OF, CANON)
        self.assertEqual(key.scope, "theme")
        mine = osc.latest_user_draft(osc.load_raw(self.ledger()), key=key)
        self.assertIsNotNone(mine, "正文 scope 与键 scope 是两件事，不该互相干扰")
        self.assertEqual(mine["scope"], "index", "正文仍记用户填的那个")

    def test_alias_and_code_resolve_to_the_same_target(self) -> None:
        """名字与代码是同一个阅读目标——身份由 River 归一，不是拿输入串当键。"""
        with mock.patch.object(ox, "resolve_identity", return_value=CANON):
            self.draft(entity=ENTITY)
            code, out = self.draft(entity="990306.FP")
        self.assertEqual(code, 0, out)
        key = ox.make_key("u1", AS_OF, CANON)
        self.assertEqual(len(osc.user_drafts(osc.load_raw(self.ledger()), key=key)), 2)

    def test_unresolvable_entity_is_an_error_not_a_guess(self) -> None:
        code, out = self.draft(entity="不存在的题材")
        self.assertEqual(code, 2)
        self.assertIn("没有", out)
        self.assertFalse(self.ledger().exists(), "解析不出身份时什么都不该落盘")

    def test_system_drafted_row_is_not_a_user_draft(self) -> None:
        """存量 / 系统生成的 ``drafted`` 剧本不能冒充用户提交——判据是作者来源不是状态。"""
        self.ledger().parent.mkdir(parents=True, exist_ok=True)
        self.ledger().write_text(
            json.dumps(
                {"id": "os-old", "status": "drafted", "as_of": AS_OF, "user_id": "u1",
                 "canonical_entity_id": CANON, "variables": SYSTEM_VARS},
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        key = ox.make_key("u1", AS_OF, CANON)
        self.assertIsNone(osc.latest_user_draft(osc.load_raw(self.ledger()), key=key))

    def test_draft_registers_no_checkpoint(self) -> None:
        self.draft()
        self.assertFalse(self.space().checkpoints_path.exists(), "保存草稿不该进回检队列")


# =========================================================================== #
# A2 原阳性对照 1：业务字段一致、元数据不同 → 差异仍为 []
# =========================================================================== #
class A2IdenticalBusinessFields(unittest.TestCase):
    def test_metadata_differences_do_not_produce_a_diff(self) -> None:
        user = {
            "id": "od-1", "draft_id": "od-1", "recorded_at": "2026-09-02T20:00:00+08:00",
            "user_id": "u1", "projection_hash": None, "evidence_refs": ["a", "b"],
            "variables": ["甲", "乙"],
            "upgrade_conditions": ["丙"],
            "downgrade_or_abandon_conditions": ["丁"],
            "machine_conditions": ["advancers>=3000"],
        }
        system = {
            "id": "os-9", "recorded_at": "2026-09-02T21:30:00+08:00", "user_id": "system",
            "projection_hash": "cp:deadbeef", "evidence_refs": ["z"],
            # 顺序不同、带空白、且有重复项——三者都不是分歧。
            "variables": ["乙 ", "甲", "甲"],
            "upgrade_conditions": ["丙"],
            "downgrade_or_abandon_conditions": [" 丁"],
            "machine_conditions": ["advancers>=3000"],
        }
        self.assertEqual(ox.diff_scripts(user, system), [])
        self.assertEqual(ox.render_diff([], comparable=True), ["- 所比较字段无差异。"])

    def test_empty_both_sides_is_not_a_crash(self) -> None:
        self.assertEqual(ox.diff_scripts({"variables": []}, {"variables": []}), [])

    def test_no_system_skeleton_is_not_reported_as_agreement(self) -> None:
        self.assertEqual(ox.diff_scripts({"variables": ["甲"]}, None), [])
        self.assertIn("无可比较", ox.render_diff([], comparable=False)[0])


# =========================================================================== #
# A3 原阳性对照 2：开着带读、无草稿也没跳过 → read 被拦，构建函数未被调用
# =========================================================================== #
class A3ReadIsBlockedWithoutDraft(Base):
    def test_text_output_is_blocked_and_build_not_called(self) -> None:
        with mock.patch.object(gr, "build", wraps=gr.build) as built:
            code, out = self.read()
        self.assertEqual(code, 0)
        self.assertEqual(built.call_count, 0, "门没过时系统构建函数一次都不该被调用")
        self.assertNotIn(SYSTEM_VARS[0], out)
        self.assertNotIn("今日带读", out)
        self.assertIn("先写下你自己", out)

    def test_json_output_leaks_no_skeleton(self) -> None:
        code, out = self.read(extra=["--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertTrue(payload["blocked"])
        self.assertEqual(payload["code"], ox.BLOCK_DRAFT_REQUIRED)
        self.assertNotIn("facts", payload)
        self.assertNotIn(SYSTEM_VARS[0], out)

    def test_no_checkpoint_and_no_script_row_written(self) -> None:
        self.read()
        self.assertFalse(self.space().checkpoints_path.exists())
        self.assertEqual(osc.load(self.ledger()), [], "被拦时不该落任何剧本行")


# =========================================================================== #
# A4 原阳性对照 3：违规草稿被同一道合规硬门拒绝
# =========================================================================== #
class A4DraftGoesThroughTheSameHardGate(Base):
    def test_direction_word_is_rejected_and_nothing_is_written(self) -> None:
        code, out = self.draft(variables=["明天低吸这个题材"], extra=["--json"])
        self.assertEqual(code, 2)
        codes = {r["code"] for r in json.loads(out)["rejections"]}
        self.assertIn("E_DIRECTION", codes)
        key = ox.make_key("u1", AS_OF, CANON)
        self.assertIsNone(osc.latest_user_draft(osc.load_raw(self.ledger()), key=key))
        self.assertEqual(self.kinds(osc.EVENT_DRAFT_SUBMITTED), [])

    def test_structural_violation_is_rejected(self) -> None:
        """结构违规（没有放弃条件 = 不可证伪）与词表违规走同一道门。"""
        code, out = _run(
            ["observation", "draft", "--user", "u1", "--as-of", AS_OF, "--entity", ENTITY,
             "--variable", MY_VARS[0], "--json"]
        )
        self.assertEqual(code, 2)
        self.assertIn(osc.E_NO_ABANDON_CONDITION, {r["code"] for r in json.loads(out)["rejections"]})

    def test_rejected_submission_does_not_replace_an_existing_valid_version(self) -> None:
        self.draft()
        before = osc.latest_user_draft(osc.load_raw(self.ledger()), key=ox.make_key("u1", AS_OF, CANON))
        self.draft(variables=["给出买点"])
        after = osc.latest_user_draft(osc.load_raw(self.ledger()), key=ox.make_key("u1", AS_OF, CANON))
        self.assertEqual(before["draft_id"], after["draft_id"])


# =========================================================================== #
# A5 非空差异
# =========================================================================== #
class A5DiffContent(Base):
    def test_read_after_draft_shows_both_directions(self) -> None:
        self.draft()
        code, out = self.read()
        self.assertEqual(code, 0, out)
        self.assertIn(gr.DIFF_SECTION_TITLE, out)
        self.assertIn(f"你写了「{MY_VARS[0]}」，系统未列", out)
        self.assertIn(f"系统列了「{SYSTEM_VARS[0]}」，你未写", out)

    def test_added_variable_only_shows_on_the_user_side(self) -> None:
        self.draft(variables=[*SYSTEM_VARS, "资金轨：板块 / 题材资金流是否延续"],
                   abandons=SYSTEM_ABANDON)
        code, out = self.read(extra=["--json"])
        self.assertEqual(code, 0, out)
        diff = {d["field"]: d for d in json.loads(out)["extraction"]["diff"]}
        self.assertEqual(diff["variables"]["user_only"], ["资金轨：板块 / 题材资金流是否延续"])
        self.assertEqual(diff["variables"]["system_only"], [])
        self.assertNotIn("downgrade_or_abandon_conditions", diff, "一致的字段不该进差异")

    def test_changing_the_abandon_condition_shows_up(self) -> None:
        self.draft(variables=SYSTEM_VARS, abandons=["题材轨阶段标签回退或转为缺口"])
        _, out = self.read(extra=["--json"])
        diff = {d["field"]: d for d in json.loads(out)["extraction"]["diff"]}
        self.assertEqual(diff["downgrade_or_abandon_conditions"]["system_only"], SYSTEM_ABANDON)

    def test_skip_path_has_no_user_side_so_it_is_not_comparable(self) -> None:
        _, out = self.read(extra=["--skip-draft", "--json"])
        payload = json.loads(out)
        self.assertFalse(payload["extraction"]["comparable"])
        self.assertEqual(payload["extraction"]["diff"], [])

    def test_diff_section_passes_the_wording_lint(self) -> None:
        self.draft()
        _, out = self.read()
        self.assertEqual(gr.lint_output(out), [])


# =========================================================================== #
# A6 跳过
# =========================================================================== #
class A6SkipDraft(Base):
    def test_explicit_skip_lets_the_read_through_once(self) -> None:
        code, out = self.read(extra=["--skip-draft"])
        self.assertEqual(code, 0, out)
        self.assertIn("今日带读", out)
        self.assertEqual(len(self.kinds(osc.EVENT_DRAFT_SKIPPED)), 1)

    def test_skip_is_recorded_before_the_skeleton_is_built(self) -> None:
        """先记跳过、再生成骨架。反过来写，崩在中间就会留下「看过但没记」的空洞。"""
        seen: list[int] = []
        real = gr.build

        def _spy(*a, **kw):
            seen.append(len(self.kinds(osc.EVENT_DRAFT_SKIPPED)))
            return real(*a, **kw)

        with mock.patch.object(gr, "build", _spy):
            self.read(extra=["--skip-draft"])
        self.assertEqual(seen, [1], "build 被调用时，跳过事件必须已经落盘")

    def test_skip_authorization_does_not_carry_to_a_new_attempt(self) -> None:
        self.read(extra=["--skip-draft"])
        code, out = self.read()  # 新尝试，没带 --skip-draft
        self.assertEqual(code, 0)
        self.assertIn("先写下你自己", out)

    def test_skip_authorization_does_not_carry_to_another_target(self) -> None:
        self.read(extra=["--skip-draft"])
        code, out = self.read(entity=OTHER_ENTITY)
        self.assertIn("先写下你自己", out)
        self.assertEqual(code, 0)

    def test_existing_draft_wins_over_skip_and_no_skip_event_is_written(self) -> None:
        self.draft()
        code, out = self.read(extra=["--skip-draft"])
        self.assertEqual(code, 0, out)
        self.assertIn(gr.DIFF_SECTION_TITLE, out, "有草稿就该走对照，不是跳过")
        self.assertEqual(self.kinds(osc.EVENT_DRAFT_SKIPPED), [], "不能记一条不存在的跳过")


# =========================================================================== #
# A7 出口覆盖：别的入口不能绕过同一道门
# =========================================================================== #
class A7AllExitsShareTheGate(Base):
    def test_confirm_from_slice_is_gated(self) -> None:
        with mock.patch.object(gr, "build", wraps=gr.build) as built:
            code, out = _run(
                ["observation", "confirm", "--user", "u1", "--as-of", AS_OF,
                 "--from-slice", ENTITY, "--db-path", "/tmp/no-such.duckdb"]
            )
        self.assertEqual(code, 0)
        self.assertEqual(built.call_count, 0)
        self.assertIn("先写下你自己", out)
        self.assertFalse(self.space().checkpoints_path.exists())
        self.assertEqual(osc.load(self.ledger()), [])

    def test_system_skip_is_gated(self) -> None:
        with mock.patch.object(gr, "build", wraps=gr.build) as built:
            code, out = _run(
                ["observation", "skip", "--user", "u1", "--as-of", AS_OF, "--entity", ENTITY]
            )
        self.assertEqual(code, 0)
        self.assertEqual(built.call_count, 0)
        self.assertEqual(osc.load(self.ledger()), [])

    def test_system_skip_passes_once_a_draft_exists(self) -> None:
        self.draft()
        code, out = _run(["observation", "skip", "--user", "u1", "--as-of", AS_OF, "--entity", ENTITY])
        self.assertEqual(code, 0, out)
        statuses = [r["status"] for r in osc.load(self.ledger())]
        self.assertIn("skipped", statuses)

    def test_list_does_not_echo_a_system_skeleton_without_a_draft(self) -> None:
        """纵深防御：台账里即使出现一条系统骨架草稿，列表也不回显它的正文。"""
        self.ledger().parent.mkdir(parents=True, exist_ok=True)
        self.ledger().write_text(
            json.dumps(
                {"id": "os-sys", "record_kind": osc.RECORD_SCRIPT, "author_origin": osc.AUTHOR_SYSTEM,
                 "status": "drafted", "as_of": AS_OF, "user_id": "u1",
                 "canonical_entity_id": CANON, "variables": SYSTEM_VARS,
                 "downgrade_or_abandon_conditions": SYSTEM_ABANDON},
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        code, out = _run(["observation", "list", "--user", "u1", "--json"])
        self.assertEqual(code, 0)
        self.assertNotIn(SYSTEM_VARS[0], out)
        self.assertIn(ox.REDACTED, out)

    def test_list_stops_redacting_once_the_user_has_answered(self) -> None:
        self.draft()
        raw_line = json.dumps(
            {"id": "os-sys", "record_kind": osc.RECORD_SCRIPT, "author_origin": osc.AUTHOR_SYSTEM,
             "status": "drafted", "as_of": AS_OF, "user_id": "u1",
             "canonical_entity_id": CANON, "variables": SYSTEM_VARS},
            ensure_ascii=False,
        )
        with self.ledger().open("a", encoding="utf-8") as fh:
            fh.write(raw_line + "\n")
        _, out = _run(["observation", "list", "--user", "u1", "--json"])
        self.assertIn(SYSTEM_VARS[0], out)

    def test_full_manual_confirm_keeps_working_and_claims_nothing(self) -> None:
        code, out = _run(
            ["observation", "confirm", "--user", "u1", "--as-of", AS_OF, "--scope", "theme",
             "--entity", ENTITY, "--variable", MY_VARS[0], "--abandon", MY_ABANDON[0],
             "--db-path", "/tmp/no-such.duckdb", "--json"]
        )
        self.assertEqual(code, 0, out)
        record = json.loads(out)
        # 夹具 as_of 早于今天，所以这条必然是 late——late 仍属确认动作，只是不进校准。
        self.assertIn(record["status"], {"confirmed", "late"})
        self.assertEqual(record["action_event"]["script_status"], record["status"])
        self.assertEqual(record["action_event"]["attempt_id"], None)
        self.assertEqual(record["action_event"]["entrypoint"], osc.ENTRYPOINT_MANUAL_CONFIRM)
        names = {e["event"] for e in self.events()}
        self.assertEqual(names, {osc.EVENT_SCRIPT_CONFIRMED},
                         "手填确认不许冒充提交草稿或读完带读")


# =========================================================================== #
# A8 日报接线
# =========================================================================== #
class A8DailySeam(Base):
    def _space_with(self, *, history: bool):
        us = userspace.user_space("daily")
        us.root.mkdir(parents=True, exist_ok=True)
        if history:
            us.checkpoints_path.write_text('{"id":"ck-1","claim":"旧判断"}\n', encoding="utf-8")
        return us

    def _section(self, us, **kw):
        with mock.patch("intelligence.services.river.slice_river") as sr:
            sr.return_value = mock.Mock(to_dict=lambda: SLICE)
            return gr.daily_section(REPORT, us, **kw)

    def test_no_draft_only_adds_the_entry_hint(self) -> None:
        us = self._space_with(history=False)
        with mock.patch.object(gr, "build", wraps=gr.build) as built:
            section = self._section(us)
        self.assertIsNone(section.guided)
        self.assertTrue(section.hint)
        self.assertEqual(built.call_count, 0)
        body = "# 2026-09-02 日报\n\n正文……\n"
        out = gr.merge_into_daily_review(body, None, hint=True)
        self.assertTrue(out.startswith(body.rstrip("\n")), "非带读正文必须一字不动")
        self.assertIn("先写下**你自己**要看什么", out)
        self.assertNotIn(SYSTEM_VARS[0], out)
        self.assertEqual(gr.lint_output(out), [])

    def test_background_run_creates_no_attempt_and_no_event(self) -> None:
        us = self._space_with(history=False)
        self._section(us)
        self.assertEqual(osc.load_raw(us.observation_scripts_path), [],
                         "无人值守日报不证明用户进过页面：不建尝试、不记事件")

    def test_guided_reading_off_adds_nothing_at_all(self) -> None:
        us = self._space_with(history=True)
        with mock.patch.dict(os.environ, {"FORESIGHT_GUIDED_READING": "off"}, clear=False):
            section = self._section(us)
        self.assertIsNone(section.guided)
        self.assertFalse(section.hint, "带读关闭时连提示都不该出现")
        text = "# 日报\n"
        self.assertIs(gr.merge_into_daily_review(text, None), text)

    def test_with_a_draft_the_daily_carries_the_reading_and_the_diff(self) -> None:
        us = self._space_with(history=False)
        key = ox.make_key(us.user_id, AS_OF, CANON)
        osc.open_attempt(us.observation_scripts_path, key=key, entrypoint="draft")
        aid = osc.pending_attempt(osc.load_raw(us.observation_scripts_path), key=key)["attempt_id"]
        osc.submit_draft(
            us.observation_scripts_path,
            osc.make(as_of=AS_OF, scope="theme", entity_ids=[ENTITY],
                     variables=MY_VARS, downgrade_or_abandon_conditions=MY_ABANDON,
                     user_id=us.user_id),
            key=key, attempt_id=aid, entrypoint="draft",
        )
        section = self._section(us)
        self.assertIsNotNone(section.guided)
        out = gr.merge_into_daily_review("正文", section.guided, diff_lines=section.diff_lines)
        self.assertIn(gr.DIFF_SECTION_TITLE, out)
        self.assertIn(MY_VARS[0], out)
        # 后台写出仍不算用户读完。
        events = {e["event"] for e in osc.load_events(us.observation_scripts_path)}
        self.assertNotIn(osc.EVENT_READ_COMPLETED, events)

    def test_daily_does_not_fail_when_the_user_never_answered(self) -> None:
        us = self._space_with(history=False)
        section = self._section(us)
        self.assertIsInstance(section.reason, str)
        self.assertTrue(section.reason)


# =========================================================================== #
# A9 事件续接
# =========================================================================== #
class A9AttemptLifecycle(Base):
    def test_read_then_draft_then_read_is_one_attempt(self) -> None:
        self.read()
        aid = self.pending()[0]["attempt_id"]
        self.draft()
        code, out = self.read()
        self.assertEqual(code, 0, out)
        names = [e["event"] for e in self.events()]
        self.assertIn(osc.EVENT_DRAFT_SUBMITTED, names)
        self.assertIn(osc.EVENT_READ_COMPLETED, names)
        self.assertNotIn(osc.EVENT_ABANDONED, names)
        self.assertTrue(all(e["attempt_id"] == aid for e in self.events()))

    def test_prompt_then_close_records_exactly_one_abandoned(self) -> None:
        self.read()
        aid = self.pending()[0]["attempt_id"]
        code, _ = _run(["observation", "close", "--user", "u1", "--attempt-id", aid])
        self.assertEqual(code, 0)
        self.assertEqual(len(self.kinds(osc.EVENT_ABANDONED)), 1)
        _run(["observation", "close", "--user", "u1", "--attempt-id", aid])
        self.assertEqual(len(self.kinds(osc.EVENT_ABANDONED)), 1, "重复 close 不叠加")

    def test_waiting_is_not_leaving(self) -> None:
        self.read()
        self.assertEqual(self.kinds(osc.EVENT_ABANDONED), [])
        self.assertEqual(len(self.pending()), 1, "没有结束信号就保持 pending，不推断超时")

    def test_close_after_an_answer_keeps_the_events_and_records_no_abandon(self) -> None:
        self.draft()
        aid = self.pending()[0]["attempt_id"]
        _run(["observation", "close", "--user", "u1", "--attempt-id", aid])
        self.assertEqual(self.kinds(osc.EVENT_ABANDONED), [])
        self.assertEqual(len(self.kinds(osc.EVENT_DRAFT_SUBMITTED)), 1)

    def test_closed_attempt_cannot_be_revived(self) -> None:
        self.read()
        aid = self.pending()[0]["attempt_id"]
        _run(["observation", "close", "--user", "u1", "--attempt-id", aid])
        code, out = self.read(extra=["--attempt-id", aid])
        self.assertEqual(code, 2)
        self.assertIn("已结束", out)

    def test_all_five_events_are_queryable_and_separated(self) -> None:
        self.draft()                                  # draft_submitted
        self.read()                                   # read_completed
        self.read(entity=OTHER_ENTITY, extra=["--skip-draft"])  # draft_skipped
        aid = self.pending()[0]["attempt_id"] if self.pending() else None
        if aid:
            _run(["observation", "close", "--user", "u1", "--attempt-id", aid])
        _run(["observation", "confirm", "--user", "u1", "--as-of", AS_OF, "--scope", "theme",
              "--entity", ENTITY, "--variable", MY_VARS[0], "--abandon", MY_ABANDON[0],
              "--db-path", "/tmp/no-such.duckdb"])
        code, out = _run(["observation", "list", "--user", "u1", "--events", "--json"])
        self.assertEqual(code, 0)
        counts = json.loads(out)["counts"]
        for name in (osc.EVENT_DRAFT_SUBMITTED, osc.EVENT_DRAFT_SKIPPED,
                     osc.EVENT_READ_COMPLETED, osc.EVENT_SCRIPT_CONFIRMED):
            self.assertGreaterEqual(counts[name], 1, name)

    def test_late_confirmation_is_still_a_confirmation_event(self) -> None:
        us = self.space()
        us.root.mkdir(parents=True, exist_ok=True)
        osc.register(
            us.observation_scripts_path,
            osc.make(as_of=AS_OF, scope="theme", entity_ids=[ENTITY], variables=MY_VARS,
                     downgrade_or_abandon_conditions=MY_ABANDON, user_id="u1",
                     status="confirmed", recorded_at="2026-09-03T10:00:00+08:00"),
            checkpoints_path=us.checkpoints_path,
            entrypoint="confirm", canonical_entity_id=CANON, user_authored=True,
        )
        (event,) = self.kinds(osc.EVENT_SCRIPT_CONFIRMED)
        self.assertEqual(event["script_status"], "late")
        self.assertIsNone(event["checkpoint_id"])

    def test_events_do_not_enter_the_recheck_denominator(self) -> None:
        self.draft()
        self.read()
        records = osc.load(self.ledger())
        self.assertTrue(all(osc.record_kind_of(r) == osc.RECORD_SCRIPT for r in records))
        self.assertEqual(sum(osc.status_counts(records).values()), 1, "只有那一版草稿算剧本")


# =========================================================================== #
# A10 重试 / 并发 / 失败
# =========================================================================== #
class A10RetryConcurrencyFailure(Base):
    def test_same_action_retried_in_one_attempt_does_not_duplicate(self) -> None:
        self.draft()
        code, out = self.draft()
        self.assertEqual(code, 0, out)
        self.assertEqual(len(self.kinds(osc.EVENT_DRAFT_SUBMITTED)), 1)
        key = ox.make_key("u1", AS_OF, CANON)
        self.assertEqual(len(osc.user_drafts(osc.load_raw(self.ledger()), key=key)), 1)

    def test_repeated_skip_in_one_attempt_records_one_event(self) -> None:
        self.read(extra=["--skip-draft"])
        aid = osc.load_events(self.ledger())[0]["attempt_id"]
        osc.record_event(self.ledger(), event=osc.EVENT_DRAFT_SKIPPED,
                         key=ox.make_key("u1", AS_OF, CANON), entrypoint="read", attempt_id=aid)
        self.assertEqual(len(self.kinds(osc.EVENT_DRAFT_SKIPPED)), 1)

    def test_at_most_one_pending_attempt_per_key(self) -> None:
        key = ox.make_key("u1", AS_OF, CANON)
        ids = {
            osc.open_attempt(self.ledger(), key=key, entrypoint="read")[0]["attempt_id"]
            for _ in range(5)
        }
        self.assertEqual(len(ids), 1)
        self.assertEqual(len(self.pending()), 1)

    def test_success_event_rides_along_with_the_script_row(self) -> None:
        """提交成功与成功事件是同一次写：不存在「剧本在、事件不在」的窗口。"""
        self.draft()
        rows = [r for r in osc.load_raw(self.ledger()) if osc.record_kind_of(r) == osc.RECORD_SCRIPT]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["action_event"]["event"], osc.EVENT_DRAFT_SUBMITTED)
        self.assertEqual(
            [r for r in osc.load_raw(self.ledger()) if osc.record_kind_of(r) == osc.RECORD_EVENT
             and r["event"] == osc.EVENT_DRAFT_SUBMITTED],
            [],
            "成功事件不该再追加第二条独立事件行",
        )

    def test_cross_user_attempt_is_refused(self) -> None:
        self.read(user="u1")
        aid = self.pending(user="u1")[0]["attempt_id"]
        # u2 的台账里根本没有这个尝试 → 拒绝，不是记到 u2 名下。
        code, out = self.read(user="u2", extra=["--attempt-id", aid])
        self.assertEqual(code, 2)
        self.assertIn("没有这个提取尝试", out)

    def test_attempt_of_another_target_is_refused(self) -> None:
        self.read(entity=ENTITY)
        aid = self.pending()[0]["attempt_id"]
        code, out = self.read(entity=OTHER_ENTITY, extra=["--attempt-id", aid])
        self.assertEqual(code, 2)
        self.assertIn("不属于", out)

    def test_receipt_write_failure_is_reported_as_unknown_not_success(self) -> None:
        self.draft()
        with mock.patch.object(osc, "record_event", side_effect=OSError("disk full")):
            code, out = self.read()
        self.assertEqual(code, 1, "收据落盘失败必须是可诊断失败")
        self.assertIn("今日带读", out, "正文已经交付了，这一点要如实")
        self.assertEqual(self.kinds(osc.EVENT_READ_COMPLETED), [])
        self.assertEqual(len(self.pending()), 1, "结果未知时尝试保持 pending")

    def test_completed_attempt_replays_the_receipt_not_the_body(self) -> None:
        self.draft()
        self.read()
        aid = osc.load_events(self.ledger())[0]["attempt_id"]
        code, out = self.read(extra=["--attempt-id", aid])
        self.assertEqual(code, 2, "已结束的尝试不能续接")
        code, out = _run(["observation", "list", "--user", "u1", "--events", "--json",
                          "--attempt-id", aid])
        self.assertEqual(json.loads(out)["counts"][osc.EVENT_READ_COMPLETED], 1)

    def test_raw_export_keeps_every_kind_without_miscounting_scripts(self) -> None:
        self.draft()
        self.read()
        raw = osc.load_raw(self.ledger())
        kinds = {osc.record_kind_of(r) for r in raw}
        self.assertEqual(kinds, {osc.RECORD_SCRIPT, osc.RECORD_ATTEMPT, osc.RECORD_EVENT})
        self.assertEqual(len(osc.load(self.ledger())), 1)


# =========================================================================== #
# A11 开关矩阵
# =========================================================================== #
class A11SwitchMatrix(Base):
    guided_reading_env = ""

    def test_explicit_off_beats_everything(self) -> None:
        with mock.patch.dict(os.environ, {"FORESIGHT_GUIDED_READING": "on"}, clear=False):
            code, out = self.read(extra=["--off"])
        self.assertEqual(code, 0)
        self.assertIn("带读未开启", out)
        self.assertEqual(osc.load_raw(self.ledger()), [], "关掉带读连提取尝试都不该建")

    def test_skip_draft_does_not_open_a_closed_reading(self) -> None:
        with mock.patch.dict(os.environ, {"FORESIGHT_GUIDED_READING": "off"}, clear=False):
            code, out = self.read(extra=["--skip-draft"])
        self.assertEqual(code, 0)
        self.assertIn("带读未开启", out)
        self.assertEqual(self.kinds(osc.EVENT_DRAFT_SKIPPED), [],
                         "带读关闭时不许凭 --skip-draft 写跳过事件")

    def test_env_on_and_off(self) -> None:
        with mock.patch.dict(os.environ, {"FORESIGHT_GUIDED_READING": "on"}, clear=False):
            _, out = self.read()
            self.assertIn("先写下你自己", out)
        with mock.patch.dict(os.environ, {"FORESIGHT_GUIDED_READING": "off"}, clear=False):
            _, out = self.read(user="u2")
            self.assertIn("带读未开启", out)

    def test_new_user_default_on_veteran_default_off(self) -> None:
        with mock.patch.dict(os.environ, {"FORESIGHT_GUIDED_READING": ""}, clear=False):
            _, out = self.read(user="rookie")
            self.assertIn("先写下你自己", out)
            veteran = self.space("veteran")
            veteran.root.mkdir(parents=True, exist_ok=True)
            veteran.checkpoints_path.write_text('{"id":"ck","claim":"旧"}\n', encoding="utf-8")
            _, out = self.read(user="veteran")
            self.assertIn("带读未开启", out)

    def test_recording_extraction_alone_does_not_flip_the_new_user_verdict(self) -> None:
        """只写提取台账不许把新用户变成老用户——判据台账是另外三个。"""
        with mock.patch.dict(os.environ, {"FORESIGHT_GUIDED_READING": ""}, clear=False):
            self.draft(user="rookie")
            us = self.space("rookie")
            self.assertTrue(us.observation_scripts_path.exists())
            self.assertTrue(gr.is_new_user(us), "提取记录不是「有历史」的判据")
            _, out = self.read(user="rookie")
            self.assertIn("今日带读", out)

    def test_timely_confirmation_makes_the_user_a_veteran_and_explicit_on_still_works(self) -> None:
        """及时确认 → 写 checkpoint → 次日默认关；显式 --on 仍能正常 draft / read。

        ``recorded_at`` 显式给成次日开盘前，**不依赖跑测试时的墙上时钟**——按 now 算，
        这条用例会在某个 09:31 之后突然从绿变红，而那是时钟变了不是代码变了。
        """
        us = self.space("rookie")
        us.root.mkdir(parents=True, exist_ok=True)
        with mock.patch.dict(os.environ, {"FORESIGHT_GUIDED_READING": ""}, clear=False):
            self.assertTrue(gr.is_new_user(us))
            _, record = osc.register(
                us.observation_scripts_path,
                osc.make(as_of=AS_OF, scope="theme", entity_ids=[ENTITY], variables=MY_VARS,
                         downgrade_or_abandon_conditions=MY_ABANDON, user_id="rookie",
                         status="confirmed", recorded_at=f"{NEXT_DAY}T08:00:00+08:00"),
                checkpoints_path=us.checkpoints_path,
                entrypoint="confirm", canonical_entity_id=CANON, user_authored=True,
            )
            self.assertEqual(record["status"], "confirmed")
            self.assertTrue(record["checkpoint_id"])
            self.assertFalse(gr.is_new_user(us), "有 checkpoint 历史 = 老用户")

            _, out = self.read(user="rookie", as_of=NEXT_DAY)
            self.assertIn("带读未开启", out)
            code, out = self.draft(user="rookie", as_of=NEXT_DAY)
            self.assertEqual(code, 0, out)
            _, out = self.read(user="rookie", as_of=NEXT_DAY, extra=["--on"])
            self.assertIn("今日带读", out)

    def test_draft_works_even_when_guided_reading_is_off(self) -> None:
        with mock.patch.dict(os.environ, {"FORESIGHT_GUIDED_READING": "off"}, clear=False):
            code, out = self.draft()
        self.assertEqual(code, 0, out)
        key = ox.make_key("u1", AS_OF, CANON)
        self.assertIsNotNone(osc.latest_user_draft(osc.load_raw(self.ledger()), key=key))


# =========================================================================== #
# A12 旧合同
# =========================================================================== #
class A12LegacyContracts(Base):
    def test_untyped_legacy_script_is_still_readable(self) -> None:
        self.ledger().parent.mkdir(parents=True, exist_ok=True)
        self.ledger().write_text(
            json.dumps({"id": "os-legacy", "status": "confirmed", "as_of": AS_OF,
                        "entity_ids": [ENTITY]}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        records = osc.load(self.ledger())
        self.assertEqual([r["id"] for r in records], ["os-legacy"])
        self.assertEqual(osc.status_counts(records)["confirmed"], 1)

    def test_events_are_not_counted_as_scripts_or_expired(self) -> None:
        self.draft()
        self.read()
        raw = osc.load_raw(self.ledger())
        scripts = osc.load(self.ledger())
        self.assertLess(len(scripts), len(raw))
        self.assertTrue(all("event" not in r for r in osc.expire_stale(scripts)))
        self.assertEqual(osc.nontrading_dues(scripts, {NEXT_DAY}), [])

    def test_unknown_record_kind_is_neither_script_nor_event(self) -> None:
        self.ledger().parent.mkdir(parents=True, exist_ok=True)
        self.ledger().write_text(
            json.dumps({"id": "x", "record_kind": "从未来来的分型"}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        self.assertEqual(osc.load(self.ledger()), [])
        self.assertEqual(osc.load_events(self.ledger()), [])
        self.assertEqual(len(osc.load_raw(self.ledger())), 1, "看不懂不等于可以丢")

    def test_confirm_from_slice_still_carries_the_projection_hash(self) -> None:
        self.draft()
        code, out = _run(
            ["observation", "confirm", "--user", "u1", "--as-of", AS_OF, "--from-slice", ENTITY,
             "--db-path", "/tmp/no-such.duckdb", "--json"]
        )
        self.assertEqual(code, 0, out)
        record = json.loads(out)
        self.assertTrue(record["projection_hash"], "从切片确认的剧本必须带投影哈希")
        self.assertNotIn("projection_hash_missing", record)

    def test_from_draft_confirm_is_user_authored_not_a_faked_projection(self) -> None:
        self.draft()
        code, out = _run(
            ["observation", "confirm", "--user", "u1", "--as-of", AS_OF, "--from-draft", ENTITY,
             "--db-path", "/tmp/no-such.duckdb", "--json"]
        )
        self.assertEqual(code, 0, out)
        record = json.loads(out)
        self.assertIsNone(record["projection_hash"])
        self.assertEqual(record["projection_hash_missing"], "user_authored")
        self.assertTrue(record["source_draft_id"], "确认要指回原稿，不覆盖它")
        self.assertEqual(list(record["variables"]), MY_VARS)

    def test_draft_is_never_auto_confirmed(self) -> None:
        self.draft()
        self.read()
        self.assertFalse(self.space().checkpoints_path.exists())
        self.assertEqual({r["status"] for r in osc.load(self.ledger())}, {"drafted"})

    def test_hindsight_flag_survives_the_draft_path(self) -> None:
        """事后视角标记这一跳不能断：断在哪一跳，下游那道门就形同虚设。"""
        section_slice = {**SLICE, "hindsight": True}
        with mock.patch.object(cli, "_observation_slice", return_value=section_slice):
            self.draft()
            _, out = self.read(extra=["--json"])
        self.assertTrue(json.loads(out)["draft"]["hindsight"])


# =========================================================================== #
# A14 不评分
# =========================================================================== #
class A14NoScoring(Base):
    """本单只做「字段差异 + 来源关联」，不做任何打分。

    这里**不用全仓关键词零命中作证**（工单 §6 A14 明禁）：那种断言既抓不住
    ``d = len(a & b) / len(a | b)`` 这种没有关键词的评分，又会把
    「不评分」这类**声明红线的文案**误判成违规。改成三条结构判据：
    差异载荷里没有数、收据里只有来源关联、以及别的台账一个字没写。
    """

    # 只用来给标识符命名做体检——不是对全文做关键词扫描。
    BANNED_IDENTIFIERS = ("similarity", "score", "convergence", "rate", "ratio", "accuracy")

    @staticmethod
    def _defined_names(path: str) -> set[str]:
        """模块里定义出来的名字（函数 / 类 / 顶层与类体赋值 / 参数）。"""
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                names.add(node.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names.add(node.name)
                names.update(a.arg for a in node.args.args)
                names.update(a.arg for a in node.args.kwonlyargs)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names.add(node.target.id)
            elif isinstance(node, ast.Assign):
                names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        return names

    def test_the_identifier_probe_goes_red_on_a_known_bad_sample(self) -> None:
        """先证明这支探针抓得住：喂一份真含评分函数的样本，必须命中。"""
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as fh:
            fh.write('"""不评分。"""\n\n\ndef agreement_score(a, b):\n    return len(a) / len(b)\n')
            bad = fh.name
        self.addCleanup(os.unlink, bad)
        hit = [n for n in self._defined_names(bad) if any(w in n.lower() for w in self.BANNED_IDENTIFIERS)]
        self.assertEqual(hit, ["agreement_score"])

    def test_the_new_module_defines_no_scoring_symbol(self) -> None:
        names = self._defined_names("intelligence/services/observation_extraction.py")
        hits = [n for n in names if any(w in n.lower() for w in self.BANNED_IDENTIFIERS)]
        self.assertEqual(hits, [], f"提取模块里出现了评分型符号：{hits}")

    def test_diff_payload_carries_no_numbers_at_all(self) -> None:
        """差异载荷里只有字段名与两侧条目——**一个数都没有**，所以无从聚合成比率。"""
        self.draft()
        _, out = self.read(extra=["--json"])
        diff = json.loads(out)["extraction"]["diff"]
        self.assertTrue(diff, "这条用例要在有差异时才有意义")
        for item in diff:
            self.assertEqual(set(item), {"field", "label", "user_only", "system_only"})
            self.assertIsInstance(item["field"], str)
            self.assertIsInstance(item["label"], str)
            for side in ("user_only", "system_only"):
                self.assertTrue(all(isinstance(v, str) for v in item[side]))

    def test_read_receipt_persists_only_source_links(self) -> None:
        """收据只存来源关联；差异与它的大小不落盘，展示时重算。"""
        self.draft()
        self.read()
        (receipt,) = self.kinds(osc.EVENT_READ_COMPLETED)
        allowed = {
            "record_kind", "id", "event", "event_id", "occurred_at", "entrypoint", "attempt_id",
            "action_key", "user_id", "as_of", "extraction_scope", "canonical_entity_id",
            "system_script_ref", "projection_hash", "source_draft_id", "granted_by",
        }
        self.assertEqual(set(receipt) - allowed, set(), "收据出现了来源关联以外的字段")
        self.assertFalse(
            [k for k, v in receipt.items() if isinstance(v, (int, float)) and not isinstance(v, bool)],
            "收据里不该有任何数值——有数就会有人拿去做时间序列",
        )

    def test_read_output_contains_no_ratio(self) -> None:
        self.draft()
        _, out = self.read()
        body = out.split(gr.DIFF_SECTION_TITLE, 1)[1]
        self.assertIsNone(re.search(r"\d+(\.\d+)?\s*%|\b\d+\s*/\s*\d+\b|\d+(\.\d+)?\s*分", body),
                          f"差异段里出现了比率 / 分数：{body}")

    def test_nothing_is_written_to_profile_or_calibration_ledgers(self) -> None:
        self.draft()
        self.read()
        us = self.space()
        for path in (us.profile_path, us.derived_path, us.answer_scores_path,
                     us.experience_cards_path, us.interactions_path, us.checkpoints_path):
            self.assertFalse(path.exists(), f"本单不该写 {path.name}")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
