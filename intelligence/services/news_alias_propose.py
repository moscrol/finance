"""W7 中英别名表运营：从 wiki 实体/概念页确定性抽取候选，人工确认后入表。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from intelligence.services.market_news import ALIAS_TABLE_PATH, _load_keyword_aliases

_HAS_CN = re.compile(r"[\u4e00-\u9fff]")
_HAS_LATIN = re.compile(r"[A-Za-z]")
_TITLE_ACRONYM = re.compile(
    r"^([A-Za-z][A-Za-z0-9+\-./]{1,24})（([\u4e00-\u9fff][^）]{1,20})）"
)
_TITLE_CN_EN = re.compile(
    r"^([\u4e00-\u9fff][^（]{1,20})（([A-Za-z][A-Za-z0-9 +\-/]{1,40})）"
)
_BODY_CN_EN = re.compile(
    r"([\u4e00-\u9fff]{2,16})（([A-Za-z][A-Za-z0-9 +\-/]{2,40})）"
)
_FM_TITLE = re.compile(r"^title:\s*[\"']?(.+?)[\"']?\s*$", re.MULTILINE)
_FM_ALIASES = re.compile(r"^aliases:\s*\[([^\]]*)\]", re.MULTILINE)
_PLACEHOLDER = re.compile(r"占位概念页|待补证定义")


@dataclass(frozen=True)
class AliasCandidate:
    zh: str
    en: str
    source: str
    status: str = "pending"

    def to_dict(self) -> dict[str, str]:
        return {"zh": self.zh, "en": self.en, "source": self.source, "status": self.status}


def propose_alias_candidates(
    wiki_root: str | Path,
    *,
    existing: dict[str, str] | None = None,
    limit: int = 50,
) -> tuple[AliasCandidate, ...]:
    """从 concepts/entities 页抽中英对；已在别名表里的不提案。"""
    root = Path(wiki_root).expanduser()
    known = existing if existing is not None else _load_keyword_aliases()
    found: list[AliasCandidate] = []
    seen: set[str] = set()
    for folder in ("concepts", "entities"):
        base = root / folder
        if not base.is_dir():
            continue
        for path in sorted(base.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            if _PLACEHOLDER.search(text):
                continue
            rel = f"{folder}/{path.name}"
            for zh, en in _extract_pairs(path.stem, text):
                key = zh.strip()
                if not key or key in known or key in seen:
                    continue
                if not _usable_zh(key) or not _usable_en(en):
                    continue
                seen.add(key)
                found.append(AliasCandidate(zh=key, en=en.strip(), source=rel))
                if len(found) >= limit:
                    return tuple(found)
    return tuple(found)


def accept_alias(
    zh: str,
    en: str,
    *,
    path: str | Path | None = None,
) -> dict[str, str]:
    """人工确认后写入 news_keyword_aliases.json。不建新台账。"""
    target = Path(path or ALIAS_TABLE_PATH)
    raw: dict[str, Any] = json.loads(target.read_text(encoding="utf-8"))
    key = str(zh or "").strip()
    value = str(en or "").strip()
    if not key or not value:
        raise ValueError("别名中英文都不能为空")
    raw[key] = value
    target.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if target.resolve() == Path(ALIAS_TABLE_PATH).resolve():
        _load_keyword_aliases.cache_clear()
    return {key: value}


def _extract_pairs(stem: str, text: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    title = ""
    fm = _FM_TITLE.search(text)
    if fm:
        title = fm.group(1).strip().strip('"').strip("'")
    acronym = _TITLE_ACRONYM.match(title or stem)
    if acronym:
        pairs.append((acronym.group(2), acronym.group(1)))
    cn_en = _TITLE_CN_EN.match(title)
    if cn_en:
        pairs.append((cn_en.group(1), cn_en.group(2)))
    aliases = _frontmatter_aliases(text)
    zh_title = title if _HAS_CN.search(title) else (stem if _HAS_CN.search(stem) else "")
    if zh_title:
        for alias in aliases:
            if _usable_en(alias):
                pairs.append((zh_title.split("（")[0], alias))
    allowed_zh = {stem, title, title.split("（")[0], *(p[0] for p in pairs)}
    allowed_zh = {item for item in allowed_zh if item}
    for match in _BODY_CN_EN.finditer(text):
        if match.group(1) in allowed_zh:
            pairs.append((match.group(1), match.group(2)))
    return pairs


def _frontmatter_aliases(text: str) -> list[str]:
    match = _FM_ALIASES.search(text)
    if not match:
        return []
    out: list[str] = []
    for part in match.group(1).split(","):
        token = part.strip().strip('"').strip("'")
        if token:
            out.append(token)
    return out


def _usable_zh(value: str) -> bool:
    text = str(value or "").strip()
    if not (2 <= len(text) <= 16) or not _HAS_CN.search(text):
        return False
    return not text.startswith(("和", "与", "及", "或", "卡", "构", "功"))


def _usable_en(value: str) -> bool:
    text = str(value or "").strip()
    if len(text) < 2 or not _HAS_LATIN.search(text):
        return False
    if _HAS_CN.search(text):
        return False
    return not text.isdigit()
