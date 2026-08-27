"""Decode the ``draft`` field of a finish envelope while it is still arriving.

The continuous episode ends by emitting one JSON object::

    {"status":"completed","draft":"自然语言回答","gaps":[...],"bindings":[...]}

Streaming that object token by token is useless on its own -- the provider
hands back JSON escape sequences, so rendering the raw deltas shows the user
``\\u60a8`` and stray quotes.  This module turns the raw content stream into
the decoded prose of exactly one field, so the answer can be shown as it is
written instead of 24 seconds later in one block.

Deliberately a pure decoder: no IO, no provider knowledge, no run identity.
It is fed raw ``content`` deltas and returns newly decoded characters.  The
caller owns where those characters go.

Fail-closed in three places, because a half-decoded answer is worse than no
streaming at all:

* the envelope prefix must appear within ``_MAX_PREFIX_CHARS`` -- otherwise the
  payload is not the expected shape (recovery prose, a fenced block, a provider
  preamble) and the decoder permanently disarms rather than guessing;
* an unrecognised escape disarms the decoder instead of emitting the raw
  backslash;
* once the closing quote is seen the decoder is done, so trailing envelope
  fields (``gaps``/``bindings``) can never leak into the visible answer.

Reusable outside this repo: any "model returns one JSON object but the user
wants to watch one string field of it" case has the same shape -- structured
output and streaming pull in opposite directions, and this is the seam where
they are reconciled.
"""

from __future__ import annotations

import re


# `{"status":"completed","draft":"` is ~31 chars. A provider that has not shown
# the field within this budget is not emitting the envelope we know how to read.
_MAX_PREFIX_CHARS = 4096

_DRAFT_PREFIX_RE = re.compile(r'"draft"\s*:\s*"')

_SIMPLE_ESCAPES = {
    '"': '"',
    "\\": "\\",
    "/": "/",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
}

_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")

# 双重转义的换行（JSON 里是 `\\n`，解码后是字面两字符 `\n`）与
# ``episode_protocol._normalize_natural_language_layout`` 用同一套还原规则。
# 两处必须一致，否则流式看到的是 `\n` 字面量、最终快照又变成真换行，
# 用户会看到正文在收尾时"跳"一下。
_LITERAL_NEWLINES = ("\\r\\n", "\\n", "\\r")
# 还原时可能被切断的最长前缀（`\r\` 之后还要再等一个 `n`）。
_LITERAL_HOLDBACK = max(len(item) for item in _LITERAL_NEWLINES) - 1


