"""workbench_probe 的 ID 配对合同：成败看 run.status，取货认 message_id。

钉住的形状（2026-09-12 事故复盘）：
- 迟到的上一轮旧答案不得被当成本轮结果（只认 POST 202 发回的 assistant_message_id）；
- 非空的失败存根不得被当成答案（run.status=failed/cancelled 直接非零退出）；
- run 终态 claim 先于消息终稿 revise，completed 时消息短暂为空要继续等而非判败。
"""

from __future__ import annotations

import sys

import pytest

from scripts import workbench_probe

POST_RESPONSE = {
    "conversation_id": "conv_test",
    "user_message_id": "msg_user",
    "assistant_message_id": "msg_ours",
    "run_id": "run_abc123",
}

OLD_MESSAGE = {
    "message_id": "msg_old",
    "role": "assistant",
    "content": "上一轮的旧答案",
}


def _our_message(content: str) -> dict:
    return {"message_id": "msg_ours", "role": "assistant", "content": content}


class _FakeServer:
    """按调用推进状态的假 workbench：run 状态依次给出，消息内容可随轮询变化。"""

    def __init__(self, run_progression: list[dict], messages) -> None:
        self._run_progression = list(run_progression)
        self._messages = messages  # list 或 callable(server) -> list
        self.run_polls = 0
        self.message_fetches = 0

    def __call__(self, base: str, path: str, payload: dict | None = None):
        if path == "/api/conversations" and payload is not None:
            return {"conversation_id": "conv_test"}
        if payload is not None and path.endswith("/messages"):
            return dict(POST_RESPONSE)
        if path.startswith("/api/runs/"):
            self.run_polls += 1
            if len(self._run_progression) > 1:
                return self._run_progression.pop(0)
            return self._run_progression[0]
        if "/messages" in path:
            self.message_fetches += 1
            if callable(self._messages):
                return self._messages(self)
            return self._messages
        raise AssertionError(f"未预期的请求：{path!r}")


def _run_probe(monkeypatch, capsys, fake: _FakeServer, *extra_args: str):
    monkeypatch.setattr(workbench_probe, "_call", fake)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "workbench_probe.py",
            "--user",
            "probe-test",
            "--question",
            "题面",
            "--poll-seconds",
            "0",
            *extra_args,
        ],
    )
    code = workbench_probe.main()
    return code, capsys.readouterr()


def test_completed_run_returns_our_answer_by_message_id(monkeypatch, capsys):
    fake = _FakeServer(
        [{"status": "running"}, {"status": "completed"}],
        [OLD_MESSAGE, _our_message("本轮的新答案")],
    )
    code, captured = _run_probe(monkeypatch, capsys, fake, "--timeout", "30")
    assert code == 0
    assert "本轮的新答案" in captured.out
    assert "run_id=run_abc123" in captured.out


def test_late_old_turn_answer_is_never_returned(monkeypatch, capsys):
    """旧轮答案一直在列表里且非空；我们的消息要到 run completed 才有内容。"""

    def messages(server: _FakeServer) -> list[dict]:
        if server.run_polls < 3:
            return [OLD_MESSAGE, _our_message("")]
        return [OLD_MESSAGE, _our_message("第三轮自己的答案")]

    fake = _FakeServer(
        [{"status": "running"}, {"status": "running"}, {"status": "completed"}],
        messages,
    )
    code, captured = _run_probe(monkeypatch, capsys, fake, "--timeout", "30")
    assert code == 0
    assert fake.run_polls == 3  # 没有在第 1/2 次轮询被旧答案骗走
    assert "第三轮自己的答案" in captured.out
    assert "上一轮的旧答案" not in captured.out


@pytest.mark.parametrize("terminal", ["failed", "cancelled"])
def test_failed_run_with_non_empty_stub_exits_nonzero(
    monkeypatch, capsys, terminal: str
):
    """失败存根内容非空（"本轮连续研究未取得可公开答案。"）也不得当答案。"""
    fake = _FakeServer(
        [{"status": "running"}, {"status": terminal, "error": "boom"}],
        [OLD_MESSAGE, _our_message("本轮连续研究未取得可公开答案。")],
    )
    code, captured = _run_probe(monkeypatch, capsys, fake, "--timeout", "30")
    assert code == 2
    assert "run_abc123" in captured.err
    assert "未取得可公开答案" not in captured.out


def test_timeout_reports_run_id(monkeypatch, capsys):
    fake = _FakeServer([{"status": "running"}], [])
    code, captured = _run_probe(monkeypatch, capsys, fake, "--timeout", "0")
    assert code == 1
    assert "run_abc123" in captured.err


def test_completed_run_waits_for_message_final(monkeypatch, capsys):
    """claim 终态先于 revise 消息：第一次取到空要继续短轮询，不能判败。"""

    def messages(server: _FakeServer) -> list[dict]:
        if server.message_fetches < 2:
            return [OLD_MESSAGE, _our_message("")]
        return [OLD_MESSAGE, _our_message("落盘稍晚的终稿")]

    fake = _FakeServer([{"status": "completed"}], messages)
    code, captured = _run_probe(monkeypatch, capsys, fake, "--timeout", "30")
    assert code == 0
    assert fake.message_fetches >= 2
    assert "落盘稍晚的终稿" in captured.out


def test_completed_but_message_stays_empty_exits_3(monkeypatch, capsys):
    fake = _FakeServer([{"status": "completed"}], [OLD_MESSAGE, _our_message("")])
    code, captured = _run_probe(monkeypatch, capsys, fake, "--timeout", "1")
    assert code == 3
    assert "run_abc123" in captured.err
