"""板块披露扫描包：宇宙 JOIN、分层、预算、空窗合并。CI 不打真网、不连生产库。"""

from __future__ import annotations

from pathlib import Path

import duckdb

from intelligence.services.ask import (
    bind_disclosure_scan_pack,
    prepare_disclosure_residual_answer,
)
from intelligence.services.ask_types import AskOptions
from intelligence.services.disclosure_scan_pack import (
    APPENDIX_KEYWORDS,
    DISCLOSURE_RESIDUAL_CONTRACT,
    MAX_PAGES,
    RESIDUAL_TRUNCATION_NOTICE,
    classify_title,
    disclosure_scan_degrade_codes,
    gate_disclosure_residual,
    is_disclosure_scan_query,
    merge_disclosure_into_public_answer,
    parse_disclosure_buckets,
    run_disclosure_scan_pack,
    strip_em,
)
from intelligence.services.route_table import route_by_id
from intelligence.services.turn_controller import decide_turn

FROZEN = "医药和科技板块有哪些个股有比较利好的公告"
AS_OF = "2026-08-25"
UNIVERSE_DATE = "2026-08-24"

ANNOUNCEMENTS = (
    {
        "secCode": "600276",
        "secName": "恒瑞医药",
        "announcementTitle": "关于获得药品注册批准的公告",
        "announcementId": "hr-reg-0821",
        "orgId": "gssh0600276",
        "announcementTime": "2026-08-21",
    },
    {
        "secCode": "002693",
        "secName": "双成药业",
        "announcementTitle": "关于获得注射用硫酸多黏菌素B药品注册证书的公告",
        "announcementId": "sc-reg-0822",
        "orgId": "gssz0002693",
        "announcementTime": "2026-08-22",
    },
    {
        "secCode": "000756",
        "secName": "新华制药",
        "announcementTitle": "关于达格列净片获得药品注册证书的公告",
        "announcementId": "xh-reg-0822",
        "orgId": "gssz0000756",
        "announcementTime": "2026-08-22",
    },
    {
        "secCode": "300687",
        "secName": "赛意信息",
        "announcementTitle": "关于签订高性能算力服务销售合同的公告",
        "announcementId": "sy-order-0820",
        "orgId": "gssz0300687",
        "announcementTime": "2026-08-20",
    },
    {
        "secCode": "300504",
        "secName": "天邑股份",
        "announcementTitle": "关于收到中选通知书的公告",
        "announcementId": "ty-win-0824",
        "orgId": "gssz0300504",
        "announcementTime": "2026-08-24",
    },
    {
        "secCode": "603296",
        "secName": "华勤技术",
        "announcementTitle": "关于回购进展的公告",
        "announcementId": "hq-buyback-0823",
        "orgId": "gssh0603296",
        "announcementTime": "2026-08-23",
    },
    {
        "secCode": "000938",
        "secName": "中关村",
        "announcementTitle": "关于国家集采中选的公告",
        "announcementId": "zgc-collect-0822",
        "orgId": "gssz0000938",
        "announcementTime": "2026-08-22",
    },
    {
        "secCode": "600812",
        "secName": "华北制药",
        "announcementTitle": "关于获得药物临床试验批准通知书的公告",
        "announcementId": "hb-ind-0821",
        "orgId": "gssh0600812",
        "announcementTime": "2026-08-21",
    },
    {
        "secCode": "600812",
        "secName": "华北制药",
        "announcementTitle": "关于撤回药品注册申请的公告",
        "announcementId": "hb-neg-0823",
        "orgId": "gssh0600812",
        "announcementTime": "2026-08-23",
    },
    {
        "secCode": "601089",
        "secName": "增持药",
        "announcementTitle": "关于控股股东增持股份的公告",
        "announcementId": "hold-0822",
        "orgId": "gssh0601089",
        "announcementTime": "2026-08-22",
    },
    {
        "secCode": "600000",
        "secName": "浦发银行",
        "announcementTitle": "关于获批设立全资子公司的公告",
        "announcementId": "unclass-0822",
        "orgId": "gssh0600000",
        "announcementTime": "2026-08-22",
    },
)


def _no_llm(_messages: list[dict[str, str]]):
    return None, None, "fixture unavailable"


