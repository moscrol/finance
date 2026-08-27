"""知识索引卫生：工件页不进索引，同 slug 多版本检索时只留最新。

设计取舍（面试常问「过滤放在哪一层」）：
- 物理 ``.rag_index`` 在知识库仓由 ``rag_index.py build`` 生成；本仓只改消费侧。
- 本模块是本仓的**索引构建入口**：``indexable_paths`` 决定哪些路径算「索引条目」。
- 检索入口 ``kb_rag.retrieve`` 走同一套规则，避免「审计排除了、召回还在」。

认不出同族时 fail open（照常收录），避免误伤正常页。
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")

# 过采样：丢掉工件页 + 折叠同族后仍要填满调用方的 k。
_FETCH_MULTIPLIER = 4
_FETCH_PADDING = 16

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?\n)---\s*(?:\n|$)", re.DOTALL)
_VERSION_STEM_RE = re.compile(r"^(?P<slug>.+)-v(?P<ver>\d+)$")

_ARTIFACT_TYPES = frozenset(
    {"artifact", "acceptance", "test_artifact", "fixture", "eval_artifact"}
)
_KB_INDEX_EXCLUDE = frozenset({"false", "0", "no", "exclude", "skip", "never"})


def fetch_k(requested_k: int) -> int:
    """检索侧过采样条数，供丢掉工件/折叠同族后仍能填满 k。"""
    k = max(1, int(requested_k))
    return max(k * _FETCH_MULTIPLIER, k + _FETCH_PADDING)


def _posix(path: str) -> str:
    return str(path or "").replace("\\", "/").lstrip("./")


def _filename(posix: str) -> str:
    return posix.rsplit("/", 1)[-1]


def _parent_dir(posix: str) -> str:
    if "/" not in posix:
        return ""
    return posix.rsplit("/", 1)[0]


def _under_synthesis(posix: str) -> bool:
    parts = [part for part in posix.split("/") if part]
    return "synthesis" in parts


def _path_is_artifact(posix: str) -> bool:
    """路径可机械识别的验收/测试产物。规则来自 2026-08-21 工件页审计。"""
    name = _filename(posix)
    if not name.endswith(".md"):
        return False
    # theme-radar 验收页：stem 含 -theme-radar-验收，可带 -vN。
    if "-theme-radar-验收" in name:
        return True
    # synthesis 下文件名含「验收」：覆盖流程验收页（无 YAML frontmatter）。
    if "验收" in name and _under_synthesis(posix):
        return True
    return False


def parse_frontmatter(page_text: str | None) -> dict[str, str]:
    """极简 YAML 头解析。认不出就空 dict（fail open），不引入 PyYAML。"""
    match = _FRONTMATTER_RE.match(str(page_text or ""))
    if match is None:
        return {}
    parsed: dict[str, str] = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        parsed[key.strip()] = value.strip().strip("'\"")
    return parsed


def _truthy_mapping(frontmatter: Mapping[str, object] | None) -> Mapping[str, object]:
    return frontmatter if frontmatter is not None else {}


def _frontmatter_excludes(frontmatter: Mapping[str, object]) -> bool:
    kb_index = frontmatter.get("kb_index")
    if isinstance(kb_index, bool):
        return not kb_index
    if str(kb_index or "").strip().lower() in _KB_INDEX_EXCLUDE:
        return True
    kind = str(frontmatter.get("type") or frontmatter.get("kind") or "").strip().lower()
    return kind in _ARTIFACT_TYPES


def is_artifact_page(
    path: str,
    *,
    frontmatter: Mapping[str, object] | None = None,
    page_text: str | None = None,
) -> bool:
    """工件页判定：路径规则或 frontmatter。两边都认不出 → False（fail open）。"""
    posix = _posix(path)
    if _path_is_artifact(posix):
        return True
    fm = _truthy_mapping(frontmatter)
    if not fm and page_text:
        fm = parse_frontmatter(page_text)
    return bool(fm) and _frontmatter_excludes(fm)


def indexable_paths(paths: Iterable[str]) -> list[str]:
    """索引构建入口：工件路径排除，其余照常收录。"""
    return [path for path in paths if not is_artifact_page(path)]


def family_key(path: str) -> tuple[str, str] | None:
    """认出版本族则返回 ``(目录, slug)``；夹心 -vN / 日期戳返回 None（fail open）。"""
    posix = _posix(path)
    stem = Path(_filename(posix)).stem
    match = _VERSION_STEM_RE.match(stem)
    if match is None:
        return None
    return _parent_dir(posix), match.group("slug")


def _version_number(path: str) -> int | None:
    stem = Path(_filename(_posix(path))).stem
    match = _VERSION_STEM_RE.match(stem)
    if match is None:
        return None
    return int(match.group("ver"))


def collapse_same_slug(
    hits: Sequence[T],
    *,
    path_of: Callable[[T], str] | None = None,
) -> list[T]:
    """同目录同 slug 的 ``-vN`` 多版本只留最新；认不出的页原样保留。"""
    get_path = path_of or (lambda hit: str(getattr(hit, "file_path", "")))
    items = list(hits)
    families: dict[tuple[str, str], list[tuple[int, T]]] = {}
    for hit in items:
        key = family_key(get_path(hit))
        if key is None:
            continue
        ver = _version_number(get_path(hit)) or 1
        families.setdefault(key, []).append((ver, hit))

    unversioned_join: dict[tuple[str, str], list[T]] = {}
    for hit in items:
        posix = _posix(get_path(hit))
        if family_key(posix) is not None:
            continue
        key = (_parent_dir(posix), Path(_filename(posix)).stem)
        if key in families:
            unversioned_join.setdefault(key, []).append(hit)

    latest: dict[tuple[str, str], T] = {}
    for key, versioned in families.items():
        candidates: list[tuple[int, float, T]] = []
        for ver, hit in versioned:
            score = float(getattr(hit, "score", 0.0) or 0.0)
            candidates.append((ver, score, hit))
        for hit in unversioned_join.get(key, ()):
            score = float(getattr(hit, "score", 0.0) or 0.0)
            candidates.append((1, score, hit))
        latest[key] = max(candidates, key=lambda item: (item[0], item[1]))[2]

    family_of_hit: dict[int, tuple[str, str]] = {}
    for key, versioned in families.items():
        for _, hit in versioned:
            family_of_hit[id(hit)] = key
        for hit in unversioned_join.get(key, ()):
            family_of_hit[id(hit)] = key

    kept: list[T] = []
    emitted: set[tuple[str, str]] = set()
    for hit in items:
        key = family_of_hit.get(id(hit))
        if key is None:
            kept.append(hit)
            continue
        if key in emitted:
            continue
        kept.append(latest[key])
        emitted.add(key)
    return kept


def sanitize_hits(
    hits: Sequence[T],
    *,
    k: int,
    path_of: Callable[[T], str] | None = None,
) -> list[T]:
    """检索出口：先排除工件页，再折叠同族，最后截到 k。"""
    get_path = path_of or (lambda hit: str(getattr(hit, "file_path", "")))
    without_artifacts = [
        hit for hit in hits if not is_artifact_page(get_path(hit))
    ]
    collapsed = collapse_same_slug(without_artifacts, path_of=get_path)
    limit = max(0, int(k))
    return collapsed[:limit]


def unique_source_paths(chunks_jsonl: str | Path) -> list[str]:
    """从 ``chunks.jsonl`` 抽出去重后的 ``file_path``（物理索引页集合）。"""
    seen: set[str] = set()
    ordered: list[str] = []
    with Path(chunks_jsonl).open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            path = str(record.get("file_path") or "")
            if not path or path in seen:
                continue
            seen.add(path)
            ordered.append(path)
    return ordered


def audit_served_index(chunks_jsonl: str | Path) -> dict[str, object]:
    """索引审计：物理页 vs 本仓索引构建入口过滤后的条目。"""
    physical = unique_source_paths(chunks_jsonl)
    artifacts = [path for path in physical if is_artifact_page(path)]
    served = indexable_paths(physical)
    served_artifacts = [path for path in served if is_artifact_page(path)]
    return {
        "physical_pages": len(physical),
        "physical_artifact_pages": len(artifacts),
        "served_pages": len(served),
        "served_artifact_pages": len(served_artifacts),
        "physical_artifact_paths": artifacts,
    }
