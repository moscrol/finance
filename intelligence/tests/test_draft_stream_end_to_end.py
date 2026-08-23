"""整链验收：假 SSE → chat_with_tools → GLMModelClient → run_store。

单测分别钉住了解码器、传输层、publisher。这个文件回答的是它们**接起来**之后
的那个问题：客户端把收到的 ``text.delta`` 按顺序拼起来，是不是正好等于模型
写的那段正文——不多一个字（重复正文），不少一个字（截断）。

用的正文是 2026-08-23 run_20260823_221135_424228 里模型真实吐出的那段的形状：
中文为主、带 markdown 结构、带引号和百分号。
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from intelligence.runtime.glm_agent_runtime import GLMModelClient
from intelligence.services import llm_refine
from intelligence.services.draft_publisher import RunDraftDeltaPublisher
from intelligence.services.run_store import RunStore


DRAFT = (
    "**继续缩量轮动、缩圈抱团**，不构成方向性断代。\n\n"
    "- 情景A（高）：大盘继续缩量，量比维持80%档\n"
    "- 情景B（中）：显著放量至20000亿上方，构成断代日候选\n"
    '- 情景C（低）：缩量跌破箱体下沿，"共建"失败\n\n'
    "失效条件：医药大幅破位、创新药成交额占比台阶性回落。（非投资建议）"
)

ENVELOPE = json.dumps(
    {"status": "completed", "draft": DRAFT, "gaps": [], "bindings": []},
    ensure_ascii=False,
)

PROVIDER = llm_refine.LLMProvider(
    name="zhipu",
    api_key="k",
    base_url="https://example.invalid/v4",
    model="glm-5.2",
)


class _ChunkedResponse:
    """把整个信封切成 size 字节一片，模拟 provider 的 SSE 流。"""

    def __init__(self, payload: str, size: int) -> None:
        pieces = [payload[i : i + size] for i in range(0, len(payload), size)]
        self._lines = [
            f"data: {json.dumps({'choices': [{'delta': {'content': p}}]}, ensure_ascii=False)}\n".encode()
            for p in pieces
        ]
        self._lines.append(b"data: [DONE]\n")

    def __enter__(self) -> "_ChunkedResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def __iter__(self):
        return iter(self._lines)


@pytest.mark.parametrize("size", [1, 3, 11, 64, 4096])
def test_client_reassembles_exactly_the_draft(tmp_path: Path, size: int) -> None:
    run_store = RunStore("e2e-stream", root=tmp_path / "runs")
    run = run_store.create_run("明天你怎么看", "ask", session_id="conv_1")
    publisher = RunDraftDeltaPublisher(
        run_store=run_store,
        run_id=run.run_id,
        conversation_id="conv_1",
        message_id="msg_1",
    )
    client = GLMModelClient(
        providers=(PROVIDER,),
        on_draft_delta=publisher.publish,
    )

    with (
        mock.patch.object(llm_refine, "_reserve_llm_call"),
        mock.patch.object(llm_refine, "_record_llm_call"),
        mock.patch.object(llm_refine, "_budget_rejection", return_value=None),
        mock.patch.object(
            llm_refine, "_insufficient_budget_reason", return_value=None
        ),
        mock.patch(
            "urllib.request.urlopen",
            return_value=_ChunkedResponse(ENVELOPE, size),
        ),
    ):
        turn = client.complete(messages=[{"role": "user", "content": "q"}], tools=[], timeout=30.0)

    # 1) agent loop 拿到的仍是完整信封，与非流式同形。
    assert json.loads(turn.content)["draft"] == DRAFT
    assert turn.error == ""

    # 2) 客户端按到达顺序拼接 text.delta，得到的正是那段正文。
    events = [
        event
        for event in run_store.load_stream_events(run.run_id)
        if event["event_type"] == "text.delta"
    ]
    narrative = "".join(event["payload"]["delta"] for event in events)
    assert narrative == DRAFT, "拼出来的正文与模型写的不一致"

    # 3) 一个字都不能多——重复正文是这条链最贵的失败形状。
    assert narrative.count("失效条件：") == 1
    assert len(narrative) == len(DRAFT)

    # 4) 信封的其它字段一个字节都不许进正文。
    assert "bindings" not in narrative and "completed" not in narrative


def test_without_a_sink_nothing_is_published(tmp_path: Path) -> None:
    """没接 sink 就是改动前的老路：一条 text.delta 都不产生。"""

    run_store = RunStore("e2e-nosink", root=tmp_path / "runs")
    run = run_store.create_run("q", "ask", session_id="conv_1")
    client = GLMModelClient(providers=(PROVIDER,))

    with (
        mock.patch.object(llm_refine, "_reserve_llm_call"),
        mock.patch.object(llm_refine, "_record_llm_call"),
        mock.patch.object(llm_refine, "_budget_rejection", return_value=None),
        mock.patch.object(
            llm_refine, "_insufficient_budget_reason", return_value=None
        ),
        mock.patch.object(
            llm_refine,
            "_post_chat_message",
            return_value={"content": ENVELOPE},
        ),
        mock.patch.object(
            llm_refine,
            "_post_chat_message_stream",
            side_effect=AssertionError("没 sink 不该走流式"),
        ),
    ):
        turn = client.complete(messages=[{"role": "user", "content": "q"}], tools=[], timeout=30.0)

    assert json.loads(turn.content)["draft"] == DRAFT
    assert run_store.load_stream_events(run.run_id) == []
