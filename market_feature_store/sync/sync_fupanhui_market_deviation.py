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
        # ECharts canvas 在本机网络下约需 5-6s 才渲染完, 固定 sleep 易踩空,
        # 改为轮询等待 canvas 出现 (最长 ~15s)。
        canvas_count = 0
        deadline = time.time() + 15
        while time.time() < deadline:
            canvas_count = _cdp_eval(target, "document.querySelectorAll('canvas').length") or 0
            if canvas_count:
                break
            time.sleep(1)
        if not canvas_count:
            raise RuntimeError("market data 页面无 canvas")
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
        # 最新交易日数据点不在画布最右边缘 (0.97 会落到数据区之外, tooltip 取不到),
        # 在 0.86~0.95 之间扫描悬停, 命中即返回。
        tooltip = ""
        for px in (0.90, 0.92, 0.88, 0.94, 0.86, 0.95, 0.83):
            hover_js = (
                "var canvas = document.querySelectorAll('canvas')[0];"
                "var rect = canvas.getBoundingClientRect();"
                f"var x = rect.x + rect.width * {px};"
                "var y = rect.y + rect.height * 0.50;"
                "canvas.dispatchEvent(new PointerEvent('pointermove', {clientX: x, clientY: y, bubbles: true, pointerId: 1, pointerType: 'mouse'}));"
                "canvas.dispatchEvent(new MouseEvent('mousemove', {clientX: x, clientY: y, bubbles: true}));"
                "'done';"
            )
            _cdp_eval(target, hover_js)
            time.sleep(0.8)
            tooltip = _cdp_eval(target, tooltip_js) or ""
            m_ma = re.search(r"周均线[:：]\s*(\d+(?:\.\d+)?)", tooltip)
            m_dev = re.search(r"偏离[:：]\s*([+-]?\d+(?:\.\d+)?)%?", tooltip)
            if m_ma and m_dev:
                return {
                    "sh_week_ma": float(m_ma.group(1)),
                    "sh_deviation_pct": float(m_dev.group(1)),
                    "tooltip": tooltip,
                }
        raise RuntimeError("tooltip 未提取到周均线/偏离度: " + tooltip.replace("\n", " | "))
    finally:
        _cdp_close(target)


def _compute_deviation_fallback(con, trade_date: str, ma_window: int = 5) -> dict | None:
    """tooltip 抓取失败时的兜底：用最近 ma_window 个交易日 sh_index_close 复算 MA/偏离度。

    与 fill_stock_daily_fallback.recompute_deviation 同口径（本地复算，非 tooltip 口径）。
    需 index-daily 已写入当日 sh_index_close，否则返回 None（调用方决定是否报错）。
    """
    closes = con.execute(
        "SELECT trade_date, sh_index_close FROM fact_market_daily "
        "WHERE trade_date <= ? AND sh_index_close IS NOT NULL "
        "ORDER BY trade_date DESC LIMIT ?",
        [trade_date, ma_window],
    ).fetchall()
    if not closes or str(closes[0][0]) != trade_date:
        return None
    ma = sum(float(r[1]) for r in closes) / len(closes)
    close = float(closes[0][1])
    dev = (close / ma - 1) * 100 if ma else None
    return {
        "sh_week_ma": round(ma, 2),
        "sh_deviation_pct": round(dev, 2) if dev is not None else None,
        "tooltip": f"[ma{len(closes)} recompute] close={close} ma={round(ma, 2)}",
        "source": "ma_recompute",
    }


def sync_market_deviation(trade_date: str | None = None) -> dict:
    init_db()
    con = connect()
    try:
        if not trade_date:
            row = con.execute("SELECT MAX(trade_date) FROM fact_market_daily").fetchone()
            trade_date = str(row[0]) if row and row[0] else None
        if not trade_date:
            raise RuntimeError("无目标交易日, 请先同步 fact_market_daily 或显式传 --trade-date")
        try:
            data = _fetch_market_deviation()
            data["source"] = "tooltip"
        except Exception as exc:
            # tooltip 抓取脆弱（fupanhui 页面/后台标签页合成 hover 常失效）→ MA 复算兜底
            print(f"[market-deviation] tooltip 抓取失败({exc})，回退 MA5 复算")
            data = _compute_deviation_fallback(con, trade_date)
            if data is None:
                raise RuntimeError(
                    f"tooltip 失败且 MA 兜底无数据(当日 sh_index_close 缺失)：{exc}"
                ) from exc
        # data["source"] 之前算了却没写库——于是存量里哪些是 tooltip、哪些是复算兜底
        # 全部分不出来（2026-09-06 审计：221 天只能一律标 unknown_preexisting）。
        # 只有这一层知道这个值，扔掉就再也补不回来了。
        con.execute(
            """
            UPDATE fact_market_daily
            SET sh_week_ma = ?, sh_deviation_pct = ?, sh_week_ma_source = ?, updated_at = ?
            WHERE trade_date = ?
            """,
            [
                data["sh_week_ma"],
                data["sh_deviation_pct"],
                data.get("source"),
                datetime.now(),
                trade_date,
            ],
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
