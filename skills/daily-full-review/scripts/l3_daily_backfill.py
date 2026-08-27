#!/usr/bin/env python3
"""全量复盘后的 L3 补录编排（放在 agent-daily 之后跑）。

两个任务合一：
1. 例行池：strategy1 HTML 矩阵**当日行**的 T1/T2/OBS 代码，每日查巨潮公告 + 交易所互动
   （沪市 sse_einteract / 深市 irm_szse / 北交所仅 cninfo）。不扫历史全表。
2. agent-daily 缺口：从 <date>-research-queue.json（fallback daily-agent.json）提取「找官方证据/今日 IMA」
   目标中的股票代码，并入本轮查询。完整 daily-agent 仅用于补充证据裁判「重点验证/能力栈候选」。

产出只进审核队列：apply 默认 dry-run；加 --apply 才写 wiki，且永远不带
--reviewed（review_required=true），不碰 relations/evidence_index、不提升图谱。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence.services.research_queue import extract_queue, load_research_queue  # noqa: E402

CODE_RE = re.compile(r"\b(\d{6})\b")
DATE_ROW_RE = re.compile(
    r'<tr[^>]*>\s*<td class="date">(?P<date>\d{4}-\d{2}-\d{2})</td>.*?</tr>',
    re.S,
)


def _codes_in(text: str) -> list[str]:
    seen: dict[str, None] = {}
    for match in CODE_RE.finditer(text):
        seen.setdefault(match.group(1), None)
    return list(seen)


def _html_row_for_date(text: str, date: str) -> str | None:
    for match in DATE_ROW_RE.finditer(text):
        if match.group("date") == date:
            return match.group(0)
    return None


def _matrix_codes(matrix_path: Path, date: str | None = None) -> list[str]:
    """HTML 只取指定交易日那一行；缺行则空池（fail closed，不退回扫全表）。

    自定义 md/txt 仍按全文抽代码，方便临时名单。
    """
    if not matrix_path.exists():
        return []
    text = matrix_path.read_text(encoding="utf-8")
    if matrix_path.suffix.lower() == ".html":
        if not date:
            return []
        row = _html_row_for_date(text, date)
        return _codes_in(row) if row else []
    return _codes_in(text)


def _agent_gap_codes(exports_dir: Path, date: str) -> list[str]:
    _path, payload = load_research_queue(exports_dir, date=date)
    targets: list[str] = []
    queue = extract_queue(payload) or {}
    for key in ("today_find_official_evidence", "today_do_ima"):
        for item in queue.get(key) or []:
            if isinstance(item, dict):
                targets.append(str(item.get("目标") or ""))
    agent_json = exports_dir / f"{date}-daily-agent.json"
    if agent_json.exists():
        try:
            report = json.loads(agent_json.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            report = {}
        decision = report.get("decision") or {}
        rows = decision.values() if isinstance(decision, dict) else []
        for group in rows:
            for row in group or []:
                if not isinstance(row, dict):
                    continue
                judgment = row.get("research_judgment") or {}
                if judgment.get("证据状态") in {"重点验证", "能力栈候选"}:
                    targets.append(str(judgment.get("目标") or ""))
    seen: dict[str, None] = {}
    for target in targets:
        for match in CODE_RE.finditer(target):
            seen.setdefault(match.group(1), None)
    return list(seen)


def _sources_for(code: str) -> str:
    if code.startswith("6"):
        return "cninfo,sse_einteract"
    if code.startswith(("0", "3")):
        return "cninfo,irm_szse"
    return "cninfo"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", required=True, help="复盘交易日 YYYY-MM-DD")
    ap.add_argument("--kb-wiki", default="/Users/a77/knowledge-base-private/wiki")
    ap.add_argument("--days", type=int, default=3, help="查询近 N 天（日常增量默认 3）")
    ap.add_argument("--limit", type=int, default=12)
    ap.add_argument("--apply", action="store_true", help="真正写入审核队列；默认只 dry-run")
    ap.add_argument(
        "--matrix",
        default="复盘/matrices/strategy1-priority-stock-matrix.html",
        help="例行候选池（HTML 当日行 / 自定义名单）；传空字符串可跳过例行池只跑 agent 缺口",
    )
    ap.add_argument("--exports-dir", default="market_feature_store/exports")
    ap.add_argument("--out-dir", default=None, help="payload 输出目录，默认 /tmp/l3_daily/<date>")
    args = ap.parse_args()

    out_dir = Path(args.out_dir or f"/tmp/l3_daily/{args.date}")
    out_dir.mkdir(parents=True, exist_ok=True)

    pool = _matrix_codes(Path(args.matrix), args.date) if args.matrix else []
    gaps = _agent_gap_codes(Path(args.exports_dir), args.date)
    codes = list(dict.fromkeys(pool + gaps))
    if not codes:
        print("没有候选代码（矩阵缺失且 agent-daily 无缺口目标），跳过。")
        return 0
    print(f"候选 {len(codes)} 只（例行池 {len(pool)}，agent 缺口 {len(gaps)}，去重后）")

    summary_lines = ["code\tsources\tcand\tapplied\tnote"]
    total_cand = 0
    for code in codes:
        sources = _sources_for(code)
        payload_path = out_dir / f"{code}.json"
        lookup = subprocess.run(
            [
                sys.executable, "-m", "intelligence.cli", "l3-ingest", "company",
                code, "--source", sources, "--days", str(args.days),
                "--limit", str(args.limit), "--out-json", str(payload_path),
            ],
            capture_output=True, text=True,
        )
        if lookup.returncode != 0 or not payload_path.exists():
            summary_lines.append(f"{code}\t{sources}\t-\tno\tlookup失败 rc={lookup.returncode}")
            continue
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        cand = len(payload.get("candidates") or [])
        total_cand += cand
        if not cand:
            summary_lines.append(f"{code}\t{sources}\t0\tno\t无候选")
            continue
        apply_cmd = [
            sys.executable, "-m", "intelligence.cli", "l3-ingest", "apply",
            str(payload_path), "--kb-wiki", args.kb_wiki,
        ]
        applied = "dry-run"
        if args.apply:
            apply_cmd.append("--apply")
            applied = "yes"
        result = subprocess.run(apply_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            applied = f"apply失败 rc={result.returncode}"
        summary_lines.append(f"{code}\t{sources}\t{cand}\t{applied}\t")

    summary_path = out_dir / "summary.tsv"
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    print(f"总候选 {total_cand} 条；summary: {summary_path}")
    print("提醒：本脚本永不带 --reviewed；候选只进审核队列，提升图谱需人工复核。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
