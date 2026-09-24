"""R3 four-first-submission failures, reduced to offline behavioral regressions.

Source: docs/verification/2026-09-18-8792-boundary-retest. Snippets preserve
failure shapes, not a financial certification. Scripted judges, blocked sockets,
real frame/verifier/parser and a temporary checkpoint sink; no live retries.
"""
import pytest

from intelligence.services import llm_refine
from intelligence.services.episode_semantic_verifier import (
    SemanticEpisodeVerifier,
    numeric_condition_unsupported,
)
from intelligence.services.research_contract import ResearchDeadline, RequiredOutput
from intelligence.services.track_contract import (
    ingest_next_watch,
    missing_contract_elements,
    parse_next_watch_items,
)
from intelligence.services.user_task import references_material, split_user_message
from intelligence.tests.test_episode_semantic_verifier import _judge, _structural
from intelligence.tests.test_task_frame import _EMPTY_CONTEXT, _REPORT, _frame_for

F2 = (
    "请分析截至2026年9月17日中际旭创（300308）的利润增长与回款兑现。选用一份你确实检索到、"
    "带明确发布日期的公告或定期报告，分清发布日期和财务报告期，再给出现状判断与证据缺口。"
    "最后请用一句完整的话安排“于2026-10-22复查本次引用的公告或报告”，在该句附上这份真实证据的"
    "系统引用编号，不要自行编编号。10月22日仅是未来复查日，不是材料发布日期；两种日期不能混淆。"
    "复查条件可以定性，但不能杜撰公司事实或数字阈值。这轮只讨论，不要登记长期跟踪。"
)
SAFE = "现金流仍待核实 E1。"
HEAD = "无上期基线，本期建立基线。复核期限：2026-10-22。\n"
WATCH = "指标=经营现金流；时间节点=2026-10-22；触发条件=若回款继续恶化，则削弱判断。"
TABLE_HEAD = "**改判条件表**\n| 变量 | 变化 | 方向 |\n|---|---|---|\n"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def denied(*_args, **_kwargs):
        raise AssertionError("offline regression must not connect")
    monkeypatch.setattr("socket.socket.connect", denied)
    monkeypatch.setattr("socket.socket.connect_ex", denied)
    monkeypatch.setattr("socket.create_connection", denied)
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)


@pytest.mark.parametrize("question", [
    F2,
    "请检索中际旭创最新公告，再核查这份公告的发布日期。",
    "请自行查找中际旭创的年报，给出该报告的引用编号。",
    "请查阅中际旭创半年报原文；在这份检索到的报告中找回款证据。",
    "请用这份你检索到的报告分析中际旭创现金流。",
    "请分析中际旭创现金流，并给这份研究列明证据缺口。",
])
def test_retrieval_or_output_reference_is_not_missing_user_material(question):
    assert not references_material(question)
    assert split_user_message(question).materials == ()
    frame = _frame_for(question, conversation_context=_EMPTY_CONTEXT)
    assert frame.materials == () and frame.referenced_material_ids == ()
    assert frame.clarification_question is None
    assert frame.subject == "中际旭创"


@pytest.mark.parametrize("question", [
    "请把这份报告提纯一下。",
    "这篇里提到的产能数字有官方来源吗？",
    "请检索中际旭创公告，同时核对附件中的利润。",
    "先解读这份材料，再检索中际旭创最新公告。",
    "请检索中际旭创公告；不要把这份我上传的报告换成网上的材料。",
    "请检索中际旭创公告，核查这份报告里的数字。",
    "如果你检索到公告，再核查这份公告；现在先分析我贴的材料。",
    "请检索中际旭创公告，核查这份公告；再核对附件。",
    "请分析这份我提交的报告。",
    "请检索中际旭创公告，再核查我发的这份公告。",
    "请检索中际旭创公告，再核对上传的这份公告。",
    "请解读这份研究的逻辑。",
    "请看这份回答有什么问题。",
    "不用检索，请分析这份报告。",
    "不要自行查找公告，请解释这份报告。",
    "请先找出这份报告里的错误。",
    "这份报告说‘请检索中际旭创公告’，请核查它的依据。",
])
def test_missing_supplied_material_is_not_waived_by_other_search_words(question):
    assert references_material(question)
    frame = _frame_for(question, conversation_context=_EMPTY_CONTEXT)
    assert frame.clarification_question is not None
    assert frame.referenced_material_ids == ()