def _db(tmp_path: Path) -> Path:
    path = tmp_path / "disclosure.duckdb"
    con = duckdb.connect(str(path))
    con.execute(
        """
        create table fact_sector_stock_daily(
          trade_date date,
          stock_ts_code varchar,
          stock_name varchar,
          sector_name varchar
        )
        """
    )
    con.execute(
        """
        insert into fact_sector_stock_daily values
          ('2026-08-24', '600276.SH', '恒瑞医药', '生物制药'),
          ('2026-08-24', '002693.SZ', '双成药业', '生物制药'),
          ('2026-08-24', '000756.SZ', '新华制药', '医药'),
          ('2026-08-24', '300687.SZ', '赛意信息', '软件服务'),
          ('2026-08-24', '300504.SZ', '天邑股份', '通信设备'),
          ('2026-08-24', '603296.SH', '华勤技术', '消费电子'),
          ('2026-08-24', '000938.SZ', '中关村', '计算机'),
          ('2026-08-24', '600812.SH', '华北制药', '医药'),
          ('2026-08-24', '601089.SH', '增持药', '医药'),
          ('2026-08-24', '600000.SH', '浦发银行', '电子'),
          ('2026-08-24', '000001.SZ', '电子专属', '电子'),
          ('2026-08-24', '000002.SZ', '计算机专属', '计算机'),
          ('2026-08-24', '688001.SH', '芯片概念', '芯片')
        """
    )
    con.close()
    return path


def _fetch_from_fixture(*, keyword: str, se_date: str, page_num: int, **_kwargs):
    from intelligence.services.disclosure_scan_pack import CninfoPage, PAGE_SIZE

    if page_num > MAX_PAGES:
        raise AssertionError(f"page {page_num} must never be requested")
    matched = [item for item in ANNOUNCEMENTS if keyword in strip_em(item["announcementTitle"])]
    start = (page_num - 1) * PAGE_SIZE
    chunk = matched[start : start + PAGE_SIZE]
    return CninfoPage(tuple(chunk), len(matched))


def _run(tmp_path: Path, query: str = FROZEN, **kwargs):
    market_db_path = kwargs.pop("market_db_path", None)
    if market_db_path is None:
        market_db_path = _db(tmp_path)
    return run_disclosure_scan_pack(
        query,
        as_of=kwargs.pop("as_of", AS_OF),
        market_db_path=market_db_path,
        cninfo_fetch=kwargs.pop("cninfo_fetch", _fetch_from_fixture),
        sleep_fn=kwargs.pop("sleep_fn", lambda _seconds: None),
        **kwargs,
    )


def test_g1_frozen_question_routes_to_disclosure_scan() -> None:
    decision = decide_turn(FROZEN, llm_complete=_no_llm)
    assert decision.question_type == "disclosure_scan"
    assert decision.lane == "research"
    assert decision.turn_intent is not None
    assert decision.turn_intent.answer_owner is None
    assert "news_search" not in decision.capabilities
    assert "market_news" not in decision.capabilities
    assert "web_search" not in decision.capabilities


def test_g1_regressions_keep_old_seats() -> None:
    news = decide_turn("宁德时代最新公告有什么影响", llm_complete=_no_llm)
    theme = decide_turn("固态电池这个题材还能不能追", llm_complete=_no_llm)
    watch = decide_turn("今天市场怎么样", llm_complete=_no_llm)
    assert news.question_type == "news_impact"
    assert theme.question_type == "theme_analysis"
    assert watch.question_type == "market_watch"


def test_g2_route_row_locks_empty_capabilities() -> None:
    row = route_by_id("disclosure_scan")
    assert row is not None
    assert row.lane == "research"
    assert row.answer_owner is None
    assert row.needs_retrieval is True
    assert row.needs_template is True
    assert row.capabilities == ()
    assert "news_search" not in row.capabilities


def test_detector_requires_sector_disclosure_and_roster() -> None:
    assert is_disclosure_scan_query(FROZEN)
    assert is_disclosure_scan_query("最近医药有哪些公司出了利好公告")
    assert is_disclosure_scan_query("电子板块近一周中标或合同公告有哪些")
    assert not is_disclosure_scan_query("宁德时代最新公告有什么影响")
    assert not is_disclosure_scan_query("固态电池这个题材还能不能追")
    assert not is_disclosure_scan_query("今天市场怎么样")


