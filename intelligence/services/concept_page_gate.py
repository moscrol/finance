"""出队前判断 concept_ingest 是不是伪缺口。

盘面触发 ≠ 库里真缺。知识库仓 `auto_triage_ima_queue.py` 在 receive 后分诊；
这里把同一口径提前到金融仓出队，避免完整页/过宽主题再进跨仓队列。

占位页和真缺页仍抛出：前者要升 L1，后者是真缺口。disclosure 不走这扇门。
"""

from __future__ import annotations

import re
from pathlib import Path

# 与知识库仓 auto_triage_ima_queue.TOO_WIDE_THEMES 对齐。有完整页时走 existing，不落到这里。
TOO_WIDE_THEMES = frozenset({
    "医疗",
    "通信",
    "机械设备",
    "粮食概念",
    "基因概念",
})

STUB_TAG_RE = re.compile(r"待补证")
STUB_BODY_MARKERS = (
    "占位概念页",
    "## 待补证定义",
    "概念状态 | 待补证",
    "该概念由 missing wikilinks",
)

ACTION_SKIP_EXISTING = "skip_existing"
ACTION_SKIP_TOO_WIDE = "skip_too_wide"
ACTION_ESCALATE_STUB = "escalate_stub"
ACTION_ESCALATE_MISSING = "escalate_missing"

DROP_ACTIONS = frozenset({ACTION_SKIP_EXISTING, ACTION_SKIP_TOO_WIDE})


def find_concept_path(concepts_dir: Path, theme: str) -> Path | None:
    name = str(theme or "").strip()
    if not name:
        return None
    direct = concepts_dir / f"{name}.md"
    if direct.exists():
        return direct
    compact = name.replace(" ", "").replace("　", "")
    for path in concepts_dir.glob("*.md"):
        if path.stem == name:
            return path
        if path.stem.replace(" ", "").replace("　", "") == compact:
            return path
    return None


def parse_frontmatter_tags(text: str) -> list[str]:
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return []
    for line in match.group(1).splitlines():
        if line.startswith("tags:"):
            return re.findall(r"[\"']([^\"']+)[\"']", line)
    return []


def is_stub_concept(text: str) -> bool:
    """占位壳，不是完整页里偶尔出现的「待补证」小节。"""
    tags = parse_frontmatter_tags(text)
    if any(STUB_TAG_RE.search(tag) for tag in tags):
        return True
    return any(marker in text for marker in STUB_BODY_MARKERS)


def classify_concept_theme(theme: str, wiki_root: str | Path) -> str:
    """返回 skip_existing / skip_too_wide / escalate_stub / escalate_missing。"""
    concepts_dir = Path(wiki_root).expanduser() / "concepts"
    path = find_concept_path(concepts_dir, theme)
    if path is not None:
        text = path.read_text(encoding="utf-8")
        if not is_stub_concept(text):
            return ACTION_SKIP_EXISTING
        if theme in TOO_WIDE_THEMES:
            return ACTION_SKIP_TOO_WIDE
        return ACTION_ESCALATE_STUB
    if theme in TOO_WIDE_THEMES:
        return ACTION_SKIP_TOO_WIDE
    return ACTION_ESCALATE_MISSING


def should_drop_concept_ingest(theme: str, wiki_root: str | Path) -> bool:
    return classify_concept_theme(theme, wiki_root) in DROP_ACTIONS
