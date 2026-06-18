"""Optional LLM refinement of the `ask` 结论 / 交易含义 sections.

The deterministic retrieval skeleton (``ask.py``) always produces a templated
``结论`` / ``交易含义``. When an LLM credential is configured *and* the caller opts
in (``--llm`` / ``AskOptions.use_llm``), this module rewrites just those two
sections from the already-retrieved, citation-numbered evidence — it never adds
new retrieval, never invents companies/numbers, and must keep ``[编号]`` citations.

Design constraints:
- **Graceful degrade is the default.** If no provider/key is detected, or the
  call/parse fails, :func:`refine` returns ``None`` and the caller keeps the
  template. Behaviour with no key is therefore identical to before.
- **Zero extra dependencies.** Uses ``urllib`` against an OpenAI-compatible
  ``/chat/completions`` endpoint, so it works for DeepSeek / Moonshot(Kimi) /
  DashScope(Qwen) / Zhipu(GLM) / OpenAI and any compatible gateway without
  installing an SDK.
- **No secrets in code.** Keys come only from environment variables.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

DEFAULT_LLM_TIMEOUT = 60

# (provider, api_key_env, default_base_url, default_model). First env var that is
# set wins. A generic LLM_API_KEY (+ LLM_BASE_URL / LLM_MODEL) overrides all.
_PROVIDERS: tuple[tuple[str, str, str, str], ...] = (
    ("deepseek", "DEEPSEEK_API_KEY", "https://api.deepseek.com/v1", "deepseek-chat"),
    ("moonshot", "MOONSHOT_API_KEY", "https://api.moonshot.cn/v1", "moonshot-v1-8k"),
    ("kimi", "KIMI_API_KEY", "https://api.moonshot.cn/v1", "moonshot-v1-8k"),
    ("dashscope", "DASHSCOPE_API_KEY", "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
    ("qwen", "QWEN_API_KEY", "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
    ("zhipu", "ZHIPU_API_KEY", "https://open.bigmodel.cn/api/paas/v4", "glm-4-plus"),
    ("glm", "GLM_API_KEY", "https://open.bigmodel.cn/api/paas/v4", "glm-4-plus"),
    ("openai", "OPENAI_API_KEY", "https://api.openai.com/v1", "gpt-4o-mini"),
)


@dataclass
class LLMProvider:
    name: str
    api_key: str
    base_url: str
    model: str


def detect_provider(model_override: str | None = None) -> LLMProvider | None:
    """Resolve an LLM provider from environment variables, or ``None``."""
    generic = os.environ.get("LLM_API_KEY")
    if generic:
        base = os.environ.get("LLM_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
        model = model_override or os.environ.get("LLM_MODEL") or "gpt-4o-mini"
        return LLMProvider(name="custom", api_key=generic, base_url=base, model=model)
    for name, env_key, base, default_model in _PROVIDERS:
        key = os.environ.get(env_key)
        if key:
            base_url = os.environ.get("LLM_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or base
            model = model_override or os.environ.get("LLM_MODEL") or default_model
            return LLMProvider(name=name, api_key=key, base_url=base_url, model=model)
    return None


_SYSTEM_PROMPT = (
    "你是严谨的A股题材研究助手。任务：仅依据用户给出的「带编号证据」改写两段——"
    "【结论】和【交易含义】。硬性要求："
    "1) 只能使用证据中出现的事实/公司/数字，严禁引入证据里没有的内容；"
    "2) 每条关键判断后必须标注引用编号（如 [S1] [G3] [R2]），可多个；"
    "3) 不确定或证据不足时要显式说明「证据不足/仅盘面驱动」，不得编造；"
    "4) 不输出买卖指令，结尾以「（非投资建议）」收尾；"
    "5) 严格输出 JSON：{\"结论\": [\"...\"], \"交易含义\": [\"...\"]}，每个数组 1-4 条短句，不要输出额外文字。"
)


def _build_user_prompt(query: str, theme: str, evidence_text: str) -> str:
    return (
        f"题材问题：{query}\n"
        f"命中主题：{theme}\n\n"
        f"以下是已检索到的带编号证据（结论与交易含义只能据此改写）：\n"
        f"{evidence_text}\n\n"
        f"请据此输出 JSON。"
    )


def _post_chat(provider: LLMProvider, messages: list[dict], timeout: int, temperature: float = 0.2) -> str:
    url = provider.base_url.rstrip("/") + "/chat/completions"
    payload = {"model": provider.model, "messages": messages, "temperature": temperature}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"]


def complete(
    messages: list[dict],
    model_override: str | None = None,
    timeout: int = DEFAULT_LLM_TIMEOUT,
    temperature: float = 0.2,
) -> tuple[str | None, "LLMProvider | None", str]:
    """Generic OpenAI-compatible chat call shared across services.

    Returns ``(content, provider, reason)``. On any failure (no key, HTTP error,
    network error) ``content`` is ``None`` and ``reason`` explains why so callers
    can degrade gracefully — same contract as :func:`refine_or_reason`.
    """
    provider = detect_provider(model_override)
    if provider is None:
        return None, None, (
            "未配置 LLM key。设置 DEEPSEEK_API_KEY / MOONSHOT_API_KEY / "
            "DASHSCOPE_API_KEY / ZHIPU_API_KEY / OPENAI_API_KEY 或通用 "
            "LLM_API_KEY(+LLM_BASE_URL,+LLM_MODEL) 即可启用"
        )
    try:
        content = _post_chat(provider, messages, timeout, temperature)
    except urllib.error.HTTPError as exc:  # pragma: no cover - network
        return None, provider, f"LLM 调用 HTTP {exc.code}"
    except Exception as exc:  # pragma: no cover - network
        return None, provider, f"LLM 调用失败（{type(exc).__name__}）"
    return content, provider, ""


def _post_chat_message(
    provider: LLMProvider,
    messages: list[dict],
    timeout: int,
    temperature: float = 0.2,
    tools: list[dict] | None = None,
    tool_choice: str | dict | None = None,
) -> dict:
    """Like :func:`_post_chat` but returns the full assistant *message* dict.

    The message may contain ``tool_calls`` (OpenAI-compatible function calling)
    in addition to / instead of ``content`` — needed to drive an agent loop."""
    url = provider.base_url.rstrip("/") + "/chat/completions"
    payload: dict = {"model": provider.model, "messages": messages, "temperature": temperature}
    if tools:
        payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body["choices"][0]["message"]


def chat_with_tools(
    messages: list[dict],
    tools: list[dict],
    model_override: str | None = None,
    timeout: int = DEFAULT_LLM_TIMEOUT,
    temperature: float = 0.2,
    tool_choice: str | dict | None = "auto",
) -> tuple[dict | None, "LLMProvider | None", str]:
    """One OpenAI-compatible chat round-trip *with tools available*.

    Returns ``(message, provider, reason)``; the agent loop inspects
    ``message["tool_calls"]`` to decide whether to dispatch tools or treat
    ``message["content"]`` as the final answer. On any failure ``message`` is
    ``None`` and ``reason`` explains why so the caller degrades gracefully."""
    provider = detect_provider(model_override)
    if provider is None:
        return None, None, (
            "未配置 LLM key。设置 DEEPSEEK_API_KEY / MOONSHOT_API_KEY / "
            "DASHSCOPE_API_KEY / ZHIPU_API_KEY / OPENAI_API_KEY 或通用 "
            "LLM_API_KEY(+LLM_BASE_URL,+LLM_MODEL) 即可启用"
        )
    try:
        msg = _post_chat_message(provider, messages, timeout, temperature, tools=tools, tool_choice=tool_choice)
    except urllib.error.HTTPError as exc:  # pragma: no cover - network
        return None, provider, f"LLM 调用 HTTP {exc.code}"
    except Exception as exc:  # pragma: no cover - network
        return None, provider, f"LLM 调用失败（{type(exc).__name__}）"
    return msg, provider, ""


def _extract_json(text: str) -> dict | None:
    text = text.strip()
    # strip ```json fences if present
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        brace = re.search(r"\{.*\}", text, re.DOTALL)
        if brace:
            text = brace.group(0)
    try:
        obj = json.loads(text)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _as_lines(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


@dataclass
class RefineResult:
    conclusion: list[str]
    implication: list[str]
    provider: str
    model: str


def refine(
    query: str,
    theme: str,
    evidence_text: str,
    model_override: str | None = None,
    timeout: int = DEFAULT_LLM_TIMEOUT,
) -> RefineResult | None:
    """Rewrite 结论 / 交易含义 from retrieved evidence. Returns ``None`` to degrade.

    The second element of failures is surfaced to the caller via
    :func:`refine_or_reason` so the warning can explain *why* it degraded.
    """
    out, _ = refine_or_reason(query, theme, evidence_text, model_override, timeout)
    return out


def refine_or_reason(
    query: str,
    theme: str,
    evidence_text: str,
    model_override: str | None = None,
    timeout: int = DEFAULT_LLM_TIMEOUT,
) -> tuple[RefineResult | None, str]:
    provider = detect_provider(model_override)
    if provider is None:
        return None, (
            "未配置 LLM key，结论/交易含义降级为模板。设置 DEEPSEEK_API_KEY / "
            "MOONSHOT_API_KEY / DASHSCOPE_API_KEY / ZHIPU_API_KEY / OPENAI_API_KEY "
            "或通用 LLM_API_KEY(+LLM_BASE_URL,+LLM_MODEL) 即可启用精修"
        )
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_prompt(query, theme, evidence_text)},
    ]
    try:
        content = _post_chat(provider, messages, timeout)
    except urllib.error.HTTPError as exc:  # pragma: no cover - network
        return None, f"LLM 调用 HTTP {exc.code}，已降级为模板"
    except Exception as exc:  # pragma: no cover - network
        return None, f"LLM 调用失败（{type(exc).__name__}），已降级为模板"
    obj = _extract_json(content)
    if not obj:
        return None, "LLM 返回无法解析为 JSON，已降级为模板"
    conclusion = _as_lines(obj.get("结论") or obj.get("conclusion"))
    implication = _as_lines(obj.get("交易含义") or obj.get("implication") or obj.get("trading_implication"))
    if not conclusion and not implication:
        return None, "LLM 返回缺少 结论/交易含义 字段，已降级为模板"
    return (
        RefineResult(
            conclusion=conclusion or ["（LLM 未给出结论，沿用模板）"],
            implication=implication or ["（LLM 未给出交易含义，沿用模板）"],
            provider=provider.name,
            model=provider.model,
        ),
        "",
    )


# --- 有机合成（compose）：把多源证据融成一段连贯的分析师口吻回答 ----------------
# 与 refine 的区别：refine 只重写 结论/交易含义 两段（仍是六段模板）；compose 让
# LLM 把 盘面/图谱/证据/语义召回/题材模块 有机融合成一段自由形态、带内联引用的回答，
# 更接近"对话式分析"。仍严守：只用给定证据、不编造、带引用编号、（非投资建议）。
_SYNTHESIS_SYSTEM_PROMPT = (
    "你是资深A股题材研究员，回答风格像一位严谨的分析师在对话中讲清一个题材。"
    "下面给你的是已经检索好的多源证据：盘面信号(S)、知识图谱概念与公司分层(G)、"
    "证据条目(R)、wiki 语义召回(W)、题材模块产出。请把它们【有机融合】成一段自然、"
    "连贯的回答，而不是逐段填模板。硬性要求："
    "1) 只能使用证据中出现的事实/公司/数字，严禁引入证据里没有的内容；信息不足就直说"
    "「证据不足/仅盘面驱动」，绝不编造公司、数字或催化；"
    "2) 关键判断、公司、数字、催化之后必须用方括号标注引用编号（如 [S1][R4][G2]），可多个；"
    "3) 结构要自然流畅（短段落即可，不要堆一堆 markdown 标题），但内容上要覆盖："
    "一句话结论 → 当前盘面状态 → 产业链与公司分层（务必区分 核心/真实暴露 与 graph_only 低置信"
    "待验证 两类，后者只能当预期差线索、不可当基本面依据）→ 关键催化与证据 → 分歧与风险 → 接下来该跟踪什么；"
    "4) 不输出任何买卖指令，结尾以「（非投资建议）」收尾；"
    "5) 直接输出回答正文，不要输出 JSON，不要复述本提示，不要附加无关解释。"
)


@dataclass
class SynthesisResult:
    answer: str
    provider: str
    model: str


def _build_synthesis_prompt(query: str, theme: str, evidence_text: str, citation_legend: str) -> str:
    legend = f"\n\n## 引用图例（编号 → 来源，回答里请沿用这些编号）\n{citation_legend}" if citation_legend else ""
    return (
        f"用户问题：{query}\n"
        f"命中主题：{theme}\n\n"
        f"以下是已检索到的多源证据（你的回答只能据此展开）：\n"
        f"{evidence_text}{legend}\n\n"
        f"请据此有机融合成一段分析师口吻的回答。"
    )


def build_synthesis_messages(
    query: str, theme: str, evidence_text: str, citation_legend: str = ""
) -> list[dict]:
    """Assemble the turn-1 synthesis ``[system, user]`` messages.

    Exposed so the multi-turn driver can keep the exact same evidence-laden first
    turn and then append follow-ups on top of it (grounding stays anchored to the
    evidence given here — follow-ups must not introduce new sources)."""
    return [
        {"role": "system", "content": _SYNTHESIS_SYSTEM_PROMPT},
        {"role": "user", "content": _build_synthesis_prompt(query, theme, evidence_text, citation_legend)},
    ]


# 追问时附在用户问题前的薄约束：复用首轮已给证据、不引入新事实、保留引用编号。
_FOLLOWUP_NUDGE = (
    "（追问，请仅基于本次对话前面已经给出的多源证据回答：不要引入证据里没有的新公司/"
    "数字/催化，继续用 [编号] 标注引用；若已有证据不足以回答就直说「证据不足」，"
    "不要编造。结尾仍以「（非投资建议）」收尾。）\n\n"
)


def followup_user_content(question: str) -> str:
    """Wrap a follow-up question with the grounding nudge sent to the model.

    The raw ``question`` is what the caller should display in a transcript; the
    wrapped form is what actually goes into the ``messages`` list."""
    return _FOLLOWUP_NUDGE + question


def synthesize_messages(
    messages: list[dict],
    model_override: str | None = None,
    timeout: int = DEFAULT_LLM_TIMEOUT,
    temperature: float = 0.3,
) -> tuple[SynthesisResult | None, str]:
    """Run a synthesis turn from a full ``messages`` list (system + history).

    Shared by single-turn :func:`synthesize` and the multi-turn driver. Returns
    ``(result, reason)``; on any failure ``result`` is ``None`` and ``reason``
    explains why so the caller degrades gracefully."""
    provider = detect_provider(model_override)
    if provider is None:
        return None, (
            "未配置 LLM key，有机合成降级为模板。设置 DEEPSEEK_API_KEY / MOONSHOT_API_KEY / "
            "DASHSCOPE_API_KEY / ZHIPU_API_KEY / OPENAI_API_KEY 或通用 LLM_API_KEY 即可启用"
        )
    try:
        content = _post_chat(provider, messages, timeout, temperature)
    except urllib.error.HTTPError as exc:  # pragma: no cover - network
        return None, f"LLM 合成 HTTP {exc.code}，已降级为模板"
    except Exception as exc:  # pragma: no cover - network
        return None, f"LLM 合成失败（{type(exc).__name__}），已降级为模板"
    text = (content or "").strip()
    if not text:
        return None, "LLM 合成返回空内容，已降级为模板"
    return SynthesisResult(answer=text, provider=provider.name, model=provider.model), ""


def synthesize(
    query: str,
    theme: str,
    evidence_text: str,
    citation_legend: str = "",
    model_override: str | None = None,
    timeout: int = DEFAULT_LLM_TIMEOUT,
    temperature: float = 0.3,
) -> tuple[SynthesisResult | None, str]:
    """Compose a free-form, citation-grounded answer from retrieved evidence.

    Returns ``(result, reason)``. On any failure (no key / HTTP / network / empty)
    ``result`` is ``None`` and ``reason`` explains why, so the caller degrades to
    the deterministic six-section template — identical behaviour to no-key today.
    """
    messages = build_synthesis_messages(query, theme, evidence_text, citation_legend)
    return synthesize_messages(
        messages, model_override=model_override, timeout=timeout, temperature=temperature
    )
