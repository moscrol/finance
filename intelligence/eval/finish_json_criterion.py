"""FINAL_JSON 验收尺：写出答案 vs 合法 JSON，分开计数。

旧判据把 ``json.loads`` 成功当成「写出了答案」。生效解析器
（``parse_finish_json``）会捞回 draft 里未转义引号的信封，产品已经交稿，
尺子却报空。本尺与解析器同口径计「写出答案」，``json.loads`` 只盯格式。
"""

from __future__ import annotations

import json

from intelligence.services.episode_protocol import parse_finish_json


def legal_json(content: str) -> bool:
    """Strict: ``json.loads`` 得到 object。不表示写出了答案。"""

    try:
        value = json.loads(content)
    except json.JSONDecodeError:
        return False
    return isinstance(value, dict)


def extracted_draft(content: str) -> str:
    """生效解析器取出的 draft；捞不出则空串。"""

    parsed = parse_finish_json(content)
    if isinstance(parsed, dict) and isinstance(parsed.get("draft"), str):
        return parsed["draft"]
    return ""


def wrote_answer(content: str) -> bool:
    """与产品生效解析器同一条路：能取出非空 ``draft`` 就算写出了答案。"""

    return bool(extracted_draft(content))
