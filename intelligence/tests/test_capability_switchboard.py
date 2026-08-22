"""第 0 步：开关板登记表 + 复印件门禁的读表测试。

对应两份设计稿的第 0 步过关条件：

  开关板稿 §7  表能被读；capability id 相对 `_DEFAULT_TOOL_METADATA` 无拼写漂移；
               每颗都查过第二道 env 门；进臂的行填得出 `positive_control`。
  谓词稿 §8    每行带 `canonical`；`canonical != exists` 的行能被一句查询筛掉，
               且不出现在任何实验臂。

这一步不动 loop、不改生产行为。

两个检测器管两种复印件形状，别混：

  `check_double_red_copies`      字面量抄写（SQL 单行/跨行、Python 内联）
  `test_double_red_*_definitions` 具名常量的第二份实现（timeline 那种，字面扫不到）
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence.services.capability_switchboard import (
    SwitchboardError,
    UnknownSwitchError,
    load_switchboard,
)
from intelligence.services.research_tool_registry import _DEFAULT_TOOL_METADATA
from scripts.check_double_red_copies import scan_paths, scan_text

REPO = Path(__file__).resolve().parents[2]
# 本树从 gitea/main 检出的底。改前正文钉死在这个 revision，不钉 HEAD——
# HEAD 会跟着本分支走，一提交「对着改前必须 ≥4 hit」就会变成对着改后的 0。
SPEC_BASELINE_REV = "4e0c6bf5"

# 门禁基线：**按文件**记，不按行号——行号会漂，文件不会。
# 清理掉任何一个都要回来改这份基线，那是有意的一次决定，不该静默通过。
# 门禁基线：生产代码里的双红字面复印件**已清零**（第 2 步第二批收口完成）。
# 空集合不是「还没开始查」——`test_copy_baseline_is_exactly_the_known_files`
# 会在任何新增字面时红，这是棘轮从此往后只减不增的起点。
BASELINE_COPY_FILES: frozenset[str] = frozenset()

# 自己定义双红阈值常量的模块。第 1 步之前是 2（timeline 另写三个 float），
# 收口后只剩正典。字面扫描抓不到这一类——写的是常量名不是 `500`。
DOUBLE_RED_THRESHOLD_MODULES = frozenset({"market_feature_store/signals.py"})


@pytest.fixture(scope="module")
def board():
    return load_switchboard()


# --------------------------------------------------------------------------
# 表本身
# --------------------------------------------------------------------------


def test_fixture_loads_and_declares_its_base(board) -> None:
    assert board.rows, "开关板不能是空表"
    assert board.revision, "表必须自述它是在哪个 revision 上核的 seam"
    assert board.switch_set == "seed", "default-v1 是第 2 步的生成物，不该在种子表里"


def test_unknown_id_fails_closed(board) -> None:
    """认不出的 id 必须抛，不能返回 None 或静默忽略。

    静默忽略会让一次拼错的差量跑出一份「看起来正常」的收据——那比不跑更糟。
    """

    with pytest.raises(UnknownSwitchError):
        board.resolve("market_dataa")
    with pytest.raises(UnknownSwitchError):
        board.resolve("predicate.double_red")  # 下划线，真名是连字符


def test_capability_ids_match_registry_exactly(board) -> None:
    """capability 行与 `_DEFAULT_TOOL_METADATA` 逐字一致，双向无漂移。"""

    registered = {row.id for row in board.of_kind("capability")}
    assert registered == set(_DEFAULT_TOOL_METADATA)


def test_every_capability_documents_its_env_gate_scan(board) -> None:
    """每颗 capability 都要交代第二道门查过没有——查了没有也得写进 notes。

    「表说 on、实际 off」就是从这里漏的：capability 在授权面里，env 却关着。
    """

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
    """`seam` 指到的文件必须真的在——除了明确标了他树的行。

    这条挡的是路径写错（`theme_lifecycle_timeline.py` 就一度被记在
    `market_feature_store/` 下，真身在 `intelligence/services/`）。
    """

    for row in board.rows:
        target = REPO / row.seam_path
        if row.status == "pending-other-branch":
            assert not target.exists(), f"{row.id} 标了他树，但本底已经有 {row.seam_path}"
        else:
            assert target.exists(), f"{row.id} 的 seam 路径不存在：{row.seam_path}"


# --------------------------------------------------------------------------
# 实验臂资格
# --------------------------------------------------------------------------


def test_non_existing_canonical_never_enters_an_arm(board) -> None:
    """正典不存在 = 没得关，不是关不掉。这些行是工单，一律不进臂。"""

    arm = set(board.arm_ids())
    for row in board.of_kind("predicate"):
        if row.canonical != "exists":
            assert row.id not in arm, f"{row.id} 的正典是 {row.canonical}，不该进实验臂"
    # 正典在、生产缝还没接到 faces() 的，不进臂（算数正控会恒真）。
    # 说明书/路由已接线的仍进。boards-min 是 CLI 参数，不进臂。
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
    """进臂就必须说得出「拧了哪个字段必须变」。

    说不出来的行，实验只能得到「没崩」——而「没崩」在离线 scripted 臂里恒真。
    """

    for switch_id in board.arm_ids():
        row = board.resolve(switch_id)
        assert row.positive_control.strip(), f"{row.id} 进臂了却没有正控字段"


def test_arm_is_not_empty_and_covers_both_families(board) -> None:
    arm = set(board.arm_ids())
    kinds = {board.resolve(switch_id).kind for switch_id in arm}
    assert "capability" in kinds
    assert "predicate" in kinds
    assert "semantic-verifier" in arm


# --------------------------------------------------------------------------
# 表的合法性（构造失败路径）
# --------------------------------------------------------------------------


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


# --------------------------------------------------------------------------
# 复印件门禁
# --------------------------------------------------------------------------


def test_daily_review_no_longer_holds_a_copy() -> None:
    """`daily_review.py` 收口后必须零命中，且真的在用正典。

    收口前这里是 4 处（3 跨行 SQL + 1 处 `🔥` 标记的 Python 内联），而原稿写的
    单行 `rg` 检法在这个文件上命中 0 处——「报 0」曾经既可能是干净、也可能是
    检法瞎。所以这条断言配一条正控：文件里得真的出现正典符号。
    """

    text = (REPO / "market_feature_store/reports/daily_review.py").read_text(
        encoding="utf-8"
    )
    assert scan_text(text, path="daily_review.py") == []
    assert "DOUBLE_RED_DESCRIPTION" in text and "DOUBLE_RED_SQL" in text
    assert "SINGLE_RED_SQL" in text and "is_double_red" in text
    assert "weighted_strength_sql" in text
    assert "DOUBLE_RED_DESCRIPTION" in text  # 🔥 图例散文也改成引用了
    assert "AND {SINGLE_RED_SQL}" in text  # 单红也走正典
    assert "if is_double_red(pct, diff, amount):" in text  # 🔥 标记那处


def test_gate_catches_each_shape() -> None:
    """门禁自身的正控：三种形状各造一条，必须都被抓到。"""

    inline_sql = "WHERE pct_chg > 0 AND diff_ratio > 10 AND amount > 500"
    multiline_sql = "WHERE trade_date = ?\n  AND pct_chg > 0\n  AND diff_ratio > 10\n  AND amount > 500"
    python_inline = "if p > 0 and d > 10 and a > 500:"
    assert [hit.shape for hit in scan_text(inline_sql)] == ["sql-inline"]
    assert [hit.shape for hit in scan_text(multiline_sql)] == ["sql-multiline"]
    assert [hit.shape for hit in scan_text(python_inline)] == ["python-inline"]


def test_gate_ignores_the_canonical_and_unrelated_thresholds() -> None:
    """负控：正典自己、以及别的谓词，不该被这条门禁拦。"""

    assert scan_text('DOUBLE_RED_SQL = "…"\nWHERE {DOUBLE_RED_SQL}') == []
    assert scan_text("if pct > 0 and diff > 10:") == []  # 少一个条件，是单红一族
    assert scan_text("if pct_chg >= 9.8:") == []  # 涨停近似，另一颗


def test_copy_baseline_is_exactly_the_known_files() -> None:
    """棘轮：生产字面复印件基线是空集，新增一个文件就红。

    比文件集合，不比条数——同一文件里挪一处、加一处，条数会变而集合不变；
    真正要拦的是「又多了一个文件在自己写阈值」。空集不是「还没查」，是只减不增的起点。
    """

    found = {hit.path for hit in scan_paths()}
    new = found - BASELINE_COPY_FILES
    gone = BASELINE_COPY_FILES - found
    assert not new, f"新增复印件文件：{sorted(new)}（新代码必须 import 正典）"
    assert not gone, f"基线里的文件已清理，请同步收紧基线：{sorted(gone)}"


def _modules_defining_double_red_thresholds() -> set[str]:
    """AST 扫：哪些模块**自己定义**双红阈值常量（赋值，不是 import）。

    字面扫描抓不到这一类——写的是 `DOUBLE_RED_PCT = 0.0` 而不是 `> 500`。两种复印件
    形状要两个检测器，少一个就会得出「已经没有第二份」的假结论。
    """

    import ast

    found: set[str] = set()
    for root in ("market_feature_store", "intelligence", "evolution", "scripts"):
        base = REPO / root
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            rel = path.relative_to(REPO).as_posix()
            if rel.startswith("intelligence/tests"):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
            for node in tree.body:  # 只看模块级
                if not isinstance(node, ast.Assign):
                    continue
                for target in node.targets:
                    if (
                        isinstance(target, ast.Name)
                        and target.id.startswith("DOUBLE_RED")
                        and isinstance(node.value, ast.Constant)
                        and isinstance(node.value.value, (int, float))
                    ):
                        found.add(rel)
    return found


def test_double_red_thresholds_are_defined_in_exactly_one_module() -> None:
    """第 1 步的收口断言：全仓只有正典自己定义那三个阈值。

    第 1 步之前这里是 2（timeline 另写一份 float）。现在是 1；再出现第二份就红。
    """

    assert _modules_defining_double_red_thresholds() == DOUBLE_RED_THRESHOLD_MODULES


def test_timeline_wrapper_delegates_and_keeps_no_thresholds() -> None:
    """timeline 的 `is_double_red` 必须是薄包装：取字段，判定交给正典。"""

    from intelligence.services import theme_lifecycle_timeline as timeline

    text = (REPO / "intelligence/services/theme_lifecycle_timeline.py").read_text(
        encoding="utf-8"
    )
    assert "is_double_red_row" in text, "包装必须委托正典"
    # 边界随正典收紧：这三例在第 1 步之前判 True / True / raise。
    assert timeline.is_double_red({"pct_chg": "1.5", "diff_ratio": "12", "amount": "900"}) is False
    assert timeline.is_double_red({"pct_chg": True, "diff_ratio": 12.0, "amount": 900.0}) is False
    assert timeline.is_double_red({"pct_chg": "", "diff_ratio": 12.0, "amount": 900.0}) is False
    # 正常数值路径不动——真实库 102,572 行零翻转（scripts/diff_predicate_impls.py）。
    assert timeline.is_double_red({"pct_chg": 1.5, "diff_ratio": 12.0, "amount": 900.0}) is True


def test_generated_sql_and_description_follow_the_constants(monkeypatch) -> None:
    """SQL 串与中文说明书由常量生成，不是各写一份。

    §8-3 要的联动：改正典阈值，下游口径跟着变。这里 patch 后重新生成，
    验证生成式而不是字面量。
    """

    import importlib

    from market_feature_store import signals

    assert signals.DOUBLE_RED_SQL == "pct_chg > 0 AND diff_ratio > 10 AND amount > 500"
    assert "500" in signals.DOUBLE_RED_DESCRIPTION

    monkeypatch.setattr(signals, "DOUBLE_RED_AMOUNT_MIN", 600.0)
    regenerated = (
        f"pct_chg > {signals.DOUBLE_RED_PCT_MIN:g}"
        f" AND diff_ratio > {signals.DOUBLE_RED_DIFF_MIN:g}"
        f" AND amount > {signals.DOUBLE_RED_AMOUNT_MIN:g}"
    )
    assert regenerated == "pct_chg > 0 AND diff_ratio > 10 AND amount > 600"
    monkeypatch.undo()
    importlib.reload(signals)


def test_default_box_regenerates_byte_identical() -> None:
    """§10-2：`default-v1` 从源码再生一次，与提交的那份**字节**一致。

    比字面量，不比个数——清理一行同时新增一行，个数不变而内容已经变了。
    """

    from scripts.generate_default_switch_box import OUTPUT, build_box, render

    assert OUTPUT.exists(), "default-v1 还没生成"
    assert OUTPUT.read_text(encoding="utf-8") == render(build_box())


def test_default_box_freezes_the_function_not_a_tool_list() -> None:
    """盒子里不许出现一份冻结的工具名单。

    本仓授权面逐 frame 解算，冻名单等于冻了一个当天恰好如此的快照。盒子只冻
    派生函数符号 + 非工具行取值；12 颗 capability 只记名字（ambient），取值靠
    每次 run 的 `resolved_capabilities`。
    """

    import json as _json

    from scripts.generate_default_switch_box import OUTPUT

    box = _json.loads(OUTPUT.read_text(encoding="utf-8"))
    assert set(box["ambient_ids"]) == set(_DEFAULT_TOOL_METADATA)
    assert not (set(box["non_tool_defaults"]) & set(_DEFAULT_TOOL_METADATA))
    assert box["capability_source"].endswith("build_episode_context")


def test_default_box_keeps_welded_and_drops_workitems() -> None:
    """两条边界各钉一次，都是踩过的坑。

    `structural-verifier` 关不掉但生产里开着 → **要进**盒子（盒子描述怎么拨的，
    不是描述哪些拧得动）。`predicate.single-red` 正典还不存在 → **不进**，否则
    盒子里会有一个没有对应物的状态位。排除项必须自述理由，否则「短了几行」和
    「本来就这么多」在下游长得一样。
    """

    import json as _json

    from scripts.generate_default_switch_box import OUTPUT

    box = _json.loads(OUTPUT.read_text(encoding="utf-8"))
    assert box["non_tool_defaults"]["structural-verifier"] == "on"
    assert "param.boards-min" in box["excluded"]
    assert "predicate.single-red" in box["non_tool_defaults"]  # 第 2 步后有正典了
    assert "param.boards-min" in box["excluded"]  # 参数不是开关
    assert "predicate.reading-baseline" in box["excluded"]
    assert all(reason.strip() for reason in box["excluded"].values())


def test_default_box_generation_fails_if_source_chain_renamed(monkeypatch) -> None:
    """派生链被改名 → 生成失败，而不是产出一个指向不存在符号的字符串。

    那个字符串会被下一个 agent 当成真的去查——失败是更好的结果。
    """

    from intelligence.services import episode_factory
    from scripts.generate_default_switch_box import resolve_capability_source

    monkeypatch.delattr(episode_factory, "_authorized_capabilities")
    with pytest.raises(AttributeError, match="派生链断了"):
        resolve_capability_source()


def test_runner_refuses_two_deltas() -> None:
    """一次只准拧一颗：两个差量的 run 无法归因，必须拒跑而不是写假收据。"""

    from scripts.run_capability_switchboard import TwoDeltasError, parse_deltas

    assert parse_deltas(["kb_search=off"]).switch_id == "kb_search"
    with pytest.raises(TwoDeltasError):
        parse_deltas(["kb_search=off", "web_search=off"])
    with pytest.raises(TwoDeltasError):
        parse_deltas([])
    with pytest.raises(TwoDeltasError):
        parse_deltas(["kb_search=maybe"])


def test_runner_positive_and_negative_control_on_one_capability() -> None:
    """第 1 步的三条判据，端到端跑一颗真的。

    正控：`offered_schemas` 差集恰好 `kb_search`。
    负控：硬点名调它，必须落 `unknown_or_unauthorized_tool`（`agent_episode.py:395-411`
          追加的 `ProviderTrace(provider="episode:tool_gate")`）。
    底盘：跑完、有收据。

    三条缺一条这步不算过——只看底盘的话，scripted 模型压根不会去碰关掉的工具，
    「没崩」在离线臂恒真。
    """

    from scripts.run_capability_switchboard import (
        DEFAULT_CASES,
        Delta,
        run_switch,
    )
    from scripts.run_episode_seam_ladder import load_cases

    board = load_switchboard()
    case = next(c for c in load_cases(DEFAULT_CASES) if c.case_id == "weekly-market-cause")
    record = run_switch(case, board, board.resolve("kb_search"), Delta("kb_search", "off"))

    assert record["outcome"] == "passed", record
    assert record["positive_control"]["schema_delta"] == ["kb_search"]
    assert record["negative_control"]["ran"] is True
    assert "kb_search" in record["negative_control"]["refused_calls"]
    assert record["chassis_survived"] is True
    # 收据必须自述解算面与派生入口，否则跨题读数不可比。
    assert record["capability_source"].endswith("build_episode_context")
    assert record["baseline_arm"]["resolved_capabilities"]


def test_noop_prompt_mounts_and_is_actually_delivered() -> None:
    """第 3 步：挂一颗零行为零件，正控是「那段说明书真的进了模型的消息流」。

    不是「没崩」——零行为零件天然不会让底盘崩，拿它当判据等于没测。对照臂里必须
    **没有**这段文字，差量臂里必须**有**，两边都要看。
    """

    from scripts.run_capability_switchboard import (
        DEFAULT_CASES,
        Delta,
        NoopPromptClient,
        run_switch,
    )
    from scripts.run_episode_seam_ladder import load_cases

    board = load_switchboard()
    case = next(c for c in load_cases(DEFAULT_CASES) if c.case_id == "weekly-market-cause")
    record = run_switch(case, board, board.resolve("noop-prompt"), Delta("noop-prompt", "on"))

    assert record["outcome"] == "passed", record
    assert record["treated_arm"]["prompt_segment_delivered"] is True
    assert record["baseline_arm"].get("prompt_segment_delivered") is False
    assert board.resolve("noop-prompt").default == "off", "新开关默认必须 off"
    assert NoopPromptClient.SEGMENT  # 段落非空，否则「投递了」无意义


def test_noop_prompt_added_no_branch_to_the_loop() -> None:
    """§10-5：挂零件不许在 loop / 梯子 / Profile 里加产品分支。

    这条用 git 比，不是用眼睛看：往 `agent_episode` 里塞一个 `if switch_on:` 同样能
    让零件「生效」，但那证明的是反面——缝不存在，是被现凿出来的。
    """

    import subprocess

    changed = subprocess.run(
        ["git", "diff", "--name-only", SPEC_BASELINE_REV],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    for guarded in (
        "intelligence/runtime/agent_episode.py",
        "intelligence/runtime/continuous_turn_adapter.py",
        "scripts/run_episode_seam_ladder.py",
        "intelligence/services/research_profile.py",
        "intelligence/services/episode_tools.py",
    ):
        assert guarded not in changed, f"{guarded} 被改了——零件应该挂在已有的缝上"


def _rev_assignment(rel_path: str, name: str, rev: str = SPEC_BASELINE_REV):
    """从指定 revision 的源码里把某个模块级赋值的**字面值**取出来。

    不加载模块——那几个模块互相 import，加载旧版会牵出一整棵旧依赖树。
    这里只做 AST 求值，够用且不产生副作用。
    """

    import ast
    import subprocess

    source = subprocess.run(
        ["git", "show", f"{rev}:{rel_path}"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    for node in ast.parse(source).body:
        # 带类型标注的赋值是 AnnAssign 不是 Assign——只认 Assign 会把
        # `_MARKET_LEVEL_STATE_WORDS: tuple[str, ...] = (...)` 整个漏掉。
        if isinstance(node, ast.AnnAssign):
            target = node.target
            if not (isinstance(target, ast.Name) and target.id == name):
                continue
            value = node.value
        elif isinstance(node, ast.Assign):
            if not any(
                isinstance(item, ast.Name) and item.id == name for item in node.targets
            ):
                continue
            value = node.value
        else:
            continue
        if value is None:
            continue
        # `re.compile(r"..." r"...")` → 取第一个实参的字面量
        if isinstance(value, ast.Call) and value.args:
            return ast.literal_eval(value.args[0])
        return ast.literal_eval(value)
    raise AssertionError(f"{rev} 的 {rel_path} 里找不到 {name}")


def test_routing_term_extensions_are_unchanged_after_sharing_vocabulary() -> None:
    """第 2.5 步 parity：词汇表收口后，四处的**外延一字不变**。

    这一步刻意**不是**「一张单子生成六处」。那六处的外延是故意不同的，至少一处的
    差异在源码注释里写明是有意为之——`query_understanding` 刻意不收「板块」（收了会
    把 theme-research 的问题抢走），而 `evidence_capabilities` 刻意收「板块」（主体词，
    命中后 mainline_context 才有意义）。并成一张单子就是削齐，会改路由。

    共享的是**词汇**（同一个词在四处各写一遍字面），不是列表。所以 parity 断言的是
    每一处仍然等于它改前的那一份。
    """

    from intelligence.services import (
        answer_orchestrator,
        evidence_capabilities,
        market_topic_terms,
        query_understanding,
    )

    assert query_understanding._DATED_MARKET_TOPIC_RE.pattern == _rev_assignment(
        "intelligence/services/query_understanding.py", "_DATED_MARKET_TOPIC_RE"
    )
    assert answer_orchestrator._MARKET_LEVEL_STATE_WORDS == _rev_assignment(
        "intelligence/services/answer_orchestrator.py", "_MARKET_LEVEL_STATE_WORDS"
    )
    assert evidence_capabilities._MARKET_SUBJECT_MARKERS == _rev_assignment(
        "intelligence/services/evidence_capabilities.py", "_MARKET_SUBJECT_MARKERS"
    )
    # 两处的取舍相反，且必须保持相反——这条是「不许削齐」的守卫。
    assert "板块" in evidence_capabilities._MARKET_SUBJECT_MARKERS
    assert "板块" not in market_topic_terms.DATED_MARKET_TOPIC


def test_single_red_canonical_treats_missing_amount_as_neither() -> None:
    """单红正典 + NULL 口径（2026-08-22 定：缺数两边都不算）。

    此前三处各写各的：日报把 NULL 算单红、`ask_blocks` 把 NULL 算双红（还贴
    「真正双红」标签）、矩阵标缺数——同一行数据进互斥两类，都是用户可见输出。
    另两种写法各自隐含一个没依据的假设（「没抓到≈量不大」/「没抓到≈量大」）。
    """

    from market_feature_store import signals

    assert signals.is_single_red(1.5, 12.0, 400.0) is True
    assert signals.is_single_red(1.5, 12.0, 900.0) is False  # 那是双红
    assert signals.is_single_red(-1.5, 12.0, 400.0) is False  # 必须涨
    # 缺数：两边都不算
    assert signals.is_single_red(1.5, 12.0, None) is False
    assert signals.is_double_red(1.5, 12.0, None) is False
    # SQL 侧天然如此：NULL <= 500 求值为 NULL，不成立
    assert "IS NULL" not in signals.SINGLE_RED_SQL


def test_ask_blocks_no_longer_calls_unknown_volume_a_double_red() -> None:
    """成交额缺失时不许再贴「真正双红」，也不许滑到「弱放量修复」。

    后者同样是把不确定说成确定——那句话隐含「量不大」，而这一行恰恰可能是双红。
    """

    from intelligence.services import ask_blocks

    assert ask_blocks._classify_mainline_volume_state(1.5, 12.0, None) == "量价状态待确认（成交额缺失）"
    assert ask_blocks._classify_mainline_volume_state(1.5, 12.0, 900.0) == "真正双红/增量启动"


def test_weighted_strength_declares_its_unit_and_keeps_unknown_unknown() -> None:
    """开根加权正典：amount 单位是亿元；缺值返 None 不返 0。

    返 0 会把「不知道」排成「中性」，与单红那条 NULL 口径同一条纪律。
    """

    from market_feature_store import signals

    assert signals.weighted_strength(2.0, 100.0) == 20.0
    assert signals.weighted_strength(2.0, None) is None
    assert signals.weighted_strength(None, 100.0) is None
    assert signals.weighted_strength(2.0, -5.0) == 0.0  # 负成交额夹到 0，不产生 NaN
    assert "GREATEST" in signals.WEIGHTED_STRENGTH_SQL
    assert signals.weighted_strength_sql() == signals.WEIGHTED_STRENGTH_SQL
    assert (
        signals.weighted_strength_sql("b.amount_yi", "b.pct_chg")
        == "b.pct_chg * sqrt(GREATEST(b.amount_yi, 0))"
    )
    with pytest.raises(ValueError, match="只接受列名"):
        signals.weighted_strength_sql("amount; DROP TABLE x")


def test_agent_and_daily_review_use_weighted_strength_canonical() -> None:
    """§8 第 2 步：进 agent / 日报的调用方改引正典，不再手写 sqrt。"""

    daily = (REPO / "market_feature_store/reports/daily_review.py").read_text(encoding="utf-8")
    market = (REPO / "intelligence/adapters/market.py").read_text(encoding="utf-8")
    assert "sqrt(b.amount_yi) * b.pct_chg" not in daily
    assert "sqrt(d.amount) * d.pct_chg" not in daily
    assert "sqrt(amount) * pct_chg" not in market
    assert "WEIGHTED_STRENGTH_SQL" in market


def test_strategy_sql_interpolates_canonical_as_fstring() -> None:
    """f 前缀必须在引号前。贴到 GROUP BY 1 后面，DuckDB 会吃到字面 `{DOUBLE_RED_SQL}`。"""

    files = (
        "evolution/strategy4.py",
        "scripts/backfill_strategy3_touch_matrix.py",
        "scripts/render_strategy4_dual_engine_matrix.py",
    )
    for rel in files:
        text = (REPO / rel).read_text(encoding="utf-8")
        assert "GROUP BY 1f" not in text, rel
        assert "WHERE {DOUBLE_RED_SQL} GROUP BY 1" in text, rel
        assert 'con.execute(f"""' in text, rel


