"""复盘会板块名 → 申万一级行业 映射。

数据来自 references/sector_shenwan_l1_mapping.json (申万2021版 31个一级行业)。
原文件是 {申万一级: [板块名, ...]} 结构, 这里反转为 {板块名: 申万一级}。
板块名带括号代码后缀的 (如 '小金属(885552)') 会同时登记裸名与带后缀名。
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
MAPPING_PATH = PROJECT_DIR / "references" / "sector_shenwan_l1_mapping.json"

_PAREN = re.compile(r"\(.*?\)")


def _strip_paren(name: str) -> str:
    return _PAREN.sub("", name).strip()


@lru_cache(maxsize=1)
def board_to_sw_l1() -> dict:
    """返回 {板块名: 申万一级}。同时登记裸名与带括号后缀名。"""
    raw = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    out = {}
    for sw_l1, boards in raw.items():
        if sw_l1.startswith("_"):
            continue
        for board in boards:
            out[board] = sw_l1
            bare = _strip_paren(board)
            if bare and bare != board:
                out.setdefault(bare, sw_l1)
    return out


def lookup_sw_l1(sector_name: str) -> str | None:
    """按板块名查申万一级。先精确匹配, 再去括号匹配。"""
    if not sector_name:
        return None
    mapping = board_to_sw_l1()
    if sector_name in mapping:
        return mapping[sector_name]
    return mapping.get(_strip_paren(sector_name))
