"""按问题意图挑暴露公司（待办 C）。

确定性排序只能按图谱静态标注排，排不出「**对这个问题**谁最相关」——「固态电池」
86 家候选挤在 9 个 (strength, confidence) 桶里，core/medium 一档 13 家而配额 12，
档内仍按公司名取舍。这一层交给模型。

这里钉的重点是**降级路径**：模型不可用/胡说/选不满时，答案不能塌，而且必须
留下为什么。选择器本身选得准不准是模型的事，测不了也不该在这里测。
"""

from __future__ import annotations

from intelligence.adapters.knowledge import KnowledgeAdapter
from intelligence.services import ask, exposure_selector
from intelligence.services.closed_loop_retrieval import ClosedLoopRetrievalResult


def _row(company: str, strength: str = "core", confidence: str = "high") -> dict:
    return {
        "company": company,
        "concept": "固态电池",
        "strength": strength,
        "confidence": confidence,
        "role": f"{company}的产业链线索",
        "score": 20,
    }


CANDIDATES = [_row(f"公司{index:02d}") for index in range(20)]


def _complete(content: str | None, reason: str = ""):
    """打桩的 llm_refine.complete，顺带记录被调用过几次。"""
    calls: list[dict] = []

    def fake(messages, model_override=None, timeout=None, **kwargs):
        calls.append({"messages": messages, "model_override": model_override})
        return content, None, reason

    fake.calls = calls  # type: ignore[attr-defined]
    return fake


def test_llm_pick_replaces_deterministic_head_and_keeps_its_order(monkeypatch) -> None:
    """模型选的按它给的顺序进正文，不是确定性那 5 家。"""
    monkeypatch.delenv("ASK_EXPOSURE_SELECTOR", raising=False)
    call = _complete('{"companies": ["公司17", "公司03", "公司11", "公司19", "公司08"]}')

    out = exposure_selector.select_exposures(
        "谁最受益", CANDIDATES, 5, complete=call
    )

    assert [row["company"] for row in out.items] == [
        "公司17",
        "公司03",
        "公司11",
        "公司19",
        "公司08",
    ]
    assert out.telemetry["mode"] == "llm"
    assert out.telemetry["llm_selected"] == 5
    assert out.telemetry["backfilled"] == 0


def test_provider_unavailable_falls_back_and_says_why(monkeypatch) -> None:
    """模型不回话就回退确定性——但必须留下原因，不能静默降级。"""
    monkeypatch.delenv("ASK_EXPOSURE_SELECTOR", raising=False)
    call = _complete(None, reason="timeout")

    out = exposure_selector.select_exposures(
        "谁最受益", CANDIDATES, 5, complete=call
    )

    assert [row["company"] for row in out.items] == [
        row["company"] for row in CANDIDATES[:5]
    ]
    assert out.telemetry["mode"] == "deterministic"
    assert out.telemetry["reason"].startswith("provider_unavailable")
    assert "timeout" in out.telemetry["reason"]


def test_unparsable_response_is_not_reported_as_provider_failure(monkeypatch) -> None:
    """provider 回话了只是读不懂，跟 provider 挂了是两回事。

    混成一类会把一次 prompt/schema 回归误判成外部故障——turn_controller 那轮的教训。
    """
    monkeypatch.delenv("ASK_EXPOSURE_SELECTOR", raising=False)
    call = _complete("我觉得公司03和公司17比较好")

    out = exposure_selector.select_exposures(
        "谁最受益", CANDIDATES, 5, complete=call
    )

    assert out.telemetry["mode"] == "deterministic"
    assert out.telemetry["reason"] == "unparsable_response"


def test_companies_outside_the_pool_are_dropped_not_appended(monkeypatch) -> None:
    """模型凭记忆报的公司不许进研究报告，只计数。"""
    monkeypatch.delenv("ASK_EXPOSURE_SELECTOR", raising=False)
    call = _complete('{"companies": ["宁德时代", "公司07", "赣锋锂业"]}')

    out = exposure_selector.select_exposures(
        "谁最受益", CANDIDATES, 5, complete=call
    )

    companies = [row["company"] for row in out.items]
    assert "宁德时代" not in companies
    assert "赣锋锂业" not in companies
    assert companies[0] == "公司07"
    assert out.telemetry["hallucinated"] == 2