def test_unwired_arithmetic_predicates_do_not_get_a_checkmark() -> None:
    """没接到 faces() 的算数面，既不进臂也不进 runner 接线名单。"""

    from intelligence.services.capability_switchboard import load_switchboard
    from intelligence.services.predicate_faces import wired_predicate_ids

    arm = set(load_switchboard().arm_ids())
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
    assert "predicate.dated-market-topic" in wired


def test_predicate_off_changes_every_declared_face() -> None:
    """正控：声明的每一面都要变。说明书拿真宪法正文，不另造样例。"""

    from intelligence.services import predicate_faces
    from intelligence.services.predicate_faces import OWNERSHIP

    methodology = (REPO / "intelligence/foresight_methodology.md").read_text(encoding="utf-8")
    lines = tuple(methodology.splitlines())
    owner = OWNERSHIP["predicate.double-red"]
    for marker in owner.prose_markers:
        assert any(marker in line for line in lines), f"宪法不再含说明书标记 {marker!r}"

    on = predicate_faces.faces()
    off = predicate_faces.faces({"predicate.double-red"})

    assert on.counts_double_red() is True
    assert off.counts_double_red() is False
    assert "双红" in on.route_alternation()
    assert "双红" not in off.route_alternation()
    assert "涨停" in off.route_alternation(), "只摘它名下的词，不许连坐"
    filtered = off.prose_lines(lines)
    assert filtered != lines
    assert not any("双红定义" in line for line in filtered)
    assert on.route_alternation() == market_topic_terms_alternation()


