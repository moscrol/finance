"""端到端钉住一条不变量：正文不得出现两遍。

流式让同一段正文有了两个出口——模型写的时候由 ``draft_publisher`` 推，收尾时
编排层还会整段再推一次。两个出口都开着，用户就会看到答案被写两遍；两个都关，
正文一个字都出不去。这个文件只测这条边界，不测流式的其它性质。
"""

from __future__ import annotations

from pathlib import Path

from intelligence.services.draft_publisher import RunDraftDeltaPublisher
from intelligence.services.run_store import RunStore
from intelligence.runtime.conversation_orchestrator import TurnOrchestrator
from intelligence.services.conversation_store import ConversationStore


def build(tmp_path: Path) -> tuple[TurnOrchestrator, RunStore, str]:
    run_store = RunStore("dup-test", root=tmp_path / "runs")
    orchestrator = TurnOrchestrator(
        repo_root=tmp_path / "runtime",
        conversation_store=ConversationStore(
            "dup-test", root=tmp_path / "conversations"
        ),
        run_store=run_store,
    )
    run = run_store.create_run("明天你怎么看", "ask", session_id="conv_1")
    return orchestrator, run_store, run.run_id


def test_orchestrator_sees_that_the_transport_already_streamed(tmp_path) -> None:
    orchestrator, run_store, run_id = build(tmp_path)
    publisher = RunDraftDeltaPublisher(
        run_store=run_store,
        run_id=run_id,
        conversation_id="conv_1",
        message_id="msg_1",
    )

    assert orchestrator._client_already_streamed(run_id, "msg_1") is False

    publisher.publish("模型正在写的正文。")

    assert orchestrator._client_already_streamed(run_id, "msg_1") is True


def test_another_message_in_the_same_run_is_not_confused(tmp_path) -> None:
    """同一个 run 里换一条消息，必须重新开始判断。"""

    orchestrator, run_store, run_id = build(tmp_path)
    RunDraftDeltaPublisher(
        run_store=run_store,
        run_id=run_id,
        conversation_id="conv_1",
        message_id="msg_1",
    ).publish("第一条消息的正文。")

    assert orchestrator._client_already_streamed(run_id, "msg_1") is True
    assert orchestrator._client_already_streamed(run_id, "msg_2") is False


def test_every_bulk_text_delta_site_goes_through_the_guard() -> None:
    """结构性回归：不许有第二条绕过闸的整段推送路径。

    2026-08-23 live 实测（:8797 run_20260823_232446_100587）就栽在这上面——
    闸只接进了 ask 车道的闭包，continuous 车道那条 ``continuous:text`` 直接
    调 ``self._emit``，832 个分片共 1229 字之后又整段推了 1222 字，正文出去
    两遍。紧随其后的 ``answer.snapshot`` 在同一秒内把它盖掉，肉眼几乎看不见，
    所以逐个发射点数一遍才是有效的检查，盯着屏幕看没用。

    这里数的是**源码里 text.delta 的发射点**，而不是某一次调用的行为：新增
    车道时如果又直接调 ``_emit``，这条会红。
    """

    import ast
    import inspect

    from intelligence.runtime import conversation_orchestrator as module

    tree = ast.parse(inspect.getsource(module))
    # 闸自己那次 _emit 当然是直接调的，它就是唯一被允许的出口。
    guard = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_emit_bulk_text_delta"
    )
    allowed = {n.lineno for n in ast.walk(guard) if isinstance(n, ast.Call)}

    raw_emits: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or node.lineno in allowed:
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "_emit"):
            continue
        if any(
            isinstance(arg, ast.Constant) and arg.value == "text.delta"
            for arg in node.args
        ):
            raw_emits.append(node.lineno)

    assert raw_emits == [], (
        "这些行直接用 _emit 推 text.delta，绕过了 _emit_bulk_text_delta 的"
        f"「已流过就不再整段推」判断：{raw_emits}"
    )


def test_unreadable_stream_log_falls_back_to_emitting(tmp_path, monkeypatch) -> None:
    """读不到就当没流过——宁可重复一次，不可整段吞掉。"""

    orchestrator, run_store, run_id = build(tmp_path)
    monkeypatch.setattr(
        run_store,
        "load_stream_events",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk gone")),
    )

    assert orchestrator._client_already_streamed(run_id, "msg_1") is False
