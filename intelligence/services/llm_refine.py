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
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, replace

DEFAULT_LLM_TIMEOUT = int(os.environ.get("LLM_TIMEOUT", "60"))
DEFAULT_SYNTHESIS_MAX_TOKENS = int(os.environ.get("LLM_SYNTHESIS_MAX_TOKENS", "2200"))
DEFAULT_SYNTHESIS_MAX_CHARS = int(os.environ.get("LLM_SYNTHESIS_MAX_CHARS", "16000"))
_ALLOWED_FINISH_REASONS = {"stop", "length", "content_filter", "tool_calls", "function_call"}

# (provider, api_key_env, default_base_url, default_model). First env var that is
# set wins. A generic LLM_API_KEY (+ LLM_BASE_URL / LLM_MODEL) overrides all.
_PROVIDERS: tuple[tuple[str, str, str, str], ...] = (
    ("deepseek", "DEEPSEEK_API_KEY", "https://api.deepseek.com/v1", "deepseek-chat"),
    ("moonshot", "MOONSHOT_API_KEY", "https://api.moonshot.cn/v1", "moonshot-v1-8k"),
    ("kimi", "KIMI_API_KEY", "https://api.moonshot.cn/v1", "moonshot-v1-8k"),
    ("dashscope", "DASHSCOPE_API_KEY", "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
    ("qwen", "QWEN_API_KEY", "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
    ("zhipu", "ZHIPU_API_KEY", "https://open.bigmodel.cn/api/paas/v4", "glm-5.2"),
    ("glm", "GLM_API_KEY", "https://open.bigmodel.cn/api/paas/v4", "glm-5.2"),
    ("openai", "OPENAI_API_KEY", "https://api.openai.com/v1", "gpt-4o-mini"),
)


@dataclass
class LLMProvider:
    name: str
    api_key: str = field(repr=False)
    base_url: str
    model: str


_PROVIDER_OVERRIDE: ContextVar[LLMProvider | None] = ContextVar(
    "llm_provider_override",
    default=None,
)


class LLMStreamCancelled(RuntimeError):
    pass


class LLMStreamingUnsupported(RuntimeError):
    pass


class LLMDeadlineExceeded(RuntimeError):
    pass


class LLMOutputTooLong(RuntimeError):
    pass


@dataclass(frozen=True)
class Deadline:
    expires_at: float

    @classmethod
    def from_timeout(cls, timeout: float) -> "Deadline":
        return cls(time.monotonic() + max(0.0, float(timeout)))

    def remaining(self) -> float:
        return max(0.0, self.expires_at - time.monotonic())

    def require_remaining(self, minimum: float = 0.0) -> float:
        remaining = self.remaining()
        if remaining < minimum:
            raise LLMDeadlineExceeded()
        return remaining


def detect_provider(model_override: str | None = None) -> LLMProvider | None:
    """Resolve an LLM provider from environment variables, or ``None``."""
    configured = _PROVIDER_OVERRIDE.get()
    if configured is not None:
        if model_override:
            return replace(configured, model=model_override)
        return configured
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


@contextmanager
def provider_override(provider: LLMProvider) -> Iterator[None]:
    token = _PROVIDER_OVERRIDE.set(provider)
    try:
        yield
    finally:
        _PROVIDER_OVERRIDE.reset(token)


def synthesis_thinking_disabled() -> bool:
    configured = os.environ.get("LLM_SYNTHESIS_THINKING")
    if configured is None:
        return os.environ.get("LLM_THINKING", "").lower() != "enabled"
    return configured.lower() == "disabled"


def _stable_finish_reason(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    reason = value.strip()
    if reason in _ALLOWED_FINISH_REASONS:
        return reason
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
    if os.environ.get("LLM_THINKING") == "disabled":
        payload["thinking"] = {"type": "disabled"}
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


def _post_chat_synthesis(
    provider: LLMProvider,
    messages: list[dict],
    timeout: int,
    temperature: float,
    max_tokens: int,
    max_chars: int,
) -> tuple[str, str | None]:
    url = provider.base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": provider.model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if synthesis_thinking_disabled():
        payload["thinking"] = {"type": "disabled"}
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    choice = body["choices"][0]
    content = choice["message"]["content"]
    if len(content) > max_chars:
        raise LLMOutputTooLong()
    return content, _stable_finish_reason(choice.get("finish_reason"))


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
    if os.environ.get("LLM_THINKING") == "disabled":
        payload["thinking"] = {"type": "disabled"}
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
    "你是资深 A 股研究员。只消费给定的 AnswerSpec 和证据，不能增加其中没有的事实、"
    "公司、数字或催化。先服从证据中的「问答编排计划」和「输出契约」。"
    "L1 固定结论配方：数据截止日、直接定性、最强证据、主要风险、条件边界、下一步验证；"
    "L2 弹性段型由问题决定，结构和篇幅由问题复杂度决定，不得为了显得完整而套用深度研究模板。"
    "个股/题材深挖先在内部写出核心矛盾句；所有视角都必须服务这个核心矛盾，"
    "禁止按公司本体、盘面、二阶导、反证逐项填空；每一段都要回答这个事实改变了什么判断。"
    "内部自检清单只用于防漏项，不得机械输出：daily-agent 的生命周期；"
    "市场/板块/个股三层资金传导；全量盘面数据的正反推导；强板块弱个股；"
    "领先核心、同步确认、后排补涨；市场正在奖励谁、抛弃谁、犹豫谁；二阶导；"
    "主线题材结构数据、主线连续性、缩量强修复/存量抱团。"
    "输出前必须在内部做一次质检和反驳，检查是否模板化、是否孤立看个股、"
    "证据是否够硬、是否有更优表达；不要附加质检过程或审稿过程。"
    "历史基线和回检只作 prior，必须用当前证据核验；缺数按“标明假设的区间推断→"
    "替代锚点→显式 gap”处理。升级/降级/证伪必须是组合门槛，不能由单一信号触发。"
    "涉及 T+1、明天或下一交易日时，只能使用证据中“交易日历约束”给出的日期，"
    "严禁自然日加一天或猜日期。不得在正文显示任何内部引用编号；严禁输出原始 JSON、"
    "路径、表名、检索状态、证据计数、warning 或内部字段。L1/L2/L3/L4 必须分别转译"
    "为行业资料、公司基础资料、公告等硬证据、盘面信号；graph_only、replay、Daily Review"
    " 等工程名也不得原样出现。不输出买卖指令，结尾以「（非投资建议）」收尾。"
)


@dataclass
class SynthesisResult:
    answer: str
    provider: str
    model: str
    fallback_reason: str | None = None
    finish_reason: str | None = None


def _build_synthesis_prompt(
    query: str,
    theme: str,
    evidence_text: str,
    citation_legend: str,
    quality_context: object | None = None,
    experience_guidance: str = "",
    exemplar_guidance: str = "",
) -> str:
    legend = (
        "\n\n## 内部引用图例（只用于事实核验；最终回答不得显示编号）\n"
        f"{citation_legend}"
        if citation_legend
        else ""
    )
    quality_block = ""
    if quality_context is not None and hasattr(quality_context, "to_prompt_block"):
        quality_block = f"\n\n{quality_context.to_prompt_block()}"
    experience_block = (
        f"\n\n## 历史经验卡片（用于避免重复犯错）\n{experience_guidance}"
        if experience_guidance
        else ""
    )
    exemplar_block = (
        "\n\n## 高分样板（few-shot 锚：只学结构、叙事组织和论证方式；"
        "严禁照抄样板里的结论、数据或个股判断，回答只能基于上方证据）\n"
        f"{exemplar_guidance}"
        if exemplar_guidance
        else ""
    )
    return (
        f"用户问题：{query}\n"
        f"命中主题：{theme}\n\n"
        f"以下是已检索到的多源证据（你的回答只能据此展开）：\n"
        f"{evidence_text}{legend}{quality_block}{experience_block}{exemplar_block}\n\n"
        "请据此有机融合成一段分析师口吻的回答。默认控制在 1200–1800 个中文字符；"
        "最多 8 个短段落；不得重复来源说明、风险和验证步骤。"
    )


def build_synthesis_messages(
    query: str,
    theme: str,
    evidence_text: str,
    citation_legend: str = "",
    quality_context: object | None = None,
    experience_guidance: str = "",
    exemplar_guidance: str = "",
) -> list[dict]:
    """Assemble the turn-1 synthesis ``[system, user]`` messages.

    Exposed so the multi-turn driver can keep the exact same evidence-laden first
    turn and then append follow-ups on top of it (grounding stays anchored to the
    evidence given here — follow-ups must not introduce new sources)."""
    return [
        {"role": "system", "content": _SYNTHESIS_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": _build_synthesis_prompt(
                query,
                theme,
                evidence_text,
                citation_legend,
                quality_context,
                experience_guidance,
                exemplar_guidance,
            ),
        },
    ]


# 追问时附在用户问题前的薄约束：复用首轮已给证据、不引入新事实、不暴露内部编号。
_FOLLOWUP_NUDGE = (
    "（追问，请仅基于本次对话前面已经给出的多源证据回答：不要引入证据里没有的新公司/"
    "数字/催化，不要显示内部编号、字段名或工程诊断；若已有证据不足以回答就直说「证据不足」，"
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
    *,
    deadline: Deadline | None = None,
    max_tokens: int = DEFAULT_SYNTHESIS_MAX_TOKENS,
    max_chars: int = DEFAULT_SYNTHESIS_MAX_CHARS,
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
    shared_deadline = deadline or Deadline.from_timeout(timeout)
    # 网络抖动（连接被重置/DNS 瞬断等 URLError）重试一次再降级：合成是整条回答的
    # 可读性关键，单次瞬断不值得整答退回模板。HTTP 4xx/5xx 不重试（重试大概率同样失败）。
    last_exc: Exception | None = None
    content = None
    finish_reason: str | None = None
    for attempt in range(2):
        try:
            remaining = shared_deadline.require_remaining(1)
            content, finish_reason = _post_chat_synthesis(
                provider,
                messages,
                remaining,
                temperature,
                max_tokens,
                max_chars,
            )
            break
        except urllib.error.HTTPError as exc:  # pragma: no cover - network
            return None, f"LLM 合成 HTTP {exc.code}，已降级为模板"
        except LLMDeadlineExceeded:
            return None, "LLM 合成超过共享截止时间，已降级为模板"
        except LLMOutputTooLong:
            return None, "LLM 合成输出超长，已降级为模板"
        except Exception as exc:  # pragma: no cover - network
            last_exc = exc
            if attempt == 0:
                remaining = shared_deadline.remaining()
                if remaining < 1:
                    return None, "LLM 合成超过共享截止时间，已降级为模板"
                time.sleep(min(2, max(0.0, remaining - 0.5)))
    if content is None and last_exc is not None:
        return None, f"LLM 合成失败（{type(last_exc).__name__}），已降级为模板"
    text = (content or "").strip()
    if not text:
        return None, "LLM 合成返回空内容，已降级为模板"
    if finish_reason != "stop":
        if finish_reason == "length":
            return None, "LLM 合成响应被截断，已降级为模板"
        return None, "LLM 合成未正常停止，已降级为模板"
    return (
        SynthesisResult(
            answer=text,
            provider=provider.name,
            model=provider.model,
            finish_reason=finish_reason,
        ),
        "",
    )


def _post_chat_stream(
    provider: LLMProvider,
    messages: list[dict],
    timeout: int,
    temperature: float,
    on_delta: Callable[[str], None],
    on_connected: Callable[[], None] | None,
    is_cancelled: Callable[[], bool] | None,
    deadline: Deadline,
    max_tokens: int,
    max_chars: int,
) -> tuple[str, str | None]:
    url = provider.base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": provider.model,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
        "max_tokens": max_tokens,
    }
    if synthesis_thinking_disabled():
        payload["thinking"] = {"type": "disabled"}
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
        method="POST",
    )
    chunks: list[str] = []
    output_chars = 0
    finish_reason: str | None = None
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if on_connected is not None:
            on_connected()
        for raw_line in response:
            if deadline.remaining() <= 0:
                raise LLMDeadlineExceeded()
            if is_cancelled is not None and is_cancelled():
                raise LLMStreamCancelled()
            line = raw_line.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                if finish_reason is None and chunks:
                    finish_reason = "stop"
                break
            try:
                event = json.loads(data)
                choice = event["choices"][0]
                finish_reason = _stable_finish_reason(choice.get("finish_reason")) or finish_reason
                delta = choice["delta"].get("content")
            except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                continue
            if isinstance(delta, str) and delta:
                output_chars += len(delta)
                if output_chars > max_chars:
                    raise LLMOutputTooLong()
                on_delta(delta)
                chunks.append(delta)
    if not chunks:
        raise LLMStreamingUnsupported()
    return "".join(chunks), finish_reason


