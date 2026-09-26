"""复盘会(fupanhui) 数据源。

默认只走 CDP：在用户已登录的 Chrome 标签页里 fetch，TLS/HTTP 指纹与真人一致。
Python urllib 直连是 opt-in（FUPANHUI_DIRECT=1），匿名 UA 会和 Chrome 双通道打同一账号。

  1. **api_get_public / api_get**：默认 CDP；直连开启时先 HTTPS，401 再回落 CDP。
  2. 429 / 「超限」触发进程级熔断，禁止重试。

CDP proxy 路径需要:
  1. CDP proxy 运行中 (web-access skill 的 check-deps 会自动拉起)。
  2. Chrome 中已登录 fupanhui.com。

调用约定与 scripts/backfill_sector_marginal.py / mcp/fupanhui/index.js 一致:
  POST 原始 JS 表达式到 /eval?target=ID, 读取返回 JSON 的 value 字段。
"""
from __future__ import annotations

import json
import os
import random
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

CDP_PROXY = os.environ.get("CDP_HOST", "http://localhost:3456")
FUPANHUI_BASE = "https://fupanhui.com"

_target_cache = {"id": None}


class FupanhuiError(RuntimeError):
    """复盘会数据源调用失败。"""


class FupanhuiRateLimitError(FupanhuiError):
    """429 / 超限：进程应立即停止，禁止重试。"""


_RATE_LIMITED = {"tripped": False, "reason": ""}
_last_call = [0.0]
_throttle_lock = threading.Lock()
_RATE_LIMIT_RE = re.compile(
    r"超限|使用工具已超限|too many|rate.?limit|访问过于频繁|请求过于频繁",
    re.I,
)
_CDP_PAGE = 20


def _read_direct_mode() -> bool:
    return os.environ.get("FUPANHUI_DIRECT", "0") != "0"


def rate_limit_tripped() -> bool:
    return bool(_RATE_LIMITED["tripped"])


def reset_session_hygiene() -> None:
    """测试/新进程入口：清熔断闩和节流时钟。"""
    _RATE_LIMITED["tripped"] = False
    _RATE_LIMITED["reason"] = ""
    _last_call[0] = 0.0


def _min_interval() -> float:
    try:
        return max(0.0, float(os.environ.get("FUPANHUI_MIN_INTERVAL", "0.8")))
    except ValueError:
        return 0.8


def _throttle() -> None:
    interval = _min_interval()
    if interval <= 0:
        return
    with _throttle_lock:
        now = time.time()
        wait = interval - (now - _last_call[0])
        if wait > 0:
            time.sleep(wait + random.uniform(0.05, min(0.4, interval)))
        _last_call[0] = time.time()


def _looks_rate_limited(status, text) -> bool:
    if status == 429:
        return True
    return bool(text and _RATE_LIMIT_RE.search(str(text)))


def _guard_rate_limit() -> None:
    if _RATE_LIMITED["tripped"]:
        raise FupanhuiRateLimitError(
            _RATE_LIMITED["reason"]
            or "rate limit latch already tripped; stop all fupanhui calls"
        )


def _trip_rate_limit(reason: str) -> None:
    _RATE_LIMITED["tripped"] = True
    _RATE_LIMITED["reason"] = reason
    raise FupanhuiRateLimitError(reason)


def _raise_if_rate_limited(status=None, text="", path=""):
    blob = text or ""
    if _looks_rate_limited(status, blob):
        _trip_rate_limit(
            f"fupanhui rate-limited ({path}): HTTP {status} {str(blob)[:200]}"
        )


def _parse_api_payload(raw, api_path: str):
    if isinstance(raw, dict) and raw.get("__fph_rate_limit"):
        _trip_rate_limit(
            f"fupanhui rate-limited ({api_path}): HTTP {raw.get('status')} {raw.get('body')}"
        )
    if isinstance(raw, str):
        _raise_if_rate_limited(None, raw, api_path)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            raise FupanhuiError(
                f"API 响应解析失败 ({api_path}): {raw[:200]}"
            ) from e
    else:
        parsed = raw
    if isinstance(parsed, dict) and parsed.get("__fph_rate_limit"):
        _trip_rate_limit(
            f"fupanhui rate-limited ({api_path}): HTTP {parsed.get('status')} {parsed.get('body')}"
        )
    if isinstance(parsed, dict):
        msg = parsed.get("message") or parsed.get("msg") or ""
        _raise_if_rate_limited(None, msg, api_path)
        code = parsed.get("code")
        if code not in (None, 0, 200):
            raise FupanhuiError(f"API 错误 {code} ({api_path}): {msg or 'unknown'}")
        if "data" in parsed:
            return parsed["data"]
    return parsed


