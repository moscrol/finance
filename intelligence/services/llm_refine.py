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
from dataclasses import dataclass

DEFAULT_LLM_TIMEOUT = int(os.environ.get("LLM_TIMEOUT", "60"))

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
    "你是资深A股题材研究员，回答风格像一位严谨的分析师在对话中讲清一个题材。"
    "下面给你的是已经检索好的多源证据：盘面信号(S)、知识图谱概念与公司分层(G)、"
    "证据条目(R)、wiki 语义召回(W)、题材模块产出。请把它们【有机融合】成一段自然、"
    "连贯的回答，而不是逐段填模板。你的底层思考要像 daily-agent：先判断市场正在定价什么，"
    "再判断题材/个股处在什么生命周期，最后才谈后续空间。硬性要求："
    "1) 只能使用证据中出现的事实/公司/数字，严禁引入证据里没有的内容；信息不足就直说"
    "「证据不足/仅盘面驱动」，绝不编造公司、数字或催化；"
    "2) 关键判断、公司、数字、催化之后必须用方括号标注引用编号（如 [S1][R4][G2]），可多个；"
    "3) 先在内部写出核心矛盾句：这家公司真实业务是什么，市场正在交易什么预期，最大的证据缺口或反证是什么；"
    "所有视角都必须服务这个核心矛盾，禁止按公司本体、盘面、二阶导、反证逐项填空；"
    "每一段都要回答这个事实改变了什么判断，比如改变了对空间、生命周期、资金选择、证据硬度或替代表达的判断；"
    "4) 结构要自然流畅（短段落即可，不要堆一堆 markdown 标题），但内容上要覆盖："
    "一句话结论 → 市场/板块/个股三层资金传导 → 全量盘面数据的正反推导（每个关键数据要说明支持什么、"
    "反证什么，尤其解释强板块弱个股/个股反弹但市场缩量/情绪回落的含义）→ 逻辑生命周期（新出现/旧逻辑唤醒/升温验证/加速定价/"
    "高位分歧/衰退观察/证伪退出，结合 priority、强势股、触发信号、新高、涨停、双红、加权强度等证据）"
    "→ 产业链与公司分层（务必区分 核心/真实暴露 与 graph_only 低置信待验证 两类，后者只能当预期差线索、"
    "不可当基本面依据）→ 关键催化与证据 → 二阶导/替代标的/产业瓶颈 → 分歧与风险 → 接下来该跟踪什么；"
    "如果证据里有 D2 客户证据硬度数据块，必须区分硬证据、候选证据、弱证据和反证/缺口；"
    "如果证据里有 D3 二阶导研究队列数据块，必须把 P0/P1/P2 转译成自然语言的研究判断，不能机械照抄；"
    "如果证据里有 D4 主线题材结构数据块，必须用它判断主线连续性、核心板块、cycle_status、启动/顺势/分歧/消亡，"
    "并区分真正双红/增量启动与缩量强修复/存量抱团；"
    "5) 对“上涨空间/怎么看/深挖”类问题，必须回答：它是领先核心、同步确认、后排补涨、二阶段回流、"
    "高低切承接还是高位兑现；同时必须回答市场正在奖励谁、抛弃谁、犹豫谁。如果证据缺失，要明确缺了哪类 daily-agent 数据，而不是跳过；"
    "6) 输出前必须在内部做一次质检和反驳：检查是否漏掉公司本体、产业链暴露、证据层、大盘/情绪/板块/个股、生命周期、二阶导、反证和条件化结论；"
    "再模拟严格用户追问“是否模板化、是否孤立看个股、证据是否够硬、是否找到更优表达”，若有缺口先补写进最终稿；"
    "7) 证据中带〔历史基线〕标注的 W 条目与 V 回检块里的旧判断只能当先验，不得原样当作当前事实："
    "引用前必须用当下盘面数据（S/D 块）核验，并对上期判断给出四态对照——支持/削弱/无变化/信息不足；"
    "核验数据缺失时明确写「历史基线未经当下数据核验」；"
    "8) 升级/降级/证伪条件必须写成组合门槛（至少两条信号同现，或主信号+确认信号搭配），"
    "禁止单一信号直接触发结论切换；"
    "9) 不输出任何买卖指令，结尾以「（非投资建议）」收尾；"
    "10) 直接输出回答正文，不要输出 JSON，不要复述本提示，不要附加质检过程或审稿过程。"
)


@dataclass
class SynthesisResult:
    answer: str
    provider: str
    model: str


def _build_synthesis_prompt(
    query: str,
    theme: str,
    evidence_text: str,
    citation_legend: str,
    quality_context: object | None = None,
    experience_guidance: str = "",
    exemplar_guidance: str = "",
) -> str:
    legend = f"\n\n## 引用图例（编号 → 来源，回答里请沿用这些编号）\n{citation_legend}" if citation_legend else ""
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
        f"请据此有机融合成一段分析师口吻的回答。"
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
    # 网络抖动（连接被重置/DNS 瞬断等 URLError）重试一次再降级：合成是整条回答的
    # 可读性关键，单次瞬断不值得整答退回模板。HTTP 4xx/5xx 不重试（重试大概率同样失败）。
    last_exc: Exception | None = None
    content = None
    for attempt in range(2):
        try:
            content = _post_chat(provider, messages, timeout, temperature)
            break
        except urllib.error.HTTPError as exc:  # pragma: no cover - network
            return None, f"LLM 合成 HTTP {exc.code}，已降级为模板"
        except Exception as exc:  # pragma: no cover - network
            last_exc = exc
            if attempt == 0:
                time.sleep(2)
    if content is None and last_exc is not None:
        detail = str(getattr(last_exc, "reason", last_exc))[:120]
        return None, f"LLM 合成失败（{type(last_exc).__name__}: {detail}），已降级为模板"
    text = (content or "").strip()
    if not text:
        return None, "LLM 合成返回空内容，已降级为模板"
    return SynthesisResult(answer=text, provider=provider.name, model=provider.model), ""


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
) -> tuple[SynthesisResult | None, str]:
    """Run draft -> shadow-user critique/rewrite for compose answers.

    The first call creates the grounded draft. The second call receives the same
    evidence, the draft, and a reviewer prompt, then returns only the revised
    final answer. If the review pass fails, keep the draft rather than dropping
    back to the deterministic template.
    """
    draft, reason = synthesize_messages(
        messages,
        model_override=model_override,
        timeout=timeout,
        temperature=temperature,
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
    try:
        content = _post_chat(provider, review_messages, timeout, review_temperature)
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
