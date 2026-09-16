"""可复现的内容摘要：同输入同摘要，与生成时间无关。

``generated_at`` 是生成时间，不进入内容摘要（总合同 §5.2）；因此收据 / 总结的
稳定 id 都从「去掉 generated_at 与 id 本身之后的内容」算出，重复汇总得到同一个 id。
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

VOLATILE_KEYS: frozenset[str] = frozenset({"generated_at"})


def canonical_json(obj: Any) -> str:
    """键排序、无多余空白、非 ASCII 原样保留的 JSON；不可序列化的值用 ``str``。"""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def content_hash(obj: Any, *, drop_keys: frozenset[str] = frozenset()) -> str:
    """对象内容的 sha256（顶层去掉 ``drop_keys``）。"""
    if isinstance(obj, Mapping) and drop_keys:
        obj = {key: value for key, value in obj.items() if key not in drop_keys}
    return sha256_hex(canonical_json(obj))


def content_id(prefix: str, obj: Any, *, drop_keys: frozenset[str] = frozenset()) -> str:
    """``<prefix>_<sha256 前 16 位>``：稠密到足以避免碰撞，短到能进文件名。"""
    return f"{prefix}_{content_hash(obj, drop_keys=drop_keys)[:16]}"


def hash_ids(ids: list[str] | tuple[str, ...] | set[str]) -> str:
    """一组 id 的顺序无关摘要。"""
    return sha256_hex("\n".join(sorted(str(item) for item in ids)))


def normalize_hash_ref(value: str | None) -> str | None:
    """把 ``sha256:<hex>`` 与裸 hex 归一成小写裸 hex；其它形态原样返回。"""
    if not isinstance(value, str):
        return None
    text = value.strip().lower()
    if text.startswith("sha256:"):
        text = text[len("sha256:"):]
    return text or None


__all__ = [
    "VOLATILE_KEYS",
    "canonical_json",
    "content_hash",
    "content_id",
    "hash_ids",
    "normalize_hash_ref",
    "sha256_hex",
]
