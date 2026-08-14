#!/usr/bin/env python3
"""知识库证据断更监控：按证据线（source_quality）分别检查最新批次，超阈值告警。

背景：盘面数据有 18:30 全量复盘链日更，但知识库研报证据靠人工 PDF ingest，
断更没人管（厦钨题暴露：证据全停在 01-29 批次）。本脚本只做「断更检测 + 告警」，
不代替 ingest 本身。

判定口径：读取 wiki/relations/evidence_index.json，按 source_quality 分组取
max(source_date)。只看 source_date 字段，**不使用文件 mtime**（任何批量改写
frontmatter 或 git checkout 都会刷新 mtime，导致假绿）。

用法：
  python3 scripts/check_kb_freshness.py                 # 打印各线状态，超阈值退出码 2
  python3 scripts/check_kb_freshness.py --max-age 7 --alert   # 超 7 天经飞书告警
  python3 scripts/check_kb_freshness.py --watch-lanes official_disclosure,broker_research_high
知识库路径：env `KNOWLEDGE_WIKI`，默认 ~/knowledge-base-private/wiki。

关键证据线（默认监控）：
  - official_disclosure：巨潮公告
  - broker_research_high：卖方研报/题材
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

# 默认监控的关键证据线（任一超阈值即告警）
DEFAULT_WATCH_LANES = ["official_disclosure", "broker_research_high"]


def load_evidence_freshness(wiki_root: Path) -> dict[str, tuple[date | None, int]]:
    """从 evidence_index.json 加载各证据线的最新日期与条目数。
    
    返回：{source_quality: (最新日期, 条目数)}
    """
    evidence_path = wiki_root.parent / "wiki" / "relations" / "evidence_index.json"
    if not evidence_path.exists():
        return {}
    
    try:
        data = json.loads(evidence_path.read_text(encoding="utf-8"))
        items = data.get("items", [])
    except (json.JSONDecodeError, OSError):
        return {}
    
    by_quality: dict[str, list[str]] = defaultdict(list)
    for item in items:
        if not isinstance(item, dict):
            continue
        source_date_str = str(item.get("source_date") or "")[:10]
        source_quality = str(item.get("source_quality") or "?")
        
        # 只收集有效日期（YYYY-MM-DD 格式且以 20 开头）
        if source_date_str and source_date_str.startswith("20"):
            try:
                date.fromisoformat(source_date_str)  # 验证格式
                by_quality[source_quality].append(source_date_str)
            except ValueError:
                continue
    
    # 转换为 (最新日期, 条目数)
    result: dict[str, tuple[date | None, int]] = {}
    for quality, dates in by_quality.items():
        if dates:
            latest = date.fromisoformat(max(dates))
            result[quality] = (latest, len(dates))
        else:
            result[quality] = (None, 0)
    
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-age", type=int, default=7, help="断更阈值（天），默认 7")
    ap.add_argument("--alert", action="store_true", help="超阈值时经飞书告警（notify_feishu.py）")
    ap.add_argument(
        "--watch-lanes",
        type=str,
        help=f"监控的证据线（逗号分隔），默认 {','.join(DEFAULT_WATCH_LANES)}",
    )
    args = ap.parse_args()

    watch_lanes = (
        args.watch_lanes.split(",") if args.watch_lanes else DEFAULT_WATCH_LANES
    )

    wiki = Path(os.environ.get("KNOWLEDGE_WIKI") or Path.home() / "knowledge-base-private" / "wiki")
    freshness = load_evidence_freshness(wiki)
    
    if not freshness:
        msg = f"知识库断更检查：{wiki.parent}/wiki/relations/evidence_index.json 不存在或无有效证据"
        print(msg)
        return 2
    
    # 按最新日期降序排列
    sorted_lanes = sorted(
        freshness.items(),
        key=lambda kv: (kv[1][0] or date.min, kv[1][1]),
        reverse=True,
    )
    
    print("=== 知识库证据新鲜度（按 source_quality 分线）===")
    today = date.today()
    stale_lanes: list[tuple[str, int]] = []
    
    for quality, (latest, count) in sorted_lanes:
        if latest is None:
            age_str = "unknown"
            age_days = None
        else:
            age_days = (today - latest).days
            age_str = f"{age_days} 天前"
        
        status = "⚠️ 断更" if age_days and age_days > args.max_age else "✓"
        marker = "🔍" if quality in watch_lanes else " "
        print(f"{marker} {status:8s} {quality:32s}  最新={str(latest) if latest else 'N/A':10s}  {age_str:12s}  条目数={count}")
        
        # 只有监控线超阈值才记录
        if quality in watch_lanes and age_days and age_days > args.max_age:
            stale_lanes.append((quality, age_days))
    
    print(f"\n阈值：{args.max_age} 天")
    print(f"监控线：{', '.join(watch_lanes)}")
    
    if stale_lanes:
        msg_parts = [f"{quality}（{age}天前）" for quality, age in stale_lanes]
        msg = f"⚠️ 知识库证据断更：{', '.join(msg_parts)}，阈值 {args.max_age} 天——研报证据需要补 ingest"
        print(f"\n{msg}")
        
        if args.alert:
            sys.path.insert(0, str(Path(__file__).parent))
            from notify_feishu import send_alert
            send_alert(msg)
        
        return 2
    else:
        print("\n✓ 所有监控线均在阈值内")
        return 0


if __name__ == "__main__":
    sys.exit(main())