def test_acquisition_clauses_are_scanned_once_not_once_per_reference(monkeypatch):
    from intelligence.services import user_task

    calls = []
    original = user_task._requested_source_families

    def count(text):
        calls.append(len(text))
        return original(text)

    monkeypatch.setattr(user_task, "_requested_source_families", count)
    assert not references_material("请检索中际旭创公告。" + "再核查这份公告。" * 80)
    assert len(calls) == 1


def test_real_supplied_material_and_history_keep_their_identity():
    parts = split_user_message(_REPORT + "\n\n这份报告的逻辑可信吗？")
    assert parts.materials and parts.material_texts == (_REPORT,)
    context = f"## 最近消息原文\nuser: {_REPORT}\nassistant: 已收到。"
    frame = _frame_for("请核查这份报告的逻辑", conversation_context=context)
    assert frame.referenced_material_ids == (parts.materials[0].material_id,)
    assert frame.clarification_question is None


def test_future_source_reference_does_not_bind_unrelated_previous_material():
    context = f"## 最近消息原文\nuser: {_REPORT}\nassistant: 已收到。"
    frame = _frame_for(F2, conversation_context=context)
    assert frame.referenced_material_ids == ()
    assert frame.clarification_question is None


BAD_CONDITIONS = [
    "区分变量：三季报OCF/净利是否回升至≥50%；",
    "区分变量：三季报净现比能否达到0.5；",
    "区分变量：净现比≥0.5，若达到则上调判断。",
    "净现比≥0.5，若达到则上调判断。",
    TABLE_HEAD + "| 经营现金流 | 三季报累计OCF/净利回升≥50% | 备货解释成立↑ |",
    TABLE_HEAD + "| 存货 | 继续快于收入增长且净现比<0.2 | 盈利质量警示↑↑ |",
    "触发条件：净现比不低于0.5。",
    "改判条件：现金流比率≤20%。",
    "证伪条件：净现比低于0.2。",
    "区分变量：净现比高于0.5。",
    "判断标准：回款比例大于等于50%。",
    "## 改判条件\n- 净现比达到0.5。",
    "## 触发条件\n- 评分超过80。",
    "触发条件：\n- 评分超过80。",
    "**改判条件表**\n| 变量 | 变化 | 公司代码 | 优先级 |\n|---|---|---|---|\n| 回款 | 净现比0.5 | 300308 | 1 |",
    # Direct comparator, no magic header required.
    "净现比<0.2 → 盈利质量警示。",
    "净现比低于0.2 → 盈利质量警示。",
    "回款比例不超过20% → 下调判断。",
    "| 现金流 | 净现比≧0.5 | 判断改善 |",
    "# 若净现比低于0.2则改判",
    "**净现比≥0.5**",
    "| 变化 | 评分>80 |",
    TABLE_HEAD + "| 经营现金流 | 回款改善 | 净现比≥0.5才上调 |",
    "## 事实\n| 变量 | 变化 | 方向 |\n|---|---|---|\n| 回款 | 净现比≥0.5 | 判断改善 |",
]


