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


# ── 2026-08-26 扩容批：operator/pack/probe 登记行 + pointers ────────────────


_EXPANSION_KINDS = ("operator", "pack", "probe")


def test_expansion_rows_registered_with_verified_seams(board) -> None:
    """扩容行齐全、seam 路径真实存在、operator id 与 research_contract 常量双向无漂移。"""

    from intelligence.services import research_contract as rc

    operators = {row.id for row in board.of_kind("operator")}
    declared = {
        value
        for name, value in vars(rc).items()
        if name.startswith("OPERATOR_") and isinstance(value, str)
    }
    assert operators == declared, "operator 登记行与 OPERATOR_* 常量漂移"

    assert {row.id for row in board.of_kind("pack")} == {
        "pack.market-watch",
        "pack.weekly-watch",
    }
    assert {row.id for row in board.of_kind("probe")} == {"probe.substitute-observation"}

    for kind in _EXPANSION_KINDS:
        for row in board.of_kind(kind):
            assert (REPO / row.seam_path).exists(), f"{row.id} 的 seam 文件不存在"
            assert row.notes.strip(), f"{row.id} 登记行必须写清选入机制与不进臂原因"


def test_expansion_rows_stay_out_of_arm_and_default_box(board) -> None:
    """棘轮 #3/#7：登记行不进臂（positive_control 留空）、不进默认盒（excluded 自述原因）。"""

    import runpy

    arm = set(board.arm_ids())
    expansion_ids = {
        row.id for kind in _EXPANSION_KINDS for row in board.of_kind(kind)
    }
    assert expansion_ids, "扩容行不该为空"
    assert not (expansion_ids & arm), "登记行在 positive_control 落实前不得进臂"

    ns = runpy.run_path(str(REPO / "scripts" / "generate_default_switch_box.py"))
    box = ns["build_box"]()
    for switch_id in expansion_ids:
        assert switch_id in box["excluded"], f"{switch_id} 该被排除在默认盒外"
        assert switch_id not in box["non_tool_defaults"]
        assert switch_id not in box["ambient_ids"]


def test_pointer_entries_document_offboard_switches() -> None:
    """pointers 登记「开关在别处」的组件：防止把「不在板上」误判成「没有开关」。"""

    fixture = json.loads(
        (REPO / "intelligence/eval/fixtures/capability_switchboard.json").read_text(
            encoding="utf-8"
        )
    )
    pointers = fixture.get("pointers")
    assert isinstance(pointers, list) and len(pointers) >= 3
    for entry in pointers:
        assert entry.get("target", "").strip()
        assert entry.get("switch_lives_at", "").strip()
        assert entry.get("note", "").strip()


def test_runner_reading_pack_face_flips_under_contextvar() -> None:
    """runner 的判读包正控（`_reading_pack_face_changed`）必须真的翻面。

    它验的是「`using()` 关断 → 注入产物归零」这条链；接线修复前它恒 False，
    全臂扫描把判读基线判成三题全败。
    """

    import runpy

    ns = runpy.run_path(str(REPO / "scripts" / "run_capability_switchboard.py"))
    assert ns["_reading_pack_face_changed"]("predicate.reading-baseline") is True
    # 别的谓词不走判读包那一面：恒 False 是契约，不是缺陷。
    assert ns["_reading_pack_face_changed"]("predicate.double-red") is False


# --------------------------------------------- 2026-08-31 补登的运行时缝

_NEW_ROWS = {"fast-path-runner", "repair-chain", "evidence-judge"}


def test_reading_baseline_lists_both_doors(board) -> None:
    """`enabled()` 是 contextvar + env 两道门任一关闭即关，登记必须两条都列。

    §5.2：「一行可以有多个关法，必须全列——漏一个就会『表说 on、实际 off』」。
    漏 env 那条时，部署层设了 `FINANCE_READING_BASELINE=0` 板上仍报 on，
    而质量臂 `run_quality_ablation` 用的正是 env 那条关法。

    断言绑到源码常量而不是字面量：改了 ENV_FLAG 名字这条测试要跟着红。
    """

    from intelligence.services.reading_baseline import ENV_FLAG

    row = board.resolve("predicate.reading-baseline")
    joined = " ".join(row.close_via)
    assert "pack:contextvar" in joined
    assert ENV_FLAG in joined, f"close_via 漏了 env 门 {ENV_FLAG}"


