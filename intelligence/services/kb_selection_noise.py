"""KB 选段结构噪声过滤（形状 IV / V5）。

词频选段常把 frontmatter 标签汤、来源清单、wikilink 堆、路径行送到窗口头。
本模块只做**结构性**识别：剥包装、丢掉噪声段、把剩下的正文前置。

不做语义重排、不接 rerank、不加长度上限。认不出噪声就原样放行（fail-open）；
整段都是噪声时保留去包装后的原文，绝不把有字的输入滤成空串。
"""

from __future__ import annotations

import re

# 钙钛矿 live 头：``# 曼恩斯特（301325） tags: … section: 曼恩斯特（301325） >``
_HEADING_TAGS_SECTION_RE = re.compile(
    r"^(?:#\s+.+?\s+)?tags:\s+\S.*?\bsection:\s+.+?>\s*",
    re.IGNORECASE | re.DOTALL,
)
_YAML_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*(?:\n|$)", re.DOTALL)
# llm_evidence 定位包装：``命中块 wiki/…::24:``（路径可含空格）
_LOCATOR_RE = re.compile(r"(?:命中块|相邻块)\s+.+?::\d+:\s*")

_NOISE_TOKEN_RE = re.compile(
    r"(?P<table>\|(?:\s*:?-{3,}:?\s*\|)+)"
    r"|(?P<source>\d+\.\s+\*\*[^*]+?\*\*.{0,240}?https?://\S+)"
    r"|(?P<wikilink>(?:\[\[[^\]]+\]\](?:\s*[·•|,/]\s*)?){2,})"
    r"|(?P<path>[-*` \t]*(?:raw/|wiki/)[\w./\u4e00-\u9fff\-]+\.\w+`?)"
)

def strip_structural_wrappers(text: str) -> str:
    """去掉标题+tags+section 头、YAML frontmatter、命中块定位符。"""

    current = str(text or "")
    for _ in range(4):
        updated = _YAML_FRONTMATTER_RE.sub("", current, count=1)
        updated = _HEADING_TAGS_SECTION_RE.sub("", updated, count=1)
        if updated == current:
            break
        current = updated
    current = _LOCATOR_RE.sub("", current)
    return current.strip()


def _is_residual_noise(segment: str) -> bool:
    piece = segment.strip()
    if not piece:
        return True
    if piece in {"---", ">", "|"}:
        return True
    if re.fullmatch(r"#+", piece):
        return True
    if re.fullmatch(r"#\s+\S.*", piece) and "tags:" not in piece and len(piece) < 80:
        return True
    if re.fullmatch(r"tags:\s+\S.*", piece, flags=re.IGNORECASE):
        return True
    return False


def classify_segments(text: str) -> list[tuple[str, bool]]:
    """``(segment, is_noise)``。供验证文档复算噪声占比，不是测试的期望真值。"""

    parts: list[tuple[str, bool]] = []
    last = 0
    for match in _NOISE_TOKEN_RE.finditer(text):
        if match.start() > last:
            gap = text[last : match.start()]
            if gap.strip():
                parts.append((gap.strip(), _is_residual_noise(gap)))
        parts.append((match.group(), True))
        last = match.end()
    if last < len(text):
        gap = text[last:]
        if gap.strip():
            parts.append((gap.strip(), _is_residual_noise(gap)))
    return parts


def structural_noise_ratio(text: str) -> float:
    """噪声字符 / 去包装后总字符。空串为 0。"""

    unwrapped = strip_structural_wrappers(text)
    if not unwrapped:
        return 0.0
    classified = classify_segments(unwrapped)
    if not classified:
        return 0.0
    noise = sum(len(segment) for segment, is_noise in classified if is_noise)
    wrapper = max(0, len(str(text or "")) - len(unwrapped))
    return (noise + wrapper) / max(len(str(text or "")), 1)


def filter_structural_noise(text: str) -> str:
    """过滤结构噪声；认不出则放行；全噪声则返回去包装文本（非空）。"""

    original = str(text or "")
    if not original.strip():
        return original

    unwrapped = strip_structural_wrappers(original)
    if not unwrapped:
        return original

    classified = classify_segments(unwrapped)
    kept = [segment for segment, is_noise in classified if not is_noise]
    if not kept:
        return unwrapped

    separator = "\n" if "\n" in original else " "
    filtered = separator.join(kept).strip()
    if not filtered:
        return unwrapped
    return filtered