@pytest.mark.parametrize("mode", ["off", "llm"])
@pytest.mark.parametrize("condition", BAD_CONDITIONS)
def test_same_unsupported_condition_is_removed_across_layouts(monkeypatch, mode, condition):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    frame, verified = _structural(SAFE + "\n" + condition, detail="现金流仍待核实。")
    assert numeric_condition_unsupported(verified)
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame, structurally_verified=verified, deadline=ResearchDeadline.from_timeout(5),
    )
    assert SAFE in result.public_answer
    assert not any(number in result.public_answer for number in ("50%", "20%", "0.5", "0.2", "80"))
    assert result.judge_status == "repaired"
    assert any(row["decision"] == "deleted" and "novel_numeric_condition" in row["reasons"]
               for row in result.sentence_verdicts)


@pytest.mark.parametrize("mode", ["off", "llm"])
@pytest.mark.parametrize("condition", BAD_CONDITIONS)
def test_supported_comparator_is_not_a_blanket_numeric_ban(monkeypatch, mode, condition):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    frame, verified = _structural(
        SAFE + "\n" + condition, detail="现金流观察基准50%、20%、0.5、0.2及评分80。",
    )
    assert not numeric_condition_unsupported(verified)
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame, structurally_verified=verified, deadline=ResearchDeadline.from_timeout(5),
    )
    assert result.public_answer == verified.outcome.draft
    assert result.judge_status == "passed"


@pytest.mark.parametrize("text", [
    "区分变量：净现比是否改善（E1）。",
    "触发条件：于2026-10-22复查 E1。",
    "## 改判条件\n- 回款继续恶化则重新评估 E1。\n## 事实\n营收417.78亿元。",
    "## 事实\n| 指标 | 当前值 |\n|---|---|\n| 净现比 | 0.132 |",
    "支持证据：公司营收417.78亿元，归母净利136.51亿元。",
    "**改判条件表**\n| 变量 | 变化 | 公司代码 | 优先级 |\n|---|---|---|---|\n| 回款 | 净现比改善 | 300308 | 1 |",
    "## 改判条件\n- 回款改善则上调判断。\n**事实**：公司营收417.78亿元。",
])
def test_qualitative_plans_dates_and_separate_facts_are_not_condition_numbers(text):
    _, verified = _structural(text)
    assert not numeric_condition_unsupported(verified)


def test_explicit_reasoning_contract_still_allows_hypothesis_thresholds():
    _, verified = _structural(SAFE + TABLE_HEAD + "| 现金流 | 净现比≥0.5 | 改善 |", required_outputs=(
        RequiredOutput("direct_assessment", "直接判断", ("market_data",), True),
        RequiredOutput("invalidation_conditions", "证伪条件", (), True, "model_reasoning"),
    ))
    assert not numeric_condition_unsupported(verified)


def test_unknown_reference_is_still_removed_even_for_qualitative_condition(monkeypatch):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")
    frame, verified = _structural(SAFE + "区分变量：回款是否改善 E999。")
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame, structurally_verified=verified, deadline=ResearchDeadline.from_timeout(5),
    )
    assert SAFE in result.public_answer and "E999" not in result.public_answer


@pytest.mark.parametrize("footer", [
    "本条已登记为长期跟踪。", "上述事项已纳入长期跟踪。",
    "本次研究不登记为长期跟踪。", "本条未登记为长期跟踪。",
    "（本条已登记为长期跟踪。）",
])
@pytest.mark.parametrize("separator", ["\n", ""])
def test_receipt_footer_is_not_a_second_watch_item(tmp_path, footer, separator):
    answer = HEAD + "下期关注清单：" + WATCH + separator + footer
    assert missing_contract_elements(answer) == ()
    items = parse_next_watch_items(answer, as_of="2026-09-18")
    assert len(items) == 1 and items[0].due == "2026-10-22"
    assert footer not in items[0].claim
    sink = tmp_path / "checkpoints.jsonl"
    assert ingest_next_watch(sink, answer, query="继续跟踪，但不要登记长期跟踪") == []
    assert not sink.exists()
    rows = ingest_next_watch(sink, answer, query="继续跟踪，请登记长期跟踪", session_id="r4-positive")
    assert len(rows) == 1 and rows[0]["session_id"] == "r4-positive"


