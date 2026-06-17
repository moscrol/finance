"""Optional vision backend for the 飞书 bot's image (multimodal) questions.

The text ``ask`` pipeline answers a *string* query. To support image questions
(B-S4) we add a thin vision layer: given raw image bytes, ask a vision-capable,
OpenAI-compatible model to distill the image into a **short retrieval query**
(题材词 / 个股名 / 核心问题), which the caller then feeds into the existing
``ask`` workflow. The image itself is never persisted.

Design constraints (mirrors :mod:`intelligence.services.llm_refine`):
- **Graceful degrade is the default.** If no vision provider/key is detected, or
  the call fails, :func:`describe_image` returns ``None`` and the caller shows a
  friendly "未配置视觉模型" notice. Behaviour with no key is a no-op.
- **Zero extra dependencies.** Uses ``urllib`` against an OpenAI-compatible
  ``/chat/completions`` endpoint with an ``image_url`` data-URL part, so it works
  for OpenAI / DashScope(Qwen-VL) / Zhipu(GLM-4V) / Moonshot vision and any
  compatible gateway without installing an SDK. Reuses ``llm_refine._post_chat``
  so there is a single HTTP path to maintain.
- **No secrets in code.** Keys come only from environment variables.
- **lark_oapi-free.** Pure function of bytes -> Optional[str]; unit-testable.
"""

from __future__ import annotations

import base64
import os
import urllib.error

from intelligence.services.llm_refine import (
    DEFAULT_LLM_TIMEOUT,
    LLMProvider,
    _post_chat,
)

# (provider, api_key_env, default_base_url, default_vision_model). First env var
# that is set wins. A generic VISION_API_KEY (+ VISION_BASE_URL / VISION_MODEL)
# overrides all; failing that a generic LLM_API_KEY gateway is reused.
_VISION_PROVIDERS: tuple[tuple[str, str, str, str], ...] = (
    ("openai", "OPENAI_API_KEY", "https://api.openai.com/v1", "gpt-4o-mini"),
    ("dashscope", "DASHSCOPE_API_KEY", "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-vl-plus"),
    ("qwen", "QWEN_API_KEY", "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-vl-plus"),
    ("zhipu", "ZHIPU_API_KEY", "https://open.bigmodel.cn/api/paas/v4", "glm-4v-flash"),
    ("glm", "GLM_API_KEY", "https://open.bigmodel.cn/api/paas/v4", "glm-4v-flash"),
    ("moonshot", "MOONSHOT_API_KEY", "https://api.moonshot.cn/v1", "moonshot-v1-8k-vision-preview"),
    ("kimi", "KIMI_API_KEY", "https://api.moonshot.cn/v1", "moonshot-v1-8k-vision-preview"),
)

# Upper bound on the distilled query we hand to ``ask`` (defensive: a vision
# model occasionally rambles despite the prompt).
_MAX_QUERY_CHARS = 200

_VISION_SYSTEM_PROMPT = (
    "你是严谨的A股题材研究助手。用户发来一张图片，可能是行情/K线截图、研报或新闻"
    "截图、公告或表格。你的任务：提取图中与投资题材最相关的关键信息，凝练成一句可"
    "直接用于检索的简短中文查询。只能描述图中确实出现的内容，不得编造个股或数字。"
)

_VISION_USER_PROMPT = (
    "请输出一句最能代表这张图核心题材/问题的简短中文检索查询，"
    "聚焦题材词、个股名或核心问题（例如「液冷 温控 渗透率」「寒武纪 业绩预增」）。"
    "只输出查询本身，不要解释、不要前后缀。"
)


def sniff_image_mime(data: bytes) -> str | None:
    """Best-effort image MIME sniff from magic bytes; ``None`` if not an image."""
    if not data:
        return None
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:2] == b"BM":
        return "image/bmp"
    return None


def detect_vision_provider(model_override: str | None = None) -> LLMProvider | None:
    """Resolve a vision-capable provider from environment variables, or ``None``.

    Priority: explicit ``VISION_API_KEY`` gateway > generic ``LLM_API_KEY``
    gateway (reused with a vision model) > the first ``_VISION_PROVIDERS`` entry
    whose key env var is set. ``model_override`` (CLI ``--vision-model``) and
    ``VISION_MODEL`` win over the provider default.
    """
    vision_key = os.environ.get("VISION_API_KEY")
    if vision_key:
        base = (
            os.environ.get("VISION_BASE_URL")
            or os.environ.get("OPENAI_BASE_URL")
            or "https://api.openai.com/v1"
        )
        model = model_override or os.environ.get("VISION_MODEL") or "gpt-4o-mini"
        return LLMProvider(name="vision", api_key=vision_key, base_url=base, model=model)

    generic = os.environ.get("LLM_API_KEY")
    if generic:
        base = (
            os.environ.get("VISION_BASE_URL")
            or os.environ.get("LLM_BASE_URL")
            or os.environ.get("OPENAI_BASE_URL")
            or "https://api.openai.com/v1"
        )
        model = model_override or os.environ.get("VISION_MODEL") or os.environ.get("LLM_MODEL") or "gpt-4o-mini"
        return LLMProvider(name="custom", api_key=generic, base_url=base, model=model)

    for name, env_key, base, default_model in _VISION_PROVIDERS:
        key = os.environ.get(env_key)
        if key:
            base_url = os.environ.get("VISION_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or base
            model = model_override or os.environ.get("VISION_MODEL") or default_model
            return LLMProvider(name=name, api_key=key, base_url=base_url, model=model)
    return None


def describe_image(
    image_bytes: bytes,
    mime: str | None = None,
    *,
    prompt: str | None = None,
    model: str | None = None,
    timeout: int = DEFAULT_LLM_TIMEOUT,
) -> str | None:
    """Distill an image into a short retrieval query, or ``None`` to degrade.

    Returns ``None`` (no exception) when: no vision key is configured, the input
    is empty/not an image, or the HTTP call / parse fails — so the bot keeps
    running and the caller can show a friendly notice.
    """
    if not image_bytes:
        return None
    provider = detect_vision_provider(model)
    if provider is None:
        return None
    mime = mime or sniff_image_mime(image_bytes) or "image/jpeg"
    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"
    messages = [
        {"role": "system", "content": _VISION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt or _VISION_USER_PROMPT},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        },
    ]
    try:
        content = _post_chat(provider, messages, timeout)
    except urllib.error.HTTPError:  # pragma: no cover - network
        return None
    except Exception:  # pragma: no cover - network
        return None
    if not isinstance(content, str):
        return None
    query = content.strip().strip("`").strip()
    # collapse newlines a chatty model might emit; keep it a single query line
    query = " ".join(query.split())
    if not query:
        return None
    return query[:_MAX_QUERY_CHARS]
