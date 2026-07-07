#!/usr/bin/env python3
"""只读生成上下文 CLI（营销链路 P0，spec §19-3）。

按 brief 组装内容生成所需上下文包：产品定位与表达边界、所需 claims 及其
支撑 features/证据、目标 personas、约束与配额，输出 markdown 到 stdout。
不写任何文件、不调用 LLM，供 agent 生成内容前作为唯一显式上下文。

用法：
  python3 scripts/marketing_generation_context.py --brief 2026-07-05-launch-batch
  python3 scripts/marketing_generation_context.py --list
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
MARKETING = ROOT / "docs" / "marketing"


def _load(name: str):
    with (MARKETING / name).open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_context(brief_id: str) -> str:
    brief_path = MARKETING / "content-briefs" / f"{brief_id}.yaml"
    if not brief_path.exists():
        raise SystemExit(f"brief 不存在: {brief_path}")
    with brief_path.open(encoding="utf-8") as f:
        brief = yaml.safe_load(f)

    products = {p["id"]: p for p in _load("products.yaml")["products"]}
    features = {x["id"]: x for x in _load("features.yaml")["features"]}
    claims = {c["id"]: c for c in _load("claims.yaml")["claims"]}
    personas = {p["id"]: p for p in _load("personas.yaml")["personas"]}

    lines: list[str] = []
    add = lines.append
    add(f"# 生成上下文包 · {brief['brief_id']}")
    add("")
    add(f"目标：{brief.get('objective', '')}")
    add(f"渠道：{', '.join(brief.get('channels', []))}")
    quotas = brief.get("quotas") or {}
    if quotas:
        add("配额：" + "、".join(f"{k}={v}" for k, v in quotas.items()))
    add("")

    add("## 产品定位与表达边界")
    for pid in brief.get("products", []):
        p = products.get(pid)
        if p is None:
            raise SystemExit(f"brief 引用未登记产品: {pid}")
        add(f"### {p['name']} ({pid})")
        add(f"- 定位：{p['positioning']}")
        pb = p.get("public_boundary", {})
        add("- 可以说：" + "；".join(pb.get("can_say", [])))
        add("- 不可以说：" + "；".join(pb.get("cannot_say", [])))
        add("")

    add("## 目标人群")
    for per_id in brief.get("personas", []):
        per = personas.get(per_id)
        if per is None:
            raise SystemExit(f"brief 引用未登记 persona: {per_id}")
        add(
            f"- {per['name']}（{per.get('priority', '')}）："
            f"痛点 {'；'.join(per.get('pain_points', []))}；CTA {per.get('cta', '')}"
        )
    add("")

    add("## 必用卖点（claims）与支撑证据")
    for cid in brief.get("required_claim_ids", []):
        c = claims.get(cid)
        if c is None:
            raise SystemExit(f"brief 引用未登记 claim: {cid}")
        add(f"### {cid}" + ("（需人工复核）" if c.get("review_required") else ""))
        add(f"- 表述：{c['text']}")
        add("- 禁止改写为：" + "；".join(c.get("prohibited_rewrites", [])))
        for fid in c.get("support_feature_ids", []):
            feat = features.get(fid)
            if feat is None:
                raise SystemExit(f"claim {cid} 引用未登记 feature: {fid}")
            refs = "; ".join(
                f"{r.get('repo')}:{r.get('path')}#{r.get('section', '')}"
                for r in feat.get("evidence_refs", [])
            )
            add(f"- 支撑功能：{feat['name']}（{fid}）｜证据：{refs}")
        add("")

    add("## 约束（逐条遵守）")
    for cst in brief.get("constraints", []):
        add(f"- {cst}")
    add("")
    add("## 内容类型")
    for ct in brief.get("content_types", []):
        add(f"- {ct}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", help="brief_id（不含 .yaml）")
    parser.add_argument("--list", action="store_true", help="列出可用 brief")
    args = parser.parse_args()
    if args.list:
        for p in sorted((MARKETING / "content-briefs").glob("*.yaml")):
            print(p.stem)
        return 0
    if not args.brief:
        parser.error("需要 --brief 或 --list")
    print(build_context(args.brief), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