@pytest.mark.parametrize("suffix", [
    "\n2. 指标=存货；时间节点=2026-10-22。",
    "\n- 本条已登记为长期跟踪；指标=存货；时间节点=2026-10-22。",
    "\n本条已登记为长期跟踪。\n- 指标=存货；时间节点=2026-10-22。",
])
def test_receipt_is_not_a_blanket_end_or_missing_item_exemption(suffix):
    answer = HEAD + "下期关注清单：\n- " + WATCH + suffix
    assert missing_contract_elements(answer) == ("next_watch",)
    assert len(parse_next_watch_items(answer, as_of="2026-09-18")) == 1


@pytest.mark.parametrize("body", [
    "本条已登记为长期跟踪。",
    "（复核期限：2026-10-22）\n本条已登记为长期跟踪。",
    "指标=存货；时间节点=2026-10-22。\n本条已登记为长期跟踪。",
])
def test_receipt_and_ttl_cannot_fulfil_a_watch(body):
    answer = HEAD + "下期关注清单：" + body
    assert missing_contract_elements(answer) == ("next_watch",)
    assert parse_next_watch_items(answer, as_of="2026-09-18") == ()


def test_heading_ttl_and_qualitative_arrow_condition_are_not_fake_items():
    answer = HEAD + (
        "**下期关注**（复核期限：2026-10-22）\n"
        "- 三季报应收账款余额与账龄：环比上升且账龄恶化 → 现金流背离解释转向回款条件恶化。"
    )
    assert missing_contract_elements(answer) == ()
    items = parse_next_watch_items(answer, as_of="2026-09-18")
    assert len(items) == 1 and "复核期限" not in items[0].claim


@pytest.mark.parametrize("line", [
    "本期收入 → 经营现金流。", "时间节点=2026-10-22 → 复查。", "持续关注 → 继续观察。",
])
def test_arrow_alone_does_not_make_an_observable_condition(line):
    answer = HEAD + "下期关注清单：" + line
    assert missing_contract_elements(answer) == ("next_watch",)
    assert parse_next_watch_items(answer, as_of="2026-09-18") == ()


@pytest.mark.parametrize("footer", [
    "事实与推测已分开：证据见E1；解释仍待核验。",
    "本回答只讨论研究证据，不构成投资建议。",
    "计算产物可下载；若仍有差异，请核对来源。",
])
def test_explicit_watch_list_does_not_absorb_following_unindented_prose(footer):
    answer = HEAD + "## 下期关注\n- " + WATCH + "\n" + footer
    assert missing_contract_elements(answer) == ()
    items = parse_next_watch_items(answer, as_of="2026-09-18")
    assert len(items) == 1 and footer not in items[0].claim


@pytest.mark.parametrize("time", [
    "时间节点=2026-10-22", "时间节点=2026年10月22日", "时间节点=2026-10月底",
    "时间节点=2026年10月", "时间节点=10天后", "复查日为2026-10-22", "于2026-10-22核查",
    "时间节点=实际披露日（不晚于2026-10-31），并于2026-10-22核查披露进度",
    "时间节点=2026-10-31披露截止；复核时间：2026-10-22",
])
def test_report_period_cannot_steal_the_review_date(time):
    answer = HEAD + "下期关注：事项=三季报（截至2026-09-30）经营现金流；" + time + "；若回款恶化则重新评估。"
    items = parse_next_watch_items(answer, as_of="2026-09-18")
    assert len(items) == 1
    expected = "2026-10-31" if "月底" in time or time.endswith("2026年10月") else (
        "2026-09-28" if "10天后" in time else "2026-10-22"
    )
    assert items[0].due == expected