def _close_http_error(err: urllib.error.HTTPError) -> str:
    body = ""
    try:
        if err.fp is not None:
            body = err.read().decode("utf-8", "ignore")
    except Exception:
        body = ""
    try:
        err.close()
    except Exception:
        pass
    return body


def _pages(items, size: int):
    size = max(1, int(size))
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _parse_batch_json(raw, label: str):
    if not raw:
        raise FupanhuiError(f"{label}返回空")
    blob = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
    _raise_if_rate_limited(None, blob, label)
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            raise FupanhuiError(f"{label}解析失败: {raw[:200]}") from e
    else:
        parsed = raw
    if isinstance(parsed, dict) and parsed.get("__fph_rate_limit"):
        _trip_rate_limit(
            f"fupanhui rate-limited ({label}): HTTP {parsed.get('status')} {parsed.get('body')}"
        )
    return parsed


_CDP_RATE_LIMIT_JS = (
    "const t=await r.text();"
    "if(r.status===429||/超限|too many|rate.?limit/i.test(t))"
    " return JSON.stringify({__fph_rate_limit:true,status:r.status,body:t.slice(0,200)});"
)
_CDP_GAP_JS = (
    "if(i+1<sectors.length) await new Promise(res=>setTimeout(res,250+Math.random()*250));"
)


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


def get_target(force: bool = False, fresh: bool = False) -> str:
    """获取一个可用的 CDP target。优先复用 fupanhui 标签页, 否则新建。

    fresh=True 时跳过复用, 直接新建一个干净的 workspace 标签页
    (适用于旧页面 JS 环境已坏、反复 500 的场景)。"""
    if _target_cache["id"] and not force and not fresh:
        return _target_cache["id"]
    try:
        targets = _http_get(f"{CDP_PROXY}/targets") if not fresh else []
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


def cdp_eval(js_expr: str, timeout: int = 120, retries: int = 3):
    """在浏览器上下文执行 JS, 返回其 value。

    重试策略: 指数退避; 连续失败 2 次后不再复用旧标签页,
    强制新建干净的 workspace 页 (旧页 JS 环境可能已坏)。
    空 value 也视为失败重试: 卡死/未加载的标签页会秒回空值而不报错。
    429 / 超限不重试。"""
    _guard_rate_limit()
    last_error = None
    for attempt in range(max(1, int(retries) + 1)):
        target = get_target(force=attempt > 0, fresh=attempt >= 2)
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
                value = result.get("value") if isinstance(result, dict) else None
                if value not in (None, "", {}):
                    return value
                last_error = FupanhuiError("CDP eval 返回空值 (标签页可能卡死或未加载)")
        except FupanhuiRateLimitError:
            raise
        except Exception as e:  # noqa: BLE001
            last_error = e
            _raise_if_rate_limited(None, str(e), "cdp_eval")
        _target_cache["id"] = None
        if isinstance(last_error, FupanhuiRateLimitError):
            raise last_error
        if attempt < int(retries):
            time.sleep(min(0.8 * (2 ** attempt), 6.0))
    raise FupanhuiError(f"CDP eval 失败: {last_error}") from last_error


# 直连是 opt-in。默认走 CDP，避免 Python urllib 与 Chrome 双通道打同一账号。
# FUPANHUI_DIRECT=1 才开直连；失败（401/网络）再回落 CDP。429 不回落、不重试。
DIRECT_MODE = _read_direct_mode()


def _direct_api_get(api_path: str, params: dict | None = None, timeout: int = 30):
    """直连 HTTPS 请求（api_path 为含 /api/v1/client 的完整路径），解析并返回 data 字段。"""
    _guard_rate_limit()
    _throttle()
    query = ""
    if params:
        items = [(k, v) for k, v in params.items() if v is not None]
        if items:
            query = "?" + urllib.parse.urlencode(items)
    url = f"{FUPANHUI_BASE}{api_path}{query}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
    except urllib.error.HTTPError as e:
        # HTTPError 本身是 file-like、持有响应 socket。批量调用方（kline/stocks
        # 各 403 个板块）把异常收进列表/异常链后，socket 只能等周期 GC 回收——
        # fupanhui 08-24 起匿名直连 401，一轮批量足以顶爆 launchd 256 软上限，
        # 随后 duckdb.connect 以「Too many open files」死掉（2026-08-26 夜跑
        # sector-daily 事故，台账 R-20260826-04；与 R-20260826-03 同族）。
        # 先关 socket 再原样重抛：401 仍由 api_get 回退 CDP，语义不变。
        body = _close_http_error(e)
        _raise_if_rate_limited(e.code, body, api_path)
        raise
    return _parse_api_payload(raw, api_path)