def market_topic_terms_alternation() -> str:
    from intelligence.services import market_topic_terms

    return market_topic_terms.as_alternation(market_topic_terms.DATED_MARKET_TOPIC)


def test_methodology_prose_still_matches_the_canonical_sql() -> None:
    """§7.2 漂移测试：思考宪法里手抄的那条 SQL 必须等于正典当前字面。

    第一期允许宪法仍是人维护的复印件，但改了正典而忘了改宪法 → 这条红。
    模型读的是宪法，不是 `signals.py`；两者一旦不一致，模型背的就是过期口径。
    """

    from market_feature_store.signals import DOUBLE_RED_SQL

    text = (REPO / "intelligence/foresight_methodology.md").read_text(encoding="utf-8")
    assert DOUBLE_RED_SQL in text, (
        "宪法里的双红公式与正典不一致——改了 signals 就要同步改宪法，"
        "或者把那一行改成生成的（§7.2：生成优于手抄）"
    )


def test_params_json_double_red_agrees_with_canonical() -> None:
    """`params.json` 保留自己的三个数，但必须与正典一致。

    为什么不改成从 signals 导出：那三个数是**版本化的实验输入**（`version` +
    `params_history.md`，`strategy1` 把 `params_version` 落进产出），导出会切断
    历史回测记录里 params_version ↔ 实际阈值的对应关系，旧结论从此不可复现。
    所以用一致性断言，不用单一真本源——不等就红，要么改参数、要么在
    `params_history.md` 里显式声明这是有意的实验偏移。
    """

    from market_feature_store import signals

    params = json.loads((REPO / "evolution/params.json").read_text(encoding="utf-8"))
    double_red = params["strategy1"]["double_red"]
    assert float(double_red["pct_chg_min"]) == signals.DOUBLE_RED_PCT_MIN
    assert float(double_red["diff_ratio_min"]) == signals.DOUBLE_RED_DIFF_MIN
    assert float(double_red["amount_min"]) == signals.DOUBLE_RED_AMOUNT_MIN