@pytest.mark.parametrize("time", [
    "复查日=2026-10-22；并于2026-10-23复查",
    "复查日=2026-02-30",
    "复查日=2026年2月30日",
])
def test_ambiguous_or_invalid_review_date_does_not_silently_register(tmp_path, time):
    answer = HEAD + "下期关注：指标=经营现金流；" + time + "；若回款恶化则重新评估。"
    assert missing_contract_elements(answer) == ("next_watch",)
    assert parse_next_watch_items(answer, as_of="2026-09-18") == ()
    sink = tmp_path / "checkpoints.jsonl"
    assert ingest_next_watch(sink, answer, query="登记长期跟踪") == []
    assert not sink.exists()


def test_implicit_watch_keeps_default_due_not_its_historical_period():
    answer = HEAD + "下期关注：若2025-12-31报告期的应收账款问题仍未改善，则重新评估。"
    items = parse_next_watch_items(answer, as_of="2026-09-18")
    assert len(items) == 1 and items[0].due == "2026-10-18"


def test_semantic_judge_opinion_is_not_automatically_a_mechanical_rejection(monkeypatch):
    # V8 intentionally keeps semantic-only doubts; don't silently overturn that
    # contract to repair an unrelated deterministic boundary. The actual record
    # must match publication. A fabricated numeric condition still gets deleted.
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "llm")
    frame, verified = _structural(SAFE + "本结论来自计算编号 abc123。")
    result = SemanticEpisodeVerifier(judge_fn=_judge(
        False, rejected=(2,), issues=("第2句：计算编号属于内部标识",),
    )).verify(frame=frame, structurally_verified=verified, deadline=ResearchDeadline.from_timeout(5))
    assert "abc123" in result.public_answer
    assert any(row["decision"] == "demoted_to_issue" for row in result.sentence_verdicts)


@pytest.mark.parametrize("mode", ["llm", "off"])
@pytest.mark.parametrize("repair", ["none", "good"])
def test_cross_layout_rejection_flows_through_bounded_delivery_repair(monkeypatch, mode, repair):
    from intelligence.tests.test_boundary_partial_delivery import (
        _delivery, FACT, HEAD as DELIVERY_HEAD, WATCH as DELIVERY_WATCH,
    )

    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    result, goals, checks = _delivery(
        repair=repair, draft=DELIVERY_HEAD + DELIVERY_WATCH + "触发条件：净现比≥0.5。",
    )
    assert FACT in result.answer and "0.5" not in result.answer
    if repair == "none":
        assert result.status == "partial"
        assert result.private_artifact["track_contract"]["missing_outputs"] == ["track_next_watch"]
    else:
        assert result.status == "completed" and len(checks) == 2
        assert len(goals) == 1 and goals[0].remaining_calls == 0 and not goals[0].reopen_tools
        assert result.private_artifact["track_contract"]["missing_outputs"] == []


@pytest.mark.parametrize("mode", ["llm", "off"])
def test_receipt_footer_does_not_spend_a_spurious_repair_turn(monkeypatch, mode):
    from intelligence.tests.test_boundary_partial_delivery import _delivery, HEAD as DELIVERY_HEAD, WATCH as DELIVERY_WATCH, GOOD

    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    result, goals, checks = _delivery(draft=DELIVERY_HEAD + DELIVERY_WATCH + GOOD + "\n本条已登记为长期跟踪。")
    assert result.status == "completed" and not goals and len(checks) == 1
    assert result.private_artifact["track_contract"]["missing_outputs"] == []


def test_numeric_rejection_cannot_be_demoted_by_a_passing_judge(monkeypatch):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "llm")
    frame, verified = _structural(SAFE + "区分变量：净现比≥0.5。")
    result = SemanticEpisodeVerifier(judge_fn=_judge(True)).verify(
        frame=frame, structurally_verified=verified, deadline=ResearchDeadline.from_timeout(5),
    )
    assert "0.5" not in result.public_answer and SAFE in result.public_answer
    assert all(row["decision"] == "deleted" for row in result.sentence_verdicts if row["stage"] == "preflight")