def test_g3_g4_g5_g6_gold_rows(tmp_path: Path) -> None:
    pack = _run(tmp_path)
    assert pack.status == "hit"
    assert pack.universe_date == UNIVERSE_DATE
    text = pack.render()
    assert any(row.code == "600276" and row.tier == "L_reg" for row in pack.rows)
    assert "600276" in text
    assert "药品注册批准" in text
    tech_rows = [row for row in pack.rows if "科技" in row.buckets]
    assert any(row.code == "300687" and row.tier == "L_order" for row in tech_rows)
    assert "注册获批" not in "".join(
        row.title for row in tech_rows if row.code == "300687"
    )
    buybacks = [row for row in pack.excluded if row.tier == "L_buyback"]
    holds = [row for row in pack.excluded if row.tier == "L_hold"]
    collects = [row for row in pack.excluded if row.tier == "L_collect"]
    assert any(row.code == "603296" for row in buybacks)
    assert any(row.tier == "L_hold" for row in holds)
    assert any(row.code == "000938" for row in collects)
    assert not any(row.code == "603296" for row in pack.rows)
    bucket_names = {bucket.name for bucket in pack.buckets}
    assert bucket_names == {"医药", "科技"}
    assert all(bucket.universe_size > 0 for bucket in pack.buckets)
    assert any(row.code == "600812" and row.tier == "L_ind" for row in pack.rows)
    assert any(row.code == "600812" and row.tier == "L_neg" for row in pack.counter_rows)
    assert "反证" in text
    assert "600812" in text
    assert pack.se_date_start == "2026-08-20"
    assert pack.se_date_end == "2026-08-25"


def test_g8_appendix_budget_does_not_mark_roster_partial(tmp_path: Path) -> None:
    state = {"elapsed": 0.0}

    def clock() -> float:
        return state["elapsed"]

    def fetch(*, keyword: str, se_date: str, page_num: int, **kwargs):
        page = _fetch_from_fixture(
            keyword=keyword, se_date=se_date, page_num=page_num, **kwargs
        )
        if keyword == APPENDIX_KEYWORDS[1]:
            state["elapsed"] = 46.0
        return page

    pack = _run(tmp_path, cninfo_fetch=fetch, clock=clock)
    assert pack.status == "hit"
    assert pack.budget_hit is True
    traces = {trace.keyword: trace.status for trace in pack.keyword_traces}
    assert traces[APPENDIX_KEYWORDS[2]] == "skipped_budget"
    assert traces[APPENDIX_KEYWORDS[1]] == "ok"
    assert any(row.code == "600276" for row in pack.rows)
    rendered = pack.render()
    assert "查询未跑完" not in rendered
    assert "附录" in rendered
    assert "disclosure_scan_pack_partial" not in disclosure_scan_degrade_codes(pack)


def test_registration_acceptance_is_not_l_reg() -> None:
    assert classify_title("关于获得药品注册批准的公告") == "L_reg"
    assert classify_title("关于获得注射用硫酸多黏菌素B药品注册证书的公告") == "L_reg"
    assert classify_title("关于公司收到药品注册受理通知书的公告") == "unclassified"
    assert classify_title("关于医疗器械注册受理的公告") == "unclassified"


def test_excluded_public_render_caps_buybacks(tmp_path: Path) -> None:
    from intelligence.services.disclosure_scan_pack import CninfoPage

    def fetch(*, keyword: str, se_date: str, page_num: int, **_kwargs):
        if keyword != "回购":
            return _fetch_from_fixture(
                keyword=keyword, se_date=se_date, page_num=page_num
            )
        rows = tuple(
            {
                "secCode": "603296",
                "secName": "华勤技术",
                "announcementTitle": f"关于回购进展的公告{i}",
                "announcementId": f"hq-buyback-{i:02d}",
                "orgId": "gssh0603296",
                "announcementTime": "2026-08-23",
            }
            for i in range(10)
        )
        return CninfoPage(rows, 10)

    pack = _run(tmp_path, cninfo_fetch=fetch)
    buybacks = [row for row in pack.excluded if row.tier == "L_buyback"]
    assert len(buybacks) == 10
    rendered = pack.render()
    assert rendered.count("【回购（资本运作备考）】") == 3
    assert "另 7 条" in rendered
    assert "hq-buyback-09" not in rendered


