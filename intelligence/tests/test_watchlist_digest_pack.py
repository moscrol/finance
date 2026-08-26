"""watchlist_digest 组件包：清单×四袋接合、冻结快照、主张分级。

Spec: docs/superpowers/specs/2026-08-26-watchlist-digest-pack-design.md
台账: R-20260826-05（路由）/ -06（快照合同）/ -07（只委托四袋）

负样本的期望值是 2026-08-26 干净树（gitea/main=0735bbe6）实测现状，
不是想象值：「复盘7月16日」在信封层就是 general_finance_qa（dated 判定
发生在 is_dated_market_review 谓词），「止损」在信封层是 general_finance_qa、
decide_turn 层才被细粒度路由改成 trade_advice。本单不得改写这些现状。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import duckdb
import pytest

from intelligence.runtime.continuous_turn_adapter import DETERMINISTIC_OWNER_TYPES
from intelligence.services import watchlist_digest_pack as wdp
from intelligence.services.answer_orchestrator import plan_answer_question
from intelligence.services.ask import bind_watchlist_digest_pack
from intelligence.services.ask_types import AskOptions
from intelligence.services.forecast_residual_budget import (
    DO_NOT_LENGTHEN_QUESTION_TYPES,
)
from intelligence.services.query_understanding import (
    is_dated_market_review,
    is_watchlist_digest_query,
    understand_query,
)
from intelligence.services.turn_controller import decide_turn
from intelligence.services.watchlist_digest_pack import (
    merge_digest_into_public_answer,
    run_watchlist_digest_pack,
    watchlist_digest_degrade_codes,
    write_snapshot,
)

FROZEN_QUERY = "按我的自选出今天的简报"
POSITIVE_QUERIES = (
    FROZEN_QUERY,
    "我的自选今天怎么样",
    "开盘简报（按自选）",
    "我的清单今天该看什么",
)
NEGATIVE_ENVELOPE_TYPES = {
    "今天市场怎么样": "market_watch",
    "今天有什么值得关注的": "market_watch",
    "复盘7月16日的A股市场": "general_finance_qa",
    "宁德时代要不要止损": "general_finance_qa",
    "基于上周的行情写一下本周展望": "market_forecast",
    "固态电池现在处于什么阶段": "theme_analysis",
}
NEGATIVE_DECIDE_TYPES = {
    "今天市场怎么样": ("workflow", "market_watch"),
    "今天有什么值得关注的": ("workflow", "market_watch"),
    "复盘7月16日的A股市场": ("workflow", "general_finance_qa"),
    "宁德时代要不要止损": ("research", "trade_advice"),
    "基于上周的行情写一下本周展望": ("research", "market_forecast"),
    "固态电池现在处于什么阶段": ("research", "theme_analysis"),
}
TRADE_WORD_RE = re.compile(r"买入|卖出|加仓|减仓|现在做多|现在做空")


def _boom(messages):
    raise AssertionError("认题不得调用 LLM")


def _db(tmp_path: Path) -> Path:
    """夹具库形状抄 test_market_watch_component_first._db，不碰真库。"""

    path = tmp_path / "market.duckdb"
    con = duckdb.connect(str(path))
    con.execute(
        """
        create table fact_market_daily(
          trade_date date,
          market_stage varchar,
          stage_day integer,
          total_amount double,
          amount_vs_yesterday_pct double,
          volume_state varchar,
          limit_up integer,
          limit_down integer,
          sh_index_pct_chg double
        )
        """
    )
    con.execute(
        """
        insert into fact_market_daily values
          ('2026-07-23', '反弹阶段', 3, 21949.97, -17.27, '缩量观望', 116, 2, 0.2519),
          ('2026-07-24', '反弹阶段', 4, 18000, -10, '缩量', 80, 1, 0.1),
          ('2026-08-21', '反弹阶段', 10, 30000, 5, '放量', 90, 0, 1.2)
        """
    )
    con.execute(
        """
        create table fact_mainline_theme_daily(
          trade_date date,
          theme_name varchar,
          sector_count integer,
          min_sort integer
        )
        """
    )
    con.execute(
        "insert into fact_mainline_theme_daily values "
        "('2026-07-23', '半导体', 4, 1), ('2026-07-23', 'AI', 3, 2),"
        "('2026-07-24', '半导体', 2, 1)"
    )
    con.execute(
        """
        create table fact_sector_daily(
          trade_date date,
          sector_name varchar,
          pct_chg double,
          diff_ratio double,
          amount double
        )
        """
    )
    con.execute(
        "insert into fact_sector_daily values "
        "('2026-07-23', '电力设备', 3.1, 12.0, 600),"
        "('2026-07-23', '锂矿', 2.0, 11.0, 550),"
        "('2026-07-24', '半导体', 4.0, 20.0, 800)"
    )
    con.execute(
        """
        create table fact_theme_limit_heat_daily(
          trade_date date,
          sector_name varchar,
          limit_up_count integer,
          market_share double
        )
        """
    )
    con.execute(
        "insert into fact_theme_limit_heat_daily values "
        "('2026-07-23', '储能', 40, 0.1), ('2026-07-24', '半导体', 20, 0.2)"
    )
    con.close()
    return path


def _users(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    watchlist: tuple[str, ...] = ("电力设备板块", "乙工业"),
    themes: tuple[str, ...] = ("AI",),
) -> str:
    users = tmp_path / "users"
    (users / "u1").mkdir(parents=True, exist_ok=True)
    (users / "u1" / "profile.json").write_text(
        json.dumps(
            {"watchlist": list(watchlist), "focus_themes": list(themes)},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(users))
    return "u1"


# ---------------------------------------------------------------------------
# 路由（R-20260826-05）
# ---------------------------------------------------------------------------


def test_positive_queries_hit_watchlist_digest_at_all_three_layers() -> None:
    for query in POSITIVE_QUERIES:
        assert is_watchlist_digest_query(query), query
        assert understand_query(query).question_type == "watchlist_digest", query
        plan = plan_answer_question(query)
        assert plan.question_type == "watchlist_digest", query
        decision = decide_turn(query, llm_complete=_boom)
        assert decision.lane == "workflow", query
        assert decision.question_type == "watchlist_digest", query
        assert decision.turn_intent is not None
        assert decision.turn_intent.question_type == "watchlist_digest", query


def test_negative_envelope_types_unchanged() -> None:
    for query, expected in NEGATIVE_ENVELOPE_TYPES.items():
        assert not is_watchlist_digest_query(query), query
        assert understand_query(query).question_type == expected, query


def test_negative_decide_turn_unchanged() -> None:
    for query, (lane, question_type) in NEGATIVE_DECIDE_TYPES.items():
        decision = decide_turn(query, llm_complete=_boom)
        assert decision.lane == lane, query
        assert decision.question_type == question_type, query


def test_dated_review_predicate_untouched() -> None:
    query = "复盘7月16日的A股市场"
    assert is_dated_market_review(query, understand_query(query))


def test_word_face_details() -> None:
    # 「关注的」不等于「关注的票」；没有当日/简报标记不触发。
    assert not is_watchlist_digest_query("今天有什么值得关注的")
    assert not is_watchlist_digest_query("帮我看看自选")
    assert is_watchlist_digest_query("我关注的票今天怎么样")
    assert is_watchlist_digest_query("WATCHLIST 今天简报")


def test_watchlist_digest_is_deterministic_owner_type() -> None:
    assert "watchlist_digest" in DETERMINISTIC_OWNER_TYPES
    assert DO_NOT_LENGTHEN_QUESTION_TYPES == DETERMINISTIC_OWNER_TYPES


def test_priority_source_order_nails() -> None:
    """自选优先的两处顺序钉：信封阶梯、编排器 owner 分叉。"""

    services = Path(__file__).resolve().parents[1] / "services"
    understanding = (services / "query_understanding.py").read_text(encoding="utf-8")
    assert understanding.index("if is_watchlist_digest_query(text)") < (
        understanding.index("if is_market_watch_query(text)")
    )
    controller = (services / "turn_controller.py").read_text(encoding="utf-8")
    assert controller.index('route_by_id("watchlist_digest")') < (
        controller.index('route_by_id("market_watch")')
    )
    orchestrator = (
        Path(__file__).resolve().parents[1]
        / "runtime"
        / "conversation_orchestrator.py"
    ).read_text(encoding="utf-8")
    assert orchestrator.index("bind_watchlist_digest_pack") < (
        orchestrator.index("elif owner_output is not None:")
    )
    assert 'report["watchlist_digest_pack"]' in orchestrator


# ---------------------------------------------------------------------------
# 包与快照（R-20260826-06）
# ---------------------------------------------------------------------------


def test_fact_rows_lock_bag_numbers_with_method_card(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = _db(tmp_path)
    user = _users(tmp_path, monkeypatch)
    pack = run_watchlist_digest_pack(
        FROZEN_QUERY,
        user_id=user,
        market_db_path=db,
        cutoff="2026-07-23",
    )
    assert pack.status == "locked"
    assert pack.standing_date == "2026-07-23"
    assert pack.user_id == user
    fact_rows = [row for row in pack.rows if row.tier == "fact"]
    gap_rows = [row for row in pack.rows if row.tier == "gap"]
    assert any(row.subject == "电力设备板块" for row in fact_rows)
    assert any(row.subject == "AI" for row in fact_rows)
    assert any(row.subject == "乙工业" for row in gap_rows)
    rendered = pack.render_public_answer()
    assert "（事实）" in rendered
    assert "（缺口）" in rendered
    assert "trade_date =" in rendered
    for token in ("3.1", "12.0", "600.0"):
        assert token in rendered
    # 公开稿数字 ⊆ 快照冻结行（对账只对这份，不再查库）。
    snapshot = pack.to_snapshot()
    frozen = json.dumps(snapshot["bags"], ensure_ascii=False)
    for token in ("3.1", "12.0", "600.0"):
        assert token in frozen
    assert snapshot["standing_date"] == "2026-07-23"
    # 全市场上下文只此一行，且必须声明不是清单。
    assert "全市场袋" in rendered
    assert "不是你的清单" in rendered
    # 主张档图例收尾。
    assert rendered.rstrip().endswith("（缺口）=清单项当日未见于袋。")
    assert TRADE_WORD_RE.search(rendered) is None


def test_multi_bag_hit_emits_inference_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = _db(tmp_path)
    user = _users(tmp_path, monkeypatch, watchlist=("半导体",), themes=())
    pack = run_watchlist_digest_pack(
        FROZEN_QUERY,
        user_id=user,
        market_db_path=db,
        cutoff="2026-07-24",
    )
    facts = [row for row in pack.rows if row.tier == "fact"]
    inferences = [row for row in pack.rows if row.tier == "inference"]
    assert len(facts) >= 2
    assert len(inferences) == 1
    # 推断行不得引入任何数字（袋外数字禁令的机械可查形式）。
    assert re.search(r"\d", inferences[0].text) is None
    assert inferences[0].bag is None


def test_gap_row_never_invents_numbers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = _db(tmp_path)
    user = _users(tmp_path, monkeypatch, watchlist=("乙工业",), themes=())
    pack = run_watchlist_digest_pack(
        FROZEN_QUERY,
        user_id=user,
        market_db_path=db,
        cutoff="2026-07-23",
    )
    gap_rows = [row for row in pack.rows if row.tier == "gap"]
    assert len(gap_rows) == 1
    assert re.search(r"\d", gap_rows[0].text) is None
    assert gap_rows[0].bag is None
    assert gap_rows[0].served_date is None


def test_empty_watchlist_fails_closed_not_market_watch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = _db(tmp_path)
    user = _users(tmp_path, monkeypatch, watchlist=(), themes=())
    pack = run_watchlist_digest_pack(
        FROZEN_QUERY,
        user_id=user,
        market_db_path=db,
        cutoff="2026-07-23",
    )
    assert pack.status == "empty"
    assert pack.stop_text and "清单" in pack.stop_text
    rendered = pack.render_public_answer()
    assert "清单" in rendered
    # 不回落全市场日报：双红名单、盘面包标题都不得出现。
    assert "指定日盘面组件包" not in rendered
    assert "3.1" not in rendered
    assert watchlist_digest_degrade_codes(pack) == ("watchlist_digest_pack_empty",)
    # 路由不因画像为空而漂移。
    assert understand_query(FROZEN_QUERY).question_type == "watchlist_digest"


def test_explicit_missing_day_stops_without_neighbor_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = _db(tmp_path)
    user = _users(tmp_path, monkeypatch)
    pack = run_watchlist_digest_pack(
        FROZEN_QUERY,
        user_id=user,
        market_db_path=db,
        cutoff="2026-07-25",
    )
    assert pack.status == "empty"
    rendered = pack.render_public_answer()
    assert "2026-07-25" in rendered
    assert "无行情" in rendered
    # 不许把 07-23 的数字借给 07-25。
    assert "2026-07-23" not in rendered
    assert "3.1" not in rendered
    assert "21949.97" not in rendered


def test_missing_db_is_locked_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _users(tmp_path, monkeypatch)
    pack = run_watchlist_digest_pack(
        FROZEN_QUERY,
        user_id=user,
        market_db_path=tmp_path / "missing.duckdb",
        cutoff="2026-07-23",
    )
    assert pack.status == "locked_db"
    rendered = pack.render_public_answer()
    assert "不可用" in rendered
    assert "无行情" not in rendered  # 库打不开 ≠ 该日无行情
    assert watchlist_digest_degrade_codes(pack) == (
        "watchlist_digest_pack_locked_db",
    )


def test_snapshot_freezes_bags_and_writes_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = _db(tmp_path)
    user = _users(tmp_path, monkeypatch)
    pack = run_watchlist_digest_pack(
        FROZEN_QUERY,
        user_id=user,
        market_db_path=db,
        cutoff="2026-07-23",
    )
    snapshot = pack.to_snapshot()
    assert snapshot["user_id"] == user
    assert snapshot["watchlist"] == ["电力设备板块", "乙工业"]
    assert snapshot["focus_themes"] == ["AI"]
    served = {
        bag["name"]: bag["served_date"]
        for bag in snapshot["bags"]
        if bag["status"] == "hit"
    }
    assert served["market_daily"] == snapshot["standing_date"]
    assert served["dual_red"] == snapshot["standing_date"]
    assert snapshot["rows"], "接合行必须冻进快照"
    path = write_snapshot(pack, base_dir=tmp_path / "snaps")
    assert path.exists()
    assert path.parent == tmp_path / "snaps" / user / "2026-07-23"
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["standing_date"] == "2026-07-23"
    assert on_disk["bags"]


def test_receipt_is_thin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = _db(tmp_path)
    user = _users(tmp_path, monkeypatch)
    pack = run_watchlist_digest_pack(
        FROZEN_QUERY,
        user_id=user,
        market_db_path=db,
        cutoff="2026-07-23",
    )
    receipt = pack.to_receipt()
    assert receipt["status"] == "locked"
    assert receipt["fact_rows"] >= 2
    assert receipt["gap_rows"] >= 1
    assert receipt["bag_status"]["dual_red"] == "hit"
    # 瘦收据不抄袋行：数字与行数组都不进 episode 台账。
    blob = json.dumps(receipt, ensure_ascii=False)
    assert "3.1" not in blob
    assert "pct_chg" not in blob


def test_bind_locks_compose_and_injects_pack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = _db(tmp_path)
    user = _users(tmp_path, monkeypatch)
    monkeypatch.setenv("FORESIGHT_USER", user)
    options = AskOptions(
        query=FROZEN_QUERY,
        market_db_path=db,
        compose=True,
        synthesize=True,
        user=user,
    )
    bound = bind_watchlist_digest_pack(options, frame=None)
    pack = bound.watchlist_digest_pack
    assert pack is not None
    assert pack.user_id == user
    # P0 残差恒关：包即公开稿。
    assert bound.compose is False
    assert bound.synthesize is False
    # 隐式「今天」= 库内最新交易日，不是日历今天。
    assert bound.date == "2026-08-21"
    assert "自选简报" in bound.supplemental_evidence


def test_public_answer_section_order_is_locked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = _db(tmp_path)
    user = _users(tmp_path, monkeypatch)
    pack = run_watchlist_digest_pack(
        FROZEN_QUERY,
        user_id=user,
        market_db_path=db,
        cutoff="2026-07-23",
    )
    rendered = pack.render_public_answer()
    order = [
        rendered.index("站立日"),
        rendered.index("方法卡"),
        rendered.index("清单命中"),
        rendered.index("清单未命中"),
        rendered.index("全市场袋"),
        rendered.index("主张档图例"),
    ]
    assert order == sorted(order)


def test_merge_shape_keeps_pack_body_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = _db(tmp_path)
    user = _users(tmp_path, monkeypatch)
    pack = run_watchlist_digest_pack(
        FROZEN_QUERY,
        user_id=user,
        market_db_path=db,
        cutoff="2026-07-23",
    )
    body = pack.render_public_answer()
    assert merge_digest_into_public_answer("", pack) == body
    merged = merge_digest_into_public_answer("残差解读", pack)
    assert merged.startswith(body)
    assert merged.rstrip().endswith("残差解读")


# ---------------------------------------------------------------------------
# 只委托四袋（R-20260826-07）
# ---------------------------------------------------------------------------


def test_pack_delegates_to_market_watch_pack_exactly_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = _db(tmp_path)
    user = _users(tmp_path, monkeypatch)
    calls: list[str] = []
    original = wdp.run_market_watch_pack

    def counting(*args, **kwargs):
        calls.append("call")
        return original(*args, **kwargs)

    monkeypatch.setattr(wdp, "run_market_watch_pack", counting)
    pack = run_watchlist_digest_pack(
        FROZEN_QUERY,
        user_id=user,
        market_db_path=db,
        cutoff="2026-07-23",
    )
    assert pack.status == "locked"
    assert calls == ["call"], "盘面袋必须且只能委托一次 run_market_watch_pack"


def test_module_contains_no_private_market_sql() -> None:
    src = Path(wdp.__file__).read_text(encoding="utf-8")
    assert "duckdb.connect" not in src
    assert re.search(r"(?i)\bselect\b", src) is None
    for table in (
        "fact_sector_daily",
        "fact_market_daily",
        "fact_mainline_theme_daily",
        "fact_theme_limit_heat_daily",
    ):
        assert table not in src, f"包内不得出现第二套 {table} 口径"


def test_trade_words_never_reach_public_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = _db(tmp_path)
    user = _users(tmp_path, monkeypatch)
    for cutoff in ("2026-07-23", "2026-07-24", "2026-07-25"):
        pack = run_watchlist_digest_pack(
            FROZEN_QUERY,
            user_id=user,
            market_db_path=db,
            cutoff=cutoff,
        )
        assert TRADE_WORD_RE.search(pack.render_public_answer()) is None


# ---------------------------------------------------------------------------
# CLI（正门之一；只读，--write 才落快照）
# ---------------------------------------------------------------------------


def test_cli_digest_prints_markdown_and_exits_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import argparse

    from intelligence.cli import cmd_digest

    db = _db(tmp_path)
    user = _users(tmp_path, monkeypatch)
    args = argparse.Namespace(
        date="2026-07-23", user=user, db=str(db), write=False
    )
    assert cmd_digest(args) == 0
    out = capsys.readouterr().out
    assert "（事实）" in out
    assert "trade_date =" in out
    assert TRADE_WORD_RE.search(out) is None


def test_cli_digest_empty_profile_exits_zero_with_gap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import argparse

    from intelligence.cli import cmd_digest

    db = _db(tmp_path)
    user = _users(tmp_path, monkeypatch, watchlist=(), themes=())
    args = argparse.Namespace(
        date="2026-07-23", user=user, db=str(db), write=False
    )
    assert cmd_digest(args) == 0
    out = capsys.readouterr().out
    assert "（缺口）" in out
    assert "清单" in out


def test_cli_digest_write_flag_drops_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import argparse

    from intelligence.cli import cmd_digest

    db = _db(tmp_path)
    user = _users(tmp_path, monkeypatch)
    snap_root = tmp_path / "snap-root"
    monkeypatch.setenv("WATCHLIST_DIGEST_DIR", str(snap_root))
    args = argparse.Namespace(
        date="2026-07-23", user=user, db=str(db), write=True
    )
    assert cmd_digest(args) == 0
    files = list((snap_root / user / "2026-07-23").glob("*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text(encoding="utf-8"))
    assert payload["standing_date"] == "2026-07-23"
