"""能力升级三处「接线」的回归锁。

三条缺口的共同形状：**能力已实现、默认入口已到达，但把它接到真实运行条件上的那一段
断掉了**，而断掉时全部静默——没有异常、没有降级日志，只有一个看起来合理的贫瘠答案。
所以这里锁的不是「函数算得对不对」，是「真实身份 / 真实库根 / 真实题面到不到得了它」。

- ``_market_db_path``：引擎 A 的盘面库此前写死 ``finance_root/db/…``，从不看
  ``MARKET_FEATURE_STORE_DB``；补数落到非默认库根后，恢复出的 run 照样读旧库。
- ``ResearchToolRegistry.calc_loader``：``inputs_from_calc``（改假设重算）此前按
  ``FORESIGHT_USER`` 找上一轮的计算记录，只在「生产恰好钉了单一身份」时碰巧落对人。
- ``decide_turn`` 的反问闸：题面自带的回指（「用中报说明**这条链**兑现到哪一层」）被
  按词面判成跨轮追问，整题落 clarify 车道，引擎 A 一次都不接手。
"""

from __future__ import annotations

import json
from pathlib import Path

from intelligence.services import episode_tools
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_tools import build_episode_registry
from intelligence.services.task_frame import TaskFrame
from intelligence.services.turn_controller import decide_turn


def _frame() -> TaskFrame:
    return TaskFrame(
        raw_question="瑞华泰是否已有量产订单",
        user_goal="核验公司端兑现",
        question_type="stock_deep_dive",
        subject="瑞华泰",
        subject_kind="company",
        market_scope="A股",
        timeframe="最近30日",
        required_outputs=("direct_assessment", "evidence_boundary"),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="company_official_evidence",
        confidence=0.95,
    )


def _context(task_id: str = "wiring-closeout"):
    # task_id 必须逐次不同：根预算按 episode 在进程内预占，同名复用会直接抛
    # （``research_contract`` 的「副作用前预占」设计，不是测试夹具的毛病）。
    return build_episode_context(
        _frame(),
        task_id=task_id,
        capabilities=("market_data",),
        timeout=30.0,
    )


# --------------------------------------------------------------- 08 · 库根解析


def test_market_db_path_honours_the_env_var_when_no_root_is_named(monkeypatch, tmp_path):
    """没人点名 finance_root 时，库根必须走 canonical 解析器（含环境变量）。

    旧实现返回 ``data_root/db/market_feature_store.duckdb``，把 ``MARKET_FEATURE_STORE_DB``
    整个忽略掉——这正是「补齐后重问仍 rows=0」的成因。
    """

    backfilled = tmp_path / "staging" / "market_feature_store.duckdb"
    backfilled.parent.mkdir(parents=True)
    backfilled.write_bytes(b"")
    monkeypatch.setenv("MARKET_FEATURE_STORE_DB", str(backfilled))

    assert episode_tools._market_db_path(None, tmp_path / "finance", None) == backfilled


def test_named_finance_root_still_beats_the_env_var(monkeypatch, tmp_path):
    """调用方点名了树，就用那棵树——显式参数压过环境变量，隔离跑批才可控。"""

    monkeypatch.setenv("MARKET_FEATURE_STORE_DB", str(tmp_path / "elsewhere.duckdb"))
    named = tmp_path / "named-tree"

    assert episode_tools._market_db_path(named, named, None) == (
        named / "db" / "market_feature_store.duckdb"
    )


def test_sealed_fixture_cannot_be_escaped_by_the_env_var(monkeypatch, tmp_path):
    """封存夹具压过一切：评测不允许被环境变量改掉读的是哪份库。"""

    monkeypatch.setenv("MARKET_FEATURE_STORE_DB", str(tmp_path / "elsewhere.duckdb"))
    sealed = tmp_path / "sealed.duckdb"
    policy = episode_tools.SealedFixturePolicy(market_db_path=sealed)

    assert episode_tools._market_db_path(None, tmp_path, policy) == sealed


def test_registry_reads_the_env_pointed_database(monkeypatch, tmp_path):
    """端到端：装配层真的把环境变量解析出的库路径递给了盘面取数。"""

    pointed = tmp_path / "pointed.duckdb"
    monkeypatch.setenv("MARKET_FEATURE_STORE_DB", str(pointed))
    seen: dict[str, object] = {}

    def capture(path, **_kwargs):
        seen["market_db"] = Path(path)
        return "2026-09-07"

    monkeypatch.setattr(episode_tools.ask_blocks, "_market_data_asof", capture)
    build_episode_registry(_frame(), _context(), knowledge_wiki=tmp_path / "wiki")

    assert seen["market_db"] == pointed


