"""同花顺目录/成员 v1 合同：同步和只读审计共用，不依赖外呼/写库模块。"""
from __future__ import annotations

import re
from typing import Any

CONTRACT_VERSION = "hithink-sector-capture-v1"
CATALOG_TAGS = ("cn_concept", "industry", "region", "tszs")
SOURCE_CATALOG = "hithink:ths-index-list"
SOURCE_KLINE = "hithink:index-historical"
SOURCE_CONSTITUENT = "hithink:ths-stock-list"


class HithinkSectorSyncError(RuntimeError):
    """板块同步失败；只使用固定内部消息，不附 key/供应商错误正文。"""


def snapshot_items(payload) -> list[dict[str, Any]]:
    """目录/成员没有合法空快照合同；拒绝坏行而不是过滤后缩池。"""
    if not isinstance(payload, dict) or type(payload.get("code")) is not int or payload["code"] != 0:
        raise HithinkSectorSyncError("快照响应业务码无效")
    data = payload.get("data")
    if isinstance(data, dict):
        keys = [key for key in ("item", "items") if key in data]
        if len(keys) != 1:
            raise HithinkSectorSyncError("快照响应列表缺失或歧义")
        raw = data[keys[0]]
    else:
        raw = data
    if not isinstance(raw, list) or not raw or any(not isinstance(row, dict) for row in raw):
        raise HithinkSectorSyncError("快照为空或格式错误，不认领完整快照")
    return raw


def normalize_catalog_items(items, tag: str) -> list[dict[str, Any]]:
    if tag not in CATALOG_TAGS or not isinstance(items, list) or not items:
        raise HithinkSectorSyncError("目录标签或列表无效")
    rows, seen = [], set()
    for item in items:
        code = item.get("thscode") if isinstance(item, dict) else None
        name = item.get("name") if isinstance(item, dict) else None
        code = code.strip().upper() if isinstance(code, str) else ""
        if (not re.fullmatch(r"[0-9]{6}\.TI", code) or code in seen
                or not isinstance(name, str) or not name.strip()):
            raise HithinkSectorSyncError("目录身份/名称缺失、无效或重复")
        seen.add(code)
        rows.append({"thscode": code, "name": name.strip(), "category": tag})
    return rows


def normalize_constituent_items(items) -> list[dict[str, Any]]:
    if not isinstance(items, list) or not items:
        raise HithinkSectorSyncError("当前成员为空或格式错误")
    rows, seen = [], set()
    for item in items:
        code = item.get("thscode") if isinstance(item, dict) else None
        code = code.strip().upper() if isinstance(code, str) else ""
        if not re.fullmatch(r"[0-9]{6}\.(SH|SZ|BJ)", code) or code in seen:
            raise HithinkSectorSyncError("当前成员身份缺失、无效或重复")
        seen.add(code)
        ticker = item.get("ticker")
        if ticker is not None and str(ticker).strip() != code[:6]:
            raise HithinkSectorSyncError("当前成员 ticker 与代码不符")
        name = item.get("name")  # 兼容抓取函数返回；审计/成员表均不保留个股名
        rows.append({"thscode": code, "ticker": code[:6] if ticker is not None else None, "name": name})
    return rows
