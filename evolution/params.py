"""策略参数：共享 baseline + 按用户稀疏 overlay（保持确定性可复现）。

设计（PR2「按用户的策略迭代」）：
- ``evolution/params.json`` 是所有用户共享的 baseline，自带 ``version``。
- ``intelligence/users/<id>/strategy_params.json`` 是**稀疏 overlay**：只写想覆盖
  的策略段（``strategy1`` / ``strategy3`` / ``strategy4`` / ``validation`` /
  ``suggest``），自带 ``_overlay_version`` 元信息。
- evolve 加载时把 overlay **深合并**到 baseline 上（overlay 标量/列表整体覆盖、
  dict 递归），并返回一份 ``meta`` 记录「用了哪些段 / overlay 版本 / baseline 版本」
  用于在生成记录里留痕。

确定性：合并是纯函数，不依赖时间或外部状态——同一 baseline + 同一 overlay 永远
得到同一份参数；overlay 不存在时返回的就是 baseline 本身。本模块不依赖 duckdb，
可独立单测。
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_PARAMS_PATH = REPO_ROOT / "evolution" / "params.json"

# overlay 只允许覆盖这些策略段（必须是 dict）。version / note / updated_at 等
# baseline 元信息不接受 overlay 覆盖，避免用户改写共享版本号造成回溯混乱。
OVERLAY_ALLOWED_SECTIONS = ("strategy1", "strategy3", "strategy4", "validation", "suggest")


def load_base_params(path: str | Path | None = None) -> dict[str, Any]:
    """读取共享 baseline 参数（``evolution/params.json``）。"""
    p = Path(path) if path else BASE_PARAMS_PATH
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):  # pragma: no cover - defensive
        raise ValueError(f"baseline 参数不是 JSON 对象：{p}")
    return data


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """递归合并：``overlay`` 的标量/列表整体覆盖，dict 递归。返回新对象，不改入参。"""
    out = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _sanitize_overlay(raw: Any) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    """从 overlay 原文里挑出可用策略段 + 元信息（``_`` 前缀），其余忽略并告警。"""
    if not isinstance(raw, dict):
        return {}, {}, ["策略 overlay 不是 JSON 对象，已忽略"]
    overlay: dict[str, Any] = {}
    meta: dict[str, Any] = {}
    warnings: list[str] = []
    for key, value in raw.items():
        if key.startswith("_"):
            meta[key] = value
            continue
        if key in OVERLAY_ALLOWED_SECTIONS and isinstance(value, dict):
            overlay[key] = value
        else:
            warnings.append(f"overlay 段「{key}」不可覆盖或类型不符，已忽略")
    return overlay, meta, warnings


def load_effective_params(
    base_path: str | Path | None = None,
    overlay_path: str | Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """加载生效参数 = baseline ⊕ 稀疏 overlay。

    返回 ``(params, meta)``。``meta`` 字段：

    - ``overlay_applied``: 是否真的合并了 overlay
    - ``overlay_path``: overlay 文件路径（字符串或 None）
    - ``base_version``: baseline ``version``
    - ``overlay_version``: overlay ``_overlay_version``（无则 None）
    - ``overlay_sections``: 实际被覆盖的策略段（排序）
    - ``warnings``: 解析/字段告警
    """
    base = load_base_params(base_path)
    meta: dict[str, Any] = {
        "overlay_applied": False,
        "overlay_path": str(overlay_path) if overlay_path else None,
        "base_version": base.get("version"),
        "overlay_version": None,
        "overlay_sections": [],
        "warnings": [],
    }
    if not overlay_path:
        return base, meta
    p = Path(overlay_path)
    if not p.exists():
        return base, meta
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        meta["warnings"].append(f"策略 overlay 解析失败：{p}（{exc}）")
        return base, meta
    overlay, ometa, warns = _sanitize_overlay(raw)
    meta["warnings"].extend(warns)
    if not overlay:
        return base, meta
    merged = deep_merge(base, overlay)
    meta["overlay_applied"] = True
    meta["overlay_version"] = ometa.get("_overlay_version")
    meta["overlay_sections"] = sorted(overlay.keys())
    return merged, meta