class DraftStreamDecoder:
    """Feed raw content deltas, get decoded ``draft`` prose back.

    ``feed`` returns only the characters decoded from that call, so the caller
    can forward them straight to a transport without tracking offsets.
    """

    def __init__(self) -> None:
        self._prefix = ""
        self._armed = True
        self._started = False
        self._finished = False
        # Escape state that can straddle a chunk boundary.
        self._pending_escape = False
        self._pending_hex = ""
        self._high_surrogate: int | None = None
        # Tail held back because it may be the start of a literal `\n` pair.
        self._literal_tail = ""
        self._emitted_chars = 0

    @property
    def started(self) -> bool:
        """True once the ``draft`` field has been located."""

        return self._started

    @property
    def finished(self) -> bool:
        """True once the field's closing quote has been consumed."""

        return self._finished

    @property
    def emitted_chars(self) -> int:
        return self._emitted_chars

    def feed(self, chunk: str) -> str:
        if not self._armed or self._finished or not chunk:
            return ""
        if not self._started:
            chunk = self._consume_prefix(chunk)
            if not self._started:
                return ""
        decoded = self._decode_body(chunk)
        return self._release(decoded)

    def flush(self) -> str:
        """Release any tail held back for literal-newline reassembly."""

        tail, self._literal_tail = self._literal_tail, ""
        self._emitted_chars += len(tail)
        return tail

    # -- internals -------------------------------------------------------

    def _consume_prefix(self, chunk: str) -> str:
        self._prefix += chunk
        match = _DRAFT_PREFIX_RE.search(self._prefix)
        if match is None:
            if len(self._prefix) > _MAX_PREFIX_CHARS:
                # Not the envelope we know how to read. Stay silent forever
                # rather than stream a guess.
                self._armed = False
                self._prefix = ""
            return ""
        self._started = True
        remainder = self._prefix[match.end() :]
        self._prefix = ""
        return remainder

    def _decode_body(self, chunk: str) -> str:
        out: list[str] = []
        index = 0
        length = len(chunk)
        while index < length:
            if self._pending_hex or (self._pending_escape and self._pending_hex == ""):
                index = self._resume_escape(chunk, index, out)
                continue
            char = chunk[index]
            index += 1
            if char == "\\":
                self._pending_escape = True
                continue
            # 任何非 \uXXXX 的东西都终结了代理对的等待：挂起的高代理这辈子
            # 等不到低代理了，放替换符出来，别把它留在状态里静默吞掉。
            self._flush_surrogate(out)
            if char == '"':
                self._finished = True
                break
            out.append(char)
        if self._finished:
            self._flush_surrogate(out)
        return "".join(out)

    def _flush_surrogate(self, out: list[str]) -> None:
        if self._high_surrogate is not None:
            self._high_surrogate = None
            out.append("�")

    def _resume_escape(self, chunk: str, index: int, out: list[str]) -> int:
        """Consume one escape sequence that may have started in a prior chunk."""

        if self._pending_escape and not self._pending_hex:
            marker = chunk[index]
            index += 1
            if marker == "u":
                # Mark "collecting hex" without consuming a digit yet.
                self._pending_hex = "u"
                return index
            self._pending_escape = False
            simple = _SIMPLE_ESCAPES.get(marker)
            if simple is None:
                # Unknown escape: disarm rather than emit a stray backslash.
                self._armed = False
                self._finished = True
                return len(chunk)
            out.append(simple)
            return index

        while index < len(chunk) and len(self._pending_hex) < 5:
            digit = chunk[index]
            if digit not in _HEX_DIGITS:
                self._armed = False
                self._finished = True
                return len(chunk)
            self._pending_hex += digit
            index += 1
        if len(self._pending_hex) < 5:
            return index
        code = int(self._pending_hex[1:], 16)
        self._pending_hex = ""
        self._pending_escape = False
        out.append(self._decode_code_point(code))
        return index

    def _decode_code_point(self, code: int) -> str:
        high = self._high_surrogate
        if high is not None:
            self._high_surrogate = None
            if 0xDC00 <= code <= 0xDFFF:
                return chr(0x10000 + ((high - 0xD800) << 10) + (code - 0xDC00))
            # A high surrogate not followed by a low one is malformed JSON.
            # Emit the replacement char for it and keep decoding this one.
            return "�" + self._decode_code_point(code)
        if 0xD800 <= code <= 0xDBFF:
            self._high_surrogate = code
            return ""
        if 0xDC00 <= code <= 0xDFFF:
            return "�"
        return chr(code)

    def _release(self, decoded: str) -> str:
        """Apply literal-newline normalisation, holding back a split prefix."""

        buffered = self._literal_tail + decoded
        for literal in _LITERAL_NEWLINES:
            buffered = buffered.replace(literal, "\n")
        if self._finished:
            self._literal_tail = ""
            self._emitted_chars += len(buffered)
            return buffered
        # A trailing backslash may be the first half of a literal `\n`; hold it
        # until the next chunk decides. Only the tail can be ambiguous.
        hold = 0
        while (
            hold < _LITERAL_HOLDBACK
            and hold < len(buffered)
            and buffered[len(buffered) - 1 - hold] == "\\"
        ):
            hold += 1
        if hold:
            self._literal_tail = buffered[len(buffered) - hold :]
            buffered = buffered[: len(buffered) - hold]
        else:
            self._literal_tail = ""
        self._emitted_chars += len(buffered)
        return buffered


__all__ = ["DraftStreamDecoder"]