def synthesize_messages_stream(
    messages: list[dict],
    *,
    on_delta: Callable[[str], None],
    on_connected: Callable[[], None] | None = None,
    on_finish_reason: Callable[[str | None], None] | None = None,
    is_cancelled: Callable[[], bool] | None = None,
    model_override: str | None = None,
    timeout: int = DEFAULT_LLM_TIMEOUT,
    temperature: float = 0.3,
    deadline: Deadline | None = None,
    max_tokens: int = DEFAULT_SYNTHESIS_MAX_TOKENS,
    max_chars: int = DEFAULT_SYNTHESIS_MAX_CHARS,
) -> tuple[SynthesisResult | None, str]:
    provider = detect_provider(model_override)
    if provider is None:
        return None, (
            "未配置 LLM key，有机合成降级为模板。设置 DEEPSEEK_API_KEY / MOONSHOT_API_KEY / "
            "DASHSCOPE_API_KEY / ZHIPU_API_KEY / OPENAI_API_KEY 或通用 LLM_API_KEY 即可启用"
        )
    shared_deadline = deadline or Deadline.from_timeout(timeout)
    try:
        remaining = shared_deadline.require_remaining(1)
        content, finish_reason = _post_chat_stream(
            provider,
            messages,
            remaining,
            temperature,
            on_delta,
            on_connected,
            is_cancelled,
            shared_deadline,
            max_tokens,
            max_chars,
        )
        if on_finish_reason is not None:
            on_finish_reason(finish_reason)
    except LLMStreamCancelled:
        raise
    except LLMDeadlineExceeded:
        return None, "LLM 流式合成超过共享截止时间，已降级为模板"
    except LLMOutputTooLong:
        return None, "LLM 流式合成输出超长，已降级为模板"
    except urllib.error.HTTPError as exc:
        if exc.code not in {400, 404, 405, 415, 422, 501}:
            return None, f"LLM 流式合成 HTTP {exc.code}，已降级为模板"
        if shared_deadline.remaining() < 1:
            return None, "LLM 流式合成超过共享截止时间，已降级为模板"
        fallback, reason = synthesize_messages(
            messages,
            model_override=model_override,
            timeout=max(1, int(shared_deadline.remaining())),
            temperature=temperature,
            deadline=shared_deadline,
            max_tokens=max_tokens,
            max_chars=max_chars,
        )
        if fallback is not None:
            on_delta(fallback.answer)
            fallback.fallback_reason = "stream_unsupported"
        return fallback, reason
    except LLMStreamingUnsupported:
        if shared_deadline.remaining() < 1:
            return None, "LLM 流式合成超过共享截止时间，已降级为模板"
        fallback, reason = synthesize_messages(
            messages,
            model_override=model_override,
            timeout=max(1, int(shared_deadline.remaining())),
            temperature=temperature,
            deadline=shared_deadline,
            max_tokens=max_tokens,
            max_chars=max_chars,
        )
        if fallback is not None:
            on_delta(fallback.answer)
            fallback.fallback_reason = "stream_unsupported"
        return fallback, reason
    except Exception as exc:  # pragma: no cover - network
        return None, f"LLM 流式合成失败（{type(exc).__name__}），已降级为模板"
    if not content.strip():
        return None, "LLM 流式合成返回空内容，已降级为模板"
    if finish_reason != "stop":
        if finish_reason == "length":
            return None, "LLM 流式合成响应被截断，已降级为模板"
        return None, "LLM 流式合成未正常停止，已降级为模板"
    return (
        SynthesisResult(
            answer=content,
            provider=provider.name,
            model=provider.model,
            finish_reason=finish_reason,
        ),
        "",
    )