def test_short_pick_is_backfilled_so_coverage_does_not_collapse(monkeypatch) -> None:
    """模型只选 2 家时用确定性排序补满。

    这是和 CC 记忆检索最大的量纲差异：CC 少选一条只是少一条上下文，我们少选
    一家就是「谁最受益」这个必需输出的覆盖面塌掉。
    """
    monkeypatch.delenv("ASK_EXPOSURE_SELECTOR", raising=False)
    call = _complete('{"companies": ["公司13", "公司02"]}')

    out = exposure_selector.select_exposures(
        "谁最受益", CANDIDATES, 5, complete=call
    )

    companies = [row["company"] for row in out.items]
    assert companies[:2] == ["公司13", "公司02"]
    assert len(companies) == 5
    assert len(set(companies)) == 5, "补齐不能补出重复公司"
    assert out.telemetry["llm_selected"] == 2
    assert out.telemetry["backfilled"] == 3


def test_off_switch_does_not_call_the_model_at_all(monkeypatch) -> None:
    """杀死开关要真的省下那次配额，不是调完再丢掉结果。"""
    monkeypatch.setenv("ASK_EXPOSURE_SELECTOR", "off")
    call = _complete('{"companies": ["公司17"]}')

    out = exposure_selector.select_exposures(
        "谁最受益", CANDIDATES, 5, complete=call
    )

    assert call.calls == [], "开关关着还调了模型，等于白烧一次滚动配额"
    assert out.telemetry["mode"] == "deterministic"
    assert out.telemetry["reason"] == "selector_off"


def test_pool_within_limit_skips_the_call(monkeypatch) -> None:
    """候选没超配额时没有可挑的余地，这次调用纯属浪费。"""
    monkeypatch.delenv("ASK_EXPOSURE_SELECTOR", raising=False)
    call = _complete('{"companies": ["公司01"]}')

    out = exposure_selector.select_exposures(
        "谁最受益", CANDIDATES[:4], 12, complete=call
    )

    assert call.calls == []
    assert out.telemetry["reason"] == "pool_within_limit"
    assert len(out.items) == 4


def test_selector_is_actually_wired_and_its_verdict_reaches_the_trace(
    monkeypatch,
) -> None:
    """截断时选择器要真的被调用，结果和降级原因要真的进 telemetry。

    只测选择器本身、不测接线，等于把上一轮「信息在系统里但没送到」再犯一遍。
    """
    monkeypatch.delenv("ASK_EXPOSURE_SELECTOR", raising=False)

    def fake_exposures(self, term: str, limit: int = 12) -> dict:
        pool = [_row(f"公司{index:02d}") for index in range(min(limit, 40))]
        return {
            "found": True,
            "term": term,
            "items": pool,
            "total_matched": 86,
            "truncated": True,
            "warnings": ["图谱共 86 家匹配…"],
            "errors": [],
        }

    call = _complete('{"companies": ["公司21", "公司09"]}')
    monkeypatch.setattr(KnowledgeAdapter, "get_exposure_matches", fake_exposures)
    monkeypatch.setattr(exposure_selector.llm_refine, "complete", call)
    monkeypatch.setattr(
        ask.closed_loop_retrieval,
        "retrieve_closed_loop",
        lambda *args, **kwargs: ClosedLoopRetrievalResult(),
    )

    result = ask.answer_query(
        ask.AskOptions(
            query="固态电池产业链现在走到哪一步了，谁最受益",
            compose=False,
            synthesize=False,
        )
    )

    assert call.calls, "截断了却没调选择器——接线断了"
    selector = (result.graph_exposure_telemetry or {}).get("selector") or {}
    assert selector.get("mode") == "llm", f"selector 遥测没送到：{selector}"
    assert selector.get("llm_selected") == 2
    assert selector.get("backfilled") == 10


def test_candidate_catalog_carries_the_signal_the_model_needs(monkeypatch) -> None:
    """prompt 里必须带上强度/置信/线索，否则模型只看得到一串公司名。

    这条防的是「信息在系统里但没送到」——候选行本来就带着这些字段。
    """
    monkeypatch.delenv("ASK_EXPOSURE_SELECTOR", raising=False)
    call = _complete('{"companies": ["公司01"]}')

    exposure_selector.select_exposures("谁最受益", CANDIDATES, 5, complete=call)

    prompt = "\n".join(m["content"] for m in call.calls[0]["messages"])
    assert "谁最受益" in prompt
    assert "强度=core" in prompt
    assert "置信=high" in prompt
    assert "公司00的产业链线索" in prompt
