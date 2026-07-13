"""M 用户记忆检索块：答题时按相关性召回你自己的核心判断/纠偏原则/回检胜率。

三个已有 per-user 台账（stdlib、离线、gitignored 私有层）此前只喂 foresight 发问，
答题链（``ask.py``）完全没用上——这块把它们接进证据链：

- ``judgments.jsonl``   核心判断（潜意识深挖沉淀，带 themes/stocks 标签）；
- ``corrections.jsonl`` 纠偏原则（你显式纠正过的方法论，带 themes 标签）；
- ``checkpoints.jsonl`` + ``verdicts.jsonl`` 回检校准（哪类判断历史靠谱→兑现率）。

与 foresight「无脑取最近 N 条」不同，这里按 query（题材/实体/关键词）与记录的
标签/正文做轻量重合打分，**只召回相关的**；召回为空时返回空串（不追加块，
无记忆用户行为逐字节不变）。渲染标 [M]，让回答站在你旧判断上往前推、
遵守你纠偏过的原则，并用回检胜率标注该信多少。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from intelligence import userspace
from intelligence.services import checkpoints, corrections, judgments

DEFAULT_LOAD_WINDOW = 200
DEFAULT_LIMIT = 5


def _norm(text: Any) -> str:
    return re.sub(r"\s+", "", str(text or "")).lower()


def _query_terms(query: str, theme: str | None = None, entity: str | None = None) -> list[str]:
    terms = [t for t in re.split(r"[，,。；;、\s/？?！!（）()]+", str(query or "")) if len(t) >= 2]
    for extra in (theme, entity):
        extra = (extra or "").strip()
        if extra:
            terms.append(extra)
    seen: set[str] = set()
    out: list[str] = []
    for t in terms:
        k = _norm(t)
        if k and k not in seen:
            seen.add(k)
            out.append(t)
    return out


def select_relevant(
    records: list[dict[str, Any]],
    query: str,
    theme: str | None = None,
    entity: str | None = None,
    text_keys: tuple[str, ...] = ("memo",),
    tag_keys: tuple[str, ...] = ("themes", "stocks"),
    limit: int = DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    """轻量相关性召回：标签命中权重高于正文重合；0 分记录不召回。"""
    terms = _query_terms(query, theme, entity)
    if not terms:
        return []

    def score(rec: dict[str, Any]) -> tuple[int, str]:
        tags = []
        for k in tag_keys:
            tags += [str(t).strip() for t in (rec.get(k) or []) if str(t).strip()]
        tag_hay = _norm(" ".join(tags))
        text_hay = _norm(" ".join(str(rec.get(k) or "") for k in text_keys))
        s = 0
        for term in terms:
            nt = _norm(term)
            if not nt:
                continue
            if nt in tag_hay:
                s += 4
            if nt in text_hay:
                s += 2
        return s, str(rec.get("ts") or "")

    ranked = [(score(r), r) for r in records if isinstance(r, dict)]
    ranked = [item for item in ranked if item[0][0] > 0]
    ranked.sort(key=lambda item: (item[0][0], item[0][1]), reverse=True)
    return [r for _, r in ranked[:limit]]


def _judgment_lines(records: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for rec in records:
        memo = str(rec.get("memo") or "").strip()
        if not memo:
            continue
        tags = [str(t).strip() for t in (rec.get("themes") or []) if str(t).strip()]
        tags += [str(s).strip() for s in (rec.get("stocks") or []) if str(s).strip()]
        date = str(rec.get("ts") or "")[:10]
        head = "、".join(tags)
        suffix = f"（{date}）" if date else ""
        lines.append(f"- 核心判断{f'[{head}]' if head else ''}：{memo}{suffix}")
    return lines


def _correction_lines(records: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for rec in records:
        correction = str(rec.get("correction") or "").strip()
        if not correction:
            continue
        principle = str(rec.get("principle") or "").strip()
        body = principle or correction
        date = str(rec.get("ts") or "")[:10]
        suffix = f"（{date}）" if date else ""
        lines.append(f"- 纠偏原则：{body}{suffix}")
    return lines


def build_memory_block(
    judgment_records: list[dict[str, Any]],
    correction_records: list[dict[str, Any]],
    calibration_text: str = "",
) -> str:
    """渲染 [M] 块；判断与纠偏都为空时返回空串（不追加块）。"""
    j_lines = _judgment_lines(judgment_records)
    c_lines = _correction_lines(correction_records)
    if not j_lines and not c_lines:
        return ""
    lines = ["## 用户记忆检索块 [M]（你自己的核心判断/纠偏原则/回检胜率，非市场事实）"]
    lines += j_lines
    lines += c_lines
    if calibration_text:
        lines.append("- 回检校准（该信多少）：")
        lines += [f"  {ln}" for ln in calibration_text.splitlines() if ln.strip()]
    lines.append(
        "- 使用要求：本块只是历史先验（prior），不是当前市场事实。它用于调整篇幅、语气、"
        "增量起点和反方重点；若用户已聊过同一标的，优先回答“相比上次发生了什么变化”，"
        "不要重跑全套模板。价格、产能、订单等易变项必须以本轮检索为准；与最新盘面/财报"
        "冲突时以硬数据块为准并显式指出冲突。"
    )
    return "\n".join(lines)


def memory_block_for_query(
    query: str,
    theme: str | None = None,
    entity: str | None = None,
    user: str | None = None,
    limit: int = DEFAULT_LIMIT,
    users_root: str | Path | None = None,
) -> str:
    """加载三源台账→相关性召回→渲染 [M]；台账缺失/无相关记录时返回空串。"""
    if users_root is not None:
        root = Path(users_root).expanduser()
        j_path = root / "judgments.jsonl"
        c_path = root / "corrections.jsonl"
        ck_path = root / "checkpoints.jsonl"
        v_path = root / "verdicts.jsonl"
    else:
        us = userspace.user_space(user)
        j_path, c_path = us.judgments_path, us.corrections_path
        ck_path, v_path = us.checkpoints_path, us.verdicts_path
    j_records, _ = judgments.load_judgments(j_path, window=DEFAULT_LOAD_WINDOW)
    c_records, _ = corrections.load_corrections(c_path, window=DEFAULT_LOAD_WINDOW)
    j_hit = select_relevant(j_records, query, theme, entity, text_keys=("memo",), limit=limit)
    c_hit = select_relevant(
        c_records,
        query,
        theme,
        entity,
        text_keys=("correction", "original", "principle"),
        tag_keys=("themes",),
        limit=limit,
    )
    calibration_text = ""
    if j_hit:
        try:
            cal, _warn = checkpoints.load_calibration(ck_path, v_path)
            calibration_text = checkpoints.render_calibration_for_prompt(cal)
        except Exception:
            calibration_text = ""
    return build_memory_block(j_hit, c_hit, calibration_text)