def test_g9_unclassified_stays_in_excluded(tmp_path: Path) -> None:
    pack = _run(tmp_path)
    unclass = [row for row in pack.excluded if row.tier == "unclassified"]
    assert any(row.announcement_id == "unclass-0822" for row in unclass)
    assert not any(row.announcement_id == "unclass-0822" for row in pack.rows)


def test_g7_empty_window_still_merges_and_lights_gap(tmp_path: Path) -> None:
    def empty_fetch(**_kwargs):
        from intelligence.services.disclosure_scan_pack import CninfoPage

        return CninfoPage((), 0)

    pack = _run(tmp_path, cninfo_fetch=empty_fetch)
    assert pack.status == "empty"
    rendered = pack.render()
    assert "2026-08-20~2026-08-25" in rendered
    assert "成分股" in rendered or "宇宙" in rendered
    merged = merge_disclosure_into_public_answer("模型草稿", pack)
    assert rendered in merged
    assert "模型草稿" in merged
    codes = disclosure_scan_degrade_codes(pack)
    assert "disclosure_scan_pack_empty" in codes
    assert any(code.startswith("disclosure_scan_bucket_empty:") for code in codes)


def test_as_of_does_not_take_future_constituents(tmp_path: Path) -> None:
    db = _db(tmp_path)
    con = duckdb.connect(str(db))
    con.execute(
        "insert into fact_sector_stock_daily values "
        "('2026-08-25', '999999.SH', '未来股', '生物制药')"
    )
    con.close()
    pack = _run(tmp_path, market_db_path=db, as_of="2026-08-24")
    assert pack.universe_date == "2026-08-24"
    assert "999999" not in {row.code for row in pack.rows}
    assert "999999" not in {
        code for bucket in pack.buckets for code in bucket.hit_codes
    }


def test_exact_electronics_is_single_sector_not_tech_union(tmp_path: Path) -> None:
    query = "电子板块近一周中标或合同公告有哪些"
    buckets = parse_disclosure_buckets(query)
    assert [bucket.name for bucket in buckets] == ["电子"]
    assert buckets[0].sector_names == ("电子",)
    pack = _run(tmp_path, query=query)
    names = {bucket.name: bucket.sector_names for bucket in pack.buckets}
    assert list(names) == ["电子"]
    assert "计算机" not in names["电子"]
    assert "芯片" not in names["电子"]


def test_chip_concept_is_not_default_tech_universe() -> None:
    buckets = parse_disclosure_buckets("科技板块有哪些个股有公告")
    assert buckets[0].name == "科技"
    assert "芯片" not in buckets[0].sector_names


def test_strip_em_before_classify() -> None:
    assert classify_title("关于获得<em>药品注册批准</em>的公告") == "L_reg"
    assert strip_em("关于<em>回购</em>进展") == "关于回购进展"


def test_page_four_is_never_requested(tmp_path: Path) -> None:
    seen: list[int] = []

    def fetch(*, keyword: str, se_date: str, page_num: int, **_kwargs):
        from intelligence.services.disclosure_scan_pack import CninfoPage, PAGE_SIZE

        seen.append(page_num)
        if page_num > MAX_PAGES:
            raise AssertionError("page 4")
        rows = tuple(
            {
                "secCode": "600276",
                "secName": "恒瑞医药",
                "announcementTitle": f"药品注册批准第{page_num}页",
                "announcementId": f"page-{keyword}-{page_num}",
                "orgId": "x",
                "announcementTime": "2026-08-21",
            }
            for _ in range(PAGE_SIZE)
        )
        return CninfoPage(rows, 400)

    pack = _run(tmp_path, query="医药板块有哪些个股有获批公告", cninfo_fetch=fetch)
    assert max(seen) == MAX_PAGES
    assert any(trace.truncated for trace in pack.keyword_traces)
    assert pack.status == "partial"


def test_szse_only_column(tmp_path: Path) -> None:
    columns: list[str] = []

    def fetch(*, keyword: str, se_date: str, page_num: int, column: str = "", **_kwargs):
        columns.append(column)
        return _fetch_from_fixture(
            keyword=keyword, se_date=se_date, page_num=page_num, column=column
        )

    _run(tmp_path, cninfo_fetch=fetch)
    assert columns
    assert set(columns) == {"szse"}


