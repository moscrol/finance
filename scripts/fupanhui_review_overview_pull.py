#!/usr/bin/env python3
"""复盘会「复盘总览」逐日记录抓取（只抓不写，输出 JSON）。

通过本机 CDP 代理，在用户已登录的复盘会标签页里分页调用
``GET /api/v1/client/reviews/overview?days=N&offset=M&direction=older``，
把逐日的内外层市场周期（``cycle_stage`` / ``external_cycle``）、量能比、宽度、
容量 / 领涨核心个股、申万前三等原样落成 JSON。载入旁路库由
``scripts/teaching_framework.py load-reference --json <文件>`` 完成。

创始人 2026-09-07：平台标注「可以作为置信度较高的来源……当参照」。它们是事后写入的
（``updated_at`` 晚于交易日），只能作对照 / 校准参照，不能作 PIT 上下文，也绝不进标签计算。

用法:
    python3 scripts/fupanhui_review_overview_pull.py --out db/vendor/fupanhui_review_overview.json
    python3 scripts/fupanhui_review_overview_pull.py --out ... --since 2024-11-01 --target <tab_id>

每次 eval 只取一页（代理对单次执行有超时），页间停 ``--delay`` 秒；非 200 立即停。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_PROXY = "http://localhost:3456"
API_PATH = "/api/v1/client/reviews/overview"

# 单页取数：Authorization 从页面 localStorage 的 user_token 取（页面自身的请求就是这样带的）。
PAGE_JS = """
(async () => {{
  let tok = localStorage.getItem("user_token");
  try {{ const p = JSON.parse(tok); tok = p.access_token || p.token || p.accessToken || tok; }} catch (e) {{}}
  const headers = {{"Authorization": "Bearer " + String(tok).replace(/^"|"$/g, "")}};
  const r = await fetch("{path}?days={days}&offset={offset}&direction=older", {{headers}});
  const text = await r.text();
  return JSON.stringify({{status: r.status, body: text.slice(0, 2000000)}});
}})()
"""


def _get(proxy: str, endpoint: str, timeout: int = 60) -> dict:
    with urllib.request.urlopen(f"{proxy}{endpoint}", timeout=timeout) as resp:
        return json.loads(resp.read())


def _eval(proxy: str, target: str, js: str, timeout: int = 60) -> dict:
    req = urllib.request.Request(
        f"{proxy}/eval?target={urllib.parse.quote(target)}", data=js.encode("utf-8"), method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read())
    if "error" in result:
        raise RuntimeError(f"CDP eval 失败: {result['error']}")
    value = result.get("value")
    return json.loads(value) if isinstance(value, str) else value


def find_target(proxy: str, host: str = "fupanhui.com") -> str:
    targets = _get(proxy, "/targets")
    for t in targets if isinstance(targets, list) else []:
        if t.get("type") == "page" and host in str(t.get("url", "")):
            return str(t["targetId"])
    raise RuntimeError(f"没有打开的 {host} 标签页；请先在 Chrome 里登录并打开复盘会")


def pull(proxy: str, target: str, *, since: str | None, days: int, delay: float, max_pages: int) -> dict:
    items: list[dict] = []
    offset = 0
    available_since = None
    pages = 0
    retries = 0
    while pages < max_pages:
        page = _eval(proxy, target, PAGE_JS.format(path=API_PATH, days=days, offset=offset))
        if page.get("status") == 429 and retries < 4:
            # 限流：退避后重试同一页；连续四次仍 429 才放弃（另一分支的「429 熔断」经验）。
            retries += 1
            wait = 30 * retries
            print(f"HTTP 429（offset={offset}），{wait}s 后重试第 {retries} 次", file=sys.stderr)
            time.sleep(wait)
            continue
        if page.get("status") != 200:
            print(f"停止：HTTP {page.get('status')}（offset={offset}）", file=sys.stderr)
            break
        retries = 0
        body = json.loads(page["body"])
        data = body.get("data") or {}
        batch = data.get("items") or []
        available_since = available_since or data.get("available_since")
        if not batch:
            break
        items.extend(batch)
        offset += len(batch)
        pages += 1
        last_day = str(batch[-1].get("trade_date"))
        print(f"页 {pages}: {len(batch)} 条，最早 {last_day}", file=sys.stderr)
        if not data.get("has_more") or (since and last_day < since):
            break
        time.sleep(delay)
    seen: set[str] = set()
    unique = []
    for it in items:
        d = str(it.get("trade_date"))
        if d in seen or (since and d < since):
            continue
        seen.add(d)
        unique.append(it)
    unique.sort(key=lambda it: str(it.get("trade_date")))
    return {
        "source": "fupanhui.com " + API_PATH,
        "pulled_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "available_since": available_since,
        "since_filter": since,
        "pages": pages,
        "items": unique,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="抓取复盘会复盘总览逐日记录为 JSON（只抓不写库）")
    ap.add_argument("--out", required=True, help="输出 JSON 路径（建议 db/vendor/ 下，该目录不进仓）")
    ap.add_argument("--proxy", default=DEFAULT_PROXY)
    ap.add_argument("--target", default=None, help="CDP 目标 tab id；缺省自动找已打开的 fupanhui.com 标签页")
    ap.add_argument("--since", default=None, help="只保留 ≥ 此日期（YYYY-MM-DD）的记录；缺省取到 available_since")
    ap.add_argument("--days", type=int, default=20, help="每页条数")
    ap.add_argument("--delay", type=float, default=1.0, help="页间停顿秒数")
    ap.add_argument("--max-pages", type=int, default=400)
    args = ap.parse_args(argv)
    try:
        target = args.target or find_target(args.proxy)
        payload = pull(args.proxy, target, since=args.since, days=args.days, delay=args.delay, max_pages=args.max_pages)
    except (RuntimeError, urllib.error.URLError, json.JSONDecodeError, KeyError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    first = payload["items"][0]["trade_date"] if payload["items"] else None
    last = payload["items"][-1]["trade_date"] if payload["items"] else None
    print(json.dumps({"out": str(out), "items": len(payload["items"]), "first_day": first, "last_day": last,
                      "available_since": payload["available_since"], "pages": payload["pages"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
