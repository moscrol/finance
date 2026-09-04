"""LLM token 用量的取值与估算（纯函数，无 IO；INDEX #23）。

三件事放在一个小模块里，让 ``llm_refine``（HTTP 路）、``grok_cli_judge``（CLI 路）
与 ``runtime/glm_agent_runtime``（写手 ModelTurn）共用同一份取值逻辑——
services 不得 import runtime（``scripts/layer_audit.py``），所以纯函数下沉到这里，
runtime 反向调用。

1. ``token_usage_counts``：OpenAI 兼容 ``usage`` 块的双命名取值
   （``prompt_tokens/completion_tokens`` 与 ``input_tokens/output_tokens``）。
2. ``cli_payload_token_usage``：grok CLI ``--output-format json`` 顶层 payload 的
   用量取值。**2026-09-05 探针实测**（``~/.finance-runtime/judge-usage-probe-2026-09-05/
   raw.json``，grok 1.0.5 / grok-4.6 / read-only 沙箱）payload 顶层带
   ``usage={input_tokens, output_tokens, reasoning_tokens, cache_read_input_tokens,
   cache_creation_input_tokens, total_tokens}`` 与 ``modelUsage={<model>: {inputTokens,
   outputTokens, ...}}``（camelCase）。先读 ``usage``，缺了再退到 ``modelUsage`` 求和。
   注意 grok 的 ``input_tokens`` **不含** ``cache_read_input_tokens``
   （``total = input + output + cache_read``，样本 128/19326 ≈ 0.7%），本模块照原样
   记 ``input_tokens``，缓存命中部分不计——与 GLM ``prompt_tokens``（含 cached）口径
   略有出入，报表按输入价计，偏差方向是**少算**缓存命中的那部分。
3. ``estimate_token_usage``：CLI payload 不带用量时的字符估算，**只作回落**，调用方
   必须标 ``usage_source=estimated``。

估算常数的依据（2026-09-05 一次校准，同一段判官提示词 2951 字符：中文 1142 /
其他 1809）：

- GLM API（服务端实际 ``glm-5.3``）返回 ``prompt_tokens=1222`` → 整体 2.415 字符/token；
  可见补全 207 字符（中文 113 / 其他 94）对应 286−180(reasoning)=106 个可见 token。
  用这两点解 ``tokens = cjk/K_cjk + other/K_other`` 得 K_cjk≈1.26、K_other≈5.7。
- grok CLI 同题可见输出 203 字符（中文 87 / 其他 116）对应 970−858=112 个可见 token
  → 1.81 字符/token（grok 分词对中文更细）。

取整为 ``CJK_CHARS_PER_TOKEN=1.3``、``OTHER_CHARS_PER_TOKEN=5.0``。回代误差：GLM 提示词
估 1240 vs 实 1222（+1.5%）；GLM 可见补全估 106 vs 实 106（0%）；grok 可见输出估 90
vs 实 112（−20%）。**估算只覆盖可见字符**：reasoning token（GLM 样本 180、grok 样本
858）与 CLI 自带的上下文（grok 实际 ``input_tokens=19326``，是提示词字符估算 1240 的
15.6 倍）都看不见——这正是估算值必须带 ``estimated`` 标记、且报表要单列估算占比的
原因。校准原始数据：``~/.finance-runtime/judge-usage-probe-2026-09-05/calibration.json``。
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence

USAGE_SOURCE_API = "api"
USAGE_SOURCE_CLI = "cli"
USAGE_SOURCE_ESTIMATED = "estimated"
USAGE_SOURCES = frozenset({USAGE_SOURCE_API, USAGE_SOURCE_CLI, USAGE_SOURCE_ESTIMATED})

CJK_CHARS_PER_TOKEN = 1.3
OTHER_CHARS_PER_TOKEN = 5.0

# CJK 统一表意文字 + 中文标点 + 全角符号；估算按中文占比加权，见模块 docstring。
_CJK_CHAR = re.compile(
    r"[\u3000-\u303f\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]"
)


def _non_negative_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value >= 0 else None


def token_usage_counts(
    usage: Mapping[str, object] | None,
) -> tuple[int | None, int | None]:
    """从 OpenAI 兼容的 ``usage`` 块取 (input, output) token 数，兼容两套命名。

    非负 int 才算数（bool 排除——``True`` 是 int 的子类），取不到返回 None，
    不猜 0：0 与「没回」在成本报表里是两件事。
    """

    if not isinstance(usage, Mapping):
        return None, None

    def token_value(*names: str) -> int | None:
        for name in names:
            parsed = _non_negative_int(usage.get(name))
            if parsed is not None:
                return parsed
        return None

    return (
        token_value("input_tokens", "prompt_tokens"),
        token_value("output_tokens", "completion_tokens"),
    )


def _model_usage_totals(
    model_usage: object,
) -> tuple[int | None, int | None]:
    """``modelUsage={<model>: {inputTokens, outputTokens}}`` 跨模型求和。"""

    if not isinstance(model_usage, Mapping):
        return None, None
    input_total: int | None = None
    output_total: int | None = None
    for entry in model_usage.values():
        if not isinstance(entry, Mapping):
            continue
        input_value = _non_negative_int(entry.get("inputTokens"))
        output_value = _non_negative_int(entry.get("outputTokens"))
        if input_value is not None:
            input_total = (input_total or 0) + input_value
        if output_value is not None:
            output_total = (output_total or 0) + output_value
    return input_total, output_total


def cli_payload_token_usage(
    payload: object,
) -> tuple[int | None, int | None]:
    """grok CLI JSON payload 的 (input, output) token 数；没有就 (None, None)。

    顶层 ``usage`` 优先（snake_case，双命名），退到 ``modelUsage``（camelCase 求和）。
    payload 不是 dict（例如 CLI 直接吐了判官对象或裸文本）→ (None, None)。
    """

    if not isinstance(payload, Mapping):
        return None, None
    input_tokens, output_tokens = token_usage_counts(payload.get("usage"))  # type: ignore[arg-type]
    if input_tokens is None and output_tokens is None:
        input_tokens, output_tokens = _model_usage_totals(payload.get("modelUsage"))
    return input_tokens, output_tokens


def estimate_token_count(text: str) -> int:
    """按中文占比加权的字符数估算 token 数；空文本为 0。常数依据见模块 docstring。"""

    if not text:
        return 0
    cjk = len(_CJK_CHAR.findall(text))
    other = len(text) - cjk
    return int(round(cjk / CJK_CHARS_PER_TOKEN + other / OTHER_CHARS_PER_TOKEN))


def _message_text(message: Mapping[str, object]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if content is None:
        return ""
    return json.dumps(content, ensure_ascii=False)


def estimate_token_usage(
    messages: Sequence[Mapping[str, object]],
    content: str | None,
) -> tuple[int, int]:
    """(input, output) 的字符估算：input 数全部 messages 正文，output 数 ``content``。

    只是回落：调用方拿到它就必须记 ``usage_source=estimated``。
    """

    prompt_chars = "".join(_message_text(message) for message in messages)
    return estimate_token_count(prompt_chars), estimate_token_count(content or "")
