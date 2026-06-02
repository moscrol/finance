"""复盘会(fupanhui) 数据源。

通过 CDP proxy (默认 http://localhost:3456) 在用户已登录的 Chrome 中执行
fetch, 调用 fupanhui.com 内部 API。需要:
  1. CDP proxy 运行中 (web-access skill 的 check-deps 会自动拉起)。
  2. Chrome 中已登录 fupanhui.com。

调用约定与 scripts/backfill_sector_marginal.py / mcp/fupanhui/index.js 一致:
  POST 原始 JS 表达式到 /eval?target=ID, 读取返回 JSON 的 value 字段。
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

CDP_PROXY = os.environ.get("CDP_HOST", "http://localhost:3456")
FUPANHUI_BASE = "https://fupanhui.com"

_target_cache = {"id": None}


class FupanhuiError(RuntimeError):
    """复盘会数据源调用失败。"""


def _http_get(url: str, timeout: int = 15):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def get_target(force: bool = False) -> str:
    """获取一个可用的 CDP target。优先复用 fupanhui 标签页, 否则新建。"""
    if _target_cache["id"] and not force:
        return _target_cache["id"]
    try:
        targets = _http_get(f"{CDP_PROXY}/targets")
    except Exception as e:  # noqa: BLE001
        raise FupanhuiError(
            f"无法连接 CDP proxy ({CDP_PROXY}): {e}. "
            "请先通过 web-access skill 启动 CDP proxy 并在 Chrome 登录 fupanhui.com。"
        ) from e

    # 只复用 fupanhui 标签页; 绝不占用用户其它站点 (如飞书) 的标签页,
    # 否则相对路径 API 会落到错误 origin 返回空。
    if isinstance(targets, list):
        fph = next((t for t in targets if "fupanhui.com" in (t.get("url") or "")), None)
        if fph:
            tid = fph.get("id") or fph.get("targetId")
            if tid:
                _target_cache["id"] = tid
                return tid

    # 没有 fupanhui 标签页, 新建一个后台 fupanhui workspace 页 (继承登录态)
    url = f"{CDP_PROXY}/new?url=" + urllib.parse.quote(FUPANHUI_BASE + "/workspace")
    d = _http_get(url, timeout=30)
    tid = d.get("targetId") or d.get("id")
    if not tid:
        raise FupanhuiError("CDP proxy 未能创建新标签页")
    _target_cache["id"] = tid
    return tid


def cdp_eval(js_expr: str, timeout: int = 120):
    """在浏览器上下文执行 JS, 返回其 value。"""
    target = get_target()
    req = urllib.request.Request(
        f"{CDP_PROXY}/eval?target={target}",
        data=js_expr.encode(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read())
    except Exception as e:  # noqa: BLE001
        raise FupanhuiError(f"CDP eval 失败: {e}") from e
    if isinstance(result, dict) and result.get("error"):
        raise FupanhuiError(f"CDP eval 错误: {result['error']}")
    return result.get("value") if isinstance(result, dict) else None


def api_get(api_path: str, params: dict | None = None, timeout: int = 60):
    """在浏览器内同步 fetch 一个 fupanhui API, 解析并返回 data 字段。"""
    query = ""
    if params:
        items = [(k, v) for k, v in params.items() if v is not None]
        if items:
            query = "?" + urllib.parse.urlencode(items)
    url = api_path + query
    js = (
        "(function(){"
        "var x=new XMLHttpRequest();"
        f"x.open('GET','{url}',false);"
        "x.send();"
        "return x.responseText;"
        "})()"
    )
    raw = cdp_eval(js, timeout=timeout)
    if not raw:
        raise FupanhuiError(f"API 返回空: {api_path}")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise FupanhuiError(f"API 响应解析失败 ({api_path}): {raw[:200]}") from e
    code = parsed.get("code") if isinstance(parsed, dict) else None
    if code not in (None, 0, 200):
        msg = parsed.get("message") or parsed.get("msg") or "unknown"
        raise FupanhuiError(f"API 错误 {code} ({api_path}): {msg}")
    if isinstance(parsed, dict) and "data" in parsed:
        return parsed["data"]
    return parsed


def get_latest_date() -> str | None:
    data = api_get("/api/v1/client/reviews/latest-date", {"mode": "auto"})
    if isinstance(data, dict):
        return data.get("latest_date") or data.get("trade_date")
    return None


def list_sectors(trade_date: str | None = None) -> list:
    """返回板块列表, 每项含 ts_code/name/pct_chg/strength 等。"""
    params = {"mode": "auto"}
    if trade_date:
        params["trade_date"] = trade_date
    data = api_get("/api/v1/client/reviews/sectors/search", params)
    if isinstance(data, dict):
        sectors = data.get("sectors") or data.get("data") or []
    elif isinstance(data, list):
        sectors = data
    else:
        sectors = []
    return [s for s in sectors if s.get("ts_code")]


def get_sector_kline(ts_code: str, trade_date: str | None = None, days: int = 20) -> list:
    """返回板块 K 线列表, 每项含 trade_date/pct_chg/diff_ratio/amount。"""
    params = {"days": days, "period": "daily", "mode": "auto"}
    if trade_date:
        params["trade_date"] = trade_date
    data = api_get(f"/api/v1/client/reviews/sector-cycle/{ts_code}/kline", params)
    if isinstance(data, dict):
        return data.get("kline") or []
    return []


def get_sector_stocks(ts_code: str, trade_date: str | None = None) -> dict:
    """返回 {trade_date, name, stock_count, stocks:[...]}。"""
    params = {}
    if trade_date:
        params["trade_date"] = trade_date
    data = api_get(f"/api/v1/client/reviews/sector-cycle/{ts_code}/stocks", params)
    if not isinstance(data, dict):
        return {"stocks": []}
    return {
        "trade_date": data.get("trade_date"),
        "name": data.get("name"),
        "stock_count": data.get("stock_count"),
        "stocks": data.get("stocks") or [],
    }
