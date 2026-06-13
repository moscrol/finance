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


def _post_chat(provider: LLMProvider, messages: list[dict], timeout: int) -> str:
    url = provider.base_url.rstrip("/") + "/chat/completions"
    payload = {"model": provider.model, "messages": messages, "temperature": 0.2}
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