# ------------------------------------------------------- 04 · 计算记录的用户路径


def _write_calc_record(runs_root: Path, calc_id: str, marker: str) -> None:
    run_dir = runs_root / "run_20260911_000001"
    run_dir.mkdir(parents=True)
    (run_dir / f"calc-{calc_id}.json").write_text(
        json.dumps({"calc_id": calc_id, "script": marker, "params": {}, "inputs": []}),
        encoding="utf-8",
    )


def test_calc_loader_follows_the_turn_owner_not_the_env_identity(monkeypatch, tmp_path):
    """A 的 episode 读 A 的计算记录，即使 ``FORESIGHT_USER`` 指着 B。

    旧实现走 ``RunStore()`` 的环境解析：单用户生产下碰巧对，多身份下要么找不到
    （``BASE_CALC_NOT_FOUND``），要么把 B 的计算记录喂进 A 的回合。
    """

    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("FORESIGHT_USER", "userB")
    calc_id = "a" * 16
    _write_calc_record(tmp_path / "users" / "userA" / "runs", calc_id, "A的脚本")
    _write_calc_record(tmp_path / "users" / "userB" / "runs", calc_id, "B的脚本")

    loader = episode_tools._calc_loader_for("userA")

    assert loader is not None
    record = loader(calc_id)
    assert record is not None
    assert record["script"] == "A的脚本"


def test_registry_carries_the_calc_loader_into_the_episode(monkeypatch, tmp_path):
    """身份穿透到装配产物为止——episode 层只转交，所以断言必须落在这里。

    与 ``memory_lookup`` 同一条经验：授权与身份穿透必须成对出现，只做一半不报错。
    """

    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setattr(
        episode_tools.ask_blocks, "_market_data_asof", lambda *_a, **_k: "2026-09-07"
    )

    with_identity = build_episode_registry(
        _frame(),
        _context("wiring-closeout-identity"),
        knowledge_wiki=tmp_path / "wiki",
        memory_user="userA",
    )
    without_identity = build_episode_registry(
        _frame(),
        _context("wiring-closeout-anonymous"),
        knowledge_wiki=tmp_path / "wiki",
    )

    assert with_identity.calc_loader is not None
    # 没有身份时留 None 而不是硬造一个：那是「调用方没给」的如实陈述，
    # 行为与接线前逐字节一致。
    assert without_identity.calc_loader is None
    # 加挂 episode 期工具 / 裁掉子研究工具都不许把身份弄丢。
    assert with_identity.without("sub_research").calc_loader is not None


# --------------------------------------------------------------- B7 · 反问闸


def _clarifies(query: str) -> bool:
    decision = decide_turn(query, previous_intent=None)
    return decision.lane == "clarify"


def test_question_carrying_its_own_subject_is_not_bounced_back(monkeypatch):
    """题面自己建立了主体，「这条链」就是题内回指，不该被当成跨轮追问。

    被挡住时 run 里连 ``continuous-episode.json`` 都不会有——深题读数量到的是
    「被门挡住」，不是研究能力。
    """

    assert not _clarifies(
        "英伟达 GB300 / 超节点机柜的液冷渗透率提升，会传导到 A 股哪些环节？"
        "请按『环节 → 代表公司 → 兑现路径』列出来，"
        "并用 2026 年中报数据说明这条链目前兑现到了哪一层。"
    )


def test_question_carrying_an_entity_anchor_is_not_bounced_back():
    assert not _clarifies(
        "从中际旭创、新易盛 2026 年中报的高增长出发，光模块景气会向上游哪些环节传导？"
        "请用 2026-09-07 的板块严格双红数据验证市场是否已经在交易这条链。"
    )


def test_question_carrying_an_explicit_date_is_not_bounced_back():
    assert not _clarifies(
        "接着 09-02 那次复盘，用 2026-09-07 收盘数据更新："
        "哪些变了（给前后两个数）、哪些没变、新出现了什么，最后给下一步要看的两个点。"
    )


def test_a_bare_follow_up_with_no_foothold_still_asks():
    """真追问仍要反问——放开的是「题面自带落点」，不是这道闸本身。

    三项落点（主体 / 实体锚 / 明确日期）全空才反问；这三句正是全空的样子。
    """

    assert _clarifies("那它的毛利率呢？")
    assert _clarifies("这条链呢？")
    assert _clarifies("接着上次继续。")