def test_gate_self_check_on_pre_cut_daily_review() -> None:
    """门禁对改前 daily_review 必须抓到 ≥4 处。检法瞎会把「干净」和「看不见」合成 0。"""

    import subprocess

    text = subprocess.check_output(
        ["git", "show", f"{SPEC_BASELINE_REV}:market_feature_store/reports/daily_review.py"],
        cwd=str(REPO),
        text=True,
    )
    hits = scan_text(text, path="daily_review.py")
    assert len(hits) >= 4, f"改前 daily_review 应至少 4 处复印件，实际 {len(hits)}"
    shapes = {hit.shape for hit in hits}
    assert "sql-multiline" in shapes
    assert "python-inline" in shapes


def test_prefetch_bind_params_follow_module_constants(monkeypatch) -> None:
    """§8 第 1 步之 3：改正典阈值，prefetch 绑参跟着变。"""

    from datetime import date

    from intelligence.services import asof_prefetch as ap

    seen: list[tuple[str, object]] = []

    class Fake:
        def execute(self, sql: str, params: object = None):
            seen.append((sql, params))
            return self

        def fetchone(self):
            sql = seen[-1][0]
            if "pct_chg" in sql:
                return (3,)
            return (1,)

    monkeypatch.setattr(ap, "DOUBLE_RED_AMOUNT_MIN", 99999.0)
    counts = ap.dual_red_counts(Fake(), (date(2026, 7, 23),))
    binds = [params for _, params in seen if isinstance(params, list) and len(params) == 4]
    assert binds, "预取没有绑三阈值"
    assert binds[-1][3] == 99999.0
    assert counts["2026-07-23"] == "3"


