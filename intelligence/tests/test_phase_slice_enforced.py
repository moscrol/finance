"""时间片必须在强制点被读取——「传下去了」不等于「被执行了」。

真实事故（2026-08-03 单题实测，phase 埋点第一次有输出）：

    brief     ok      入口剩余=89999ms  分片=22s  实耗=69740ms
    composer  failed  入口剩余=20258ms  分片=10s  实耗=20261ms

brief 分到 22 秒，跑了 69.7 秒。原因是 ``synthesize_messages`` 里
``shared_deadline = deadline or Deadline.from_timeout(timeout)`` —— 调用方显式
传 deadline 时（grounded 三段链一直这么传），``timeout`` 参数被整个丢弃，随后
``require_remaining(1)`` 把**整条剩余预算**当成本次调用的超时。三个 0.25/0.5/0.35
的时间片算得很认真，消费端一次都没读。

这类 bug 在 trace 里长得像「模型慢」，只有把「进场时还剩多少 / 分到多少 / 实际用了
多少」三个数并排放才暴露。所以这个文件守的不是某个数值，是**分片与实际超时之间的
那条等式**。
"""

from __future__ import annotations

import pytest

from intelligence.services import llm_refine


class TestCallTimeoutClamp:
    def test_slice_wins_when_deadline_is_generous(self) -> None:
        """剩 90 秒、片 22 秒 → 本次调用最多 22 秒。就是事故里错掉的那一步。"""
        deadline = llm_refine.Deadline.from_timeout(90)

        assert deadline.call_timeout(22) == pytest.approx(22, abs=0.5)

    def test_deadline_wins_when_slice_is_generous(self) -> None:
        """反向：片比剩余大时以剩余为准，子阶段不得越过根截止时间。"""
        deadline = llm_refine.Deadline.from_timeout(5)

        assert deadline.call_timeout(60) == pytest.approx(5, abs=0.5)

    def test_exhausted_deadline_still_raises(self) -> None:
        """预算已尽时照旧抛 LLMDeadlineExceeded，不因为夹逼而吞掉。"""
        deadline = llm_refine.Deadline(expires_at=0.0)

        with pytest.raises(llm_refine.LLMDeadlineExceeded):
            deadline.call_timeout(22)

    def test_zero_slice_falls_back_to_remaining(self) -> None:
        """没给片（0/None）时保持旧语义，不要把它当成「立刻超时」。"""
        deadline = llm_refine.Deadline.from_timeout(30)

        assert deadline.call_timeout(0) == pytest.approx(30, abs=0.5)


class TestEnforcedAtTheCallSite:
    """夹逼函数存在还不够——得证明**调用点**真的用了它。"""

    def test_non_streaming_call_receives_the_slice(self, monkeypatch) -> None:
        seen: list[float] = []

        def fake_post(provider, messages, timeout, *args, **kwargs):
            seen.append(timeout)
            return "答案", "stop"

        monkeypatch.setattr(
            llm_refine,
            "detect_provider",
            lambda override=None: llm_refine.LLMProvider(
                "fake", "k", "https://example.invalid/v1", "m"
            ),
        )
        monkeypatch.setattr(llm_refine, "_post_chat_synthesis", fake_post)

        result, reason = llm_refine.synthesize_messages(
            [{"role": "user", "content": "x"}],
            timeout=22,
            deadline=llm_refine.Deadline.from_timeout(90),
        )

        assert result is not None, reason
        assert seen, "没有发起调用"
        # 修复前这里会拿到 ~90：整条 deadline 被当成单段超时。
        assert seen[0] <= 23, f"时间片未被强制执行：实际传入 {seen[0]}s"

    def test_streaming_call_receives_the_slice(self, monkeypatch) -> None:
        """流式路径是同一处错误的第二份拷贝，别只修一半。"""
        seen: list[float] = []

        def fake_stream(provider, messages, timeout, *args, **kwargs):
            seen.append(timeout)
            return "答案", "stop"

        monkeypatch.setattr(
            llm_refine,
            "detect_provider",
            lambda override=None: llm_refine.LLMProvider(
                "fake", "k", "https://example.invalid/v1", "m"
            ),
        )
        monkeypatch.setattr(llm_refine, "_post_chat_stream", fake_stream)

        llm_refine.synthesize_messages_stream(
            [{"role": "user", "content": "x"}],
            on_delta=lambda _delta: None,
            timeout=15,
            deadline=llm_refine.Deadline.from_timeout(90),
        )

        assert seen, "没有发起调用"
        assert seen[0] <= 16, f"流式时间片未被强制执行：实际传入 {seen[0]}s"
