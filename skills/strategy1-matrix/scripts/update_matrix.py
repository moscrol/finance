from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def stock_block(items: list[dict], default_tag: str) -> str:
    if not items:
        return '<span class="stock"><span class="tag obs">OBS</span>当日无明确输出。</span>'
    parts = []
    for item in items:
        tag = esc(item.get("tag") or default_tag)
        name = esc(item.get("name"))
        code = esc(item.get("code"))
        reason = esc(item.get("reason"))
        code_text = f" {code}" if code else ""
        cls = "obs" if tag.upper().startswith("OBS") else "t2" if tag.upper().startswith("T2") else "t1"
        parts.append(
            f'<span class="stock"><span class="tag {cls}">{tag}</span>'
            f'<b>{name}{code_text}</b><br>{reason}</span>'
        )
    return "".join(parts)


def render_row(row: dict) -> str:
    date = esc(row["date"])
    return "".join([
        f'<tr class="filled"><td class="date">{date}</td>',
        f'<td>{esc(row.get("state"))}</td>',
        f'<td>{stock_block(row.get("t1") or [], "T1")}</td>',
        f'<td>{stock_block(row.get("t2") or [], "T2")}</td>',
        f'<td>{stock_block(row.get("obs") or [], "OBS")}</td>',
        f'<td>{esc(row.get("verify"))}</td></tr>',
    ])


def update_range_text(text: str, date: str) -> str:
    text = re.sub(r"策略1每日优先个股矩阵 2026-04-08~\d{4}-\d{2}-\d{2}", f"策略1每日优先个股矩阵 2026-04-08~{date}", text)
    text = re.sub(r"日期范围：2026-04-08 ~ \d{4}-\d{2}-\d{2}", f"日期范围：2026-04-08 ~ {date}", text)
    text = re.sub(r"4\.8-\d+\.\d+", f"4.8-{int(date[5:7])}.{int(date[8:10])}", text)
    progress_matches = list(re.finditer(r"回填进度：([^<]+)", text))
    for match in reversed(progress_matches):
        progress = match.group(1)
        dates = [x.strip() for x in progress.split("、") if x.strip()]
        if date not in dates:
            dates.append(date)
        replacement = "回填进度：" + "、".join(dates)
        text = text[:match.start()] + replacement + text[match.end():]
        break
    return text


def upsert_row(text: str, date: str, row_html: str) -> tuple[str, str]:
    pattern = re.compile(rf'<tr[^>]*>\s*<td class="date">{re.escape(date)}</td>.*?</tr>', re.S)
    if pattern.search(text):
        return pattern.sub(row_html, text, count=1), "replaced"
    marker = "</tbody></table></div>"
    if marker not in text:
        raise RuntimeError("matrix tbody marker not found")
    return text.replace(marker, row_html + marker, 1), "inserted"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--row-json", required=True)
    parser.add_argument("--matrix", default="复盘/matrices/strategy1-priority-stock-matrix.html")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    row_path = Path(args.row_json)
    matrix_path = Path(args.matrix)
    row = json.loads(row_path.read_text(encoding="utf-8"))
    date = str(row["date"])
    text = matrix_path.read_text(encoding="utf-8")
    row_html = render_row(row)
    updated, action = upsert_row(text, date, row_html)
    updated = update_range_text(updated, date)

    print(json.dumps({
        "matrix": str(matrix_path),
        "date": date,
        "action": action,
        "t1": len(row.get("t1") or []),
        "t2": len(row.get("t2") or []),
        "obs": len(row.get("obs") or []),
        "dry_run": bool(args.dry_run),
    }, ensure_ascii=False))

    if not args.dry_run:
        matrix_path.write_text(updated, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