def test_bind_opens_compose_only_on_hit(tmp_path: Path) -> None:
    """P1-① 行为反转（计划 §4 点名）：hit+有行保留调用方 compose，其余仍锁死。"""

    db_path = _db(tmp_path)
    options = AskOptions(
        query=FROZEN,
        market_db_path=db_path,
        date=AS_OF,
        compose=True,
        synthesize=True,
    )
    bound = bind_disclosure_scan_pack(
        options,
        cninfo_fetch=_fetch_from_fixture,
        sleep_fn=lambda _seconds: None,
    )
    assert bound.disclosure_scan_pack is not None
    assert bound.disclosure_scan_pack.status == "hit"
    assert bound.compose is True
    assert bound.synthesize is True
    caller_off = AskOptions(
        query=FROZEN,
        market_db_path=db_path,
        date=AS_OF,
        compose=False,
        synthesize=False,
    )
    off = bind_disclosure_scan_pack(
        caller_off,
        cninfo_fetch=_fetch_from_fixture,
        sleep_fn=lambda _seconds: None,
    )
    assert off.compose is False
    assert off.synthesize is False


def test_bind_keeps_p0_shape_on_empty_and_partial(tmp_path: Path) -> None:
    from intelligence.services.disclosure_scan_pack import CninfoPage, PAGE_SIZE

    def empty_fetch(*, keyword: str, se_date: str, page_num: int, **_kwargs):
        return CninfoPage((), 0)

    options = AskOptions(
        query=FROZEN,
        market_db_path=_db(tmp_path),
        date=AS_OF,
        compose=True,
        synthesize=True,
    )
    empty = bind_disclosure_scan_pack(
        options,
        cninfo_fetch=empty_fetch,
        sleep_fn=lambda _seconds: None,
    )
    assert empty.disclosure_scan_pack is not None
    assert empty.disclosure_scan_pack.status == "empty"
    assert empty.compose is False
    assert empty.synthesize is False

    def paged_fetch(*, keyword: str, se_date: str, page_num: int, **_kwargs):
        rows = tuple(
            {
                "secCode": "600276",
                "secName": "恒瑞医药",
                "announcementTitle": f"关于获得药品注册批准的公告{page_num}-{i}",
                "announcementId": f"pg-{keyword}-{page_num}-{i}",
                "orgId": "x",
                "announcementTime": "2026-08-21",
            }
            for i in range(PAGE_SIZE)
        )
        return CninfoPage(rows, 400)

    partial = bind_disclosure_scan_pack(
        options,
        cninfo_fetch=paged_fetch,
        sleep_fn=lambda _seconds: None,
    )
    assert partial.disclosure_scan_pack is not None
    assert partial.disclosure_scan_pack.status == "partial"
    assert partial.compose is False
    assert partial.synthesize is False


def test_residual_gate_shapes(tmp_path: Path) -> None:
    pack = _run(tmp_path)
    clean = gate_disclosure_residual(
        "恒瑞医药（600276）属注册获批档；集采中选具有量价双重性，不默认利好。",
        pack,
    )
    assert clean.dropped is False
    assert clean.text
    unknown = gate_disclosure_residual("建议关注贵州茅台（600519）的机会。", pack)
    assert unknown.dropped is True
    assert unknown.reason == "unknown_code"
    assert unknown.detail == "600519"
    assert unknown.text == ""
    roster = gate_disclosure_residual(
        "600276 【注册获批】恒瑞医药 2026-08-21 关于获得药品注册批准的公告",
        pack,
    )
    assert roster.dropped is True
    assert roster.reason == "roster_line"
    embedded = gate_disclosure_residual(
        "公告编号 1225497236 对应的行属注册获批档，无需另查。", pack
    )
    assert embedded.dropped is False
    long = gate_disclosure_residual("这一段解读反复展开。" * 400, pack)
    assert long.dropped is False
    assert long.reason == "truncated"
    assert long.text.endswith(RESIDUAL_TRUNCATION_NOTICE)
    renarration = gate_disclosure_residual(
        "600276、002693、000756、300687、300504、600812、603296、000938、601089 "
        "本轮均有披露，逐一说明如下。",
        pack,
    )
    assert renarration.dropped is True
    assert renarration.reason == "roster_renarration"
    assert renarration.detail == "9"