def test_new_rows_seams_resolve_to_real_symbols(board) -> None:
    """seam 不只文件要在，符号也要在——路径存在但符号改名了，登记就是一句空话。"""

    expected_symbols = {
        "fast-path-runner": ("CONTINUOUS_FAST_PATH_TYPES",),
        "repair-chain": ("_resolve_seconds_cap",),
        "evidence-judge": ("ENV_MODE",),
    }
    for switch_id, symbols in expected_symbols.items():
        row = board.resolve(switch_id)
        source = (REPO / row.seam_path).read_text(encoding="utf-8")
        for symbol in symbols:
            assert symbol in source, f"{switch_id} 的 seam 里找不到符号 {symbol}"
        assert row.notes.strip(), f"{switch_id} 必须写清关法与不进臂原因"


def test_new_rows_stay_out_of_arm_without_positive_control(board) -> None:
    """§5.1：填不出正控的只登记、不进臂。「没崩」不是读数。

    三行都是登记行：fast-path 与 repair 的真关法是 route/代码级（见下两条测试
    钉住的实测事实），evidence-judge 的可观测面在质量臂不在结构臂。
    """

    arm = set(board.arm_ids())
    for switch_id in _NEW_ROWS:
        row = board.resolve(switch_id)
        assert not row.positive_control, f"{switch_id} 有正控就得真能被 runner 拧动"
        assert switch_id not in arm


def test_fast_path_constructor_injection_is_abort_not_off(board) -> None:
    """钉住 2026-08-31 实测：注入 null fast_path_runner 拿到的是降级的一集。

    路由决定在调 runner **之前**（`frame.question_type in CONTINUOUS_FAST_PATH_TYPES`），
    异常被就地捕获 → `status="failed"`，而 `execution_kind` **仍是**
    `deterministic_fast_path`。与设计稿 §3 记的 semantic-verifier deadline 陷阱同形：
    拿它当 off，会得到一份「拧了、正控恒不变」的假失败。

    这条测试守的不是代码，是**下一个 agent 不要再把构造注入写进这行的 close_via**。
    """

    adapter = (REPO / "intelligence/runtime/continuous_turn_adapter.py").read_text(
        encoding="utf-8"
    )
    route_at = adapter.index("if frame.question_type in CONTINUOUS_FAST_PATH_TYPES")
    call_at = adapter.index("self._fast_path_runner(")
    assert route_at < call_at, "路由若挪到 runner 之后，构造注入才可能成为真关法"

    row = board.resolve("fast-path-runner")
    assert not any("constructor_injection" in item for item in row.close_via), (
        "构造注入不是这颗的关法：它产出 status=failed 且 execution_kind 不变"
    )

    from intelligence.services.episode_tools import FAST_PATH_RUNNER_SUPPORTED_TYPES

    # 覆盖面别再被写大：这条路只服务一个题型。
    assert FAST_PATH_RUNNER_SUPPORTED_TYPES == frozenset({"market_technical"})


def test_repair_seconds_cap_zero_falls_back_not_off(board) -> None:
    """钉住 2026-08-31 实测：帽设 0 回到默认 30s，等于没拧。

    `_resolve_seconds_cap` 是 fail-safe（坏输入不压成 0），所以 0 / 负数 / None
    三者同解。把 0 当 off 会得到「拧了、没变、正控空」的假失败读数。
    """

    from intelligence.runtime.repair_budget import (
        _REPAIR_SECONDS_CAP,
        _resolve_seconds_cap,
    )

    assert _resolve_seconds_cap(0) == _REPAIR_SECONDS_CAP
    assert _resolve_seconds_cap(-1) == _REPAIR_SECONDS_CAP
    assert _resolve_seconds_cap(None) == _REPAIR_SECONDS_CAP

    row = board.resolve("repair-chain")
    joined = " ".join(row.close_via)
    assert "repair_seconds_cap=0" not in joined, "帽设 0 不是关法，别写进 close_via"
    assert "ASK_REPAIR_SECONDS_CAP" not in joined, "env 走同一条解析，同样关不掉"


def test_evidence_judge_registered_with_its_env_door(board) -> None:
    """质量臂测出的最高边际贡献（+2.8/20）此前不在板上，读板的人会以为它没开关。"""

    from intelligence.services.evidence_judge import ENV_MODE

    row = board.resolve("evidence-judge")
    assert ENV_MODE in " ".join(row.close_via)
    assert row.default == "ambient", "缺省是 auto（配了 key 才生效），不是硬 on"


def test_new_rows_stay_out_of_default_box(board) -> None:
    """棘轮 #3：新开关进默认盒要另一次对照 + 用户确认，且 excluded 要自述原因。"""

    import runpy

    ns = runpy.run_path(str(REPO / "scripts" / "generate_default_switch_box.py"))
    box = ns["build_box"]()
    for switch_id in _NEW_ROWS:
        assert switch_id in box["excluded"], f"{switch_id} 该被排除在默认盒外"
        assert box["excluded"][switch_id].strip()
        assert switch_id not in box["non_tool_defaults"]
        assert switch_id not in box["ambient_ids"]
