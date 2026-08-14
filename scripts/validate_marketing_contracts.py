#!/usr/bin/env python3
"""只读校验 docs/marketing/ 数据契约与生成内容。

用法：python3 scripts/validate_marketing_contracts.py
退出码：0=通过，1=存在错误。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
MARKETING = ROOT / "docs" / "marketing"

PROHIBITED_PATTERNS = [
    "保证收益",
    "稳赚",
    "自动赚钱",
    "明天买什么",
    "保证抓涨停",
    "替你买卖",
    "自动下单",
]

PERFORMANCE_REQUIRED = [
    "content_id",
    "brief_id",
    "product_ids",
    "persona",
    "channel",
    "hook_type",
    "claim_ids",
    "metrics",
    "human_notes",
    "next_action",
]


def load_yaml(path: Path):
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> int:
    errors: list[str] = []

    products = load_yaml(MARKETING / "products.yaml")["products"]
    features = load_yaml(MARKETING / "features.yaml")["features"]
    claims = load_yaml(MARKETING / "claims.yaml")["claims"]
    personas = load_yaml(MARKETING / "personas.yaml")["personas"]

    product_ids = {p.get("id") for p in products}
    for p in products:
        for field in ("id", "name", "positioning", "public_boundary"):
            if not p.get(field):
                errors.append(f"products.yaml: {p.get('id', '?')} 缺字段 {field}")
        pb = p.get("public_boundary") or {}
        if not pb.get("can_say") or not pb.get("cannot_say"):
            errors.append(f"products.yaml: {p.get('id')} public_boundary 缺 can_say/cannot_say")

    feature_ids = set()
    for f in features:
        fid = f.get("id")
        feature_ids.add(fid)
        if f.get("product_id") not in product_ids:
            errors.append(f"features.yaml: {fid} product_id 不在 products 中")
        if not f.get("evidence_refs"):
            errors.append(f"features.yaml: {fid} 缺 evidence_refs")

    claim_ids = set()
    for c in claims:
        cid = c.get("id")
        claim_ids.add(cid)
        for pid in c.get("product_ids", []):
            if pid not in product_ids:
                errors.append(f"claims.yaml: {cid} product_id {pid} 不存在")
        for sfid in c.get("support_feature_ids", []):
            if sfid not in feature_ids:
                errors.append(f"claims.yaml: {cid} support_feature_id {sfid} 不存在")

    persona_ids = {p.get("id") for p in personas}

    for brief_path in sorted((MARKETING / "content-briefs").glob("*.yaml")):
        brief = load_yaml(brief_path)
        for rcid in brief.get("required_claim_ids", []):
            if rcid not in claim_ids:
                errors.append(f"{brief_path.name}: required_claim_id {rcid} 不存在")
        for pid in brief.get("products", []):
            if pid not in product_ids:
                errors.append(f"{brief_path.name}: product {pid} 不存在")
        for per in brief.get("personas", []):
            if per not in persona_ids:
                errors.append(f"{brief_path.name}: persona {per} 不存在")

    for gen_path in sorted((MARKETING / "generated").glob("*.md")):
        text = gen_path.read_text(encoding="utf-8")
        for pat in PROHIBITED_PATTERNS:
            for m in re.finditer(re.escape(pat), text):
                line_no = text.count("\n", 0, m.start()) + 1
                line = text.splitlines()[line_no - 1]
                if pat in ("保证收益", "自动赚钱", "明天买什么") and (
                    "无" in line or "不" in line or "禁" in line
                ):
                    continue  # 自查/否定语境
                errors.append(f"{gen_path.name}:{line_no} 命中禁用表达「{pat}」")
        for cid in re.findall(r"claim-[a-z0-9-]+", text):
            if cid not in claim_ids:
                errors.append(f"{gen_path.name}: 引用了未登记 claim {cid}")

    perf = MARKETING / "performance" / "marketing-performance.jsonl"
    if perf.exists():
        for i, raw in enumerate(perf.read_text(encoding="utf-8").splitlines(), 1):
            if not raw.strip():
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError as e:
                errors.append(f"marketing-performance.jsonl:{i} JSON 解析失败: {e}")
                continue
            for field in PERFORMANCE_REQUIRED:
                if field not in rec:
                    errors.append(f"marketing-performance.jsonl:{i} 缺字段 {field}")

    if errors:
        print(f"校验失败，共 {len(errors)} 个问题：")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(
        "校验通过："
        f"products={len(products)} features={len(features)} "
        f"claims={len(claims)} personas={len(personas)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
