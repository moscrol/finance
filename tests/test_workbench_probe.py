"""workbench_probe 的 ID 配对合同：成败看 run.status，取货认 message_id。

钉住的形状（2026-09-12 事故复盘）：
- 迟到的上一轮旧答案不得被当成本轮结果（只认 POST 202 发回的 assistant_message_id）；
- 非空的失败存根不得被当成答案（run.status=failed/cancelled 直接非零退出）；
- run 终态 claim 先于消息终稿 revise，completed 时消息短暂为空要继续等而非判败。
"""

from __future__ import annotations

import http.client
import io
import sys
import urllib.error

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

    def __init__(
        self,
        run_progression: list[dict],
        messages,
        submission_error=None,
        post_message_error=None,
    ) -> None:
        self._run_progression = list(run_progression)
        self._messages = messages  # list / 异常实例 / callable(server) -> list
        self._submission_error = submission_error  # 非空则任何 POST 都抛它
        self._post_message_error = post_message_error  # 非空则仅 POST 消息抛它
        self.run_polls = 0
        self.message_fetches = 0

    def __call__(self, base: str, path: str, payload: dict | None = None):
        if payload is not None and self._submission_error is not None:
            raise self._submission_error
        if path == "/api/conversations" and payload is not None:
            return {"conversation_id": "conv_test"}
        if payload is not None and path.endswith("/messages"):
            if self._post_message_error is not None:
                raise self._post_message_error
            return dict(POST_RESPONSE)
        if path.startswith("/api/runs/"):
            self.run_polls += 1
            item = (
                self._run_progression.pop(0)
                if len(self._run_progression) > 1
                else self._run_progression[0]
            )
            if isinstance(item, BaseException):
                raise item
            return item
        if "/messages" in path:
            self.message_fetches += 1
            messages = (
                self._messages(self) if callable(self._messages) else self._messages
            )
            if isinstance(messages, BaseException):
                raise messages
            return messages
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


def test_message_id_not_list_position(monkeypatch, capsys):
    """本轮消息不在列表末尾（同会话后续轮已插入）也必须按 message_id 取回本轮。

    若实现退化成「忽略 ID、直接拿最后一条非空」，本用例即红。
    """
    fake = _FakeServer(
        [{"status": "completed"}],
        [
            OLD_MESSAGE,
            _our_message("第二轮：本轮自己的答案"),
            {
                "message_id": "msg_followup",
                "role": "assistant",
                "content": "第三轮：后续轮的答案",
            },
        ],
    )
    code, captured = _run_probe(monkeypatch, capsys, fake, "--timeout", "30")
    assert code == 0
    assert "第二轮：本轮自己的答案" in captured.out
    assert "第三轮：后续轮的答案" not in captured.out


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "http://probe", code, "boom", hdrs=None, fp=io.BytesIO(b"server said no")
    )


@pytest.mark.parametrize(
    "failure",
    [_http_error(500), TimeoutError("timed out")],
    ids=["http-500", "read-timeout"],
)
def test_message_fetch_failure_exits_2_without_traceback(monkeypatch, capsys, failure):
    """run 已 completed，取消息时接口 500 / 底层读取超时：走 exit 2 合同，不带 traceback。"""
    fake = _FakeServer([{"status": "completed"}], failure)
    code, captured = _run_probe(monkeypatch, capsys, fake, "--timeout", "30")
    assert code == 2
    assert "Traceback" not in captured.err


def test_run_poll_read_timeout_exits_2(monkeypatch, capsys):
    fake = _FakeServer([TimeoutError("timed out")], [])
    code, captured = _run_probe(monkeypatch, capsys, fake, "--timeout", "30")
    assert code == 2
    assert "Traceback" not in captured.err


def test_submission_read_timeout_exits_2(monkeypatch, capsys):
    fake = _FakeServer([], [], submission_error=TimeoutError("timed out"))
    code, captured = _run_probe(monkeypatch, capsys, fake, "--timeout", "30")
    assert code == 2
    assert "Traceback" not in captured.err


def _incomplete_read() -> http.client.IncompleteRead:
    """正文传到一半断开。它属 http.client.HTTPException，不是 OSError 子类。"""
    return http.client.IncompleteRead(b'{"partial":', 120)


@pytest.mark.parametrize("stage", ["create", "submit", "poll", "fetch"])
def test_incomplete_read_exits_2_without_traceback(monkeypatch, capsys, stage: str):
    """四个阶段（建会话/提交/轮询/取消息）的 IncompleteRead 都走 exit 2 合同。"""
    if stage == "create":
        fake = _FakeServer([], [], submission_error=_incomplete_read())
    elif stage == "submit":
        fake = _FakeServer([], [], post_message_error=_incomplete_read())
    elif stage == "poll":
        fake = _FakeServer([_incomplete_read()], [])
    else:
        fake = _FakeServer([{"status": "completed"}], _incomplete_read())
    code, captured = _run_probe(monkeypatch, capsys, fake, "--timeout", "30")
    assert code == 2
    assert "Traceback" not in captured.err


def _http_error_with_boom_body() -> urllib.error.HTTPError:
    """HTTP 错误本身能给出，但读它的正文会再次超时。"""

    class _BoomBody:
        def read(self, *args, **kwargs):
            raise TimeoutError("timed out reading error body")

        def close(self) -> None:
            pass  # addinfourl 是 io 对象，GC 时 __del__ 会调 fp.close()，缺了打印噪音

    return urllib.error.HTTPError(
        "http://probe", 429, "slow down", hdrs=None, fp=_BoomBody()
    )


def test_http_error_body_read_failure_still_exits_2(monkeypatch, capsys):
    """handler 里 exc.read() 再爆炸也不能逃出 except 块（QC 实测 exit 1 + traceback）。"""
    fake = _FakeServer([], [], submission_error=_http_error_with_boom_body())
    code, captured = _run_probe(monkeypatch, capsys, fake, "--timeout", "30")
    assert code == 2
    assert "HTTP 429" in captured.err
    assert "Traceback" not in captured.err
