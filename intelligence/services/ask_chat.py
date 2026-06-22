"""Multi-turn (追问) driver on top of the single-shot 有机合成 (``--compose``).

This is the first step from "one-shot 问答" toward an agent: it gives the LLM
**conversation memory** so the user can dig deeper across turns.

Boundary (deliberately *not* a full agent loop yet):
- **Turn 1** runs the full multi-source retrieval (S/G/R/W/modules) + 有机合成,
  exactly like ``answer_query(compose=True)``.
- **Follow-up turns** reuse turn-1's evidence + the running conversation history
  and let the LLM continue — they do **not** re-route / re-retrieve per turn, and
  they must stay grounded in the already-retrieved evidence (no new sources, keep
  ``[编号]`` citations). Per-turn tool-calling is a future phase.

Graceful degrade is preserved: with no LLM key (or a failed turn-1), the
conversation cannot start and reports the template/degrade reason instead of
crashing — identical no-key behaviour to the rest of the ``ask`` stack.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from intelligence.services import llm_refine
from intelligence.services.ask import AskOptions, AskResult, answer_query


@dataclass
class ConversationTurn:
    """One exchange in a chat session (the user's question + the answer)."""

    question: str
    answer: str
    provider: str | None = None
    # True when the answer was LLM-composed; False when degraded (no key / error).
    composed: bool = False
    warning: str = ""


class AskConversation:
    """Stateful multi-turn session over a single ``ask`` retrieval.

    Usage::

        conv = AskConversation(AskOptions(query="液冷", ...))
        first = conv.start()              # full retrieval + 合成
        second = conv.ask("强瑞和冰轮哪个证据更硬")  # reuse evidence + history
    """

    def __init__(
        self,
        options: AskOptions,
        model_override: str | None = None,
        timeout: int = 60,
    ) -> None:
        # compose is mandatory for chat — multi-turn只在有机合成模式下成立。
        self.options = replace(options, compose=True)
        self.model_override = model_override
        self.timeout = timeout
        # None until a successful turn-1 establishes the grounded evidence context.
        self.messages: list[dict] | None = None
        self.first_result: AskResult | None = None
        self.turns: list[ConversationTurn] = []

    @property
    def ready(self) -> bool:
        """True once turn-1 synthesised successfully and follow-ups are possible."""
        return self.messages is not None

    def start(self) -> ConversationTurn:
        """Run turn-1: full multi-source retrieval + 有机合成."""
        result = answer_query(self.options)
        self.first_result = result
        if result.synthesis and result.synthesis_messages:
            self.messages = list(result.synthesis_messages)
            turn = ConversationTurn(
                question=self.options.query,
                answer=result.synthesis,
                provider=result.llm_provider,
                composed=True,
            )
        else:
            # No LLM key / synthesis failed → can't enter multi-turn. Surface the
            # degrade reason; the structured template is still available via
            # render_answer(self.first_result).
            warn = next(
                (w for w in result.warnings if "LLM" in w or "key" in w or "降级" in w),
                "未启用 LLM 合成（缺少 key 或调用失败），无法进入多轮对话；已退回模板检索。",
            )
            turn = ConversationTurn(
                question=self.options.query,
                answer=result.synthesis or "（未启用有机合成，无法进入多轮对话——见下方模板检索结果）",
                provider=result.llm_provider,
                composed=False,
                warning=warn,
            )
        self.turns.append(turn)
        return turn

    def ask(self, question: str) -> ConversationTurn:
        """Ask a follow-up, reusing turn-1 evidence + full conversation history."""
        if self.messages is None:
            turn = ConversationTurn(
                question=question,
                answer="（对话未就绪：首轮未成功合成，无法追问。请先成功跑通首轮，或检查 LLM key。）",
                composed=False,
                warning="conversation not started / turn-1 degraded",
            )
            self.turns.append(turn)
            return turn

        # Append the follow-up (wrapped with the grounding nudge) and synthesise.
        self.messages.append({"role": "user", "content": llm_refine.followup_user_content(question)})
        composed, reason = llm_refine.synthesize_messages(
            self.messages, model_override=self.model_override, timeout=self.timeout
        )
        if composed is None:
            # Roll back the unanswered user turn so the history stays consistent
            # and the user can retry.
            self.messages.pop()
            turn = ConversationTurn(
                question=question,
                answer=f"（追问失败，已降级：{reason}）",
                composed=False,
                warning=reason,
            )
        else:
            self.messages.append({"role": "assistant", "content": composed.answer})
            turn = ConversationTurn(
                question=question,
                answer=composed.answer,
                provider=composed.provider,
                composed=True,
            )
        self.turns.append(turn)
        return turn