def test_candidate_cases_are_not_evidence_free() -> None:
    """开关板 §6.3：候选题必须对账 `_is_evidence_free_task`，且本期全是 false。"""

    from intelligence.services.episode_factory import _is_evidence_free_task
    from scripts.run_capability_switchboard import DEFAULT_CASES
    from scripts.run_episode_seam_ladder import load_cases, resolve_control

    raw = json.loads(
        (REPO / "intelligence/eval/fixtures/capability_switchboard.json").read_text(
            encoding="utf-8"
        )
    )
    recorded = raw["candidate_cases"]
    assert recorded, "第 0 步必须把候选题的 evidence-free 判定写进夹具"
    cases = {case.case_id: case for case in load_cases(DEFAULT_CASES)}
    for item in recorded:
        control = resolve_control(cases[item["id"]])
        actual = _is_evidence_free_task(control.task_frame)
        assert actual is item["evidence_free"], item["id"]
        assert actual is False, f"{item['id']} 是 evidence-free，关 capability 是空操作"


def test_l3_lookup_cannot_be_recorded_on_when_env_off(monkeypatch) -> None:
    """§5.2：env 关着时不许把 l3_lookup 记成 on。"""

    monkeypatch.delenv("FINANCE_L3_LOOKUP_ENABLED", raising=False)
    from scripts.generate_default_switch_box import _reject_l3_on_when_env_off, build_box

    with pytest.raises(ValueError, match="不许把 l3_lookup 记成 on"):
        _reject_l3_on_when_env_off({"l3_lookup": "on"})
    # 生产默认是 ambient，env 关着也不该让整盒生成失败。
    box = build_box()
    assert "l3_lookup" in box["ambient_ids"]
    assert "l3_lookup" not in box["non_tool_defaults"]