_SELF_REVIEW_REVISION_PROMPT = (
    "请把上一条回答当作初稿，先在内部扮演严格的用户影子审稿人做二次反驳，然后重写最终稿。"
    "反驳重点：是否模板化、是否孤立看个股、是否漏掉大盘/情绪/板块/个股相对强度、证据是否够硬、"
    "生命周期四问是否完整、是否说明市场正在奖励谁/抛弃谁/犹豫谁、是否给出二阶导和更优表达、"
    "是否有升级/降级/证伪条件且写成了组合门槛（≥2 条信号同现或主信号+确认信号；单信号触发要改写）、"
    "对〔历史基线〕/上期判断是否给出了四态对照（支持/削弱/无变化/信息不足）。"
    "还要检查全文有没有先抓住核心矛盾；每个视角是否都服务这条矛盾，而不是按清单填空；"
    "每段是否回答了“这个事实改变了什么判断”。"
    "如果证据不足或数据块没有给出某项指标，必须明确写缺口，不能编造。"
    "只输出修订后的最终回答正文，不要输出审稿过程、评分、JSON 或提示词。结尾仍以「（非投资建议）」收尾。"
)


# 质检闸门 WARN 回灌修订（修订版在前契约）：把 output_review 的 WARN 意见送回同一段
# 对话做一轮定向修订，用户拿到的是可直接引用的修订版全文，审查意见退居附录。
_GATE_REVISION_PROMPT = (
    "输出质检闸门对上一条回答给出以下 WARN 意见，请针对性修订：\n{notes}\n"
    "要求：只修意见相关的问题，不改动无关内容；仍只能使用已给证据，证据不足处显式写缺口而不是补写内容；"
    "只输出修订后的最终回答正文，不输出修订说明，结尾仍以「（非投资建议）」收尾。"
)