def api_get(api_path: str, params: dict | None = None, timeout: int = 60):
    """请求一个 fupanhui API, 解析并返回 data 字段。

    直连模式下先直接 HTTPS 请求；失败（需登录/网络错误）再回退到浏览器内 fetch。
    429 / 超限不回落、不重试。"""
    _guard_rate_limit()
    if DIRECT_MODE:
        try:
            return _direct_api_get(api_path, params, timeout=min(timeout, 30))
        except FupanhuiRateLimitError:
            raise
        except FupanhuiError:
            raise
        except Exception:  # noqa: BLE001 - 401/超时等，回退 CDP
            pass
    _throttle()
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
        "var t=await r.text();"
        "if(r.status===429||/超限|too many|rate.?limit/i.test(t))"
        " return JSON.stringify({__fph_rate_limit:true,status:r.status,body:t.slice(0,200)});"
        "return t;"
        "})()"
    )
    raw = cdp_eval(js, timeout=timeout)
    if not raw:
        raise FupanhuiError(f"API 返回空: {api_path}")
    return _parse_api_payload(raw, api_path)


def api_get_public(api_path: str, params: dict | None = None, timeout: int = 30):
    """公开端点：默认走 CDP，不先打匿名 urllib。

    历史上无需登录；2026-08-24 起匿名直连 401。直连仅 FUPANHUI_DIRECT=1 时
    才先 HTTPS，401 再回落 CDP。429 熔断，不重试。
    """
    _guard_rate_limit()
    if not DIRECT_MODE:
        return api_get(f"/api/v1/client{api_path}", params, timeout=max(timeout, 60))
    query = ""
    if params:
        items = [(k, v) for k, v in params.items() if v is not None]
        if items:
            query = "?" + urllib.parse.urlencode(items)
    url = f"{FUPANHUI_BASE}/api/v1/client{api_path}{query}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    _throttle()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
    except urllib.error.HTTPError as e:
        body = _close_http_error(e)
        _raise_if_rate_limited(e.code, body, api_path)
        if e.code == 401:
            try:
                return api_get(f"/api/v1/client{api_path}", params, timeout=max(timeout, 60))
            except FupanhuiRateLimitError:
                raise
            except Exception as exc:  # noqa: BLE001
                raise FupanhuiError(
                    f"公开 API HTTP 401 ({api_path}) 且 CDP 回退失败: {exc}"
                ) from e
        raise FupanhuiError(f"公开 API HTTP {e.code} ({api_path}): {e.reason}") from e
    except FupanhuiRateLimitError:
        raise
    except Exception as e:
        raise FupanhuiError(f"公开 API 请求失败 ({api_path}): {e}") from e
    return _parse_api_payload(raw, api_path)


def _direct_batch(ts_codes: list, fetch_one, concurrency: int):
    """直连批量抓取。默认串行；concurrency>1 才线程池。

    单个 code 普通失败返回空结果（与 CDP 路径 JS 的 catch 行为一致）；
    429 / 超限立即抛出，不再继续打。全部失败则抛错，让调用方回退 CDP。"""
    _guard_rate_limit()
    results = []
    failures = []
    n = max(1, int(concurrency))

    def _safe(ts):
        try:
            return fetch_one(ts)
        except FupanhuiRateLimitError:
            raise
        except Exception as e:  # noqa: BLE001
            failures.append(e)
            return None

    if n == 1:
        for ts in ts_codes:
            r = _safe(ts)
            if r is not None:
                results.append(r)
    else:
        with ThreadPoolExecutor(max_workers=n) as pool:
            for r in pool.map(_safe, ts_codes):
                if r is not None:
                    results.append(r)
    if not results and failures:
        raise FupanhuiError(f"直连批量全部失败: {failures[0]}") from failures[0]
    return results


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


def get_review_summary(trade_date: str) -> dict:
    data = api_get_public("/reviews/summary", {"trade_date": trade_date})
    return data if isinstance(data, dict) else {}


def get_leader_ladder(trade_date: str) -> dict:
    data = api_get_public("/reviews/leader-ladder", {"trade_date": trade_date})
    return data if isinstance(data, dict) else {}


def get_global_market(trade_date: str) -> dict:
    data = api_get_public("/reviews/global-market", {"trade_date": trade_date})
    return data if isinstance(data, dict) else {}


