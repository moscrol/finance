#!/usr/bin/env python3
"""把长 description 拆成候选条目；ID 对同输入稳定，不保证跨修订稳定。

## 为什么要拆

一个长字符串容纳多条规则时，规则无法单独引用、修订或证伪。
这里产生可复核的拆分候选；源画像与拆分产物均留在调用方指定的私有路径。

## 三条纪律

1. **只拆不删。** 拆分前后内容必须逐字可还原，``verify_lossless`` 守这一条，不过就抛。
2. **不静默判断。** 分号后面跟的到底是一条新规则，还是上一条的后半截（「否则不升级」「则抱团反复」），
   机器判不准。判不准的一律标 ``needs_review`` 并写明理由，交人裁定——
   不是挑一个看起来合理的切法然后不说。
3. **不改语义。** 这里不润色、不归纳、不去重、不排序。合并重复规则是另一件事，
   需要用户裁定，不由文本拆分器决定。

## ID 稳定性

``<profile>.<lens_slug>.<序号>`` + 内容指纹 ``text_sha256[:12]``。
同一输入可重算同一 ID；新增/删除条目后重新拆分会改变后续序号，当前不保证跨修订 ID 稳定。
内容指纹用于识别文本变化，跨修订合并仍需调用方比对。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

SPLIT_CHARS = "；;"

# 以这些词开头的片段，多半是上一句的后半截而不是独立规则。不自动合并——标出来让人看。
CONTINUATION_STARTS = (
    "否则", "则", "而", "但", "不是", "不然", "再", "又", "且", "并", "或", "反之",
    "缺一不可", "两者", "同样", "同上", "此时", "这时", "那时", "后者", "前者",
)
# 以这些结尾的片段，像是话没说完
DANGLING_ENDS = ("：", ":", "，", ",", "、", "=", "＝")

# 谓词/判断标记。一条规则总得「说了点什么」——下判断、给条件、作比较。
# 单用这条会误标（「指数箱体+成交额中枢定市场阶段」是真规则却不含这些词），
# 所以只在「又短又没有谓词」时才标：短 + 无谓词 ≈ 名词短语 ≈ 上一条的附加状语。
PREDICATE_MARKS = (
    "=", "＝", "才", "要", "不", "看", "做", "认", "是", "则", "须", "必", "用", "按",
    "优先", "回避", "警惕", "可", "会", "进入", "转", "确认", "视为", "降低", "寻找",
)
MIN_STANDALONE = 10  # 短于此且无谓词标记 → 判不准，交人裁


def _slug(name: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "_", name).strip("_")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _norm(text: str) -> str:
    """比对用的规范化：Unicode NFC + 去掉所有空白。不动任何实义字符。"""
    return re.sub(r"\s+", "", unicodedata.normalize("NFC", text))


def split_description(text: str) -> list[dict[str, Any]]:
    """按分号切，但**不**把判不准的合并掉——标 needs_review 交人裁。"""
    parts: list[str] = []
    buf = ""
    for ch in text:
        if ch in SPLIT_CHARS:
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    parts.append(buf)

    out: list[dict[str, Any]] = []
    for i, raw in enumerate(parts):
        body = raw.strip()
        if not body:
            continue
        reasons: list[str] = []
        head = next((w for w in CONTINUATION_STARTS if body.startswith(w)), None)
        if head:
            reasons.append(f"以「{head}」开头，可能是上一条（{len(out)} 号）的后半截，不是独立规则")
        if body.endswith(DANGLING_ENDS):
            reasons.append("以标点收尾，像是话没说完")
        if len(body) < MIN_STANDALONE and not any(m in body for m in PREDICATE_MARKS):
            reasons.append(
                f"只有 {len(body)} 字且不含任何谓词/判断标记，像名词短语——"
                "多半是上一条的附加状语，被分号切了出来"
            )
        if body.count("（") != body.count("）"):
            reasons.append("括号不配对，分号很可能切在了括号内部")
        out.append({
            "seq": i,
            "text": body,
            "status": "needs_review" if reasons else "clear",
            "review_reasons": reasons,
        })
    return out


def verify_lossless(original: str, rules: list[dict[str, Any]]) -> None:
    """拆完拼回去必须覆盖原文每一个实义字符，不漏不增。不过就抛。"""
    rejoined = "；".join(r["text"] for r in rules)
    a, b = _norm(original), _norm(rejoined)
    if a == b:
        return
    # 原文可能以分号收尾，或分号与中文句号混用——逐字符定位第一处差异再报
    i = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))
    raise AssertionError(
        "拆分不可逆：拼回去与原文不一致。\n"
        f"  原文 {len(a)} 字 / 拼回 {len(b)} 字，首处差异在第 {i} 字\n"
        f"  原文 …{a[max(0, i - 25):i + 25]}…\n"
        f"  拼回 …{b[max(0, i - 25):i + 25]}…"
    )


def split_lens(profile: dict[str, Any], lens_name: str, *, profile_id: str) -> dict[str, Any]:
    lenses = profile.get("market_lenses") or []
    lens = next((x for x in lenses if x.get("name") == lens_name), None)
    if lens is None:
        raise SystemExit(f"画像里没有镜头 {lens_name!r}（有：{[x.get('name') for x in lenses]}）")
    desc = str(lens.get("description") or "")
    rules = split_description(desc)
    verify_lossless(desc, rules)
    slug = _slug(lens_name)
    for n, r in enumerate(rules, start=1):
        r["rule_id"] = f"{profile_id}.{slug}.{n:03d}"
        r["text_sha256"] = _sha(r["text"])[:12]
        r.pop("seq", None)
    return {
        "lens": lens_name,
        "weight": lens.get("weight"),
        "source_chars": len(desc),
        "source_sha256": _sha(desc),
        "rule_count": len(rules),
        "clear": sum(1 for r in rules if r["status"] == "clear"),
        "needs_review": sum(1 for r in rules if r["status"] == "needs_review"),
        "rules": rules,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="把画像的长 description 拆成候选条目（同输入 ID 稳定，不改源画像）")
    ap.add_argument("profile", type=Path, help="画像 JSON 路径")
    ap.add_argument("--lens", action="append", required=True, help="要拆的镜头名，可多次给出")
    ap.add_argument("--out", type=Path, help="候选产物写到哪（不给则打到 stdout）")
    args = ap.parse_args(argv)

    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    pid = str(profile.get("id") or args.profile.stem)
    result = {
        "schema_version": 1,
        "kind": "lens_split_candidate",
        "profile_id": pid,
        "profile_sha256": _sha(args.profile.read_text(encoding="utf-8")),
        "note": "候选产物，未写回生产画像；needs_review 的条目需用户裁定后才能定稿",
        "lenses": [split_lens(profile, name, profile_id=pid) for name in args.lens],
    }
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        tot = sum(item["rule_count"] for item in result["lenses"])
        rev = sum(item["needs_review"] for item in result["lenses"])
        for item in result["lenses"]:
            print(f"  {item['lens']}（weight {item['weight']}）：{item['source_chars']} 字 → "
                  f"{item['rule_count']} 条（{item['clear']} 条清晰，{item['needs_review']} 条待裁定）")
        print(f"→ {args.out}　合计 {tot} 条，其中 {rev} 条需要你裁定；逐字可还原已核验")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
