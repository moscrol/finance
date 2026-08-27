from __future__ import annotations

import json

import pytest

from intelligence.services.draft_stream import DraftStreamDecoder


def envelope(draft: str) -> str:
    return json.dumps(
        {"status": "completed", "draft": draft, "gaps": [], "bindings": []},
        ensure_ascii=False,
    )


def ascii_envelope(draft: str) -> str:
    """The same envelope with non-ASCII escaped as \\uXXXX, like some providers."""

    return json.dumps(
        {"status": "completed", "draft": draft, "gaps": [], "bindings": []},
        ensure_ascii=True,
    )


def drive(payload: str, size: int) -> str:
    decoder = DraftStreamDecoder()
    out = [decoder.feed(payload[i : i + size]) for i in range(0, len(payload), size)]
    out.append(decoder.flush())
    return "".join(out)


DRAFTS = [
    "明天继续缩量轮动。",
    'A股说"缩量"时，指的是成交额环比回落。',
    "第一段。\n\n- 情景A（高）：继续缩量\n- 情景B（中）：放量断代\n",
    "反斜杠 \\ 与制表 \t 与回车 \r 混排",
    "emoji 😀 与生僻字 𠀋 都要过",
    "",
]


# 逐字节切是最狠的一档：每个转义序列、每个 \uXXXX 的四位十六进制、代理对的
# 两半，都会被切在 chunk 边界上。1/2/3 覆盖 \n（2 字符）与 \uXXXX（6 字符）
# 的各种错位；7 是个与 6 互质的尺寸，专门错开 \uXXXX 的对齐。
@pytest.mark.parametrize("draft", DRAFTS)
@pytest.mark.parametrize("size", [1, 2, 3, 5, 7, 13, 4096])
def test_decodes_identically_at_every_chunk_boundary(draft: str, size: int) -> None:
    assert drive(envelope(draft), size) == draft
    assert drive(ascii_envelope(draft), size) == draft


def test_stops_at_the_closing_quote_so_later_fields_never_leak() -> None:
    decoder = DraftStreamDecoder()
    out = decoder.feed(envelope("正文到此为止。"))

    assert out == "正文到此为止。"
    assert decoder.finished is True
    # gaps/bindings 在同一个 chunk 里，但一个字符都不能进正文。
    assert "gaps" not in out and "bindings" not in out
    # 收尾后继续喂也不再吐字。
    assert decoder.feed('{"more":"x"}') == ""


def test_non_envelope_payload_stays_silent_instead_of_guessing() -> None:
    decoder = DraftStreamDecoder()

    emitted = "".join(decoder.feed(chunk) for chunk in ("这是一段普通散文，", "没有 JSON 信封。"))

    assert emitted == ""
    assert decoder.started is False


def test_disarms_once_the_prefix_budget_is_spent() -> None:
    decoder = DraftStreamDecoder()

    decoder.feed("x" * 5000)
    # 预算花完之后，即便信封真的来了也不再启动——宁可不流，不猜。
    assert decoder.feed(envelope("迟到的正文")) == ""
    assert decoder.started is False


def test_unknown_escape_disarms_rather_than_emitting_a_stray_backslash() -> None:
    decoder = DraftStreamDecoder()

    emitted = decoder.feed('{"draft":"正常\\q异常"')

    assert emitted == "正常"
    assert decoder.finished is True


def test_lone_high_surrogate_does_not_crash_or_emit_a_broken_char() -> None:
    decoder = DraftStreamDecoder()

    emitted = decoder.feed('{"draft":"\\ud83dA"')

    # 孤立高代理不是合法字符：用替换符占位，后面的字符照常解码。
    assert emitted == "�A"
    assert emitted.encode("utf-8")  # 必须可编码，否则传输层会炸


def test_literal_backslash_n_is_normalised_like_the_final_snapshot() -> None:
    """双重转义的换行要和 episode_protocol 的还原规则一致。

    否则流式阶段显示字面 `\\n`，收尾快照换成真换行，正文会在用户眼前跳一下。
    """

    payload = json.dumps(
        {"draft": "第一段\\n\\n第二段"}, ensure_ascii=False
    )

    assert drive(payload, 4096) == "第一段\n\n第二段"
    # 切在 `\` 和 `n` 中间也必须得到同一结果。
    assert drive(payload, 1) == "第一段\n\n第二段"


def test_trailing_backslash_is_held_back_not_emitted_early() -> None:
    decoder = DraftStreamDecoder()

    # `\\` 解码成一个字面反斜杠，它可能是 `\n` 的前半——先扣住。
    first = decoder.feed('{"draft":"尾部\\\\')
    assert first == "尾部"
    # 后面跟的不是 n，说明它就是个反斜杠，flush 时放出来。
    assert decoder.feed('X"') == "\\X"


def test_emitted_chars_counts_what_actually_crossed() -> None:
    decoder = DraftStreamDecoder()

    decoder.feed(envelope("一二三四五"))

    assert decoder.emitted_chars == 5