def get_dragon_list(trade_date: str) -> dict:
    data = api_get_public("/data/dragon/list", {"trade_date": trade_date})
    return data if isinstance(data, dict) else {}


def get_dragon_all(trade_date: str) -> dict:
    """龙虎榜全量：summary（机构/游资净买入日汇总）+ stocks 名单。"""
    data = api_get_public("/data/dragon/all", {"trade_date": trade_date})
    return data if isinstance(data, dict) else {}


def get_dragon_detail(trade_date: str, ts_code: str) -> dict:
    """单股龙虎榜席位明细（买方/卖方席位）。id 参数为 ts_code。"""
    data = api_get_public(
        "/data/dragon/detail", {"trade_date": trade_date, "id": ts_code}
    )
    return data if isinstance(data, dict) else {}


def get_regulation_logs(trade_date: str) -> dict:
    data = api_get_public("/regulation/logs", {"trade_date": trade_date})
    return data if isinstance(data, dict) else {}


def get_regulation_pool(trade_date: str) -> dict:
    data = api_get_public("/regulation/pool", {"trade_date": trade_date})
    return data if isinstance(data, dict) else {}


def get_core_stocks(trade_date: str) -> dict:
    data = api_get_public("/core-stocks/list", {"trade_date": trade_date})
    return data if isinstance(data, dict) else {}


def get_auction_dashboard(trade_date: str) -> dict:
    data = api_get_public("/data/auction/dashboard", {"trade_date": trade_date})
    return data if isinstance(data, dict) else {}


def get_news_events_timeline(trade_date: str) -> dict:
    data = api_get_public("/news/events/timeline", {"date": trade_date})
    return data if isinstance(data, dict) else {}


def get_news_events_future() -> dict:
    data = api_get_public("/news/events/future")
    return data if isinstance(data, dict) else {}


def get_reports_page(page: int = 1, page_size: int = 50) -> dict:
    data = api_get_public("/reports/list", {"page": page, "page_size": page_size})
    return data if isinstance(data, dict) else {}


def get_fundamentals_list(limit: int = 100, offset: int = 0, trade_date: str | None = None) -> dict:
    params = {"limit": limit, "offset": offset}
    if trade_date:
        params["trade_date"] = trade_date
    data = api_get_public("/topics/fundamentals", params)
    return data if isinstance(data, dict) else {}


def get_fundamentals_detail(document_pk: int | str) -> dict:
    data = api_get_public(f"/topics/fundamentals/{document_pk}")
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
    batch: int = 1,
    timeout: int = 300,
) -> dict:
    """批量抓取多个板块的 K 线序列。

    CDP 路径串行 fetch（默认 batch=1），返回
    {ts_code: [{trade_date, pct_chg, diff_ratio, amount}, ...]}。
    复盘会 kline 要求 days>=20, 这里强制下限。
    """
    _guard_rate_limit()
    days = max(int(days), 20)
    batch = max(1, int(batch))
    if DIRECT_MODE:
        params = {"days": days, "period": "daily", "mode": "auto"}
        if trade_date:
            params["trade_date"] = trade_date

        def _one_kline(ts):
            d = _direct_api_get(f"/api/v1/client/reviews/sector-cycle/{ts}/kline", params)
            k = (d or {}).get("kline") or [] if isinstance(d, dict) else []
            return ts, [
                {"trade_date": (x.get("date") or x.get("trade_date")), "pct_chg": x.get("pct_chg"),
                 "diff_ratio": x.get("diff_ratio"), "amount": x.get("amount")}
                for x in k
            ]

        try:
            return dict(_direct_batch(ts_codes, _one_kline, batch))
        except FupanhuiRateLimitError:
            raise
        except Exception:  # noqa: BLE001 - 直连失败回退 CDP
            pass
    td_param = f"&trade_date={trade_date}" if trade_date else ""
    out: dict = {}
    for page in _pages(list(ts_codes), _CDP_PAGE):
        codes_json = json.dumps(page)
        js = (
            "(async()=>{"
            "const token=localStorage.getItem('user_token');"
            "const headers={};"
            "if(token){headers['Authorization']='Bearer '+token;}"
            "const sectors=" + codes_json + ";"
            "const results={};"
            f"const BATCH={batch};"
            "for(let i=0;i<sectors.length;i++){"
            "const ts=sectors[i];"
            "const r=await fetch('/api/v1/client/reviews/sector-cycle/'+ts+'/kline"
            f"?days={days}&period=daily&mode=auto{td_param}',{{headers}});"
            + _CDP_RATE_LIMIT_JS
            + "let d={}; try{d=JSON.parse(t)}catch(e){d={}};"
            "const k=d.data&&d.data.kline?d.data.kline:[];"
            "results[ts]=k.map(x=>({trade_date:(x.date||x.trade_date),pct_chg:x.pct_chg,"
            "diff_ratio:x.diff_ratio,amount:x.amount}));"
            + _CDP_GAP_JS
            + "}"
            "return JSON.stringify(results);"
            "})()"
        )
        raw = cdp_eval(js, timeout=timeout)
        part = _parse_batch_json(raw, "批量板块 K 线")
        if isinstance(part, dict):
            out.update(part)
        _throttle()
    return out


