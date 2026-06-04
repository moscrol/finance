"""同步复盘会市场页周均线/偏离度到 fact_market_daily。"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime

from ..db import connect, init_db

CDP_PROXY = os.environ.get("CDP_HOST", "http://localhost:3456")
MARKET_URL = "https://fupanhui.com/workspace/data/market"


def _http_json(url: str, timeout: int = 30):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read())


def _cdp_new(url: str) -> str:
    data = _http_json(f"{CDP_PROXY}/new?url=" + urllib.parse.quote(url, safe=""), timeout=30)
    target = data.get("targetId") or data.get("id")
    if not target:
        raise RuntimeError("CDP proxy 未返回 targetId")
    return target


def _cdp_close(target: str) -> None:
    try:
        urllib.request.urlopen(f"{CDP_PROXY}/close?target={target}", timeout=10).read()
    except Exception:
        pass


def _cdp_eval(target: str, expr: str, timeout: int = 30, retries: int = 3):
    last_error = None
    for attempt in range(max(1, retries)):
        try:
            req = urllib.request.Request(
                f"{CDP_PROXY}/eval?target={target}",
                data=expr.encode(),
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result = json.loads(resp.read())
            if isinstance(result, dict) and "value" in result:
                return result["value"]
            last_error = result.get("error") if isinstance(result, dict) else result
        except Exception as exc:
            last_error = exc
            try:
                data = urllib.parse.urlencode({"expr": expr}).encode()
                req = urllib.request.Request(
                    f"{CDP_PROXY}/eval?target={target}",
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    result = json.loads(resp.read())
                if isinstance(result, dict) and "value" in result:
                    return result["value"]
                last_error = result.get("error") if isinstance(result, dict) else result
            except Exception as fallback_exc:
                last_error = fallback_exc
        if attempt < retries - 1:
            time.sleep(1 * (attempt + 1))
    raise RuntimeError(f"CDP eval 失败: {last_error}")


def _fetch_market_deviation() -> dict:
    target = _cdp_new(MARKET_URL)
    try:
        time.sleep(4)
        canvas_count = _cdp_eval(target, "document.querySelectorAll('canvas').length")
        if not canvas_count:
            raise RuntimeError("market data 页面无 canvas")
        hover_js = """
        var canvas = document.querySelectorAll('canvas')[0];
        var rect = canvas.getBoundingClientRect();
        var x = rect.x + rect.width * 0.97;
        var y = rect.y + rect.height * 0.50;
        canvas.dispatchEvent(new PointerEvent('pointermove', {clientX: x, clientY: y, bubbles: true, pointerId: 1, pointerType: 'mouse'}));
        canvas.dispatchEvent(new MouseEvent('mousemove', {clientX: x, clientY: y, bubbles: true}));
        'done';
        """
        _cdp_eval(target, hover_js)
        time.sleep(1)
        tooltip_js = """
        var overlays = document.querySelectorAll('div[style*=\"z-index\"]');
        var tooltipText = '';
        for (var i = 0; i < overlays.length; i++) {
          var st = window.getComputedStyle(overlays[i]);
          var txt = overlays[i].innerText || '';
          if (st.display !== 'none' && txt.indexOf('周均线') >= 0) { tooltipText = txt; break; }
        }
        tooltipText;
        """
        tooltip = _cdp_eval(target, tooltip_js) or ""
        m_ma = re.search(r"周均线[:：]\s*(\d+(?:\.\d+)?)", tooltip)
        m_dev = re.search(r"偏离[:：]\s*([+-]?\d+(?:\.\d+)?)%?", tooltip)
        if not (m_ma and m_dev):
            raise RuntimeError("tooltip 未提取到周均线/偏离度: " + tooltip.replace("\n", " | "))
        return {
            "sh_week_ma": float(m_ma.group(1)),
            "sh_deviation_pct": float(m_dev.group(1)),
            "tooltip": tooltip,
        }
    finally:
        _cdp_close(target)


def sync_market_deviation(trade_date: str | None = None) -> dict:
    init_db()
    con = connect()
    try:
        if not trade_date:
            row = con.execute("SELECT MAX(trade_date) FROM fact_market_daily").fetchone()
            trade_date = str(row[0]) if row and row[0] else None
        if not trade_date:
            raise RuntimeError("无目标交易日, 请先同步 fact_market_daily 或显式传 --trade-date")
        data = _fetch_market_deviation()
        con.execute(
            """
            UPDATE fact_market_daily
            SET sh_week_ma = ?, sh_deviation_pct = ?, updated_at = ?
            WHERE trade_date = ?
            """,
            [data["sh_week_ma"], data["sh_deviation_pct"], datetime.now(), trade_date],
        )
        row = con.execute(
            """
            SELECT trade_date, sh_week_ma, sh_deviation_pct
            FROM fact_market_daily
            WHERE trade_date = ?
            """,
            [trade_date],
        ).fetchone()
    finally:
        con.close()
    return {
        "trade_date": trade_date,
        "sh_week_ma": data["sh_week_ma"],
        "sh_deviation_pct": data["sh_deviation_pct"],
        "tooltip": data["tooltip"],
        "current": row,
    }