def gate_revision_user_content(warn_notes: list[str]) -> str:
    """Build the user turn that feeds output-review WARN notes back for revision."""
    notes = "\n".join(f"- {n}" for n in warn_notes)
    return _GATE_REVISION_PROMPT.format(notes=notes)


def synthesize_messages_with_review(
    messages: list[dict],
    model_override: str | None = None,
    timeout: int = DEFAULT_LLM_TIMEOUT,
    temperature: float = 0.3,
    review_temperature: float = 0.2,
    *,
    deadline: Deadline | None = None,
    max_tokens: int = DEFAULT_SYNTHESIS_MAX_TOKENS,
    max_chars: int = DEFAULT_SYNTHESIS_MAX_CHARS,
) -> tuple[SynthesisResult | None, str]:
    """Run draft -> shadow-user critique/rewrite for compose answers.

    The first call creates the grounded draft. The second call receives the same
    evidence, the draft, and a reviewer prompt, then returns only the revised
    final answer. If the review pass fails, keep the draft rather than dropping
    back to the deterministic template.
    """
    shared_deadline = deadline or Deadline.from_timeout(timeout)
    draft, reason = synthesize_messages(
        messages,
        model_override=model_override,
        timeout=timeout,
        temperature=temperature,
        deadline=shared_deadline,
        max_tokens=max_tokens,
        max_chars=max_chars,
    )
    if draft is None:
        return None, reason

    provider = detect_provider(model_override)
    if provider is None:
        return draft, ""
    review_messages = [
        *messages,
        {"role": "assistant", "content": draft.answer},
        {"role": "user", "content": _SELF_REVIEW_REVISION_PROMPT},
    ]
    if shared_deadline.remaining() < 1:
        draft.fallback_reason = "review_timeout"
        return draft, "LLM 二次自审因共享截止时间不足而跳过，保留初稿并标记降级"
    try:
        content = _post_chat(
            provider,
            review_messages,
            shared_deadline.require_remaining(1),
            review_temperature,
        )
    except LLMDeadlineExceeded:
        draft.fallback_reason = "review_timeout"
        return draft, "LLM 二次自审超过共享截止时间，保留初稿并标记降级"
    except Exception as exc:
        return draft, f"LLM 二次自审失败（{type(exc).__name__}），保留初稿并标记降级"
    revised = (content or "").strip()
    if not revised:
        return draft, "LLM 二次自审返回空内容，保留初稿并标记降级"
    return SynthesisResult(answer=revised, provider=provider.name, model=provider.model), ""


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