def get_sector_stocks_batch(
    ts_codes: list,
    trade_date: str | None = None,
    batch: int = 1,
    timeout: int = 300,
) -> dict:
    """批量抓取多个板块在某交易日的成分股 (已裁剪 pattern 等大字段)。

    返回 {ts_code: {trade_date, name, stock_count, stocks:[{...slim...}]}}。
    调用方应分块 (chunk) 传入, 控制单次 eval 响应大小。
    slim 字段与 fact_sector_stock_daily 所需列对齐 (含 p3/hs/hl/lt/rt/cm/lsp)。
    CDP 路径串行 fetch，默认 batch=1。
    """
    _guard_rate_limit()
    batch = max(1, int(batch))
    if DIRECT_MODE:
        params = {"trade_date": trade_date} if trade_date else None

        def _one_stocks(ts):
            dd = _direct_api_get(f"/api/v1/client/reviews/sector-cycle/{ts}/stocks", params)
            dd = dd if isinstance(dd, dict) else {}
            arr = [
                {"c": s.get("ts_code"), "n": s.get("name"), "p": s.get("price"),
                 "pc": s.get("pct_chg"), "a": s.get("amount"), "p3": s.get("pct_chg_3d"),
                 "p5": s.get("pct_chg_5d"), "p10": s.get("pct_chg_10d"), "p20": s.get("pct_chg_20d"),
                 "f1": s.get("fund_flow_1d"), "f5": s.get("fund_flow_5d"), "sw": s.get("sw_industry"),
                 "lp": s.get("leader_plate"), "hs": s.get("high_status"), "hl": s.get("high_status_label"),
                 "lt": s.get("limit_times"), "rt": s.get("role_tags"), "cm": s.get("circ_mv")}
                for s in (dd.get("stocks") or [])
            ]
            return ts, {"td": dd.get("trade_date"), "nm": dd.get("name"),
                        "sc": dd.get("stock_count"), "st": arr}

        try:
            return dict(_direct_batch(ts_codes, _one_stocks, batch))
        except FupanhuiRateLimitError:
            raise
        except Exception:  # noqa: BLE001 - 直连失败回退 CDP
            pass
    td_param = f"?trade_date={trade_date}" if trade_date else ""
    out: dict = {}
    for page in _pages(list(ts_codes), _CDP_PAGE):
        codes_json = json.dumps(page)
        js = (
            "(async()=>{"
            "const token=localStorage.getItem('user_token');"
            "const headers={};"
            "if(token){headers['Authorization']='Bearer '+token;}"
            "const sectors=" + codes_json + ";"
            "const out={};"
            f"const BATCH={batch};"
            "for(let i=0;i<sectors.length;i++){"
            "const ts=sectors[i];"
            "const r=await fetch('/api/v1/client/reviews/sector-cycle/'+ts+'/stocks"
            + td_param + "',{headers});"
            + _CDP_RATE_LIMIT_JS
            + "let d={}; try{d=JSON.parse(t)}catch(e){d={}};"
            "const dd=d.data||{};"
            "const arr=(dd.stocks||[]).map(s=>({c:s.ts_code,n:s.name,p:s.price,"
            "pc:s.pct_chg,a:s.amount,p3:s.pct_chg_3d,p5:s.pct_chg_5d,p10:s.pct_chg_10d,p20:s.pct_chg_20d,"
            "f1:s.fund_flow_1d,f5:s.fund_flow_5d,sw:s.sw_industry,lp:s.leader_plate,"
            "hs:s.high_status,hl:s.high_status_label,lt:s.limit_times,rt:s.role_tags,cm:s.circ_mv}));"
            "out[ts]={td:dd.trade_date,nm:dd.name,sc:dd.stock_count,st:arr};"
            + _CDP_GAP_JS
            + "}"
            "return JSON.stringify(out);"
            "})()"
        )
        raw = cdp_eval(js, timeout=timeout)
        part = _parse_batch_json(raw, "批量成分股")
        if isinstance(part, dict):
            out.update(part)
        _throttle()
    return out


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
