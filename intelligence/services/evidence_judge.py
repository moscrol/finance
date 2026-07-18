"""知识库召回的 LLM 语义相关性闸门（词面闸门之上的第二道闸）。

closed-loop 检索的词面重叠闸门有能力上限：问「科创50的支撑点位」时，「支撑」
在「兰花科创：煤价反弹提供基本面支撑」里也出现，词面重叠成立但语义完全无关，
这类召回会进入结论/反方线索污染证据链。本模块用一次低温 LLM 批量裁定补上
语义判断：

- 输入问题 + 候选召回（标题+摘录），LLM 只输出保留编号，不改写任何内容；
- fail-open：LLM 未配置/超时/输出不合法时返回 ``None``，调用方保持原有行为，
  确定性主链不因 LLM 失败而丢证据；
- 被丢弃的召回进入 discarded 桶并记 warning，可回查不静默。

灰度：``ASK_EVIDENCE_JUDGE=off|auto|on``，默认 ``auto``（配置了 LLM key 才生效，
未配置时零行为变化）。
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Sequence

from intelligence.services import llm_refine

ENV_MODE = "ASK_EVIDENCE_JUDGE"
MODE_OFF = "off"
MODE_AUTO = "auto"
MODE_ON = "on"
_VALID_MODES = {MODE_OFF, MODE_AUTO, MODE_ON}
DEFAULT_TIMEOUT = 12
MAX_CANDIDATES = 16
_EXCERPT_CHARS = 160

_SYSTEM_PROMPT = (
    "你是金融研究证据审核员。给定用户问题和知识库召回候选，"
    "判断每条候选与问题是否语义相关：候选讨论的主体或主题必须与问题一致，"
    "仅个别词语相同（如问指数「支撑位」而候选是某公司「基本面支撑」）不算相关。"
    "拿不准时保留。只输出 JSON（无 markdown 代码栏）："
    '{"keep": [编号], "reason": "一句话说明丢弃了什么"}'
)


def judge_mode() -> str:
    mode = str(os.environ.get(ENV_MODE) or MODE_AUTO).strip().lower()
    return mode if mode in _VALID_MODES else MODE_AUTO


def should_judge() -> bool:
    mode = judge_mode()
    if mode == MODE_OFF:
        return False
    if mode == MODE_ON:
        return True
    return bool(llm_refine.detect_providers(None))


def judge_relevance(
    query: str,
    candidates: Sequence[tuple[str, str]],
    *,
    timeout: int = DEFAULT_TIMEOUT,
    complete_fn=None,
) -> tuple[set[int], str] | None:
    """按语义相关性裁定候选，返回 ``(保留下标集合, 理由)``。

    ``candidates`` 为 ``(title, excerpt)`` 序列（下标即编号）。任何失败返回
    ``None``，调用方保持全量保留。
    """
    if not candidates:
        return None
    complete = complete_fn or llm_refine.complete
    numbered = "\n".join(
        f"{index}. {title}：{excerpt[:_EXCERPT_CHARS]}"
        for index, (title, excerpt) in enumerate(candidates[:MAX_CANDIDATES])
    )
    content, _provider, _reason = complete(
        [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"用户问题：{query}\n\n候选召回：\n{numbered}",
            },
        ],
        timeout=timeout,
        temperature=0.0,
    )
    if not content:
        return None
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if match is None:
        return None
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    raw_keep = payload.get("keep")
    if not isinstance(raw_keep, list):
        return None
    keep: set[int] = set()
    for value in raw_keep:
        if isinstance(value, int) and 0 <= value < len(candidates):
            keep.add(value)
    # 超出裁定窗口的候选一律保留（宁多勿漏）。
    keep.update(range(MAX_CANDIDATES, len(candidates)))
    reason = str(payload.get("reason") or "").strip()
    return keep, reason