def test_declared_faces_reach_prefetch_route_and_methodology() -> None:
    """第 3 步接线：runner 注入的 disabled 集合必须打到生产三缝，不只打到 faces 模块。"""

    from datetime import date

    from intelligence.services import asof_prefetch as ap
    from intelligence.services.foresight import ForesightOptions, load_methodology
    from intelligence.services.predicate_faces import using
    from intelligence.services.query_understanding import (
        is_dated_market_review,
        understand_query,
    )

    dual_query = "2026-07-23 哪些板块是双红"
    limit_query = "2026-07-23 涨停集中在哪些题材"
    assert is_dated_market_review(dual_query, understand_query(dual_query))
    assert is_dated_market_review(limit_query, understand_query(limit_query))
    on_text, _, _ = load_methodology(ForesightOptions())
    assert "双红定义" in on_text

    with using({"predicate.double-red"}):
        assert ap.dual_red_counts(object(), (date(2026, 7, 23),)) == {}
        assert not is_dated_market_review(dual_query, understand_query(dual_query))
        assert is_dated_market_review(limit_query, understand_query(limit_query))
        off_text, _, _ = load_methodology(ForesightOptions())
    assert "双红定义" not in off_text
    assert "双红题材边际量" not in off_text
    assert "双红题材首日" not in off_text


