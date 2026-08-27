"""V10 节标题覆盖审计：冻结小语料夹具 + 启发式钉。

夹具在 ``intelligence/tests/fixtures/kb-section-coverage/``。
``.rag_index/chunks.jsonl`` 与 ``poison.md`` 故意放了「伪造索引节」，扫到即红。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from intelligence.services.kb_window_reexcerpt import STRUCTURAL_SECTIONS  # noqa: E402
from scripts.audit_kb_section_coverage import (  # noqa: E402
    audit_wiki,
    is_body_header,
    is_structural_heading,
    main,
    render_table,
)

_FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "kb-section-coverage" / "wiki"
)

_BODY = ("一句话", "核心逻辑", "最新市场逻辑", "边际变化", "产业链", "公司简介")
_VARIANTS = ("相关公司/实体", "来源", "关键公司")


def test_heuristic_covers_every_blacklist_name() -> None:
    """覆盖率钉：黑名单 6 名必须被启发式认成结构节。恒 False → 本条红。"""

    covered = {name for name in STRUCTURAL_SECTIONS if is_structural_heading(name)}
    assert covered == set(STRUCTURAL_SECTIONS)


def test_heuristic_rejects_body_headings() -> None:
    for title in _BODY:
        assert is_structural_heading(title) is False, title


def test_heuristic_accepts_frozen_variants() -> None:
    for title in _VARIANTS:
        assert is_structural_heading(title) is True, title


def test_frozen_corpus_ranking_and_blind_spots() -> None:
    report = audit_wiki(_FIXTURE, min_blind_pages=1)
    assert report["pages_scanned"] == 3
    titles = {row["title"]: row for row in report["heading_rank"]}
    assert "伪造索引节" not in titles
    assert titles["相关实体"]["page_count"] == 1
    assert titles["相关实体"]["in_blacklist"] is True
    assert titles["相关公司/实体"]["structural_candidate"] is True
    assert titles["相关公司/实体"]["in_blacklist"] is False
    assert titles["来源"]["structural_candidate"] is True
    assert titles["来源"]["in_blacklist"] is False
    assert report["blacklist_heuristic_coverage"] == 1.0
    present = set(report["blacklist_present"])
    assert present >= {
        "相关实体",
        "相关概念",
        "原始资料链接",
        "Source 分类",
        "Raw / Manifest Trace",
        "使用口径",
    }
    blind_titles = {row["title"] for row in report["blind_spots"]}
    assert "相关公司/实体" in blind_titles
    assert "来源" in blind_titles
    assert "关键公司" in blind_titles
    assert "相关实体" not in blind_titles


def test_does_not_scan_rag_index_or_chunks(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    (wiki / "entities").mkdir(parents=True)
    (wiki / "entities" / "ok.md").write_text("## 相关实体\n\nx\n", encoding="utf-8")
    poison = wiki / ".rag_index"
    poison.mkdir()
    (poison / "chunks.jsonl").write_text(
        json.dumps({"h": "## 伪造索引节"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (poison / "poison.md").write_text("## 伪造索引节\n", encoding="utf-8")
    report = audit_wiki(wiki, min_blind_pages=1)
    titles = {row["title"] for row in report["heading_rank"]}
    assert "伪造索引节" not in titles
    assert "相关实体" in titles


def test_wiki_root_required() -> None:
    with pytest.raises(SystemExit):
        main([])


def test_cli_writes_json_and_table(tmp_path: Path) -> None:
    json_out = tmp_path / "out.json"
    md_out = tmp_path / "out.md"
    assert (
        main(
            [
                "--wiki-root",
                str(_FIXTURE),
                "--min-blind-pages",
                "1",
                "--json-out",
                str(json_out),
                "--md-out",
                str(md_out),
            ]
        )
        == 0
    )
    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["blacklist_heuristic_coverage"] == 1.0
    text = md_out.read_text(encoding="utf-8")
    assert "盲区" in text
    assert "相关公司/实体" in text
    assert "伪造索引节" not in text
    assert "结构候选" in render_table(payload)


def test_body_header_false_on_structural_title() -> None:
    """正文头钉：结构节 title 不得算正文头。恒 True → 本条红。"""

    assert is_body_header("相关实体", "[[华天]]") is False
    assert is_body_header("一句话", "封测龙头") is True
    assert is_body_header("", "## 原始资料链接\n1. **x**") is False
