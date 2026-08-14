#!/usr/bin/env python3
"""知识库证据断更监控：检查 wiki/sources 最新研报/证据批次距今多少天，超阈值告警。

背景：盘面数据有 18:30 全量复盘链日更，但知识库研报证据靠人工 PDF ingest，
断更没人管（厦钨题暴露：证据全停在 01-29 批次）。本脚本只做「断更检测 + 告警」，
不代替 ingest 本身。

判定口径：wiki/sources/*.md 里取「文件名中的 YYYY-MM-DD / YYYYMMDD 日期」与
「文件 mtime」两者的最大值作为该批次日期，全库最大者即最新批次。

用法：
  python3 scripts/check_kb_freshness.py                 # 打印状态，超阈值退出码 2
  python3 scripts/check_kb_freshness.py --max-age 7 --alert   # 超 7 天经飞书告警
知识库路径：env `KNOWLEDGE_WIKI`，默认 ~/knowledge-base-private/wiki。
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

_DATE_RE = re.compile(r"(20\d{2})[-_]?(\d{2})[-_]?(\d{2})")


def _date_from_name(name: str) -> date | None:
    m = _DATE_RE.search(name)
    if not m:
        return None
    try:
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None
    return d if d <= date.today() else None


def latest_source_date(wiki: Path) -> tuple[date | None, int]:
    """返回 (最新批次日期, source 文件数)；目录不存在返回 (None, 0)。"""
    sources = wiki / "sources"
    if not sources.is_dir():
        return None, 0
    latest: date | None = None
    count = 0
    for p in sources.glob("*.md"):
        count += 1
        candidates = [_date_from_name(p.name)]
        try:
            candidates.append(datetime.fromtimestamp(p.stat().st_mtime).date())
        except OSError:
            pass
        for d in candidates:
            if d is not None and (latest is None or d > latest):
                latest = d
    return latest, count


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-age", type=int, default=7, help="断更阈值（天），默认 7")
    ap.add_argument("--alert", action="store_true", help="超阈值时经飞书告警（notify_feishu.py）")
    args = ap.parse_args()

    wiki = Path(os.environ.get("KNOWLEDGE_WIKI") or Path.home() / "knowledge-base-private" / "wiki")
    latest, count = latest_source_date(wiki)
    if latest is None:
        msg = f"知识库断更检查：{wiki}/sources 不存在或无 source note"
        print(msg)
        stale = True
        age = None
    else:
        age = (date.today() - latest).days
        stale = age > args.max_age
        status = "断更" if stale else "正常"
        msg = f"知识库证据{status}：最新批次 {latest}（{age} 天前），共 {count} 篇 source note，阈值 {args.max_age} 天"
        print(msg)

    if stale and args.alert:
        sys.path.insert(0, str(Path(__file__).parent))
        from notify_feishu import send_alert

        send_alert(f"⚠️ {msg}——研报证据需要补 ingest（PDF 批次）")
    return 2 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