def test_prepare_residual_answer_carries_contract(tmp_path: Path) -> None:
    options = AskOptions(
        query=FROZEN,
        market_db_path=_db(tmp_path),
        date=AS_OF,
        compose=True,
        synthesize=True,
    )
    bound = bind_disclosure_scan_pack(
        options,
        cninfo_fetch=_fetch_from_fixture,
        sleep_fn=lambda _seconds: None,
    )
    prepared = prepare_disclosure_residual_answer(bound)
    result = prepared.result
    assert result.synthesis is None
    assert result.answer_spec is not None
    messages = result.prepared_synthesis_messages
    assert messages
    assert DISCLOSURE_RESIDUAL_CONTRACT in messages[0]["content"]
    assert "600276" in messages[1]["content"]


def test_residual_answer_spec_covers_every_roster_row(tmp_path: Path) -> None:
    """P1-①c：claim 集必须全行覆盖，不走通用 builder 的 [:8] 截断。

    shadow 有据链（composer/judge）的输入完全从 answer_spec 生成——claim
    只有 8 条时模型解读全名单必然越界被拒收（live R5 m 轮根因）。
    """

    from intelligence.services.disclosure_scan_pack import (
        DISCLOSURE_EVIDENCE_ID,
        build_disclosure_residual_answer_spec,
    )

    pack = _run(tmp_path)
    assert pack.status == "hit"
    spec = build_disclosure_residual_answer_spec(pack, query=FROZEN)

    row_claim_ids = {
        claim.claim_id
        for claim in spec.verified_facts
        if claim.claim_id.startswith("disc:row:")
    }
    excl_claim_ids = {
        claim.claim_id
        for claim in spec.verified_facts
        if claim.claim_id.startswith("disc:excl:")
    }
    counter_claim_ids = {claim.claim_id for claim in spec.counter_evidence}
    assert len(row_claim_ids) == len(pack.rows)
    assert len(excl_claim_ids) == len(pack.excluded)
    assert len(counter_claim_ids) == len(pack.counter_rows)
    for row in pack.rows:
        assert f"disc:row:{row.code}:{row.announcement_id}" in row_claim_ids
    for row in pack.counter_rows:
        assert (
            f"disc:counter:{row.code}:{row.announcement_id}" in counter_claim_ids
        )

    # 聚合 claim 给归纳句数字出处；行级 claim 是点名个股的绑定位。
    fact_ids = {claim.claim_id for claim in spec.verified_facts}
    assert "disc:agg:tiers" in fact_ids
    assert "disc:agg:excluded" in fact_ids
    assert "disc:agg:keywords" in fact_ids
    assert "disc:agg:window" in fact_ids

    # 全部行级/聚合 claim 是硬证据形状：VERIFIED + L3 tier + evidence_ids，
    # 措辞不被治理软化，且满足 shadow 链 support claims 门槛。
    from intelligence.services import answer_model

    for claim in (*spec.summary, *spec.verified_facts, *spec.counter_evidence):
        assert claim.status is answer_model.ClaimStatus.VERIFIED
        assert claim.evidence_ids == (DISCLOSURE_EVIDENCE_ID,)
        assert claim.evidence_tier.startswith("l3")

    # claim_id 全局唯一（registry/绑定的前提）。
    all_ids = [
        claim.claim_id
        for claim in (
            *spec.summary,
            *spec.verified_facts,
            *spec.counter_evidence,
            *spec.gaps,
            *spec.triggers,
        )
    ]
    assert len(all_ids) == len(set(all_ids))

    # 残差契约经 prompt_constraints 进 shadow 链 required_outputs 槽。
    assert spec.prompt_constraints
    joined = "\n".join(spec.prompt_constraints)
    assert "不超过 8 家" in joined
    assert "不要输出六位代码开头的名单行" in joined

    # summary 首条要把「名单已置顶」的定位讲给 composer（direct_answer 素材）。
    assert "置顶" in spec.summary[0].text


