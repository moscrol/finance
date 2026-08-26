"""第 0 步：开关板读表。不搬超集树 960 行夹具。

超集树上那份夹具假设双红复印件已清零、reading_baseline 已合、路由/说明书
三面都接到 faces()。reading_baseline 已随 feat/reading-rules-baseline-r3
落地本底（2026-08-26，#343 的 rebase 重开），转 active/exists 并进臂；
另两件（复印件清零、路由/说明书接线）仍不成立，整份搬过来仍会红。

本文件只锁本底真实做到的：

  表能被读；认不出的 id fail-closed
  capability id 与 ``_DEFAULT_TOOL_METADATA`` 双向无漂移
  seam 文件存在，pending-other-branch 的文件必须还不在
  welded / 正典不存在 / 面没接线 的行不进臂
  生产 serving 路径不 import ``capability_switchboard``
  预取算数面读 ``faces()``；路由/说明书本底仍不读

离线 runner 正控、复印件棘轮：后续单独加，不要为了绿把那些文件拷进来。
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from intelligence.services.capability_switchboard import (
    SwitchboardError,
    UnknownSwitchError,
    load_switchboard,
)
from intelligence.services.research_tool_registry import _DEFAULT_TOOL_METADATA

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def board():
    return load_switchboard()


def test_fixture_loads_and_declares_its_base(board) -> None:
    assert board.rows, "开关板不能是空表"
    assert board.revision, "表必须自述它是在哪个 revision 上核的 seam"
    assert board.switch_set == "seed", "default-v1 是生成物，不该在种子表里"


def test_unknown_id_fails_closed(board) -> None:
    with pytest.raises(UnknownSwitchError):
        board.resolve("market_dataa")
    with pytest.raises(UnknownSwitchError):
        board.resolve("predicate.double_red")


def test_capability_ids_match_registry_exactly(board) -> None:
    registered = {row.id for row in board.of_kind("capability")}
    assert registered == set(_DEFAULT_TOOL_METADATA)


def test_every_capability_documents_its_env_gate_scan(board) -> None:
    known_env_gates = {
        "l3_lookup": "FINANCE_L3_LOOKUP_ENABLED",
        "web_search": "FINANCE_WEB_SEARCH",
        "news_search": "FINANCE_NEWS_FETCH",
        "financial_data": "FINANCE_FINANCIALS_FETCH",
    }
    for row in board.of_kind("capability"):
        assert row.notes.strip(), f"{row.id} 没写第二道门的排查结论"
        gate = known_env_gates.get(row.id)
        if gate is None:
            continue
        joined = " ".join(row.close_via)
        assert gate in joined, f"{row.id} 的 close_via 漏了 env 门 {gate}"


def test_seam_paths_exist_except_pending(board) -> None:
    for row in board.rows:
        target = REPO / row.seam_path
        if row.status == "pending-other-branch":
            assert not target.exists(), f"{row.id} 标了他树，但本底已经有 {row.seam_path}"
        else:
            assert target.exists(), f"{row.id} 的 seam 路径不存在：{row.seam_path}"


def test_reading_baseline_landed_and_enters_the_arm(board) -> None:
    """r3 落地后翻钉：正典在本底、登记转 active/exists、自动进臂。"""

    row = board.resolve("predicate.reading-baseline")
    assert row.status == "active"
    assert row.canonical == "exists"
    assert "predicate.reading-baseline" in board.arm_ids()
    assert (REPO / "intelligence/services/reading_baseline.py").exists()


def test_non_existing_canonical_never_enters_an_arm(board) -> None:
    arm = set(board.arm_ids())
    for row in board.of_kind("predicate"):
        if row.canonical != "exists":
            assert row.id not in arm, f"{row.id} 的正典是 {row.canonical}，不该进实验臂"
    assert "predicate.single-red" not in arm
    assert "predicate.volume-surge-10" not in arm
    assert "predicate.mainup-consecutive-3" not in arm
    assert "predicate.limit-approx-9p8" not in arm
    assert "predicate.double-red" in arm
    assert "predicate.sqrt-weighted" in arm
    assert "predicate.dated-market-topic" in arm
    assert "param.boards-min" not in arm


def test_welded_never_enters_an_arm(board) -> None:
    assert "structural-verifier" not in board.arm_ids()


def test_every_arm_row_has_a_positive_control(board) -> None:
    for switch_id in board.arm_ids():
        row = board.resolve(switch_id)
        assert row.positive_control.strip(), f"{row.id} 进臂了却没有正控字段"


def test_arm_is_not_empty_and_covers_both_families(board) -> None:
    arm = set(board.arm_ids())
    kinds = {board.resolve(switch_id).kind for switch_id in arm}
    assert "capability" in kinds
    assert "predicate" in kinds
    assert "semantic-verifier" in arm


def _write_board(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "board.json"
    path.write_text(
        json.dumps({"switch_set": "t", "revision": "t", "rows": rows}, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def _minimal_row(**overrides) -> dict:
    row = {
        "id": "x",
        "kind": "capability",
        "status": "active",
        "seam": "market_feature_store/signals.py::DOUBLE_RED_SQL",
        "close_via": ["allowed_capabilities:remove"],
        "default": "ambient",
        "singleton_when_on": False,
        "chassis_survives": True,
        "positive_control": "offered_schemas",
        "notes": "t",
    }
    row.update(overrides)
    return row


def test_predicate_row_must_declare_canonical(tmp_path: Path) -> None:
    path = _write_board(tmp_path, [_minimal_row(id="predicate.x", kind="predicate")])
    with pytest.raises(SwitchboardError, match="canonical"):
        load_switchboard(path)


def test_duplicate_id_rejected(tmp_path: Path) -> None:
    path = _write_board(tmp_path, [_minimal_row(), _minimal_row()])
    with pytest.raises(SwitchboardError, match="duplicate"):
        load_switchboard(path)


def test_unknown_enum_rejected(tmp_path: Path) -> None:
    path = _write_board(tmp_path, [_minimal_row(status="disabled")])
    with pytest.raises(SwitchboardError, match="status"):
        load_switchboard(path)


def test_empty_close_via_rejected(tmp_path: Path) -> None:
    path = _write_board(tmp_path, [_minimal_row(close_via=[])])
    with pytest.raises(SwitchboardError, match="close_via"):
        load_switchboard(path)


def test_serving_path_does_not_import_switchboard() -> None:
    """生产请求路径永远不读登记表。离线 runner / 生成脚本 / 本测试除外。"""

    roots = (
        REPO / "intelligence" / "services",
        REPO / "intelligence" / "runtime",
        REPO / "intelligence" / "adapters",
        REPO / "intelligence" / "api",
    )
    skip_names = {"capability_switchboard.py"}
    offenders: list[str] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            if path.name in skip_names:
                continue
            text = path.read_text(encoding="utf-8")
            if "capability_switchboard" in text:
                offenders.append(str(path.relative_to(REPO)))
    assert offenders == []


def test_route_and_prose_faces_are_not_wired_on_this_extract() -> None:
    """本刀只重贴预取算数面。不要把超集树的路由/说明书接线整文件盖回来。"""

    for rel in (
        "intelligence/services/query_understanding.py",
        "intelligence/services/foresight.py",
        "intelligence/services/ask_blocks.py",
    ):
        text = (REPO / rel).read_text(encoding="utf-8")
        assert "predicate_faces" not in text, rel


def test_default_faces_count_double_red() -> None:
    from intelligence.services.predicate_faces import faces

    assert faces().counts_double_red() is True
    assert faces({"predicate.double-red"}).counts_double_red() is False


def test_disabled_double_red_face_skips_prefetch_counts() -> None:
    from intelligence.services.asof_prefetch import dual_red_counts
    from intelligence.services.predicate_faces import using

    with using({"predicate.double-red"}):
        assert dual_red_counts(object(), (date(2026, 7, 23),)) == {}


def test_unwired_arithmetic_predicates_do_not_enter_arm_or_wired_set(board) -> None:
    from intelligence.services.predicate_faces import wired_predicate_ids

    arm = set(board.arm_ids())
    wired = wired_predicate_ids()
    for switch_id in (
        "predicate.single-red",
        "predicate.volume-surge-10",
        "predicate.mainup-consecutive-3",
        "predicate.limit-approx-9p8",
    ):
        assert switch_id not in arm
        assert switch_id not in wired
    assert "predicate.double-red" in wired
    # r3 落地后：声明 + 正典 + 面都在，既 wired 也进臂。
    assert "predicate.reading-baseline" in wired
    assert "predicate.reading-baseline" in arm


def test_default_box_regenerates() -> None:
    import runpy

    script = REPO / "scripts" / "generate_default_switch_box.py"
    ns = runpy.run_path(str(script))
    rendered = ns["render"](ns["build_box"]())
    current = (REPO / "intelligence/eval/fixtures/switch_box_default_v1.json").read_text(
        encoding="utf-8"
    )
    assert current == rendered
