"""复盘会(fupanhui) 数据源。

两种调用路径:
  1. **公开 API** (api_get_public): 直接 HTTPS 请求，无需登录/CDP proxy。
     适用: reviews/latest-date, topics/mainline-*, data/theme/panels,
           reviews/sector-rotation, reviews/historical-mapping 等。
  2. **认证 API** (api_get): 通过 CDP proxy 在用户 Chrome 中 fetch，自动带 token。
     适用: watchlist/*, selection/*, 需登录态的端点。

CDP proxy 路径需要:
  1. CDP proxy 运行中 (web-access skill 的 check-deps 会自动拉起)。
  2. Chrome 中已登录 fupanhui.com。

调用约定与 scripts/backfill_sector_marginal.py / mcp/fupanhui/index.js 一致:
  POST 原始 JS 表达式到 /eval?target=ID, 读取返回 JSON 的 value 字段。
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
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


def _is_fupanhui_tab(url: str) -> bool:
    """是否为 fupanhui 标签页, 但排除 www 首页 (其 origin localStorage 无登录 token)。"""
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    if host == "www.fupanhui.com":
        return False
    return host == "fupanhui.com" or host.endswith(".fupanhui.com")


def _fph_tab_priority(url: str) -> int:
    """fupanhui 标签页优先级: workspace 页带完整登录态, 优先复用。"""
    return 1 if "/workspace" in url else 0


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
    # 注意: 登录 token 存在 fupanhui.com (无 www) 这个 origin 的 localStorage,
    # www.fupanhui.com 首页是独立 origin、localStorage 为空, 用它发认证 API 会 401。
    # 因此排除 www 首页, 并优先选带登录态的 workspace 标签页。
    if isinstance(targets, list):
        fph_tabs = [
            t for t in targets if _is_fupanhui_tab(t.get("url") or "")
        ]
        fph_tabs.sort(key=lambda t: _fph_tab_priority(t.get("url") or ""), reverse=True)
        for t in fph_tabs:
            tid = t.get("id") or t.get("targetId")
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


def cdp_eval(js_expr: str, timeout: int = 120, retries: int = 2):
    """在浏览器上下文执行 JS, 返回其 value。"""
    last_error = None
    for attempt in range(max(1, int(retries) + 1)):
        target = get_target(force=attempt > 0)
        req = urllib.request.Request(
            f"{CDP_PROXY}/eval?target={target}",
            data=js_expr.encode(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result = json.loads(resp.read())
            if isinstance(result, dict) and result.get("error"):
                last_error = FupanhuiError(f"CDP eval 错误: {result['error']}")
            else:
                return result.get("value") if isinstance(result, dict) else None
        except Exception as e:  # noqa: BLE001
            last_error = e
        _target_cache["id"] = None
        if attempt < int(retries):
            time.sleep(0.8 * (attempt + 1))
    raise FupanhuiError(f"CDP eval 失败: {last_error}") from last_error


def api_get(api_path: str, params: dict | None = None, timeout: int = 60):
    """在浏览器内同步 fetch 一个 fupanhui API, 解析并返回 data 字段。"""
    query = ""
    if params:
        items = [(k, v) for k, v in params.items() if v is not None]
        if items:
            query = "?" + urllib.parse.urlencode(items)
    url = json.dumps(api_path + query)
    js = (
        "(async()=>{"
        "var token=localStorage.getItem('user_token');"
        "var headers={};"
        "if(token){headers['Authorization']='Bearer '+token;}"
        f"var r=await fetch({url},{{headers:headers}});"
        "return await r.text();"
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


def api_get_public(api_path: str, params: dict | None = None, timeout: int = 30):
    """直接 HTTPS 请求公开 fupanhui API，无需 CDP proxy 或登录态。

    适用于不需认证的端点:
      /reviews/latest-date, /topics/mainline-themes, /data/theme/panels,
      /reviews/sector-rotation, /reviews/historical-mapping 等。
    """
    query = ""
    if params:
        items = [(k, v) for k, v in params.items() if v is not None]
        if items:
            query = "?" + urllib.parse.urlencode(items)
    url = f"{FUPANHUI_BASE}/api/v1/client{api_path}{query}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
    except urllib.error.HTTPError as e:
        raise FupanhuiError(f"公开 API HTTP {e.code} ({api_path}): {e.reason}") from e
    except Exception as e:
        raise FupanhuiError(f"公开 API 请求失败 ({api_path}): {e}") from e
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise FupanhuiError(f"公开 API 响应解析失败 ({api_path}): {raw[:200]}") from e
    code = parsed.get("code") if isinstance(parsed, dict) else None
    if code not in (None, 0, 200):
        msg = parsed.get("message") or parsed.get("msg") or "unknown"
        raise FupanhuiError(f"公开 API 错误 {code} ({api_path}): {msg}")
    if isinstance(parsed, dict) and "data" in parsed:
        return parsed["data"]
    return parsed


# ── 公开 API 便捷函数 ──────────────────────────────────────


def get_mainline_themes(trade_date: str) -> list[dict]:
    """获取每日主线题材列表。返回 [{theme_code, theme_name, sector_count, min_sort}, ...]"""
    data = api_get_public("/topics/mainline-themes", {"trade_date": trade_date})
    if isinstance(data, dict):
        return data.get("items") or []
    return []


def get_mainline_stocks(trade_date: str, theme_code: str) -> dict:
    """获取某主线题材下的个股。"""
    data = api_get_public(
        "/topics/mainline-stocks",
        {"trade_date": trade_date, "theme_code": theme_code},
    )
    return data if isinstance(data, dict) else {}


def get_mainline_sectors(trade_date: str, theme_code: str) -> list[dict]:
    """获取某主线题材对应的板块。"""
    data = api_get_public(
        "/topics/mainline-sectors",
        {"trade_date": trade_date, "theme_code": theme_code},
    )
    if isinstance(data, dict):
        return data.get("items") or []
    return []


def get_theme_panels(trade_date: str | None = None) -> list[dict]:
    """获取题材资金面板（每题材的资金流向+个股）。"""
    params = {}
    if trade_date:
        params["trade_date"] = trade_date
    data = api_get_public("/data/theme/panels", params)
    if isinstance(data, dict):
        return data.get("panels") or []
    return []


def get_sector_rotation(trade_date: str | None = None) -> dict:
    """获取板块轮动完整数据。"""
    params = {}
    if trade_date:
        params["trade_date"] = trade_date
    data = api_get_public("/reviews/sector-rotation", params)
    return data if isinstance(data, dict) else {}


def get_historical_mapping(trade_date: str) -> dict:
    """获取 AI 历史相似日映射。"""
    data = api_get_public("/reviews/historical-mapping", {"trade_date": trade_date})
    return data if isinstance(data, dict) else {}


def get_latest_date_public() -> str | None:
    """公开路径获取最新交易日期（不需 CDP）。"""
    data = api_get_public("/reviews/latest-date")
    if isinstance(data, dict):
        return data.get("latest_date") or data.get("trade_date")
    return None


# ── CDP 认证 API 便捷函数 ──────────────────────────────────


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
    """返回板块 K 线列表, 每项含 date/pct_chg/diff_ratio/amount。days 下限20。"""
    days = max(int(days), 20)
    params = {"days": days, "period": "daily", "mode": "auto"}
    if trade_date:
        params["trade_date"] = trade_date
    data = api_get(f"/api/v1/client/reviews/sector-cycle/{ts_code}/kline", params)
    if isinstance(data, dict):
        return data.get("kline") or []
    return []


def get_sector_klines_batch(
    ts_codes: list,
    trade_date: str | None = None,
    days: int = 25,
    batch: int = 12,
    timeout: int = 180,
) -> dict:
    """批量抓取多个板块的 K 线序列。

    一次 eval 内用 Promise.all 分批并发, 返回
    {ts_code: [{trade_date, pct_chg, diff_ratio, amount}, ...]}。
    复盘会 kline 要求 days>=20, 这里强制下限。
    """
    days = max(int(days), 20)
    codes_json = json.dumps(ts_codes)
    td_param = f"&trade_date={trade_date}" if trade_date else ""
    js = (
        "(async()=>{"
        "const sectors=" + codes_json + ";"
        "const results={};"
        f"const BATCH={batch};"
        "for(let i=0;i<sectors.length;i+=BATCH){"
        "const b=sectors.slice(i,i+BATCH);"
        "const ps=b.map(ts=>"
        "fetch('/api/v1/client/reviews/sector-cycle/'+ts+'/kline"
        f"?days={days}&period=daily&mode=auto{td_param}')"
        ".then(r=>r.json()).then(d=>{"
        "const k=d.data&&d.data.kline?d.data.kline:[];"
        "results[ts]=k.map(x=>({trade_date:(x.date||x.trade_date),pct_chg:x.pct_chg,"
        "diff_ratio:x.diff_ratio,amount:x.amount}));"
        "}).catch(()=>{results[ts]=[];}));"
        "await Promise.all(ps);"
        "}"
        "return JSON.stringify(results);"
        "})()"
    )
    raw = cdp_eval(js, timeout=timeout)
    if not raw:
        raise FupanhuiError("批量板块 K 线返回空")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise FupanhuiError(f"批量板块 K 线解析失败: {raw[:200]}") from e


def get_sector_stocks_batch(
    ts_codes: list,
    trade_date: str | None = None,
    batch: int = 8,
    timeout: int = 180,
) -> dict:
    """批量抓取多个板块在某交易日的成分股 (已裁剪 pattern 等大字段)。

    返回 {ts_code: {trade_date, name, stock_count, stocks:[{...slim...}]}}。
    调用方应分块 (chunk) 传入, 控制单次 eval 响应大小。
    """
    codes_json = json.dumps(ts_codes)
    td_param = f"?trade_date={trade_date}" if trade_date else ""
    js = (
        "(async()=>{"
        "const sectors=" + codes_json + ";"
        "const out={};"
        f"const BATCH={batch};"
        "for(let i=0;i<sectors.length;i+=BATCH){"
        "const b=sectors.slice(i,i+BATCH);"
        "const ps=b.map(ts=>"
        "fetch('/api/v1/client/reviews/sector-cycle/'+ts+'/stocks" + td_param + "')"
        ".then(r=>r.json()).then(d=>{"
        "const dd=d.data||{};"
        "const arr=(dd.stocks||[]).map(s=>({c:s.ts_code,n:s.name,p:s.price,"
        "pc:s.pct_chg,a:s.amount,p5:s.pct_chg_5d,p10:s.pct_chg_10d,p20:s.pct_chg_20d,"
        "f1:s.fund_flow_1d,f5:s.fund_flow_5d,sw:s.sw_industry,lp:s.leader_plate}));"
        "out[ts]={td:dd.trade_date,nm:dd.name,sc:dd.stock_count,st:arr};"
        "}).catch(()=>{out[ts]={st:[]};}));"
        "await Promise.all(ps);"
        "}"
        "return JSON.stringify(out);"
        "})()"
    )
    raw = cdp_eval(js, timeout=timeout)
    if not raw:
        raise FupanhuiError("批量成分股返回空")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise FupanhuiError(f"批量成分股解析失败: {raw[:200]}") from e


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