def test_residual_registry_holds_all_rows_within_budget(tmp_path: Path) -> None:
    """12k 字符 registry 预算必须装得下全行 claim——装不下就是设计回退。

    ⚠ 这条只在**小包**上成立（本夹具 11 行）。生产规模的守卫见下一条：本条曾经
    是绿的、而生产 61 行的包被截到 18 条——金样本把理想写进了断言。
    """

    from intelligence.services import answer_model
    from intelligence.services.disclosure_scan_pack import (
        build_disclosure_residual_answer_spec,
    )

    pack = _run(tmp_path)
    assert len(pack.rows) + len(pack.excluded) + len(pack.counter_rows) < 20
    spec = build_disclosure_residual_answer_spec(pack, query=FROZEN)
    registry = answer_model.grounded_claim_registry_block(
        spec, query=FROZEN, max_chars=12_000
    )
    for row in (*pack.rows, *pack.excluded, *pack.counter_rows):
        assert row.code in registry
    assert "因窗口预算未纳入" not in registry
    atoms = answer_model.evidence_atoms_from_answer_spec(spec)
    assert atoms
    atom_claim_ids = {atom.provenance.get("claim_id") for atom in atoms}
    for row in pack.rows:
        assert f"disc:row:{row.code}:{row.announcement_id}" in atom_claim_ids


def test_production_scale_registry_keeps_counterevidence_and_gaps() -> None:
    """生产规模（61 行）下预算一定会截断——被截掉的**不能是反证和缺口**。

    2026-08-26 实测现场：68 条 claim / 12k 预算只装下 18 条 + 截断注，
    ``disc:counter`` 与 ``disc:excl`` 一条没进。模型于是把「扫描包里有一条华北
    制药撤回的反证行」绑到 ``disc:summary:1`` 上，确定性闸判 cross_subject、
    整句被删——公开稿因此没有反证解读。反证与缺口是「不许过度宣称」的材料，
    它们被挤掉，模型手里就只剩支持性事实。

    上一条用的是 11 行夹具，永远绿，看不见这个。
    """

    from intelligence.services import answer_model
    from intelligence.services.disclosure_scan_pack import (
        DisclosureBucket,
        DisclosureRow,
        DisclosureScanPack,
        build_disclosure_residual_answer_spec,
    )

    def _row(index: int, tier: str) -> DisclosureRow:
        return DisclosureRow(
            code=f"{600000 + index}",
            name=f"样例公司{index}",
            date="2026-08-25",
            # 生产的公告标题就是这个量级，行长主要由它决定。
            title=f"关于全资子公司获得药物临床试验批准通知书的公告（第{index}号）",
            tier=tier,
            announcement_id=f"12255{index:05d}",
            org_id=f"gssh{600000 + index}",
            url=f"https://www.cninfo.com.cn/new/disclosure/detail?x={index}",
            buckets=("医药",),
        )

    pack = DisclosureScanPack(
        status="hit",
        as_of="2026-08-26",
        universe_date="2026-08-25",
        se_date_start="2026-08-21",
        se_date_end="2026-08-26",
        elapsed_ms=1,
        budget_hit=True,
        buckets=(
            DisclosureBucket(
                name="医药",
                sector_names=("医药",),
                universe_size=512,
                hit_codes=tuple(f"{600000 + i}" for i in range(21)),
            ),
        ),
        rows=tuple(_row(i, "L_approve") for i in range(21)),
        excluded=tuple(_row(100 + i, "L_buyback") for i in range(39)),
        counter_rows=(_row(900, "L_neg"),),
        keyword_traces=(),
        warnings=(),
        fetch_calls=(),
    )
    assert len(pack.rows) + len(pack.excluded) + len(pack.counter_rows) == 61

    spec = build_disclosure_residual_answer_spec(pack, query=FROZEN)
    registry = answer_model.grounded_claim_registry_block(
        spec, query=FROZEN, max_chars=12_000
    )

    # 截断本身是允许的——但必须留痕，模型才知道 registry 还有别的 claim。
    assert "因窗口预算未纳入" in registry
    # 反证行一条都不许被挤掉：它是模型解读反证时唯一能绑的 claim。
    for row in pack.counter_rows:
        assert f"disc:counter:{row.code}:{row.announcement_id}" in registry
    # 缺口 claim 同理：被挤掉就等于把「没查完」说成「没有」。
    for gap in spec.gaps:
        assert gap.claim_id in registry


