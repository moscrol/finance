"""视角叙事契约验收尺（spec §3.3.1 / §3.3.2）。

只扫 LLM 正文。程序化 ``answer_header`` 先用 ``strip_answer_header`` 剥掉，
不要把头里的「当前视角」当成模型又输出了一次结构。
词表以设计稿固化表为准，不得为了过机检把 ``置信度：`` 写回契约。
"""

from __future__ import annotations

import re
from collections.abc import Sequence

ELEMENT_GROUPS: dict[str, tuple[str, ...]] = {
    "原始判断": ("原始判断", "原文", "该视角认为", "他写过"),
    "映射": ("映射", "对照今天", "落到今天", "按此看"),
    "支持/冲突": ("支持", "冲突", "对得上", "对不上"),
    "适用": ("适用", "成立前提", "在什么条件下", "前提是"),
    "证伪": ("证伪", "失效"),
    "置信": ("置信", "把握", "信心", "概率"),
    "未知": ("未知", "该视角未知"),
}

_HEADING_LABELS = (
    "KOL原始判断",
    "当前行情映射",
    "原始判断",
    "行情映射",
    "支持/冲突",
    "适用条件",
    "失效条件",
    "证伪条件",
    "置信度",
    "未知项",
)
_HEADING_RE = re.compile(
    r"^[ \t]*(?:#{1,6}[ \t]*|\*{1,2}[ \t]*)?(?:"
    + "|".join(re.escape(label) for label in _HEADING_LABELS)
    + r")(?:[ \t]*\*{1,2})?(?:[ \t]*[:：].*)?\s*$",
    re.MULTILINE,
)
_BRACKET_HEADING_RE = re.compile(r"【[^】]{1,40}】")
_REPEATED_HEADER_RE = re.compile(r"^[ \t]*(?:当前视角|来源范围)[：:].*$", re.MULTILINE)
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def strip_answer_header(text: str) -> str:
    """剥掉交付层 ``当前视角：`` / ``来源范围：`` 两行，剩下 LLM 正文。"""

    lines = str(text or "").splitlines()
    if (
        len(lines) >= 2
        and lines[0].startswith("当前视角：")
        and lines[1].startswith("来源范围：")
    ):
        rest = lines[2:]
        while rest and not rest[0].strip():
            rest = rest[1:]
        return "\n".join(rest)
    return str(text or "")


def _citation_hit(body: str, titles: Sequence[str]) -> bool:
    if _DATE_RE.search(body):
        return True
    return any(len(title.strip()) >= 4 and title.strip() in body for title in titles)


def _style_violations(body: str) -> list[str]:
    found: list[str] = []
    for match in _BRACKET_HEADING_RE.finditer(body):
        found.append(match.group(0))
    for match in _HEADING_RE.finditer(body):
        found.append(match.group(0).strip())
    for match in _REPEATED_HEADER_RE.finditer(body):
        found.append(match.group(0).strip())
    return list(dict.fromkeys(found))


def score_narrative_body(
    body: str,
    *,
    titles: Sequence[str] = (),
) -> dict[str, object]:
    text = str(body or "")
    hits = {
        name: any(token in text for token in tokens)
        for name, tokens in ELEMENT_GROUPS.items()
    }
    hits["原文回指"] = _citation_hit(text, titles)
    violations = _style_violations(text)
    elements_ok = all(hits.values())
    style_ok = not violations
    return {
        "element_hits": hits,
        "elements_ok": elements_ok,
        "style_violations": violations,
        "style_ok": style_ok,
        "ok": elements_ok and style_ok,
    }


def score_compare_extras(body: str) -> bool:
    text = str(body or "")
    has_conflict = "冲突" in text or "综合" in text
    has_reasoning = "AI 推理" in text or "推理层" in text
    return has_conflict and has_reasoning


def main(argv: Sequence[str] | None = None) -> int:
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description="视角叙事契约机检（§3.3.1 / §3.3.2）")
    parser.add_argument("path", help="answer.md 或正文文件")
    parser.add_argument("--title", action="append", default=[], help="本轮召回 title，可重复")
    parser.add_argument("--keep-header", action="store_true", help="不要剥程序化头")
    args = parser.parse_args(argv)
    raw = Path(args.path).read_text(encoding="utf-8")
    body = raw if args.keep_header else strip_answer_header(raw)
    result = score_narrative_body(body, titles=args.title)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