def _align_surface(**overrides: object) -> dict:
    case = {
        "id": "next-session-index",
        "question_type": "market_forecast",
        "subject": "A股市场",
        "dated_market_review": False,
        "capabilities": ["market_data"],
        "allowed_capabilities": ["market_data"],
        "mandatory_capabilities": ["market_data"],
        "prefetch": [{"title": "双红个数序列", "detail_sha": "abc"}],
        "dual_red_counts": {"2026-08-07": "32"},
    }
    case.update({k: v for k, v in overrides.items() if k in case or k == "id"})
    return {
        "db_connected": True,
        "db_path": "db",
        "double_red_sql": "pct_chg > 0 AND diff_ratio > 10 AND amount > 500",
        "methodology_sha": "same",
        "methodology_chars": 4420,
        "cases": [case],
    }


def test_default_box_diff_is_empty_when_surfaces_match() -> None:
    from scripts.align_default_box_quality import _diff

    left = _align_surface()
    assert _diff(left, _align_surface()) == []


def test_default_box_diff_fails_closed_when_db_missing() -> None:
    from scripts.align_default_box_quality import _diff

    treated = _align_surface()
    treated["db_connected"] = False
    gaps = _diff(treated, _align_surface())
    assert any(item.startswith("db not connected") for item in gaps)


def test_default_box_diff_flags_prefetch_and_route_drift() -> None:
    from scripts.align_default_box_quality import _diff

    gaps = _diff(
        _align_surface(prefetch=[], question_type="market_watch"),
        _align_surface(),
    )
    assert any(item.startswith("next-session-index.prefetch") for item in gaps)
    assert any(item.startswith("next-session-index.question_type") for item in gaps)