def test_residual_grounded_validation_accepts_bound_reading(
    tmp_path: Path,
) -> None:
    """行级 claim 齐了之后，绑定名单行的解读句必须能过确定性校验；
    包外码句仍被拦——修的是覆盖，不是放松判据。"""

    from intelligence.services import answer_model
    from intelligence.services.disclosure_scan_pack import (
        build_disclosure_residual_answer_spec,
    )

    pack = _run(tmp_path)
    spec = build_disclosure_residual_answer_spec(pack, query=FROZEN)
    atoms = answer_model.evidence_atoms_from_answer_spec(spec)

    def atom_of(claim_id: str) -> str:
        for atom in atoms:
            if atom.provenance.get("claim_id") == claim_id:
                return atom.atom_id
        raise AssertionError(f"no atom for {claim_id}")

    hr = "disc:row:600276:hr-reg-0821"
    hb_neg = "disc:counter:600812:hb-neg-0823"
    tiers = "disc:agg:tiers"
    answer = "\n".join(
        [
            f"恒瑞医药（600276）2026-08-21 的公告属注册获批档。 "
            f"<!-- claim_ids={hr}; evidence_atom_ids={atom_of(hr)}; "
            "claim_type=fact -->",
            f"华北制药（600812）2026-08-23 存在撤回类反证，须与其临床批件并读。 "
            f"<!-- claim_ids={hb_neg}; evidence_atom_ids={atom_of(hb_neg)}; "
            "claim_type=fact -->",
            f"主名单以注册获批与合同/中选为主。 "
            f"<!-- claim_ids={tiers}; evidence_atom_ids={atom_of(tiers)}; "
            "claim_type=fact -->",
        ]
    )
    issues = answer_model.validate_grounded_composer_answer(answer, spec)
    assert not [issue for issue in issues if issue.severity == "error"]

    stray = (
        "贵州茅台（600519）也值得关注。 "
        f"<!-- claim_ids={hr}; evidence_atom_ids={atom_of(hr)}; "
        "claim_type=fact -->"
    )
    stray_issues = answer_model.validate_grounded_composer_answer(stray, spec)
    assert [issue for issue in stray_issues if issue.severity == "error"]


def test_orchestrator_gates_residual_after_synthesis() -> None:
    src = (
        Path(__file__).resolve().parents[1]
        / "runtime"
        / "conversation_orchestrator.py"
    ).read_text(encoding="utf-8")
    assert "prepare_disclosure_residual_answer(" in src
    synth_at = src.index("synthesize_prepared_answer(")
    gate_at = src.index("gate_disclosure_residual(")
    assert synth_at < gate_at
    assert "disclosure_residual_dropped:" in src
    # 有据呈现器拒收（synthesis=确定性兜底骨架）必须按丢弃处理回纯包，
    # 不得把 spec 骨架当残差交付——live run_20260825_200157_247884 实锤。
    assert 'synthesis_diagnostic.state == "rejected"' in src
    assert "grounded_rejected" in src


def test_unsupported_without_sector_does_not_scan_all_a_shares(tmp_path: Path) -> None:
    pack = _run(tmp_path, query="有哪些个股有比较利好的公告")
    assert pack.status == "unsupported"
    assert "全市场" in pack.render()
    assert disclosure_scan_degrade_codes(pack) == ("disclosure_scan_pack_unsupported",)


def test_orchestrator_binds_pack_before_owner_fork() -> None:
    src = (
        Path(__file__).resolve().parents[1]
        / "runtime"
        / "conversation_orchestrator.py"
    ).read_text(encoding="utf-8")
    bind_at = src.index("bind_disclosure_scan_pack")
    owner_at = src.index("elif owner_output is not None:")
    assert bind_at < owner_at
    assert "merge_disclosure_into_public_answer" in src
    assert 'report["disclosure_scan_pack"]' in src
    assert 'not in {\n                    QUESTION_MARKET_TECHNICAL,\n                    QUESTION_EXTERNAL_MARKET,\n                    "disclosure_scan",\n                }' in src or '"disclosure_scan"' in src


def test_pack_to_dict_exposes_diagnostics(tmp_path: Path) -> None:
    pack = _run(tmp_path)
    payload = pack.to_dict()
    assert payload["budget_hit"] is False
    assert payload["fetch_calls"]
    assert any(trace["pages_fetched"] >= 1 for trace in payload["keyword_traces"])
    assert any(trace["page_rows"] >= 1 for trace in payload["keyword_traces"])
    assert payload["rows"][0]["org_id"]
    rendered = pack.render()
    assert "页/" in rendered
    assert "orgId=" in rendered or "cninfo.com.cn" in rendered


def test_theme_research_l3_lookup_stays_closed() -> None:
    from intelligence.workbench_skills.research_owner import THEME_RESEARCH

    assert THEME_RESEARCH.use_l3_lookup is False
