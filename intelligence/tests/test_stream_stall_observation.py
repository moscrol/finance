"""流式 stall 观测：记录相邻 delta 的最大间隔，TTFB 不计入。

ch06b «API 通信层» 的双看门狗里，这是**日志型**的那一半：
- **idle**（中断型）= 一个事件都没收到，连接可能已经死了 → 中断流
- **stall**（日志型）= 收到了事件但间隔太大，连接活着但那边很慢 → 只记录

关键细节来自源码：``lastEventTime`` 在第一个 chunk 到达之后才开始设置，
避免把 TTFB（模型在思考，可以合法地很慢）误判成 stall。

**这里故意不设阈值。** ch06b 的 30s 来自 Anthropic 的生产数据；我们的
composer 固定 grant 也只有 40 秒，照抄 30s 基本不会触发。先记实测分布，有数据再定阈值——
这条也是我们自己踩出来的教训：先加观测再迭代。

测试走**真实的 capture 闭包**：monkeypatch 流式函数 → 它按可控时钟回调 on_delta
→ 断言真实产出的遥测。在闭包外面重写一遍同样的算术是抓不到 bug 的。
"""
from __future__ import annotations

from unittest import mock

import pytest

from intelligence.services import llm_refine
from intelligence.services.ask import (
    AskOptions,
    AskResult,
    PreparedAnswer,
    synthesize_prepared_answer,
)


def _prepared() -> PreparedAnswer:
    """能走到流式分支的最小 PreparedAnswer（形状抄 test_answer_orchestrator）。"""
    options = AskOptions(query="测试问题", compose=True)
    result = AskResult(
        query=options.query,
        trade_date=None,
        matched_theme="测试主题",
        candidate_tier=None,
        priority_score=None,
    )
    result.answer_spec = mock.Mock(
        sources=(),
        summary=(),
        verified_facts=(),
        counter_evidence=(),
        gaps=(),
        triggers=(),
        candidate_facts=(),
        company_table=(),
    )
    result.prepared_synthesis_messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "evidence"},
    ]
    return PreparedAnswer(options=options, result=result)


def _max_gap_ms(
    monkeypatch: pytest.MonkeyPatch,
    delta_times_ms: list[int],
) -> int:
    """按时间线喂 delta，返回**真实算出的** max_delta_gap_ms。

    时钟由 fake_stream 显式推进，而不是按「第 N 次读取」排队——被测代码除了
    capture 之外还会读 monotonic（started、deadline、stream_elapsed…），
    按次数排 tick 会被那些读取吃掉，测出来永远是 0。
    """
    now = {"t": 0.0}

    def fake_stream(messages, *, on_delta, **kwargs):
        del messages, kwargs
        for t_ms in delta_times_ms:
            now["t"] = t_ms / 1000
            on_delta("字")
        # 返回 None 让它走降级分支：本测试只关心遥测，不关心合成结果。
        return None, "LLM 合成返回空内容，已降级为模板"

    monkeypatch.setattr(
        "intelligence.services.ask_synthesis.time.monotonic", lambda: now["t"]
    )
    monkeypatch.setattr(
        llm_refine, "synthesize_messages_stream", fake_stream
    )

    prepared = _prepared()
    synthesize_prepared_answer(prepared)
    return int(prepared.result.llm_stream_telemetry["max_delta_gap_ms"])


def test_ttfb_is_not_counted_as_a_gap(monkeypatch: pytest.MonkeyPatch) -> None:
    """首 token 慢是模型在想，不是卡住——ch06b 明确点名的坑。

    TTFB 40 秒，之后间隔只有 100ms。把 TTFB 算进去会误报成 40 秒。
    """
    assert _max_gap_ms(monkeypatch, [40_000, 40_100]) == 100


def test_the_largest_gap_wins_not_the_last(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """记最大间隔而不是最后一个——中间卡一下也要留痕。"""
    assert _max_gap_ms(monkeypatch, [100, 200, 12_000, 12_050]) == 11_800


def test_single_delta_reports_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """只有一个 delta 时没有「相邻」可言，不能报成首 token 时间。"""
    assert _max_gap_ms(monkeypatch, [5_000]) == 0


def test_no_threshold_is_hardcoded() -> None:
    """防未来的自己：别看到 ch06b 的 30_000 就顺手抄进来。

    我们 composer 固定 grant 只有 40 秒，抄了等于几乎永不触发——比不做还糟，
    因为它会让人以为已经有 stall 检测了。
    """
    import inspect

    from intelligence.services import ask_synthesis

    source = inspect.getsource(ask_synthesis.synthesize_prepared_answer)

    assert "30_000" not in source
    assert "STALL_THRESHOLD" not in source
